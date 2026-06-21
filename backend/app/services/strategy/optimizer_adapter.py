"""Adapter between the optimizer loop and the BacktestEngine.

Provides encoding/decoding of parameters and an evaluator factory
that runs a backtest and returns a scalar fitness score.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from app.services.strategy.optimizer_bounds import TEMPLATE_PARAM_BOUNDS, clamp_params
from app.services.strategy.generation_optimizer import compute_generation_candidate_score
from app.services.strategy.lookback_windows import strategy_lookback_days
from app.services.strategy.template_catalog import sanitize_strategy_params_for_template

logger = logging.getLogger(__name__)


def encode_params_to_program(template: str, params: dict[str, Any]) -> str:
    """Encode a parameter dict as a minimal JSON program string."""
    payload = {'template': template, 'params': params}
    return json.dumps(payload, sort_keys=True)


def decode_program_to_params(program: str) -> dict[str, Any]:
    """Decode a program string back to parameter dict."""
    payload = json.loads(program)
    return dict(payload.get('params', {}))


def validate_params_in_bounds(template: str, params: dict[str, Any]) -> bool:
    """Return True if all parameters are within template bounds."""
    bounds = TEMPLATE_PARAM_BOUNDS.get(template, {})
    if not bounds:
        return True
    for key, (lo, hi) in bounds.items():
        if key not in params:
            continue
        try:
            val = float(params[key])
        except (TypeError, ValueError):
            return False
        if val < lo or val > hi:
            return False
    return True


def build_evaluator(
    template: str,
    symbol: str,
    timeframe: str,
    lookback_days: int | None = None,
) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """Build an evaluation function that backtests params and returns score + metrics.

    Returns a callable: (params: dict) -> {"score": float, "metrics": dict}
    """

    def evaluator(params: dict[str, Any]) -> dict[str, Any]:
        from app.services.backtest.engine import BacktestEngine

        lb_days = lookback_days or strategy_lookback_days(symbol)
        end_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        start_date = (datetime.now(timezone.utc) - timedelta(days=lb_days)).strftime('%Y-%m-%d')

        # Sanitize params for the template
        sanitized, _ = sanitize_strategy_params_for_template(template, params)

        # Clamp to bounds
        clamped = clamp_params(template, sanitized)

        engine = BacktestEngine()
        try:
            result = engine.run(
                symbol,
                timeframe,
                start_date,
                end_date,
                strategy=template,
                db=None,
                strategy_params=clamped,
                run_id=None,
            )
        except Exception as exc:
            logger.warning(
                'optimizer_evaluator_backtest_failed template=%s err=%s',
                template,
                str(exc)[:200],
            )
            return {'score': 0.0, 'metrics': {}}

        metrics = dict(result.metrics or {})
        score = compute_generation_candidate_score(metrics)
        return {'score': score, 'metrics': metrics}

    return evaluator
