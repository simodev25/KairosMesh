"""Strategy Optimizer service — orchestrates evolutionary campaign loop.

Provides CRUD operations on campaigns and the main optimization loop.
When OpenEvolve is available, uses LLM-driven mutation with MAP-Elites.
Falls back to naive hill climbing (random ±20%) when OpenEvolve is not installed.
"""

from __future__ import annotations

import json
import logging
import os
import random
import shutil
import tempfile
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import yaml
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models.strategy import Strategy
from app.db.models.strategy_optimizer_campaign import StrategyOptimizerCampaign
from app.db.models.strategy_optimizer_evaluation import StrategyOptimizerEvaluation
from app.services.strategy.generation_optimizer import compute_generation_candidate_score
from app.services.strategy.lookback_windows import strategy_lookback_days
from app.services.strategy.optimizer_adapter import build_evaluator, validate_params_in_bounds
from app.services.strategy.optimizer_bounds import clamp_params, get_bounds_for_template

try:
    from openevolve import run_evolution
    from openevolve.evaluation_result import EvaluationResult
    OPENEVOLVE_AVAILABLE = True
except ImportError:
    OPENEVOLVE_AVAILABLE = False

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


def evaluator_direct(template: str, symbol: str, timeframe: str, params: dict) -> dict:
    """Direct evaluation without file I/O — for initial and final scoring."""
    from app.services.backtest.engine import BacktestEngine

    lb_days = strategy_lookback_days(symbol)
    end_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    start_date = (datetime.now(timezone.utc) - timedelta(days=lb_days)).strftime('%Y-%m-%d')

    clamped = clamp_params(template, params)
    engine = BacktestEngine()
    try:
        result = engine.run(
            symbol, timeframe, start_date, end_date,
            strategy=template, db=None, strategy_params=clamped, run_id=None,
        )
        metrics = dict(result.metrics or {})
        score = compute_generation_candidate_score(metrics)
        return {'score': score, 'metrics': metrics}
    except Exception:
        return {'score': 0.0, 'metrics': {}}


def run_optimization_loop(db: Session, campaign_id: int) -> None:
    """Main optimization loop — called by the Celery task.

    Uses OpenEvolve (LLM-driven mutation with MAP-Elites) when available.
    Falls back to naive hill climbing when OpenEvolve is not installed.
    """
    campaign = db.get(StrategyOptimizerCampaign, campaign_id)
    if campaign is None:
        raise ValueError(f'Campaign {campaign_id} not found')

    strategy = db.get(Strategy, campaign.strategy_id)
    if strategy is None:
        raise ValueError(f'Strategy not found for campaign {campaign_id}')

    # Mark as running
    campaign.status = 'RUNNING'
    campaign.started_at = datetime.now(timezone.utc)
    db.commit()

    config = campaign.config or {}
    max_iterations = int(config.get('max_iterations', 50))

    if OPENEVOLVE_AVAILABLE:
        _run_openevolve_loop(db, campaign, strategy, config, max_iterations)
    else:
        _run_naive_loop(db, campaign, strategy, config, max_iterations)


