import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.governance.service import GovernanceService


def _make_position(pos_id='pos-123', symbol='BTCUSD'):
    return {
        'id': pos_id, 'symbol': symbol, 'type': 'POSITION_TYPE_BUY',
        'openPrice': 64200.0, 'currentPrice': 65115.0,
        'stopLoss': 63500.0, 'takeProfit': 67000.0,
        'unrealizedProfit': 915.0, 'volume': 0.01, 'time': '2026-04-10T10:00:00Z',
    }


@pytest.mark.asyncio
async def test_analyze_open_positions_skips_if_run_in_progress():
    service = GovernanceService()
    db = MagicMock()
    # Simulate existing in-progress run for pos-123
    db.query.return_value.filter.return_value.first.return_value = MagicMock()

    with patch.object(service, '_fetch_open_positions', new_callable=AsyncMock,
                      return_value=[_make_position('pos-123')]):
        run_ids = await service.analyze_open_positions(db, depth='light', system_user_id=1)

    assert run_ids == []  # skipped because run already in progress


@pytest.mark.asyncio
async def test_analyze_open_positions_creates_run_when_no_duplicate():
    service = GovernanceService()
    db = MagicMock()
    # No in-progress run
    db.query.return_value.filter.return_value.first.return_value = None
    mock_run = MagicMock(id=42)
    db.refresh = MagicMock()

    with patch.object(service, '_fetch_open_positions', new_callable=AsyncMock,
                      return_value=[_make_position('pos-456')]):
        with patch('app.services.governance.service.AnalysisRun', return_value=mock_run):
            with patch('app.services.governance.service.run_governance_task') as mock_task:
                run_ids = await service.analyze_open_positions(db, depth='light', system_user_id=1)

    assert 42 in run_ids
    mock_task.delay.assert_called_once()


@pytest.mark.asyncio
async def test_approve_action_calls_modify_position_for_adjust_sl():
    service = GovernanceService()
    db = MagicMock()
    mock_run = MagicMock()
    mock_run.governance_position_id = 'pos-123'
    mock_run.decision = {
        'action': 'ADJUST_SL', 'new_sl': 63500.0, 'new_tp': None,
        'reasoning': 'Breakeven', 'risk_score': 0.1, 'confidence': 0.9,
    }
    db.query.return_value.filter.return_value.first.return_value = mock_run

    with patch('app.services.governance.service.MetaApiClient') as MockClient:
        mock_client = AsyncMock()
        MockClient.return_value = mock_client
        mock_client.modify_position = AsyncMock(return_value={'executed': True})
        await service.approve_action(db, run_id=42, actor='admin@test.com')

    mock_client.modify_position.assert_called_once_with(
        position_id='pos-123', stop_loss=63500.0, take_profit=None
    )


@pytest.mark.asyncio
async def test_approve_action_calls_close_position_for_close():
    service = GovernanceService()
    db = MagicMock()
    mock_run = MagicMock()
    mock_run.governance_position_id = 'pos-123'
    mock_run.decision = {
        'action': 'CLOSE', 'new_sl': None, 'new_tp': None,
        'reasoning': 'Volatility', 'risk_score': 0.9, 'confidence': 0.7,
    }
    db.query.return_value.filter.return_value.first.return_value = mock_run

    with patch('app.services.governance.service.MetaApiClient') as MockClient:
        mock_client = AsyncMock()
        MockClient.return_value = mock_client
        mock_client.close_position = AsyncMock(return_value={'executed': True})
        await service.approve_action(db, run_id=42, actor='admin@test.com')

    mock_client.close_position.assert_called_once_with(position_id='pos-123')
