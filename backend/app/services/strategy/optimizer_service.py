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

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models.strategy import Strategy
from app.db.models.strategy_optimizer_campaign import StrategyOptimizerCampaign
from app.db.models.strategy_optimizer_evaluation import StrategyOptimizerEvaluation
from app.services.llm.model_selector import AgentModelSelector
from app.services.strategy.generation_optimizer import compute_generation_candidate_score
from app.services.strategy.lookback_windows import strategy_lookback_days
from app.services.strategy.optimizer_adapter import build_evaluator, validate_params_in_bounds
from app.services.strategy.optimizer_bounds import clamp_params, get_bounds_for_template

try:
    from openevolve.controller import OpenEvolve as _OEController  # noqa: F401
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


def _resolve_llm_config(db: Session) -> tuple[str, str, str, str]:
    """Resolve LLM provider, model, base_url, api_key from project settings.

    Returns (provider, model_name, base_url, api_key).
    Falls back to settings defaults if model_selector is unavailable.
    """
    settings = get_settings()
    try:
        selector = AgentModelSelector()
        provider = selector.resolve_provider(db)
        model_name = selector.resolve(db)
    except Exception:
        # Fallback: use settings defaults
        provider = 'openai'
        model_name = 'gpt-4.1-mini'

    if provider == 'openai':
        base_url = settings.openai_base_url
        api_key = settings.openai_api_key
    elif provider == 'mistral':
        base_url = settings.mistral_base_url
        api_key = settings.mistral_api_key
    else:  # ollama
        base_url = settings.ollama_base_url
        api_key = settings.ollama_api_key

    return provider, model_name, base_url or '', api_key or ''


def _build_evaluator_script(
    template: str,
    symbol: str,
    timeframe: str,
    db_url: str,
    cancel_file: str,
) -> str:
    """Build a standalone Python evaluator script for OpenEvolve subprocess.

    OpenEvolve loads the evaluator via ``importlib`` in the same process,
    so the script must be self-contained (no ORM closures).  It imports
    application modules lazily so it works from the project ``/app`` root.
    """
    return f'''"""Auto-generated evaluator for OpenEvolve — strategy optimizer."""

import json
import sys
import os

# Ensure the backend package is importable inside the worker.
sys.path.insert(0, '/app')
os.environ.setdefault('DATABASE_URL', {db_url!r})

_CANCEL_FILE = {cancel_file!r}


def evaluate(file_path: str):
    """Evaluate a candidate JSON program via back-test."""
    from openevolve.evaluation_result import EvaluationResult

    # Check cancellation sentinel file
    if os.path.exists(_CANCEL_FILE):
        raise RuntimeError('Campaign cancelled by user')

    try:
        with open(file_path, 'r') as f:
            content = f.read()

        candidate_data = json.loads(content)
        candidate_params = candidate_data.get('params', candidate_data)

        # LLM sometimes strips the wrapper — handle flat dicts
        if 'template' not in candidate_data:
            candidate_params = candidate_data

        # Clamp parameters to template bounds
        from app.services.strategy.optimizer_bounds import clamp_params
        clamped = clamp_params({template!r}, candidate_params)

        # Run the back-test
        from app.services.backtest.engine import BacktestEngine
        from app.services.strategy.lookback_windows import strategy_lookback_days
        from app.services.strategy.generation_optimizer import compute_generation_candidate_score
        from datetime import datetime, timedelta, timezone

        lb_days = strategy_lookback_days({symbol!r})
        end_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        start_date = (datetime.now(timezone.utc) - timedelta(days=lb_days)).strftime('%Y-%m-%d')

        engine = BacktestEngine()
        result = engine.run(
            {symbol!r}, {timeframe!r},
            start_date, end_date,
            strategy={template!r},
            db=None,
            strategy_params=clamped,
            run_id=None,
        )

        metrics = dict(result.metrics or {{}})
        score = compute_generation_candidate_score(metrics)

        win_rate = metrics.get('win_rate_pct', metrics.get('win_rate', 0))
        pf = metrics.get('profit_factor', 0)
        dd = metrics.get('max_drawdown_pct', metrics.get('max_drawdown', 0))
        trades = metrics.get('total_trades', 0)

        feedback = (
            f"Score: {{score:.1f}}/100 | Win Rate: {{win_rate:.1f}}% | "
            f"Profit Factor: {{pf:.2f}} | Max Drawdown: {{dd:.1f}}% | Trades: {{trades}}\\n"
        )
        if trades < 5:
            feedback += "WARNING: Too few trades.\\n"
        if float(dd) > 25:
            feedback += "WARNING: Excessive drawdown.\\n"
        if score > 60:
            feedback += "GOOD: Above threshold.\\n"

        return EvaluationResult(
            metrics={{"combined_score": score, "performance": score, "drawdown": abs(float(dd))}},
            artifacts={{"llm_feedback": feedback}},
        )

    except json.JSONDecodeError as e:
        return EvaluationResult(
            metrics={{"combined_score": -1.0, "performance": -1.0}},
            artifacts={{"stderr": f"INVALID JSON: {{e}}"}},
        )
    except Exception as e:
        return EvaluationResult(
            metrics={{"combined_score": 0.0, "performance": 0.0}},
            artifacts={{"stderr": f"Backtest error: {{str(e)[:200]}}"}},
        )
'''


