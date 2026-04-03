import pytest

from app.services.strategy.signal_engine import (
    compute_strategy_overlays_and_signals,
    get_supported_strategy_templates,
)


def _candles(close_values: list[float]) -> list[dict]:
    return [
        {
            'time': f'2025-01-01T{idx:02d}:00:00Z',
            'open': value,
            'high': value + 0.001,
            'low': value - 0.001,
            'close': value,
            'volume': 1000,
        }
        for idx, value in enumerate(close_values)
    ]


def test_supported_strategy_templates_are_executable() -> None:
    assert set(get_supported_strategy_templates()) == {
        'ema_crossover',
        'rsi_mean_reversion',
        'bollinger_breakout',
        'macd_divergence',
    }


@pytest.mark.parametrize(
    ('template', 'params', 'expected_overlays'),
    [
        ('ema_crossover', {'ema_fast': 5, 'ema_slow': 20, 'rsi_filter': 30}, ['EMA_5', 'EMA_20']),
        ('rsi_mean_reversion', {'rsi_period': 14, 'oversold': 30, 'overbought': 70}, ['EMA_20']),
        ('bollinger_breakout', {'bb_period': 20, 'bb_std': 2.0, 'volume_filter': True}, ['BB_Upper', 'BB_Middle', 'BB_Lower']),
        ('macd_divergence', {'fast': 6, 'slow': 18, 'signal': 5}, ['EMA_6', 'EMA_18']),
    ],
)
def test_compute_strategy_overlays_and_signals_returns_expected_overlays(
    template: str,
    params: dict,
    expected_overlays: list[str],
) -> None:
    candles = _candles([1.1000 + i * 0.0005 for i in range(80)])

    result = compute_strategy_overlays_and_signals(candles, template, params)

    assert [overlay['name'] for overlay in result['overlays']] == expected_overlays
    assert isinstance(result['signals'], list)


def test_unknown_template_raises_value_error() -> None:
    candles = _candles([1.1000 for _ in range(40)])

    with pytest.raises(ValueError, match='Unsupported strategy template: supertrend'):
        compute_strategy_overlays_and_signals(candles, 'supertrend', {})
