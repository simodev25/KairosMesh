from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models.benchmark_attempt import BenchmarkAttempt
from app.db.models.benchmark_case import BenchmarkCase
from app.db.models.benchmark_fixture import BenchmarkFixture
from app.db.models.benchmark_run import BenchmarkRun
from app.db.models.user import User
from app.schemas.benchmark import BenchmarkRunCreateRequest
from app.services.benchmark.fixtures_service import compute_fixture_hash
from app.services.benchmark import runs_service
from app.services.benchmark.runs_service import create_run, get_run_results


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


def test_get_run_results_aggregates_scores_by_agent_and_overall() -> None:
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(bind=engine)

    fixture_id: int
    run_id: int

    with Session(engine) as db:
        user = User(email='benchmark-results@local.dev', hashed_password='x', role='admin', is_active=True)
        db.add(user)
        db.commit()
        db.refresh(user)

        fixture = BenchmarkFixture(
            name='fixture-results',
            agent_name='technical-analyst',
            version=1,
            hash='a' * 64,
            inputs={'symbol': 'EURUSD.PRO'},
            config={'llm_enabled': True},
            created_by_id=user.id,
        )
        db.add(fixture)
        db.commit()
        db.refresh(fixture)

        run = BenchmarkRun(
            fixture_id=fixture.id,
            fixture_hash=fixture.hash,
            model_spec={'provider': 'ollama', 'model_name': 'deepseek-v3.2', 'parameters': {}},
            scenario_type='single-agent',
            status='COMPLETED',
            repetitions=3,
            created_by_id=user.id,
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        run_id = int(run.id)
        fixture_id = int(fixture.id)

        case_a = BenchmarkCase(run_id=run.id, agent_name='technical-analyst', case_order=1)
        case_b = BenchmarkCase(run_id=run.id, agent_name='news-analyst', case_order=2)
        db.add(case_a)
        db.add(case_b)
        db.commit()
        db.refresh(case_a)
        db.refresh(case_b)

        db.add(
            BenchmarkAttempt(
                case_id=case_a.id,
                attempt_number=1,
                raw_output={'decision': 'buy'},
                schema_validity_score=1.0,
                completeness_score=0.9,
                tool_policy_compliance_score=1.0,
                reference_consistency_score=0.8,
                stability_score=0.7,
                aggregate_score=0.88,
                llm_calls_count=1,
            )
        )
        db.add(
            BenchmarkAttempt(
                case_id=case_a.id,
                attempt_number=2,
                raw_output={'decision': 'hold'},
                schema_validity_score=0.8,
                completeness_score=0.7,
                tool_policy_compliance_score=0.9,
                reference_consistency_score=0.6,
                stability_score=0.7,
                aggregate_score=0.74,
                llm_calls_count=1,
            )
        )
        db.add(
            BenchmarkAttempt(
                case_id=case_b.id,
                attempt_number=1,
                raw_output={'decision': 'sell'},
                schema_validity_score=0.6,
                completeness_score=0.8,
                tool_policy_compliance_score=1.0,
                reference_consistency_score=0.9,
                stability_score=0.5,
                aggregate_score=0.76,
                llm_calls_count=1,
            )
        )
        db.commit()

        results = get_run_results(db, run_id)

    assert results.run_id == run_id
    assert results.fixture_id == fixture_id
    assert results.status == 'COMPLETED'
    assert results.total_attempts == 3

    assert results.overall_scores.schema_validity == pytest.approx((1.0 + 0.8 + 0.6) / 3)
    assert results.overall_scores.completeness == pytest.approx((0.9 + 0.7 + 0.8) / 3)
    assert results.overall_scores.tool_policy == pytest.approx((1.0 + 0.9 + 1.0) / 3)
    assert results.overall_scores.reference_consistency == pytest.approx((0.8 + 0.6 + 0.9) / 3)
    assert results.overall_scores.stability == pytest.approx((0.7 + 0.7 + 0.5) / 3)
    assert results.overall_scores.overall == pytest.approx((0.88 + 0.74 + 0.76) / 3)

    by_agent = {row.agent_key: row for row in results.agent_results}
    assert set(by_agent.keys()) == {'technical-analyst', 'news-analyst'}

    tech = by_agent['technical-analyst']
    assert tech.attempts_count == 2
    assert tech.avg_scores.schema_validity == pytest.approx(0.9)
    assert tech.avg_scores.overall == pytest.approx(0.81)

    news = by_agent['news-analyst']
    assert news.attempts_count == 1
    assert news.avg_scores.schema_validity == pytest.approx(0.6)
    assert news.avg_scores.overall == pytest.approx(0.76)


def test_get_run_results_returns_zero_scores_when_no_attempts() -> None:
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(bind=engine)

    run_id: int

    with Session(engine) as db:
        user = User(email='benchmark-empty@local.dev', hashed_password='x', role='admin', is_active=True)
        db.add(user)
        db.commit()
        db.refresh(user)

        fixture = BenchmarkFixture(
            name='fixture-empty-results',
            agent_name='technical-analyst',
            version=1,
            hash='b' * 64,
            inputs={'symbol': 'EURUSD.PRO'},
            config={'llm_enabled': True},
            created_by_id=user.id,
        )
        db.add(fixture)
        db.commit()
        db.refresh(fixture)

        run = BenchmarkRun(
            fixture_id=fixture.id,
            fixture_hash=fixture.hash,
            model_spec={'provider': 'ollama', 'model_name': 'deepseek-v3.2', 'parameters': {}},
            scenario_type='single-agent',
            status='PENDING',
            repetitions=3,
            created_by_id=user.id,
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        run_id = int(run.id)

        results = get_run_results(db, run_id)

    assert results.run_id == run_id
    assert results.total_attempts == 0
    assert results.agent_results == []
    assert results.overall_scores.schema_validity == 0.0
    assert results.overall_scores.completeness == 0.0
    assert results.overall_scores.tool_policy == 0.0
    assert results.overall_scores.reference_consistency == 0.0
    assert results.overall_scores.stability == 0.0
    assert results.overall_scores.overall == 0.0