def _run_openevolve_loop(
    db: Session,
    campaign: StrategyOptimizerCampaign,
    strategy: Strategy,
    config: dict[str, Any],
    max_iterations: int,
) -> None:
    """Run optimization using OpenEvolve with LLM-driven mutation.

    The evaluator runs inside OpenEvolve's own process via ``importlib``,
    so it must be a **standalone .py file** — no closures over ORM objects.
    """
    import asyncio

    campaign_id = campaign.id

    # 0. Resolve LLM config from project settings
    provider, model_name, base_url, api_key = _resolve_llm_config(db)
    logger.info(
        'openevolve_loop_start campaign_id=%s provider=%s model=%s',
        campaign_id, provider, model_name,
    )

    # 1. Evaluate initial params directly (before OpenEvolve)
    initial_eval = evaluator_direct(
        strategy.template, strategy.symbol, strategy.timeframe,
        dict(strategy.params or {}),
    )
    campaign.initial_score = initial_eval['score']
    campaign.best_params = dict(strategy.params or {})
    campaign.best_score = initial_eval['score']
    campaign.best_metrics = initial_eval['metrics']
    db.commit()

    # 2. Write the initial program JSON to a temp file
    output_dir = tempfile.mkdtemp(prefix='openevolve_strategy_')
    initial_program_path = os.path.join(output_dir, 'initial_program.json')
    initial_data = json.dumps({
        'template': strategy.template,
        'symbol': strategy.symbol,
        'timeframe': strategy.timeframe,
        'params': dict(strategy.params or {}),
    }, indent=2)

    with open(initial_program_path, 'w') as f:
        f.write(initial_data)

    # 3. Write standalone evaluator script to disk
    settings = get_settings()
    cancel_file = os.path.join(output_dir, '.cancel')
    evaluator_code = _build_evaluator_script(
        template=strategy.template,
        symbol=strategy.symbol,
        timeframe=strategy.timeframe,
        db_url=settings.database_url,
        cancel_file=cancel_file,
    )
    evaluator_file_path = os.path.join(output_dir, 'evaluator.py')
    with open(evaluator_file_path, 'w') as f:
        f.write(evaluator_code)

    # 4. Build OpenEvolve Config
    from openevolve.config import Config as OEConfig, LLMModelConfig

    bounds = get_bounds_for_template(strategy.template)
    bounds_description = '\n'.join(
        f'  - {k}: min={lo}, max={hi}' for k, (lo, hi) in bounds.items()
    )

    system_message = (
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
    )

    # Ensure base_url ends with /v1 for OpenAI-compatible providers
    llm_base_url = (base_url or '').rstrip('/')
    if not llm_base_url.endswith('/v1'):
        llm_base_url += '/v1'

    oe_config = OEConfig()
    oe_config.max_iterations = max_iterations
    oe_config.diff_based_evolution = False   # JSON, not code — disable diff mode
    oe_config.language = 'json'
    oe_config.database.num_islands = 1       # Simpler for trading optimisation
    oe_config.database.in_memory = True
    oe_config.llm = OEConfig().llm           # fresh LLMConfig to avoid __post_init__ issues
    oe_config.llm.models = [
        LLMModelConfig(
            name=model_name,
            api_key=api_key or 'ollama',
            api_base=llm_base_url,
            temperature=0.7,
            system_message=system_message,
        ),
    ]

    # 5. Start cancel-watcher thread (polls DB every 3s, writes sentinel file)
    import threading

    def _cancel_watcher() -> None:
        from app.db.session import SessionLocal
        while not os.path.exists(cancel_file):
            try:
                with SessionLocal() as check_db:
                    row = check_db.get(StrategyOptimizerCampaign, campaign_id)
                    if row and row.status == 'CANCELLED':
                        with open(cancel_file, 'w') as cf:
                            cf.write('cancelled')
                        logger.info('cancel_watcher: sentinel written for campaign %s', campaign_id)
                        return
            except Exception:
                pass
            time.sleep(3)

    cancel_thread = threading.Thread(target=_cancel_watcher, daemon=True)
    cancel_thread.start()

    # 6. Run OpenEvolve (async → sync bridge)
    try:
        from openevolve.controller import OpenEvolve as OEController

        oe = OEController(
            initial_program_path=initial_program_path,
            evaluation_file=evaluator_file_path,
            config=oe_config,
            output_dir=output_dir,
        )

        # Run the async evolution loop from a sync context.
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # Already inside an event loop (e.g. Celery with gevent/eventlet).
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                result = pool.submit(
                    asyncio.run, oe.run(iterations=max_iterations),
                ).result()
        else:
            result = asyncio.run(oe.run(iterations=max_iterations))

        # 6. Parse the best result
        if result and hasattr(result, 'code') and result.code:
            try:
                best_data = json.loads(result.code)
                best_params = best_data.get('params', best_data)
                clamped_best = clamp_params(strategy.template, best_params)

                # 7. Final confirmation evaluation
                final_eval = evaluator_direct(
                    strategy.template, strategy.symbol, strategy.timeframe, clamped_best,
                )
                if final_eval['score'] > (campaign.best_score or 0.0):
                    campaign.best_params = clamped_best
                    campaign.best_score = final_eval['score']
                    campaign.best_metrics = final_eval['metrics']
            except (json.JSONDecodeError, KeyError):
                pass  # Keep whatever best was found during initial eval

        # 8. Update campaign tracking from OpenEvolve result
        if result and hasattr(result, 'iteration_found'):
            campaign.current_iteration = result.iteration_found
        else:
            campaign.current_iteration = max_iterations

        campaign.status = 'COMPLETED'
    except Exception as exc:
        logger.error(
            'openevolve_run_failed campaign_id=%s: %s',
            campaign_id, str(exc)[:300], exc_info=True,
        )
        # Fallback: if OpenEvolve fails, the initial eval is still valid
        if campaign.best_score and campaign.best_score > (campaign.initial_score or 0.0):
            campaign.status = 'COMPLETED'
        else:
            campaign.status = 'FAILED'
            campaign.error = str(exc)[:500]
    finally:
        campaign.completed_at = datetime.now(timezone.utc)
        db.commit()
        # 9. Cleanup temp files
        shutil.rmtree(output_dir, ignore_errors=True)


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
