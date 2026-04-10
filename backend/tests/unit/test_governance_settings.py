import pytest
from unittest.mock import MagicMock, patch
from app.db.models.governance_settings import GovernanceSettings
from app.services.governance.settings_crud import get_governance_settings, update_governance_settings


def _mock_db_with_row(row):
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = row
    return db


def test_get_governance_settings_returns_defaults_when_no_row():
    db = _mock_db_with_row(None)
    result = get_governance_settings(db)
    assert result['enabled'] is False
    assert result['execution_mode'] == 'confirmation'
    assert result['analysis_depth'] == 'light'
    assert result['interval_minutes'] == 15


def test_get_governance_settings_returns_persisted_row():
    row = GovernanceSettings(
        id=1, enabled=True, execution_mode='auto',
        analysis_depth='full', interval_minutes=5,
    )
    db = _mock_db_with_row(row)
    result = get_governance_settings(db)
    assert result['enabled'] is True
    assert result['execution_mode'] == 'auto'
    assert result['analysis_depth'] == 'full'
    assert result['interval_minutes'] == 5


def test_update_governance_settings_creates_row_if_missing():
    db = _mock_db_with_row(None)
    update_governance_settings(db, enabled=True, execution_mode='auto',
                                analysis_depth='full', interval_minutes=10,
                                actor='test@example.com')
    db.add.assert_called_once()
    db.commit.assert_called_once()


def test_update_governance_settings_updates_existing_row():
    row = GovernanceSettings(id=1, enabled=False, execution_mode='confirmation',
                              analysis_depth='light', interval_minutes=15)
    db = _mock_db_with_row(row)
    update_governance_settings(db, enabled=True, execution_mode='auto',
                                analysis_depth='full', interval_minutes=5,
                                actor='admin@example.com')
    assert row.enabled is True
    assert row.execution_mode == 'auto'
    assert row.analysis_depth == 'full'
    assert row.interval_minutes == 5
    db.commit.assert_called_once()
