"""Tests for optimizer_service — campaign CRUD and state transitions."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest

from app.db.models.strategy import Strategy
from app.db.models.strategy_optimizer_campaign import StrategyOptimizerCampaign
from app.services.strategy.optimizer_service import (
    accept_campaign,
    cancel_campaign,
    create_campaign,
    get_active_campaign,
    reject_campaign,
)


class FakeQuery:
    """Simulate SQLAlchemy query chainable interface."""

    def __init__(self, results=None):
        self._results = results or []

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def first(self):
        return self._results[0] if self._results else None


@pytest.fixture
def db():
    """Create a mock DB session."""
    session = MagicMock()
    session.add = MagicMock()
    session.commit = MagicMock()
    session.refresh = MagicMock(side_effect=lambda obj: None)
    return session


@pytest.fixture
def strategy():
    s = MagicMock(spec=Strategy)
    s.id = 1
    s.strategy_id = 'STRAT-001'
    s.status = 'VALIDATED'
    s.params = {'ema_fast': 9, 'ema_slow': 21, 'rsi_filter': 30}
    s.template = 'ema_crossover'
    s.symbol = 'EURUSD.PRO'
    s.timeframe = 'H1'
    s.score = 75.0
    s.metrics = {}
    return s


def test_create_campaign_success(db, strategy):
    """Creating a campaign returns a PENDING campaign."""
    db.get = MagicMock(return_value=strategy)
    db.query = MagicMock(return_value=FakeQuery(results=[]))

    campaign = create_campaign(db, strategy.id, {'max_iterations': 30})

    assert campaign.status == 'PENDING'
    assert campaign.strategy_id == strategy.id
    assert campaign.config['max_iterations'] == 30
    assert campaign.initial_params == strategy.params
    db.add.assert_called_once()
    db.commit.assert_called()


def test_create_campaign_fails_if_active_exists(db, strategy):
    """Cannot create campaign if one is already RUNNING."""
    existing = MagicMock(spec=StrategyOptimizerCampaign)
    existing.id = 99
    existing.status = 'RUNNING'
    db.query = MagicMock(return_value=FakeQuery(results=[existing]))

    with pytest.raises(ValueError, match='already active'):
        create_campaign(db, strategy.id, {})


def test_accept_campaign_applies_best_params(db, strategy):
    """Accept updates strategy params and triggers re-validation."""
    campaign = MagicMock(spec=StrategyOptimizerCampaign)
    campaign.id = 10
    campaign.status = 'COMPLETED'
    campaign.strategy_id = strategy.id
    campaign.best_params = {'ema_fast': 12, 'ema_slow': 36, 'rsi_filter': 35}

    db.get = MagicMock(side_effect=lambda model, pk: campaign if model == StrategyOptimizerCampaign else strategy)

    with patch('app.services.strategy.optimizer_service.get_settings') as mock_settings:
        mock_settings.return_value = MagicMock(celery_backtest_queue='backtests')
        with patch('app.tasks.strategy_backtest_task.execute') as mock_task:
            mock_task.apply_async = MagicMock()
            result = accept_campaign(db, campaign.id)

    assert result.status == 'ACCEPTED'
    assert strategy.params == campaign.best_params
    assert strategy.status == 'BACKTESTING'


def test_reject_campaign_leaves_strategy_unchanged(db, strategy):
    """Reject sets campaign status without modifying strategy."""
    campaign = MagicMock(spec=StrategyOptimizerCampaign)
    campaign.id = 10
    campaign.status = 'COMPLETED'
    campaign.strategy_id = strategy.id

    db.get = MagicMock(return_value=campaign)
    original_params = dict(strategy.params)

    result = reject_campaign(db, campaign.id)

    assert result.status == 'REJECTED_BY_USER'
    assert strategy.params == original_params


def test_cancel_campaign_sets_cancelled(db):
    """Cancel sets campaign status to CANCELLED."""
    campaign = MagicMock(spec=StrategyOptimizerCampaign)
    campaign.id = 10
    campaign.status = 'RUNNING'
    campaign.celery_task_id = None
    campaign.completed_at = None

    db.get = MagicMock(return_value=campaign)

    result = cancel_campaign(db, campaign.id)

    assert result.status == 'CANCELLED'
    assert result.completed_at is not None


def test_reject_non_completed_raises(db):
    """Cannot reject a campaign that is not COMPLETED."""
    campaign = MagicMock(spec=StrategyOptimizerCampaign)
    campaign.id = 10
    campaign.status = 'RUNNING'

    db.get = MagicMock(return_value=campaign)

    with pytest.raises(ValueError, match='Cannot reject'):
        reject_campaign(db, campaign.id)


def test_get_active_campaign_returns_latest(db):
    """get_active_campaign returns latest campaign by created_at."""
    mock_result = MagicMock(id=42)
    db.query = MagicMock(return_value=FakeQuery(results=[mock_result]))

    result = get_active_campaign(db, strategy_id=1)
    assert result is not None
    assert result.id == 42
