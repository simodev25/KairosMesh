import os

import pytest
from fastapi.testclient import TestClient

os.environ['DATABASE_URL'] = 'sqlite:///./test.db'

pytest.importorskip('agentscope')

from app.main import app


def test_scoped_trading_config_save_does_not_leak_to_other_profiles() -> None:
    with TestClient(app) as client:
        login_resp = client.post('/api/v1/auth/login', json={'email': 'admin@local.dev', 'password': 'admin1234'})
        assert login_resp.status_code == 200
        token = login_resp.json()['access_token']
        headers = {'Authorization': f'Bearer {token}'}

        save_resp = client.put(
            '/api/v1/connectors/trading-config?decision_mode=permissive&execution_mode=live',
            json={
                'gating': {
                    'min_combined_score': 0.13,
                    'min_confidence': 0.25,
                    'min_aligned_sources': 1,
                    'allow_technical_single_source_override': True,
                },
                'risk_limits': {
                    'max_risk_per_trade_pct': 0.5,
                    'max_open_risk_pct': 3.0,
                    'max_positions': 2,
                    'max_positions_per_symbol': 1,
                    'min_free_margin_pct': 55.0,
                },
                'sizing': {
                    'sl_atr_multiplier': 2.2,
                    'tp_atr_multiplier': 2.0,
                    'min_sl_distance_pct': 0.08,
                },
            },
            headers=headers,
        )
        assert save_resp.status_code == 200

        live_resp = client.get(
            '/api/v1/connectors/trading-config?decision_mode=permissive&execution_mode=live',
            headers=headers,
        )
        assert live_resp.status_code == 200
        live_values = live_resp.json()['values']
        assert live_values['risk_limits']['max_open_risk_pct'] == 3.0
        assert live_values['risk_limits']['max_positions'] == 2
        assert live_values['sizing']['sl_atr_multiplier'] == 2.2

        simulation_resp = client.get(
            '/api/v1/connectors/trading-config?decision_mode=balanced&execution_mode=simulation',
            headers=headers,
        )
        assert simulation_resp.status_code == 200
        simulation_values = simulation_resp.json()['values']
        assert simulation_values['risk_limits']['max_open_risk_pct'] == 15.0
        assert simulation_values['risk_limits']['max_positions'] == 10
        assert simulation_values['sizing']['sl_atr_multiplier'] == 1.5

        paper_resp = client.get(
            '/api/v1/connectors/trading-config?decision_mode=permissive&execution_mode=paper',
            headers=headers,
        )
        assert paper_resp.status_code == 200
        paper_values = paper_resp.json()['values']
        assert paper_values['risk_limits']['max_open_risk_pct'] == 8.0
        assert paper_values['risk_limits']['max_positions'] == 4
        assert paper_values['sizing']['sl_atr_multiplier'] == 1.2
