"""Tests for optimizer API endpoints — HTTP status codes and response schemas."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
import pytest

from fastapi.testclient import TestClient


@pytest.fixture
def app():
    """Create a minimal FastAPI app with the strategies router."""
    from fastapi import FastAPI
    from app.api.routes.strategies import router
    application = FastAPI()
    application.include_router(router, prefix='/api/v1')
    return application


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def mock_auth():
    """Mock authentication to always pass."""
    from app.db.models.user import User
    from app.core.security import Role

    user = User.__new__(User)
    user.id = 1
    user.role = Role.ADMIN
    user.email = 'test@test.com'

    with patch('app.api.routes.strategies.require_roles') as mock_roles:
        mock_roles.return_value = lambda: user

        # Also patch Depends resolution
        def fake_depends(*args, **kwargs):
            return user

        mock_roles.return_value = fake_depends
        yield user


@pytest.fixture
def mock_db():
    """Mock database session."""
    session = MagicMock()
    with patch('app.api.routes.strategies.get_db') as mock_get_db:
        mock_get_db.return_value = session
        yield session


@pytest.fixture
def validated_strategy():
    """A strategy with VALIDATED status."""
    from app.db.models.strategy import Strategy
    s = Strategy.__new__(Strategy)
    s.id = 1
    s.strategy_id = 'STRAT-001'
    s.status = 'VALIDATED'
    s.params = {'ema_fast': 9, 'ema_slow': 21, 'rsi_filter': 30}
    s.template = 'ema_crossover'
    s.symbol = 'EURUSD.PRO'
    s.timeframe = 'H1'
    s.score = 75.0
    s.metrics = {}
    s.name = 'Test Strategy'
    s.description = 'Test'
    s.is_monitoring = False
    s.monitoring_mode = 'simulation'
    s.monitoring_risk_percent = 1.0
    s.last_signal_key = None
    s.prompt_history = []
    s.last_backtest_id = None
    s.created_by_id = 1
    s.created_at = datetime.now(timezone.utc)
    s.updated_at = datetime.now(timezone.utc)
    return s


@pytest.fixture
def draft_strategy():
    """A strategy with DRAFT status."""
    from app.db.models.strategy import Strategy
    s = Strategy.__new__(Strategy)
    s.id = 2
    s.strategy_id = 'STRAT-002'
    s.status = 'DRAFT'
    s.params = {'ema_fast': 9, 'ema_slow': 21}
    s.template = 'ema_crossover'
    s.symbol = 'EURUSD.PRO'
    s.timeframe = 'H1'
    s.score = 0.0
    s.metrics = {}
    return s


class TestStartOptimization:
    """Tests for POST /strategies/{id}/optimize."""

    def test_launch_on_validated_returns_201(self, client, mock_auth, mock_db, validated_strategy):
        """POST /optimize on VALIDATED strategy returns 201."""
        from app.db.models.strategy_optimizer_campaign import StrategyOptimizerCampaign

        mock_db.get = MagicMock(return_value=validated_strategy)

        campaign = StrategyOptimizerCampaign.__new__(StrategyOptimizerCampaign)
        campaign.id = 1
        campaign.strategy_id = 1
        campaign.status = 'PENDING'
        campaign.current_iteration = 0
        campaign.config = {'max_iterations': 50, 'time_budget_seconds': 300, 'max_candidates_per_iteration': 3}
        campaign.initial_params = validated_strategy.params
        campaign.initial_score = None
        campaign.best_params = None
        campaign.best_score = None
        campaign.best_metrics = None
        campaign.celery_task_id = None
        campaign.error_message = None
        campaign.created_at = datetime.now(timezone.utc)
        campaign.completed_at = None

        with patch('app.api.routes.strategies.create_campaign', return_value=campaign):
            with patch('app.api.routes.strategies.optimizer_execute') as mock_task:
                mock_task.apply_async.return_value = MagicMock(id='task-123')
                response = client.post(
                    '/api/v1/strategies/1/optimize',
                    json={'max_iterations': 50},
                )

        assert response.status_code == 201
        data = response.json()
        assert data['status'] == 'PENDING'
        assert data['strategy_id'] == 1

    def test_launch_on_draft_returns_422(self, client, mock_auth, mock_db, draft_strategy):
        """POST /optimize on DRAFT strategy returns 422."""
        mock_db.get = MagicMock(return_value=draft_strategy)

        response = client.post(
            '/api/v1/strategies/2/optimize',
            json={},
        )

        assert response.status_code == 422

    def test_launch_with_active_campaign_returns_409(self, client, mock_auth, mock_db, validated_strategy):
        """POST /optimize when campaign already RUNNING returns 409."""
        mock_db.get = MagicMock(return_value=validated_strategy)

        with patch('app.api.routes.strategies.create_campaign', side_effect=ValueError('Campaign already active')):
            response = client.post(
                '/api/v1/strategies/1/optimize',
                json={},
            )

        assert response.status_code == 409


class TestGetOptimizerCampaign:
    """Tests for GET /strategies/{id}/optimizer-campaign."""

    def test_returns_campaign(self, client, mock_auth, mock_db, validated_strategy):
        """GET returns campaign data when one exists."""
        from app.db.models.strategy_optimizer_campaign import StrategyOptimizerCampaign

        mock_db.get = MagicMock(return_value=validated_strategy)

        campaign = StrategyOptimizerCampaign.__new__(StrategyOptimizerCampaign)
        campaign.id = 5
        campaign.strategy_id = 1
        campaign.status = 'RUNNING'
        campaign.current_iteration = 10
        campaign.config = {'max_iterations': 50, 'time_budget_seconds': 300, 'max_candidates_per_iteration': 3}
        campaign.initial_params = {'ema_fast': 9, 'ema_slow': 21, 'rsi_filter': 30}
        campaign.initial_score = 30.0
        campaign.best_params = {'ema_fast': 12, 'ema_slow': 36, 'rsi_filter': 35}
        campaign.best_score = 45.0
        campaign.best_metrics = {'win_rate_pct': 55}
        campaign.celery_task_id = 'task-abc'
        campaign.error_message = None
        campaign.created_at = datetime.now(timezone.utc)
        campaign.completed_at = None

        with patch('app.api.routes.strategies.get_active_campaign', return_value=campaign):
            response = client.get('/api/v1/strategies/1/optimizer-campaign')

        assert response.status_code == 200
        data = response.json()
        assert data['id'] == 5
        assert data['status'] == 'RUNNING'
        assert data['current_iteration'] == 10
        assert data['max_iterations'] == 50
        assert data['best_score'] == 45.0

    def test_returns_404_when_no_campaign(self, client, mock_auth, mock_db, validated_strategy):
        """GET returns 404 when no campaign exists."""
        mock_db.get = MagicMock(return_value=validated_strategy)

        with patch('app.api.routes.strategies.get_active_campaign', return_value=None):
            response = client.get('/api/v1/strategies/1/optimizer-campaign')

        assert response.status_code == 404


class TestAcceptReject:
    """Tests for accept/reject endpoints."""

    def test_accept_on_non_completed_returns_409(self, client, mock_auth, mock_db):
        """POST /accept on non-COMPLETED campaign returns 409."""
        with patch('app.api.routes.strategies.accept_campaign', side_effect=ValueError('Cannot accept campaign in status RUNNING')):
            response = client.post('/api/v1/strategies/optimizer-campaign/1/accept')

        assert response.status_code == 409

    def test_reject_not_found_returns_404(self, client, mock_auth, mock_db):
        """POST /reject on non-existent campaign returns 404."""
        with patch('app.api.routes.strategies.reject_campaign', side_effect=ValueError('Campaign 999 not found')):
            response = client.post('/api/v1/strategies/optimizer-campaign/999/reject')

        assert response.status_code == 404


class TestCancelCampaign:
    """Tests for DELETE /optimizer-campaign/{id}."""

    def test_cancel_running_returns_204(self, client, mock_auth, mock_db):
        """DELETE on RUNNING campaign returns 204."""
        with patch('app.api.routes.strategies.cancel_campaign', return_value=MagicMock()):
            response = client.delete('/api/v1/strategies/optimizer-campaign/1')

        assert response.status_code == 204