def _run_openevolve_loop(
    db: Session,
    campaign: StrategyOptimizerCampaign,
    strategy: Strategy,
    config: dict[str, Any],
    max_iterations: int,
) -> None:
    """Run optimization using OpenEvolve with LLM-driven mutation."""
    campaign_id = campaign.id

    # 1. Initial program = JSON of params
    initial_program = json.dumps({
        'template': strategy.template,
        'symbol': strategy.symbol,
        'timeframe': strategy.timeframe,
        'params': dict(strategy.params or {}),
    }, indent=2)

    # 2. Build evaluator for OpenEvolve (file-based interface)
    bounds = get_bounds_for_template(strategy.template)

    def openevolve_evaluator(file_path: str) -> 'EvaluationResult':
        """Evaluate a candidate strategy by backtesting it."""
        # Check cancellation
        db.refresh(campaign)
        if campaign.status == 'CANCELLED':
            raise RuntimeError('Campaign cancelled')

        try:
            with open(file_path, 'r') as f:
                content = f.read()

            # Parse the JSON (LLM may produce varied formats)
            candidate_data = json.loads(content)
            candidate_params = candidate_data.get('params', candidate_data)

            # If params is the top-level dict (LLM sometimes strips structure)
            if 'template' not in candidate_data and all(
                k in candidate_data for k in (strategy.params or {}).keys()
            ):
                candidate_params = candidate_data

            # Clamp to bounds
            clamped = clamp_params(strategy.template, candidate_params)

            # Backtest
            from app.services.backtest.engine import BacktestEngine

            lb_days = strategy_lookback_days(strategy.symbol)
            end_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
            start_date = (datetime.now(timezone.utc) - timedelta(days=lb_days)).strftime('%Y-%m-%d')

            engine = BacktestEngine()
            result = engine.run(
                strategy.symbol, strategy.timeframe,
                start_date, end_date,
                strategy=strategy.template,
                db=None,
                strategy_params=clamped,
                run_id=None,
            )

            metrics = dict(result.metrics or {})
            score = compute_generation_candidate_score(metrics)

            # Store evaluation in DB
            db.add(StrategyOptimizerEvaluation(
                campaign_id=campaign_id,
                iteration=campaign.current_iteration or 0,
                params=clamped,
                score=score,
                metrics=metrics,
            ))
            campaign.current_iteration = (campaign.current_iteration or 0) + 1
            if score > (campaign.best_score or 0.0):
                campaign.best_score = score
                campaign.best_params = clamped
                campaign.best_metrics = metrics
            db.commit()

            # Return result with feedback for LLM
            win_rate = metrics.get('win_rate_pct', metrics.get('win_rate', 0))
            pf = metrics.get('profit_factor', 0)
            dd = metrics.get('max_drawdown_pct', metrics.get('max_drawdown', 0))
            trades = metrics.get('total_trades', 0)

            feedback = (
                f"Score: {score:.1f}/100 | Win Rate: {win_rate:.1f}% | "
                f"Profit Factor: {pf:.2f} | Max Drawdown: {dd:.1f}% | Trades: {trades}\n"
            )
            if trades < 5:
                feedback += "WARNING: Too few trades — parameters may be too restrictive.\n"
            if float(dd) > 25:
                feedback += "WARNING: Excessive drawdown — reduce risk exposure.\n"
            if score > 60:
                feedback += "GOOD: Above threshold. Try fine-tuning for higher profit factor.\n"

            return EvaluationResult(
                metrics={'performance': score, 'drawdown': abs(float(dd))},
                artifacts={'llm_feedback': feedback},
            )

        except json.JSONDecodeError as e:
            return EvaluationResult(
                metrics={'performance': -1.0, 'drawdown': 100.0},
                artifacts={'stderr': f'INVALID JSON: {e}. You MUST return valid JSON with the same structure.'},
            )
        except RuntimeError:
            raise  # Re-raise cancellation
        except Exception as e:
            logger.warning('optimizer_evaluator_error: %s', str(e)[:200])
            return EvaluationResult(
                metrics={'performance': 0.0, 'drawdown': 100.0},
                artifacts={'stderr': f'Backtest error: {str(e)[:200]}'},
            )

    # 3. Write OpenEvolve config
    bounds_description = '\n'.join(
        f'  - {k}: min={lo}, max={hi}' for k, (lo, hi) in bounds.items()
    )

    openevolve_config = {
        'max_iterations': max_iterations,
        'llm': {
            'model': config.get('model', 'gpt-4.1-mini'),
            'temperature': 0.7,
        },
        'database': {
            'population_size': min(max_iterations * 2, 100),
            'num_islands': 2,
        },
        'evaluator': {
            'enable_artifacts': True,
        },
        'prompt': {
            'num_top_programs': 2,
            'num_diverse_programs': 1,
            'include_artifacts': True,
            'system_message': (
                f"You are a quantitative trading strategy optimizer.\n"
                f"You optimize parameters for a '{strategy.template}' strategy "
                f"on {strategy.symbol} {strategy.timeframe}.\n\n"
                f"RULES:\n"
                f"- Return ONLY valid JSON (no markdown, no explanation).\n"
                f"- Keep the exact same structure: "
                f"{{\"template\": ..., \"symbol\": ..., \"timeframe\": ..., \"params\": {{...}}}}\n"
                f"- Only modify values inside 'params'.\n"
                f"- Respect parameter bounds:\n{bounds_description}\n\n"
                f"GOAL: Maximize the composite score "
                f"(win_rate × profit_factor × low_drawdown × positive_return × sufficient_trades).\n"
                f"Use the feedback from previous evaluations to guide your changes.\n"
            ),
        },
    }

    # 4. Run OpenEvolve
    config_dir = tempfile.mkdtemp(prefix='openevolve_strategy_')
    config_path = os.path.join(config_dir, 'config.yaml')

    with open(config_path, 'w') as f:
        yaml.dump(openevolve_config, f)

    try:
        # Evaluate initial params first
        initial_eval = evaluator_direct(
            strategy.template, strategy.symbol, strategy.timeframe,
            dict(strategy.params or {}),
        )
        campaign.initial_score = initial_eval['score']
        campaign.best_params = dict(strategy.params or {})
        campaign.best_score = initial_eval['score']
        campaign.best_metrics = initial_eval['metrics']
        db.commit()

        # Run OpenEvolve
        result = run_evolution(
            initial_program=initial_program,
            evaluator=openevolve_evaluator,
            iterations=max_iterations,
            config_path=config_path,
        )

        # Parse the best result
        if result and hasattr(result, 'best_code') and result.best_code:
            try:
                best_data = json.loads(result.best_code)
                best_params = best_data.get('params', best_data)
                clamped_best = clamp_params(strategy.template, best_params)

                # Final evaluation to confirm
                final_eval = evaluator_direct(
                    strategy.template, strategy.symbol, strategy.timeframe, clamped_best,
                )
                if final_eval['score'] > (campaign.best_score or 0.0):
                    campaign.best_params = clamped_best
                    campaign.best_score = final_eval['score']
                    campaign.best_metrics = final_eval['metrics']
            except (json.JSONDecodeError, KeyError):
                pass  # Keep whatever best was found during evaluations

        campaign.status = 'COMPLETED'
    except Exception as exc:
        logger.error(
            'openevolve_run_failed campaign_id=%s: %s',
            campaign_id, str(exc)[:300], exc_info=True,
        )
        # Fallback: if OpenEvolve fails, the best found during evaluations is still valid
        if campaign.best_score and campaign.best_score > (campaign.initial_score or 0.0):
            campaign.status = 'COMPLETED'
        else:
            campaign.status = 'FAILED'
            campaign.error = str(exc)[:500]
    finally:
        campaign.completed_at = datetime.now(timezone.utc)
        db.commit()
        # Cleanup temp dir
        shutil.rmtree(config_dir, ignore_errors=True)


def _run_naive_loop(
    db: Session,
    campaign: StrategyOptimizerCampaign,
    strategy: Strategy,
    config: dict[str, Any],
    max_iterations: int,
) -> None:
    """Fallback optimization loop — naive hill climbing with random ±20% perturbation."""
    campaign_id = campaign.id
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
