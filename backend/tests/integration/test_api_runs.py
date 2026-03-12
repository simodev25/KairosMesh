
import os

from fastapi.testclient import TestClient

os.environ['DATABASE_URL'] = 'sqlite:///./test.db'

from app.main import app


async def _fake_execute(self, db, run, risk_percent, metaapi_account_ref=None):
    run.status = 'completed'
    run.decision = {'decision': 'HOLD', 'confidence': 0.5, 'risk': {'accepted': True, 'reasons': ['test'], 'suggested_volume': 0}}
    db.commit()
    db.refresh(run)
    return run


def test_login_and_create_run(monkeypatch) -> None:
    monkeypatch.setattr('app.services.orchestrator.engine.ForexOrchestrator.execute', _fake_execute)

    with TestClient(app) as client:
        login_resp = client.post('/api/v1/auth/login', json={'email': 'admin@local.dev', 'password': 'admin1234'})
        assert login_resp.status_code == 200
        token = login_resp.json()['access_token']

        run_resp = client.post(
            '/api/v1/runs?async_execution=false',
            json={'pair': 'EURUSD', 'timeframe': 'H1', 'mode': 'simulation', 'risk_percent': 1.0},
            headers={'Authorization': f'Bearer {token}'},
        )
        assert run_resp.status_code == 200
        payload = run_resp.json()
        assert payload['pair'] == 'EURUSD'
        assert payload['status'] == 'completed'

        list_resp = client.get('/api/v1/runs', headers={'Authorization': f'Bearer {token}'})
        assert list_resp.status_code == 200
        assert len(list_resp.json()) >= 1
