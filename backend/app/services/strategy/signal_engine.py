from __future__ import annotations

from typing import Any

import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator, MACD
from ta.volatility import BollingerBands

from app.services.strategy.template_catalog import EXECUTABLE_STRATEGY_TEMPLATES


def get_supported_strategy_templates() -> list[str]:
    return list(EXECUTABLE_STRATEGY_TEMPLATES.keys())


def _validate_template(template: str) -> None:
    if template not in EXECUTABLE_STRATEGY_TEMPLATES:
        raise ValueError(f'Unsupported strategy template: {template}')


def _overlay_points(times: list[Any], series: pd.Series) -> list[dict[str, Any]]:
    return [
        {'time': t, 'value': round(float(v), 6)}
        for t, v in zip(times, series)
        if pd.notna(v)
    ]


def compute_strategy_overlays_and_signals(
    candles: list[dict],
    template: str,
    params: dict,
) -> dict[str, list[dict]]:
    _validate_template(template)

    if not candles:
        return {'overlays': [], 'signals': []}

    df = pd.DataFrame(candles)
    close = df['close'].astype(float)
    times = df['time'].tolist()
    overlays: list[dict] = []
    signals: list[dict] = []

    if template == 'ema_crossover':
        fast_period = params.get('ema_fast', 9)
        slow_period = params.get('ema_slow', 21)
        rsi_filter = params.get('rsi_filter', 30)
        ema_fast = close.ewm(span=fast_period, adjust=False).mean()
        ema_slow = close.ewm(span=slow_period, adjust=False).mean()
        rsi = RSIIndicator(close=close, window=14).rsi()

        overlays.append({'name': f'EMA_{fast_period}', 'color': '#4a90d9', 'data': _overlay_points(times, ema_fast)})
        overlays.append({'name': f'EMA_{slow_period}', 'color': '#e6a23c', 'data': _overlay_points(times, ema_slow)})

        for i in range(1, len(df)):
            if pd.isna(ema_fast.iloc[i]) or pd.isna(rsi.iloc[i]):
                continue
            if (
                ema_fast.iloc[i] > ema_slow.iloc[i]
                and ema_fast.iloc[i - 1] <= ema_slow.iloc[i - 1]
                and rsi.iloc[i] < (100 - rsi_filter)
            ):
                signals.append({'time': times[i], 'price': float(close.iloc[i]), 'side': 'BUY'})
            elif (
                ema_fast.iloc[i] < ema_slow.iloc[i]
                and ema_fast.iloc[i - 1] >= ema_slow.iloc[i - 1]
                and rsi.iloc[i] > rsi_filter
            ):
                signals.append({'time': times[i], 'price': float(close.iloc[i]), 'side': 'SELL'})

    elif template == 'rsi_mean_reversion':
        rsi_period = params.get('rsi_period', 14)
        oversold = params.get('oversold', 30)
        overbought = params.get('overbought', 70)
        rsi = RSIIndicator(close=close, window=rsi_period).rsi()
        ema20 = EMAIndicator(close=close, window=20).ema_indicator()

        overlays.append({'name': 'EMA_20', 'color': '#4a90d9', 'data': _overlay_points(times, ema20)})

        for i in range(1, len(df)):
            if pd.isna(rsi.iloc[i]):
                continue
            if rsi.iloc[i] < oversold and rsi.iloc[i - 1] >= oversold:
                signals.append({'time': times[i], 'price': float(close.iloc[i]), 'side': 'BUY'})
            elif rsi.iloc[i] > overbought and rsi.iloc[i - 1] <= overbought:
                signals.append({'time': times[i], 'price': float(close.iloc[i]), 'side': 'SELL'})

    elif template == 'bollinger_breakout':
        bb_period = params.get('bb_period', 20)
        bb_std = params.get('bb_std', 2.0)
        bb = BollingerBands(close=close, window=bb_period, window_dev=bb_std)
        upper = bb.bollinger_hband()
        lower = bb.bollinger_lband()
        middle = bb.bollinger_mavg()

        overlays.append({'name': 'BB_Upper', 'color': '#ef4444', 'data': _overlay_points(times, upper)})
        overlays.append({'name': 'BB_Middle', 'color': '#8a8f98', 'data': _overlay_points(times, middle)})
        overlays.append({'name': 'BB_Lower', 'color': '#22c55e', 'data': _overlay_points(times, lower)})

        for i in range(1, len(df)):
            if pd.isna(lower.iloc[i]):
                continue
            if close.iloc[i] <= lower.iloc[i] and close.iloc[i - 1] > lower.iloc[i - 1]:
                signals.append({'time': times[i], 'price': float(close.iloc[i]), 'side': 'BUY'})
            elif close.iloc[i] >= upper.iloc[i] and close.iloc[i - 1] < upper.iloc[i - 1]:
                signals.append({'time': times[i], 'price': float(close.iloc[i]), 'side': 'SELL'})

    elif template == 'macd_divergence':
        fast = params.get('fast', 12)
        slow = params.get('slow', 26)
        signal_period = params.get('signal', 9)
        macd_ind = MACD(close=close, window_fast=fast, window_slow=slow, window_sign=signal_period)
        macd_line = macd_ind.macd()
        signal_line = macd_ind.macd_signal()
        ema_fast = close.ewm(span=fast, adjust=False).mean()
        ema_slow = close.ewm(span=slow, adjust=False).mean()

        overlays.append({'name': f'EMA_{fast}', 'color': '#4a90d9', 'data': _overlay_points(times, ema_fast)})
        overlays.append({'name': f'EMA_{slow}', 'color': '#e6a23c', 'data': _overlay_points(times, ema_slow)})

        for i in range(1, len(df)):
            if pd.isna(macd_line.iloc[i]) or pd.isna(signal_line.iloc[i]):
                continue
            if macd_line.iloc[i] > signal_line.iloc[i] and macd_line.iloc[i - 1] <= signal_line.iloc[i - 1]:
                signals.append({'time': times[i], 'price': float(close.iloc[i]), 'side': 'BUY'})
            elif macd_line.iloc[i] < signal_line.iloc[i] and macd_line.iloc[i - 1] >= signal_line.iloc[i - 1]:
                signals.append({'time': times[i], 'price': float(close.iloc[i]), 'side': 'SELL'})

    return {'overlays': overlays, 'signals': signals}
