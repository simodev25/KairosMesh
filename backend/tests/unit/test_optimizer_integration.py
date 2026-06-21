"""Integration-style unit tests for the Strategy Optimizer.

Tests cover the full optimizer workflow: campaign CRUD, mutation logic,
evaluation fallback, and schema handling — all without external services.
"""

from __future__ import annotations

import random
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers — fake DB objects as SimpleNamespace
# ---------------------------------------------------------------------------

def _make_strategy(
    id: int = 1,
    template: str = 'ema_crossover',
    symbol: str = 'EURUSD.PRO',
    timeframe: str = 'H1',
    params: dict | None = None,
    status: str = 'VALIDATED',
) -> SimpleNamespace:
    return SimpleNamespace(
        id=id,
        template=template,
        symbol=symbol,
        timeframe=timeframe,
        params=params or {'ema_fast': 9, 'ema_slow': 21, 'rsi_filter': 30},
        status=status,
        score=65.0,
        metrics={'win_rate_pct': 45.0, 'profit_factor': 1.5},
    )


def _make_campaign(
    id: int = 10,
    strategy_id: int = 1,
    status: str = 'PENDING',
    config: dict | None = None,
    initial_params: dict | None = None,
    initial_score: float | None = None,
    best_params: dict | None = None,
    best_score: float | None = None,
    best_metrics: dict | None = None,
    current_iteration: int = 0,
    celery_task_id: str | None = None,
    error_message: str | None = None,
    created_at: datetime | None = None,
    completed_at: datetime | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=id,
        strategy_id=strategy_id,
        status=status,
        config=config or {'max_iterations': 50, 'time_budget_seconds': 300, 'max_candidates_per_iteration': 3},
        initial_params=initial_params or {'ema_fast': 9, 'ema_slow': 21, 'rsi_filter': 30},
        initial_score=initial_score,
        best_params=best_params,
        best_score=best_score,
        best_metrics=best_metrics,
        current_iteration=current_iteration,
        celery_task_id=celery_task_id,
        error_message=error_message,
        created_at=created_at or datetime(2026, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
        completed_at=completed_at,
        updated_at=datetime(2026, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
    )


class FakeDB:
    """Minimal DB session mock with query support."""

    def __init__(self, objects: dict[tuple, Any] | None = None) -> None:
        self._objects = objects or {}
        self._added: list = []
        self.committed = False

    def get(self, model, obj_id):
        return self._objects.get((model, obj_id))

    def query(self, model):
        return FakeQuery(self._objects, model)

    def add(self, obj):
        self._added.append(obj)

    def commit(self):
        self.committed = True

    def refresh(self, obj):
        pass  # no-op for tests


class FakeQuery:
    """Chainable query mock."""

    def __init__(self, objects: dict, model) -> None:
        self._objects = objects
        self._model = model
        self._filters: list = []

    def filter(self, *args, **kwargs):
        # Store but don't evaluate — return self for chaining
        return self

    def order_by(self, *args):
        return self

    def first(self):
        # Return first matching object of the model type
        for (model, _), obj in self._objects.items():
            if model is self._model:
                return obj
        return None


# ---------------------------------------------------------------------------
# Test 1: create_campaign creates a PENDING campaign with correct config
# ---------------------------------------------------------------------------

@patch('app.services.strategy.optimizer_service.get_settings')
def test_create_campaign_creates_pending_with_correct_config(mock_settings) -> None:
    """create_campaign should create PENDING campaign clamped by settings limits."""
    mock_settings.return_value = SimpleNamespace(
        optimizer_max_iterations=100,
        optimizer_max_iterations_limit=200,
        optimizer_time_budget_seconds=300,
        optimizer_time_budget_limit=600,
        optimizer_max_candidates_per_iteration=5,
    )

    from app.db.models.strategy import Strategy
    from app.db.models.strategy_optimizer_campaign import StrategyOptimizerCampaign

    strategy = _make_strategy()

    # DB that has no existing campaign and has the strategy
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None  # no active campaign
    db.get.return_value = strategy

    # Capture what gets added
    added_campaigns = []

    def fake_add(obj):
        added_campaigns.append(obj)

    db.add.side_effect = fake_add

    from app.services.strategy.optimizer_service import create_campaign

    result = create_campaign(db, strategy_id=1, config={'max_iterations': 80, 'time_budget_seconds': 250})

    # Verify add was called
    assert db.add.called
    campaign = added_campaigns[0]
    assert campaign.status == 'PENDING'
    assert campaign.config['max_iterations'] == 80
    assert campaign.config['time_budget_seconds'] == 250
    assert campaign.current_iteration == 0
    assert campaign.initial_params == {'ema_fast': 9, 'ema_slow': 21, 'rsi_filter': 30}


# ---------------------------------------------------------------------------
# Test 2: create_campaign raises ValueError if active campaign exists
# ---------------------------------------------------------------------------

@patch('app.services.strategy.optimizer_service.get_settings')
def test_create_campaign_raises_if_active_exists(mock_settings) -> None:
    """create_campaign should raise ValueError if an active campaign exists."""
    mock_settings.return_value = SimpleNamespace(
        optimizer_max_iterations=100,
        optimizer_max_iterations_limit=200,
        optimizer_time_budget_seconds=300,
        optimizer_time_budget_limit=600,
        optimizer_max_candidates_per_iteration=5,
    )

    existing_campaign = _make_campaign(status='RUNNING')

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = existing_campaign

    from app.services.strategy.optimizer_service import create_campaign

    with pytest.raises(ValueError, match='Campaign already active'):
        create_campaign(db, strategy_id=1, config={})


# ---------------------------------------------------------------------------
# Test 3: run_optimization_loop (naive fallback) updates best_score
# ---------------------------------------------------------------------------

@patch('app.services.strategy.optimizer_service.OPENEVOLVE_AVAILABLE', False)
@patch('app.services.strategy.optimizer_service.build_evaluator')
def test_run_naive_loop_updates_best_score_on_improvement(mock_build_evaluator) -> None:
    """The naive loop should update best_score when a better candidate is found."""
    from app.db.models.strategy import Strategy
    from app.db.models.strategy_optimizer_campaign import StrategyOptimizerCampaign

    strategy = _make_strategy()
    campaign = _make_campaign(
        status='PENDING',
        config={'max_iterations': 2, 'time_budget_seconds': 600, 'max_candidates_per_iteration': 1},
    )

    # Evaluator returns increasing scores
    call_count = {'n': 0}

    def fake_evaluator(params):
        call_count['n'] += 1
        score = 50.0 + call_count['n'] * 10.0
        return {'score': score, 'metrics': {'win_rate_pct': score}}

    mock_build_evaluator.return_value = fake_evaluator

    db = MagicMock()
    db.get.side_effect = lambda model, id: (
        campaign if model is StrategyOptimizerCampaign else strategy
    )
    db.refresh.side_effect = lambda obj: None

    from app.services.strategy.optimizer_service import run_optimization_loop

    run_optimization_loop(db, campaign_id=campaign.id)

    # Campaign should be updated — best_score should be > initial (60.0)
    assert campaign.best_score > 60.0
    assert campaign.status == 'COMPLETED'


# ---------------------------------------------------------------------------
# Test 4: run_optimization_loop marks COMPLETED when done
# ---------------------------------------------------------------------------

@patch('app.services.strategy.optimizer_service.OPENEVOLVE_AVAILABLE', False)
@patch('app.services.strategy.optimizer_service.build_evaluator')
def test_run_naive_loop_marks_completed(mock_build_evaluator) -> None:
    """The naive loop marks campaign COMPLETED after all iterations."""
    from app.db.models.strategy import Strategy
    from app.db.models.strategy_optimizer_campaign import StrategyOptimizerCampaign

    strategy = _make_strategy()
    campaign = _make_campaign(
        status='PENDING',
        config={'max_iterations': 1, 'time_budget_seconds': 600, 'max_candidates_per_iteration': 1},
    )

    mock_build_evaluator.return_value = lambda params: {'score': 42.0, 'metrics': {}}

    db = MagicMock()
    db.get.side_effect = lambda model, id: (
        campaign if model is StrategyOptimizerCampaign else strategy
    )
    db.refresh.side_effect = lambda obj: None

    from app.services.strategy.optimizer_service import run_optimization_loop

    run_optimization_loop(db, campaign_id=campaign.id)

    assert campaign.status == 'COMPLETED'
    assert campaign.completed_at is not None


# ---------------------------------------------------------------------------
# Test 5: run_optimization_loop marks CANCELLED when campaign cancelled mid-run
# ---------------------------------------------------------------------------

@patch('app.services.strategy.optimizer_service.OPENEVOLVE_AVAILABLE', False)
@patch('app.services.strategy.optimizer_service.build_evaluator')
def test_run_naive_loop_stops_on_cancellation(mock_build_evaluator) -> None:
    """If campaign is CANCELLED mid-run, the loop should stop without marking COMPLETED."""
    from app.db.models.strategy import Strategy
    from app.db.models.strategy_optimizer_campaign import StrategyOptimizerCampaign

    strategy = _make_strategy()
    campaign = _make_campaign(
        status='PENDING',
        config={'max_iterations': 100, 'time_budget_seconds': 600, 'max_candidates_per_iteration': 1},
    )

    mock_build_evaluator.return_value = lambda params: {'score': 42.0, 'metrics': {}}

    # Simulate cancellation on first db.refresh call during loop
    def fake_refresh(obj):
        if hasattr(obj, 'status') and obj.status == 'RUNNING':
            obj.status = 'CANCELLED'

    db = MagicMock()
    db.get.side_effect = lambda model, id: (
        campaign if model is StrategyOptimizerCampaign else strategy
    )
    db.refresh.side_effect = fake_refresh

    from app.services.strategy.optimizer_service import run_optimization_loop

    run_optimization_loop(db, campaign_id=campaign.id)

    # The campaign should remain CANCELLED (not overwritten to COMPLETED)
    assert campaign.status == 'CANCELLED'


# ---------------------------------------------------------------------------
# Test 6: accept_campaign applies best_params and resets strategy status
# ---------------------------------------------------------------------------

@patch('app.services.strategy.optimizer_service.get_settings')
def test_accept_campaign_applies_best_params(mock_settings) -> None:
    """accept_campaign should apply best_params to strategy and reset to BACKTESTING."""
    mock_settings.return_value = SimpleNamespace(celery_backtest_queue='backtest')

    from app.db.models.strategy import Strategy
    from app.db.models.strategy_optimizer_campaign import StrategyOptimizerCampaign

    strategy = _make_strategy()
    campaign = _make_campaign(
        status='COMPLETED',
        best_params={'ema_fast': 12, 'ema_slow': 30, 'rsi_filter': 25},
    )

    db = MagicMock()
    db.get.side_effect = lambda model, id: (
        campaign if model is StrategyOptimizerCampaign else strategy
    )

    from app.services.strategy.optimizer_service import accept_campaign

    with patch('app.tasks.strategy_backtest_task.execute') as mock_task:
        mock_task.apply_async = MagicMock()
        result = accept_campaign(db, campaign_id=campaign.id)

    assert strategy.params == {'ema_fast': 12, 'ema_slow': 30, 'rsi_filter': 25}
    assert strategy.status == 'BACKTESTING'
    assert strategy.score == 0.0
    assert result.status == 'ACCEPTED'


# ---------------------------------------------------------------------------
# Test 7: reject_campaign marks REJECTED_BY_USER without changing strategy
# ---------------------------------------------------------------------------

def test_reject_campaign_marks_rejected() -> None:
    """reject_campaign should mark campaign REJECTED_BY_USER, leave strategy untouched."""
    from app.db.models.strategy_optimizer_campaign import StrategyOptimizerCampaign

    strategy = _make_strategy()
    campaign = _make_campaign(status='COMPLETED')
    original_params = dict(strategy.params)

    db = MagicMock()
    db.get.side_effect = lambda model, id: (
        campaign if model is StrategyOptimizerCampaign else strategy
    )

    from app.services.strategy.optimizer_service import reject_campaign

    result = reject_campaign(db, campaign_id=campaign.id)

    assert result.status == 'REJECTED_BY_USER'
    assert strategy.params == original_params
    assert strategy.status == 'VALIDATED'


# ---------------------------------------------------------------------------
# Test 8: cancel_campaign marks CANCELLED and revokes celery task
# ---------------------------------------------------------------------------

def test_cancel_campaign_revokes_celery_task() -> None:
    """cancel_campaign should mark CANCELLED and revoke the Celery task."""
    from app.db.models.strategy_optimizer_campaign import StrategyOptimizerCampaign

    campaign = _make_campaign(status='RUNNING', celery_task_id='task-abc-123')

    db = MagicMock()
    db.get.return_value = campaign

    from app.services.strategy.optimizer_service import cancel_campaign

    with patch('app.tasks.celery_app.celery_app') as mock_celery:
        mock_celery.control.revoke = MagicMock()
        result = cancel_campaign(db, campaign_id=campaign.id)

    assert result.status == 'CANCELLED'
    assert result.completed_at is not None
    mock_celery.control.revoke.assert_called_once_with('task-abc-123', terminate=True)


# ---------------------------------------------------------------------------
# Test 9: _mutate_params stays within bounds
# ---------------------------------------------------------------------------

def test_mutate_params_stays_within_bounds() -> None:
    """_mutate_params should never produce values outside template bounds."""
    from app.services.strategy.optimizer_service import _mutate_params
    from app.services.strategy.optimizer_bounds import get_bounds_for_template

    base_params = {'ema_fast': 9, 'ema_slow': 21, 'rsi_filter': 30}
    template = 'ema_crossover'
    bounds = get_bounds_for_template(template)

    random.seed(42)
    for _ in range(100):
        mutated = _mutate_params(base_params, template, perturbation_pct=0.50)
        for key, (lo, hi) in bounds.items():
            assert lo <= float(mutated[key]) <= hi, (
                f'{key}={mutated[key]} not in [{lo}, {hi}]'
            )


# ---------------------------------------------------------------------------
# Test 10: _mutate_params preserves int types
# ---------------------------------------------------------------------------

def test_mutate_params_preserves_int_types() -> None:
    """_mutate_params should return int values for int-typed input params."""
    from app.services.strategy.optimizer_service import _mutate_params

    base_params = {'ema_fast': 9, 'ema_slow': 21, 'rsi_filter': 30}
    template = 'ema_crossover'

    random.seed(0)
    for _ in range(50):
        mutated = _mutate_params(base_params, template)
        for key in base_params:
            assert isinstance(mutated[key], int), (
                f'{key} should be int, got {type(mutated[key])}'
            )


# ---------------------------------------------------------------------------
# Test 11: evaluator_direct returns score 0 when BacktestEngine raises
# ---------------------------------------------------------------------------

def test_evaluator_direct_returns_zero_on_engine_error() -> None:
    """evaluator_direct should return score 0 if BacktestEngine.run() raises."""
    from app.services.strategy.optimizer_service import evaluator_direct

    with patch('app.services.backtest.engine.BacktestEngine') as MockEngine:
        instance = MockEngine.return_value
        instance.run.side_effect = RuntimeError('Market data unavailable')

        result = evaluator_direct(
            template='ema_crossover',
            symbol='EURUSD.PRO',
            timeframe='H1',
            params={'ema_fast': 9, 'ema_slow': 21, 'rsi_filter': 30},
        )

    assert result['score'] == 0.0
    assert result['metrics'] == {}


# ---------------------------------------------------------------------------
# Test 12: OptimizerCampaignOut.from_campaign handles naive datetime
# ---------------------------------------------------------------------------

def test_optimizer_campaign_out_handles_naive_datetime() -> None:
    """OptimizerCampaignOut.from_campaign should handle naive datetimes without crash."""
    from app.schemas.optimizer import OptimizerCampaignOut

    # Simulate a campaign with naive (no tzinfo) created_at
    campaign = _make_campaign(
        status='RUNNING',
        created_at=datetime(2026, 1, 15, 10, 0, 0),  # naive — no tzinfo
        completed_at=None,
        initial_score=50.0,
    )

    result = OptimizerCampaignOut.from_campaign(campaign)

    assert result.status == 'RUNNING'
    assert result.elapsed_seconds is not None
    assert result.elapsed_seconds > 0
    assert result.initial_score == 50.0
    assert result.max_iterations == 50
