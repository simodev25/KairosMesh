from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator

from app.services.market.yfinance_provider import YFinanceMarketProvider


@dataclass
class BacktestResult:
    metrics: dict[str, Any]
    equity_curve: list[dict[str, Any]]
    trades: list[dict[str, Any]]


class BacktestEngine:
    PERIODS_PER_YEAR = {
        'M5': 72576,
        'M15': 24192,
        'H1': 6048,
        'H4': 1512,
        'D1': 252,
    }

    def __init__(self) -> None:
        self.market_provider = YFinanceMarketProvider()

    def _extract_trades(self, frame: pd.DataFrame, signals: pd.Series) -> list[dict[str, Any]]:
        trades: list[dict[str, Any]] = []
        current_side = 0
        entry_time: datetime | None = None
        entry_price = 0.0

        for ts, signal in signals.items():
            signal = int(signal)
            price = float(frame.loc[ts, 'Close'])

            if current_side == 0 and signal != 0:
                current_side = signal
                entry_time = ts.to_pydatetime()
                entry_price = price
                continue

            if current_side != 0 and signal != current_side:
                exit_time = ts.to_pydatetime()
                pnl_pct = ((price - entry_price) / entry_price) * (1 if current_side == 1 else -1)
                trades.append(
                    {
                        'side': 'BUY' if current_side == 1 else 'SELL',
                        'entry_time': entry_time,
                        'exit_time': exit_time,
                        'entry_price': round(entry_price, 6),
                        'exit_price': round(price, 6),
                        'pnl_pct': round(float(pnl_pct * 100), 4),
                        'outcome': 'win' if pnl_pct > 0 else 'loss' if pnl_pct < 0 else 'flat',
                    }
                )

                if signal == 0:
                    current_side = 0
                    entry_time = None
                    entry_price = 0.0
                else:
                    current_side = signal
                    entry_time = ts.to_pydatetime()
                    entry_price = price

        if current_side != 0 and entry_time is not None:
            last_ts = frame.index[-1]
            last_price = float(frame['Close'].iloc[-1])
            pnl_pct = ((last_price - entry_price) / entry_price) * (1 if current_side == 1 else -1)
            trades.append(
                {
                    'side': 'BUY' if current_side == 1 else 'SELL',
                    'entry_time': entry_time,
                    'exit_time': last_ts.to_pydatetime(),
                    'entry_price': round(entry_price, 6),
                    'exit_price': round(last_price, 6),
                    'pnl_pct': round(float(pnl_pct * 100), 4),
                    'outcome': 'win' if pnl_pct > 0 else 'loss' if pnl_pct < 0 else 'flat',
                }
            )

        return trades

    def run(self, pair: str, timeframe: str, start_date: str, end_date: str) -> BacktestResult:
        frame = self.market_provider.get_historical_candles(pair, timeframe, start_date=start_date, end_date=end_date)
        if frame.empty or len(frame) < 80:
            raise ValueError('Insufficient historical candles for backtesting')

        frame = frame.copy().dropna()
        close = frame['Close']
        frame['ema_fast'] = EMAIndicator(close=close, window=20).ema_indicator()
        frame['ema_slow'] = EMAIndicator(close=close, window=50).ema_indicator()
        frame['rsi'] = RSIIndicator(close=close, window=14).rsi()
        frame = frame.dropna()

        signal = np.where((frame['ema_fast'] > frame['ema_slow']) & (frame['rsi'] < 70), 1, 0)
        signal = np.where((frame['ema_fast'] < frame['ema_slow']) & (frame['rsi'] > 30), -1, signal)
        frame['signal'] = signal
        frame['position'] = pd.Series(signal, index=frame.index).shift(1).fillna(0)
        frame['ret'] = frame['Close'].pct_change().fillna(0) * frame['position']
        frame['equity'] = (1 + frame['ret']).cumprod()

        drawdown = frame['equity'] / frame['equity'].cummax() - 1
        max_drawdown = float(drawdown.min()) if not drawdown.empty else 0.0

        avg_ret = float(frame['ret'].mean())
        std_ret = float(frame['ret'].std())
        periods = self.PERIODS_PER_YEAR.get(timeframe.upper(), 252)
        sharpe = (avg_ret / std_ret * np.sqrt(periods)) if std_ret > 0 else 0.0

        downside = frame.loc[frame['ret'] < 0, 'ret']
        downside_std = float(downside.std()) if not downside.empty else 0.0
        sortino = (avg_ret / downside_std * np.sqrt(periods)) if downside_std > 0 else 0.0

        trades = self._extract_trades(frame, frame['signal'])
        wins = [trade for trade in trades if trade['pnl_pct'] > 0]
        losses = [trade for trade in trades if trade['pnl_pct'] < 0]

        gross_profit = sum(trade['pnl_pct'] for trade in wins)
        gross_loss = abs(sum(trade['pnl_pct'] for trade in losses))
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float('inf')

        metrics = {
            'total_return_pct': round(float((frame['equity'].iloc[-1] - 1) * 100), 4),
            'annualized_return_pct': round(float(((frame['equity'].iloc[-1]) ** (periods / max(len(frame), 1)) - 1) * 100), 4),
            'max_drawdown_pct': round(max_drawdown * 100, 4),
            'sharpe_ratio': round(float(sharpe), 4),
            'sortino_ratio': round(float(sortino), 4),
            'profit_factor': round(float(profit_factor), 4) if profit_factor != float('inf') else None,
            'trades': len(trades),
            'win_rate_pct': round((len(wins) / len(trades) * 100), 2) if trades else 0.0,
            'avg_trade_return_pct': round((sum(trade['pnl_pct'] for trade in trades) / len(trades)), 4) if trades else 0.0,
        }

        equity_curve = [
            {
                'ts': ts.isoformat(),
                'equity': round(float(value), 6),
            }
            for ts, value in frame['equity'].items()
        ]

        return BacktestResult(metrics=metrics, equity_curve=equity_curve, trades=trades)
