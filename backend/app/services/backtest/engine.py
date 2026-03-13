from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import logging
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator
from ta.volatility import AverageTrueRange

from app.core.config import get_settings
from app.services.market.yfinance_provider import YFinanceMarketProvider
from app.services.orchestrator.agents import AgentContext
from app.services.orchestrator.engine import ForexOrchestrator

logger = logging.getLogger(__name__)


@dataclass
class BacktestResult:
    metrics: dict[str, Any]
    equity_curve: list[dict[str, Any]]
    trades: list[dict[str, Any]]


class BacktestEngine:
    SUPPORTED_STRATEGIES = {'ema_rsi', 'agents_v1'}
    STRATEGY_ALIASES = {
        'ema-rsi': 'ema_rsi',
        'legacy_ema_rsi': 'ema_rsi',
        'legacy-ema-rsi': 'ema_rsi',
        'agent': 'agents_v1',
        'agents': 'agents_v1',
        'multi_agent': 'agents_v1',
        'multi-agent': 'agents_v1',
        'trading_agents': 'agents_v1',
        'trading-agents': 'agents_v1',
        'default': 'agents_v1',
    }

    PERIODS_PER_YEAR = {
        'M5': 72576,
        'M15': 24192,
        'H1': 6048,
        'H4': 1512,
        'D1': 252,
    }

    def __init__(self) -> None:
        self.settings = get_settings()
        self.market_provider = YFinanceMarketProvider()
        self.orchestrator = ForexOrchestrator()

    @classmethod
    def normalize_strategy(cls, strategy: str | None) -> str | None:
        value = (strategy or '').strip().lower().replace(' ', '_')
        if not value:
            return 'agents_v1'
        if value in cls.SUPPORTED_STRATEGIES:
            return value
        return cls.STRATEGY_ALIASES.get(value)

    def _prepare_indicator_frame(self, frame: pd.DataFrame) -> pd.DataFrame:
        prepared = frame.copy().dropna()
        close = prepared['Close']
        high = prepared['High']
        low = prepared['Low']
        prepared['ema_fast'] = EMAIndicator(close=close, window=20).ema_indicator()
        prepared['ema_slow'] = EMAIndicator(close=close, window=50).ema_indicator()
        prepared['rsi'] = RSIIndicator(close=close, window=14).rsi()
        prepared['atr'] = AverageTrueRange(high=high, low=low, close=close).average_true_range()
        prepared = prepared.dropna()
        prepared['change_pct'] = prepared['Close'].pct_change().fillna(0) * 100
        return prepared

    def _signal_series_ema_rsi(self, frame: pd.DataFrame) -> pd.Series:
        signal = np.where((frame['ema_fast'] > frame['ema_slow']) & (frame['rsi'] < 70), 1, 0)
        signal = np.where((frame['ema_fast'] < frame['ema_slow']) & (frame['rsi'] > 30), -1, signal)
        return pd.Series(signal, index=frame.index, dtype='int64')

    def _market_snapshot_at(self, pair: str, timeframe: str, frame: pd.DataFrame, index_pos: int) -> dict[str, Any]:
        row = frame.iloc[index_pos]
        last_price = float(row['Close'])
        ema_fast = float(row['ema_fast'])
        ema_slow = float(row['ema_slow'])
        trend = 'bullish' if ema_fast > ema_slow else 'bearish'
        if abs(ema_fast - ema_slow) < last_price * 0.0003:
            trend = 'neutral'

        return {
            'degraded': False,
            'pair': pair,
            'timeframe': timeframe,
            'last_price': last_price,
            'change_pct': round(float(row['change_pct']), 5),
            'rsi': round(float(row['rsi']), 3),
            'ema_fast': round(ema_fast, 6),
            'ema_slow': round(ema_slow, 6),
            # Use EMA spread as deterministic momentum proxy for backtests.
            'macd_diff': round(float(ema_fast - ema_slow), 6),
            'atr': round(float(row['atr']), 6),
            'trend': trend,
        }

    def _signal_series_agents(self, pair: str, timeframe: str, frame: pd.DataFrame, db: Session | None = None) -> pd.Series:
        signals: list[int] = []
        llm_enabled = bool(self.settings.backtest_enable_llm and db is not None)
        llm_every = max(int(self.settings.backtest_llm_every), 1)
        news_context = self.market_provider.get_news_context(pair) if llm_enabled else {'degraded': False, 'pair': pair, 'news': []}
        log_every = max(int(self.settings.backtest_agent_log_every), 1)
        for index_pos, ts in enumerate(frame.index):
            market_snapshot = self._market_snapshot_at(pair, timeframe, frame, index_pos)
            context = AgentContext(
                pair=pair,
                timeframe=timeframe,
                mode='backtest',
                risk_percent=1.0,
                market_snapshot=market_snapshot,
                news_context=news_context,
                memory_context=[],
            )
            should_log_steps = self.settings.log_agent_steps and (
                index_pos == 0 or (index_pos + 1) % log_every == 0 or index_pos == len(frame.index) - 1
            )
            use_llm_for_candle = llm_enabled and (
                index_pos == 0 or (index_pos + 1) % llm_every == 0 or index_pos == len(frame.index) - 1
            )
            analysis_bundle = self.orchestrator.analyze_context(
                context=context,
                db=db if use_llm_for_candle else None,
                run=None,
                record_steps=False,
                emit_step_logs=should_log_steps,
            )
            trader = analysis_bundle['trader_decision']
            risk = analysis_bundle['risk']

            decision = str(trader.get('decision', 'HOLD')).upper() if risk.get('accepted') else 'HOLD'
            if should_log_steps:
                logger.info(
                    'backtest_agent_cycle pair=%s timeframe=%s candle=%s decision=%s accepted=%s llm=%s',
                    pair,
                    timeframe,
                    ts.isoformat(),
                    decision,
                    risk.get('accepted'),
                    use_llm_for_candle,
                )
            if decision == 'BUY':
                signals.append(1)
            elif decision == 'SELL':
                signals.append(-1)
            else:
                signals.append(0)

        return pd.Series(signals, index=frame.index, dtype='int64')

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

    def run(
        self,
        pair: str,
        timeframe: str,
        start_date: str,
        end_date: str,
        strategy: str = 'agents_v1',
        db: Session | None = None,
    ) -> BacktestResult:
        normalized_strategy = self.normalize_strategy(strategy)
        if not normalized_strategy:
            raise ValueError(f'Unsupported backtest strategy: {strategy}')
        llm_enabled = bool(self.settings.backtest_enable_llm and db is not None)
        logger.info(
            'backtest_engine_start pair=%s timeframe=%s strategy_in=%s strategy=%s llm_enabled=%s llm_every=%s',
            pair,
            timeframe,
            strategy,
            normalized_strategy,
            llm_enabled,
            int(self.settings.backtest_llm_every),
        )

        frame = self.market_provider.get_historical_candles(pair, timeframe, start_date=start_date, end_date=end_date)
        if frame.empty or len(frame) < 80:
            raise ValueError('Insufficient historical candles for backtesting')

        frame = self._prepare_indicator_frame(frame)
        if frame.empty or len(frame) < 80:
            raise ValueError('Insufficient indicator-ready candles for backtesting')

        if normalized_strategy == 'ema_rsi':
            signal_series = self._signal_series_ema_rsi(frame)
        else:
            signal_series = self._signal_series_agents(pair, timeframe, frame, db=db)

        frame['signal'] = signal_series
        frame['position'] = signal_series.shift(1).fillna(0)
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

        workflow = (
            list(ForexOrchestrator.WORKFLOW_STEPS[:-1])
            if normalized_strategy == 'agents_v1'
            else ['technical-analyst', 'trader-agent']
        )

        metrics = {
            'strategy': normalized_strategy,
            'workflow': workflow,
            'workflow_source': 'ForexOrchestrator.analyze_context' if normalized_strategy == 'agents_v1' else 'BacktestEngine.ema_rsi',
            'execution_mode': 'disabled-in-backtest' if normalized_strategy == 'agents_v1' else 'strategy-internal',
            'agent_logging_enabled': bool(self.settings.log_agent_steps),
            'backtest_agent_log_every': int(self.settings.backtest_agent_log_every),
            'llm_enabled': llm_enabled,
            'llm_every': int(self.settings.backtest_llm_every),
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

        logger.info(
            'backtest_engine_done pair=%s timeframe=%s strategy=%s workflow_source=%s trades=%s',
            pair,
            timeframe,
            normalized_strategy,
            metrics.get('workflow_source'),
            metrics.get('trades'),
        )

        return BacktestResult(metrics=metrics, equity_curve=equity_curve, trades=trades)
