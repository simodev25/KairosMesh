import numpy as np
import pandas as pd

from app.services.backtest.engine import BacktestEngine


def test_backtest_engine_returns_metrics(monkeypatch) -> None:
    index = pd.date_range('2025-01-01', periods=180, freq='D')
    trend = np.linspace(1.05, 1.20, len(index))
    noise = 0.002 * np.sin(np.arange(len(index)))
    close = trend + noise

    frame = pd.DataFrame(
        {
            'Open': close,
            'High': close + 0.003,
            'Low': close - 0.003,
            'Close': close,
            'Volume': np.full(len(index), 1000),
        },
        index=index,
    )

    monkeypatch.setattr('app.services.market.yfinance_provider.YFinanceMarketProvider.get_historical_candles', lambda *args, **kwargs: frame)

    engine = BacktestEngine()
    result = engine.run('EURUSD', 'D1', '2025-01-01', '2025-06-30', strategy='ema_rsi')

    assert 'total_return_pct' in result.metrics
    assert 'sharpe_ratio' in result.metrics
    assert result.metrics.get('strategy') == 'ema_rsi'
    assert result.metrics.get('workflow_source') == 'BacktestEngine.ema_rsi'
    assert isinstance(result.equity_curve, list)
    assert len(result.equity_curve) > 0


def test_backtest_engine_agents_strategy(monkeypatch) -> None:
    index = pd.date_range('2025-01-01', periods=180, freq='D')
    trend = np.linspace(1.05, 1.20, len(index))
    noise = 0.002 * np.sin(np.arange(len(index)))
    close = trend + noise

    frame = pd.DataFrame(
        {
            'Open': close,
            'High': close + 0.003,
            'Low': close - 0.003,
            'Close': close,
            'Volume': np.full(len(index), 1000),
        },
        index=index,
    )

    monkeypatch.setattr('app.services.market.yfinance_provider.YFinanceMarketProvider.get_historical_candles', lambda *args, **kwargs: frame)

    analyze_calls = {'count': 0}

    def fake_analyze_context(*args, **kwargs):
        analyze_calls['count'] += 1
        context = kwargs.get('context') or args[1]
        last_price = float(context.market_snapshot['last_price'])
        return {
            'analysis_outputs': {},
            'bullish': {'arguments': []},
            'bearish': {'arguments': []},
            'trader_decision': {
                'decision': 'BUY',
                'entry': last_price,
                'stop_loss': round(last_price - 0.002, 5),
                'take_profit': round(last_price + 0.004, 5),
            },
            'risk': {'accepted': True, 'reasons': ['Risk checks passed.'], 'suggested_volume': 0.2},
        }

    monkeypatch.setattr('app.services.orchestrator.engine.ForexOrchestrator.analyze_context', fake_analyze_context)

    engine = BacktestEngine()
    result = engine.run('EURUSD', 'D1', '2025-01-01', '2025-06-30', strategy='agents')

    assert 'total_return_pct' in result.metrics
    assert result.metrics.get('strategy') == 'agents_v1'
    assert result.metrics.get('workflow_source') == 'ForexOrchestrator.analyze_context'
    assert analyze_calls['count'] > 0
    assert isinstance(result.equity_curve, list)
    assert len(result.equity_curve) > 0
