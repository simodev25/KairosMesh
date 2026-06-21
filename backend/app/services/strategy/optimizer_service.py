"""Strategy Optimizer service — orchestrates evolutionary campaign loop.

Provides CRUD operations on campaigns and the main optimization loop
that mutates parameters within template bounds, evaluates via BacktestEngine,
and persists progress to DB.
"""

from __future__ import annotations

import logging
import random
import time
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models.strategy import Strategy
from app.db.models.strategy_optimizer_campaign import StrategyOptimizerCampaign
from app.db.models.strategy_optimizer_evaluation import StrategyOptimizerEvaluation
from app.services.strategy.optimizer_adapter import build_evaluator, validate_params_in_bounds
from app.services.strategy.optimizer_bounds import clamp_params, get_bounds_for_template

logger = logging.getLogger(__name__)

_ACTIVE_STATUSES = ('PENDING', 'RUNNING')


def create_campaign(
    db: Session,
    strategy_id: int,
    config: dict[str, Any],
) -> StrategyOptimizerCampaign:
    """Create a new optimization campaign for a strategy.

    Raises ValueError if a RUNNING or PENDING campaign already exists.
    """
    existing = (
        db.query(StrategyOptimizerCampaign)
        .filter(
            StrategyOptimizerCampaign.strategy_id == strategy_id,
            StrategyOptimizerCampaign.status.in_(_ACTIVE_STATUSES),
        )
        .first()
    )
    if existing:
        raise ValueError(f'Campaign already active (id={existing.id}, status={existing.status})')

    strategy = db.get(Strategy, strategy_id)
    if strategy is None:
        raise ValueError(f'Strategy {strategy_id} not found')

    settings = get_settings()
    max_iterations = min(
        int(config.get('max_iterations', settings.optimizer_max_iterations)),
        settings.optimizer_max_iterations_limit,
    )
    time_budget = min(
        int(config.get('time_budget_seconds', settings.optimizer_time_budget_seconds)),
        settings.optimizer_time_budget_limit,
    )

    campaign = StrategyOptimizerCampaign(
        strategy_id=strategy_id,
        status='PENDING',
        config={
            'max_iterations': max_iterations,
            'time_budget_seconds': time_budget,
            'max_candidates_per_iteration': int(
                config.get('max_candidates_per_iteration', settings.optimizer_max_candidates_per_iteration)
            ),
        },
        initial_params=dict(strategy.params or {}),
        initial_score=None,
        best_params=None,
        best_score=None,
        best_metrics=None,
        current_iteration=0,
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    return campaign


def get_active_campaign(db: Session, strategy_id: int) -> StrategyOptimizerCampaign | None:
    """Return the latest campaign for a strategy (most recent first)."""
    return (
        db.query(StrategyOptimizerCampaign)
        .filter(StrategyOptimizerCampaign.strategy_id == strategy_id)
        .order_by(StrategyOptimizerCampaign.created_at.desc())
        .first()
    )


def accept_campaign(db: Session, campaign_id: int) -> StrategyOptimizerCampaign:
    """Accept a completed campaign: apply best_params to the strategy."""
    campaign = db.get(StrategyOptimizerCampaign, campaign_id)
    if campaign is None:
        raise ValueError(f'Campaign {campaign_id} not found')
    if campaign.status != 'COMPLETED':
        raise ValueError(f'Cannot accept campaign in status {campaign.status}')

    strategy = db.get(Strategy, campaign.strategy_id)
    if strategy is None:
        raise ValueError(f'Strategy {campaign.strategy_id} not found')

    # Apply best params and reset strategy for re-validation
    strategy.params = dict(campaign.best_params or strategy.params)
    strategy.status = 'BACKTESTING'
    strategy.score = 0.0
    strategy.metrics = {}

    campaign.status = 'ACCEPTED'
    db.commit()
    db.refresh(campaign)

    # Launch re-validation backtest
    try:
        from app.tasks.strategy_backtest_task import execute as execute_strategy_backtest
        settings = get_settings()
        execute_strategy_backtest.apply_async(
            args=[strategy.id],
            queue=settings.celery_backtest_queue,
            ignore_result=True,
        )
    except Exception:
        logger.warning('optimizer_accept_revalidation_enqueue_failed strategy_id=%s', strategy.id, exc_info=True)

    return campaign


def reject_campaign(db: Session, campaign_id: int) -> StrategyOptimizerCampaign:
    """Reject a completed campaign: mark as rejected, leave strategy unchanged."""
    campaign = db.get(StrategyOptimizerCampaign, campaign_id)
    if campaign is None:
        raise ValueError(f'Campaign {campaign_id} not found')
    if campaign.status != 'COMPLETED':
        raise ValueError(f'Cannot reject campaign in status {campaign.status}')

    campaign.status = 'REJECTED_BY_USER'
    db.commit()
    db.refresh(campaign)
    return campaign


def cancel_campaign(db: Session, campaign_id: int) -> StrategyOptimizerCampaign:
    """Cancel a running/pending campaign."""
    campaign = db.get(StrategyOptimizerCampaign, campaign_id)
    if campaign is None:
        raise ValueError(f'Campaign {campaign_id} not found')
    if campaign.status not in _ACTIVE_STATUSES:
        raise ValueError(f'Cannot cancel campaign in status {campaign.status}')

    campaign.status = 'CANCELLED'
    campaign.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(campaign)

    # Revoke celery task if known
    if campaign.celery_task_id:
        try:
            from app.tasks.celery_app import celery_app
            celery_app.control.revoke(campaign.celery_task_id, terminate=True)
        except Exception:
            logger.warning('optimizer_cancel_revoke_failed task_id=%s', campaign.celery_task_id, exc_info=True)

    return campaign


def _mutate_params(
    base_params: dict[str, Any],
    template: str,
    perturbation_pct: float = 0.20,
) -> dict[str, Any]:
    """Mutate parameters by random perturbation within template bounds."""
    bounds = get_bounds_for_template(template)
    mutated: dict[str, Any] = {}

    for key, value in base_params.items():
        if key not in bounds:
            mutated[key] = value
            continue
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            mutated[key] = value
            continue

        lo, hi = bounds[key]
        # Random perturbation: uniform in [-perturbation_pct, +perturbation_pct]
        factor = 1.0 + random.uniform(-perturbation_pct, perturbation_pct)
        new_val = numeric * factor

        # Clamp to bounds
        new_val = max(lo, min(hi, new_val))

        # Preserve int type for integer-valued params
        if isinstance(value, int):
            mutated[key] = int(round(new_val))
        else:
            mutated[key] = round(new_val, 4)

    return mutated


def run_optimization_loop(db: Session, campaign_id: int) -> None:
    """Main optimization loop — called by the Celery task."""
    campaign = db.get(StrategyOptimizerCampaign, campaign_id)
    if campaign is None:
        raise ValueError(f'Campaign {campaign_id} not found')

    strategy = db.get(Strategy, campaign.strategy_id)
    if strategy is None:
        raise ValueError(f'Strategy not found for campaign {campaign_id}')

    # Mark as running
    campaign.status = 'RUNNING'
    db.commit()

    config = campaign.config or {}
    max_iterations = int(config.get('max_iterations', 50))
    time_budget = int(config.get('time_budget_seconds', 300))
    max_candidates = int(config.get('max_candidates_per_iteration', 3))

    # Build evaluator
    evaluator = build_evaluator(
        template=strategy.template,
        symbol=strategy.symbol,
        timeframe=strategy.timeframe,
    )

    # Evaluate initial params
    initial_result = evaluator(campaign.initial_params)
    campaign.initial_score = initial_result['score']
    campaign.best_params = dict(campaign.initial_params)
    campaign.best_score = initial_result['score']
    campaign.best_metrics = initial_result['metrics']
    db.commit()

    # Record initial evaluation
    db.add(StrategyOptimizerEvaluation(
        campaign_id=campaign_id,
        iteration=0,
        params=campaign.initial_params,
        score=initial_result['score'],
        metrics=initial_result['metrics'],
    ))
    db.commit()

    start_time = time.time()

    for iteration in range(1, max_iterations + 1):
        # Check cancellation
        db.refresh(campaign)
        if campaign.status == 'CANCELLED':
            logger.info('optimizer_loop_cancelled campaign_id=%s iteration=%d', campaign_id, iteration)
            return

        # Check time budget
        elapsed = time.time() - start_time
        if elapsed >= time_budget:
            logger.info('optimizer_loop_time_budget_reached campaign_id=%s elapsed=%.1fs', campaign_id, elapsed)
            break

        # Generate and evaluate candidates for this iteration
        best_iteration_score = campaign.best_score or 0.0
        best_iteration_params = dict(campaign.best_params or campaign.initial_params)
        best_iteration_metrics: dict[str, Any] = dict(campaign.best_metrics or {})

        for _ in range(max_candidates):
            candidate_params = _mutate_params(
                base_params=best_iteration_params,
                template=strategy.template,
            )

            # Skip if params are out of bounds or identical
            if not validate_params_in_bounds(strategy.template, candidate_params):
                continue

            result = evaluator(candidate_params)
            score = result['score']

            # Record evaluation
            db.add(StrategyOptimizerEvaluation(
                campaign_id=campaign_id,
                iteration=iteration,
                params=candidate_params,
                score=score,
                metrics=result['metrics'],
            ))

            if score > best_iteration_score:
                best_iteration_score = score
                best_iteration_params = candidate_params
                best_iteration_metrics = result['metrics']

        # Update campaign progress
        campaign.current_iteration = iteration
        if best_iteration_score > (campaign.best_score or 0.0):
            campaign.best_score = best_iteration_score
            campaign.best_params = best_iteration_params
            campaign.best_metrics = best_iteration_metrics
        db.commit()

    # Mark completed
    campaign.status = 'COMPLETED'
    campaign.completed_at = datetime.now(timezone.utc)
    db.commit()
    logger.info(
        'optimizer_loop_completed campaign_id=%s iterations=%d best_score=%.4f initial_score=%.4f',
        campaign_id,
        campaign.current_iteration,
        campaign.best_score or 0.0,
        campaign.initial_score or 0.0,
    )
