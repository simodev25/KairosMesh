"""Optimizer parameter bounds derived from _TEMPLATE_PRESETS.

Each template defines min/max bounds for every tuneable parameter.
The optimizer mutates parameters within these bounds.
"""

from __future__ import annotations

from typing import Any


# Bounds per template: {param_name: (min_value, max_value)}
TEMPLATE_PARAM_BOUNDS: dict[str, dict[str, tuple[float, float]]] = {
    # ── Trend Following ──
    'ema_crossover': {
        'ema_fast': (3, 20),
        'ema_slow': (15, 55),
        'rsi_filter': (15, 45),
    },
    'supertrend': {
        'atr_period': (5, 21),
        'atr_multiplier': (1.0, 5.0),
    },
    'adx_trend': {
        'adx_period': (7, 25),
        'adx_threshold': (15, 40),
        'di_period': (7, 25),
    },
    'ichimoku': {
        'tenkan': (5, 15),
        'kijun': (18, 40),
        'senkou_b': (35, 75),
    },
    'parabolic_sar': {
        'af_start': (0.005, 0.05),
        'af_step': (0.005, 0.05),
        'af_max': (0.1, 0.4),
    },
    'donchian_breakout': {
        'entry_period': (5, 70),
        'exit_period': (3, 35),
    },
    # ── Mean Reversion ──
    'rsi_mean_reversion': {
        'rsi_period': (5, 28),
        'oversold': (15, 40),
        'overbought': (60, 90),
    },
    'stochastic_reversal': {
        'k_period': (5, 21),
        'd_period': (2, 7),
        'oversold': (10, 30),
        'overbought': (70, 95),
    },
    'williams_r': {
        'period': (5, 28),
        'oversold': (-95, -70),
        'overbought': (-30, -5),
    },
    'cci_reversal': {
        'cci_period': (10, 30),
        'oversold': (-200, -50),
        'overbought': (50, 200),
    },
    'keltner_reversion': {
        'ema_period': (10, 30),
        'atr_period': (7, 21),
        'atr_multiplier': (0.8, 3.0),
    },
    # ── Breakout / Volatility ──
    'bollinger_breakout': {
        'bb_period': (10, 40),
        'bb_std': (1.0, 3.5),
    },
    'squeeze_momentum': {
        'bb_period': (10, 35),
        'bb_std': (1.0, 3.5),
        'kc_period': (10, 35),
        'kc_multiplier': (0.8, 3.0),
    },
    'atr_trailing_stop': {
        'atr_period': (7, 28),
        'atr_multiplier': (1.0, 5.0),
        'trend_ema': (15, 60),
    },
    # ── Momentum ──
    'macd_divergence': {
        'fast': (5, 20),
        'slow': (18, 45),
        'signal': (4, 15),
    },
    'roc_momentum': {
        'roc_period': (5, 30),
        'signal_period': (3, 18),
        'threshold': (0.2, 3.0),
    },
    'vwap_strategy': {
        'trend_ema': (15, 60),
        'deviation_pct': (0.1, 1.0),
    },
    # ── Hybrid ──
    'triple_ema': {
        'ema_1': (2, 12),
        'ema_2': (6, 25),
        'ema_3': (18, 70),
    },
    'macd_rsi_combo': {
        'macd_fast': (5, 18),
        'macd_slow': (18, 40),
        'macd_signal': (4, 15),
        'rsi_period': (7, 25),
        'rsi_oversold': (20, 40),
        'rsi_overbought': (60, 85),
    },
    'pivot_points': {
        'lookback': (1, 10),
    },
}


def get_bounds_for_template(template: str) -> dict[str, tuple[float, float]]:
    """Return parameter bounds for a template. Empty dict if template unknown."""
    return TEMPLATE_PARAM_BOUNDS.get(template, {})


def clamp_params(template: str, params: dict[str, Any]) -> dict[str, Any]:
    """Clamp parameters to template bounds. Non-bounded params pass through."""
    bounds = get_bounds_for_template(template)
    result: dict[str, Any] = {}
    for key, value in params.items():
        if key in bounds:
            lo, hi = bounds[key]
            try:
                numeric = float(value)
                clamped = max(lo, min(hi, numeric))
                # Preserve int type for integer bounds
                if isinstance(value, int) and lo == int(lo) and hi == int(hi):
                    result[key] = int(round(clamped))
                else:
                    result[key] = round(clamped, 4)
            except (TypeError, ValueError):
                result[key] = value
        else:
            result[key] = value
    return result
