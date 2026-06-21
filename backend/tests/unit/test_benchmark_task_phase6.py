from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models.benchmark_fixture import BenchmarkFixture
from app.db.models.benchmark_run import BenchmarkRun
from app.db.models.user import User
from app.services.benchmark.constants import BenchmarkRunStatus
from app.tasks import benchmark_task


def _seed_run(db: Session) -> int:
    user = User(email='bench-task@local.dev', hashed_password='x', role='admin', is_active=True)
    db.add(user)
    db.commit()
    db.refresh(user)

    fixture = BenchmarkFixture(
        name='fixture-task',
        agent_name='technical-analyst',
        version=1,
        hash='a' * 64,
        inputs={'symbol': 'EURUSD.PRO', 'timeframe': 'H1', 'context': 'task-context'},
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
        status=BenchmarkRunStatus.PENDING,
        repetitions=2,
        created_by_id=user.id,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return int(run.id)


def test_benchmark_task_transitions_to_completed(monkeypatch) -> None:
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(bind=engine)

    with Session(engine) as db:
        run_id = _seed_run(db)

    class _FakeEngine:
        async def execute_run(self, db, run):
            run.status = BenchmarkRunStatus.COMPLETED
            return run

    monkeypatch.setattr(benchmark_task, 'SessionLocal', lambda: Session(engine))
    monkeypatch.setattr(benchmark_task, 'BenchmarkEngine', _FakeEngine)

    benchmark_task.execute_benchmark_run(run_id)

    with Session(engine) as db:
        run = db.get(BenchmarkRun, run_id)
        assert run is not None
        assert run.status == BenchmarkRunStatus.COMPLETED


def test_benchmark_task_transitions_to_failed_on_exception(monkeypatch) -> None:
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(bind=engine)

    with Session(engine) as db:
        run_id = _seed_run(db)

    class _FailingEngine:
        async def execute_run(self, db, run):
            raise RuntimeError('boom')

    monkeypatch.setattr(benchmark_task, 'SessionLocal', lambda: Session(engine))
    monkeypatch.setattr(benchmark_task, 'BenchmarkEngine', _FailingEngine)

    benchmark_task.execute_benchmark_run(run_id)

    with Session(engine) as db:
        run = db.get(BenchmarkRun, run_id)
        assert run is not None
        assert run.status == BenchmarkRunStatus.FAILED
        assert 'boom' in (run.error or '')
