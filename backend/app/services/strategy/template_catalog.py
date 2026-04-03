from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class StrategyTemplateSpec:
    key: str
    description: str
    params: dict[str, str]
    best_for: str
    category: str


EXECUTABLE_STRATEGY_TEMPLATES: dict[str, StrategyTemplateSpec] = {
    'ema_crossover': StrategyTemplateSpec(
        key='ema_crossover',
        description='EMA crossover with RSI filter',
        params={'ema_fast': 'int (5-50)', 'ema_slow': 'int (20-200)', 'rsi_filter': 'int (15-50)'},
        best_for='trending markets, medium-term',
        category='trend',
    ),
    'rsi_mean_reversion': StrategyTemplateSpec(
        key='rsi_mean_reversion',
        description='RSI mean reversion',
        params={'rsi_period': 'int (5-30)', 'oversold': 'int (10-40)', 'overbought': 'int (60-90)'},
        best_for='ranging markets',
        category='mean_reversion',
    ),
    'bollinger_breakout': StrategyTemplateSpec(
        key='bollinger_breakout',
        description='Bollinger Band breakout',
        params={'bb_period': 'int (5-50)', 'bb_std': 'float (0.5-4.0)', 'volume_filter': 'bool'},
        best_for='breakout setups',
        category='breakout',
    ),
    'macd_divergence': StrategyTemplateSpec(
        key='macd_divergence',
        description='MACD signal line crossover',
        params={'fast': 'int (4-20)', 'slow': 'int (15-50)', 'signal': 'int (3-15)'},
        best_for='momentum shifts',
        category='momentum',
    ),
}
