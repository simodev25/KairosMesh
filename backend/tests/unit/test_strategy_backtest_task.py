from __future__ import annotations

import importlib
import sys
from types import ModuleType, SimpleNamespace

from app.db.models.strategy import Strategy


def _task_decorator(*args, **kwargs):  # noqa: ANN001, ARG001
    def _decorator(func):  # noqa: ANN001
        return func

    return _decorator


def _load_strategy_backtest_task(monkeypatch):
    fake_celery_app_module = ModuleType('app.tasks.celery_app')
    fake_celery_app_module.celery_app = SimpleNamespace(task=_task_decorator)
    monkeypatch.setitem(sys.modules, 'app.tasks.celery_app', fake_celery_app_module)
    sys.modules.pop('app.tasks.strategy_backtest_task', None)
    return importlib.import_module('app.tasks.strategy_backtest_task')


class _FakeDB:
    def __init__(self, strategy: object) -> None:
        self._strategy = strategy
        self.committed = False
        self.closed = False

    def get(self, model, strategy_id):  # noqa: ANN001, ARG002
        if model is Strategy and strategy_id == self._strategy.id:
            return self._strategy
        return None

    def commit(self) -> None:
        self.committed = True

    def close(self) -> None:
        self.closed = True


def test_strategy_backtest_task_passes_persisted_params(monkeypatch) -> None:
    task_module = _load_strategy_backtest_task(monkeypatch)
    execute = task_module.execute

    strategy = SimpleNamespace(
        id=1,
        strategy_id='STRAT-001',
        name='ema crossover',
        description='validated with persisted params',
        status='BACKTESTING',
        score=0.0,
        template='ema_crossover',
        symbol='EURUSD.PRO',
        timeframe='H1',
        params={'ema_fast': 7, 'ema_slow': 14, 'rsi_filter': 25},
        metrics={},
        prompt_history=[],
        is_monitoring=False,
        monitoring_mode='simulation',
        monitoring_risk_percent=1.0,
        last_signal_key=None,
        last_backtest_id=None,
        created_by_id=42,
    )
    db = _FakeDB(strategy)
    captured: dict[str, object] = {}

    class FakeEngine:
        def run(self, *args, **kwargs):  # noqa: ANN001
            captured['args'] = args
            captured['kwargs'] = kwargs
            return SimpleNamespace(
                metrics={
                    'win_rate_pct': 80,
                    'profit_factor': 2.0,
                    'max_drawdown_pct': 5.0,
                    'total_return_pct': 25.0,
                    'total_trades': 5,
                }
            )

    monkeypatch.setattr('app.tasks.strategy_backtest_task.SessionLocal', lambda: db)
    monkeypatch.setattr('app.tasks.strategy_backtest_task.BacktestEngine', FakeEngine)

    execute(strategy_db_id=1)

    assert captured['args'][0] == 'EURUSD.PRO'
    assert captured['args'][1] == 'H1'
    assert len(captured['args']) >= 4
    assert captured['kwargs']['strategy'] == 'ema_crossover'
    assert captured['kwargs']['strategy_params'] == {'ema_fast': 7, 'ema_slow': 14, 'rsi_filter': 25}
    assert strategy.status == 'VALIDATED'
    assert db.committed is True
    assert db.closed is True
    assert strategy.metrics['validated_template'] == 'ema_crossover'
    assert strategy.metrics['validated_params'] == {'ema_fast': 7, 'ema_slow': 14, 'rsi_filter': 25}
