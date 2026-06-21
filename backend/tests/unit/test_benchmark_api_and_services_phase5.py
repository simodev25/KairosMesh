from datetime import datetime, timezone

import pytest

from app.schemas.benchmark import BenchmarkRunCreateRequest
from app.services.benchmark.fixtures_service import compute_fixture_hash
from app.services.benchmark import runs_service
from app.services.benchmark.runs_service import create_run


class _FakeTaskResult:
    def __init__(self, task_id: str) -> None:
        self.id = task_id


class _FakeTaskDispatcher:
    def __init__(self) -> None:
        self.calls = []

    def apply_async(self, args=None, kwargs=None, queue=None, ignore_result=None):
        self.calls.append({'args': args, 'kwargs': kwargs, 'queue': queue, 'ignore_result': ignore_result})
        return _FakeTaskResult('task-123')


class _FakeDB:
    def __init__(self, fixture) -> None:
        self.fixture = fixture
        self.runs = []

    def add(self, obj):
        if getattr(obj, 'id', None) is None:
            obj.id = len(self.runs) + 1
        self.runs.append(obj)

    def commit(self):
        return None

    def refresh(self, _obj):
        return None


class _FixtureObj:
    def __init__(self) -> None:
        self.id = 10
        self.hash = compute_fixture_hash(agent_name='technical-analyst', inputs={'symbol': 'EURUSD.PRO'}, config={})
        self.is_active = True
        self.is_deleted = False
        self.default_scoring_weights = {'schema_validity_score': 0.2}


def test_runs_schema_accepts_contract_payload() -> None:
    payload = BenchmarkRunCreateRequest(
        fixture_id=10,
        fixture_hash='a' * 64,
        model_spec={'provider': 'openai', 'model_name': 'gpt-4o-mini', 'parameters': {'temperature': 0.0}},
        scenario_type='single-agent',
        repetitions=3,
        max_llm_calls=100,
    )
    assert payload.fixture_id == 10
    assert payload.model_spec.provider == 'openai'


def test_create_run_raises_409_on_fixture_hash_mismatch() -> None:
    fixture = _FixtureObj()
    db = _FakeDB(fixture)

    with pytest.raises(Exception) as exc_info:
        create_run(
            db,
            fixture=fixture,
            fixture_hash='b' * 64,
            model_spec={'provider': 'ollama', 'model_name': 'deepseek-v3.2', 'parameters': {}},
            scenario_type='single-agent',
            repetitions=3,
            created_by_id=1,
            benchmark_queue='benchmark',
        )

    assert getattr(exc_info.value, 'status_code', None) == 409


def test_create_run_sets_pending_and_enqueues_task(monkeypatch) -> None:
    fixture = _FixtureObj()
    db = _FakeDB(fixture)
    dispatcher = _FakeTaskDispatcher()

    monkeypatch.setattr(runs_service, 'execute_benchmark_run', dispatcher)

    run = create_run(
        db,
        fixture=fixture,
        fixture_hash=fixture.hash,
        model_spec={'provider': 'ollama', 'model_name': 'deepseek-v3.2', 'parameters': {}},
        scenario_type='single-agent',
        repetitions=3,
        created_by_id=1,
        benchmark_queue='benchmark',
    )

    assert run.status == 'PENDING'
    assert run.celery_task_id == 'task-123'
    assert len(dispatcher.calls) == 1
    assert dispatcher.calls[0]['queue'] == 'benchmark'
