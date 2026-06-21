import asyncio

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models.benchmark_fixture import BenchmarkFixture
from app.db.models.benchmark_run import BenchmarkRun
from app.db.models.user import User
from app.services.benchmark.constants import BenchmarkRunStatus
from app.services.benchmark.engine import BenchmarkEngine


class _FakeAgentMessage:
    def __init__(self, metadata: dict) -> None:
        self.metadata = metadata


def _build_user_and_fixture(db: Session) -> BenchmarkFixture:
    user = User(email='bench-engine@local.dev', hashed_password='x', role='admin', is_active=True)
    db.add(user)
    db.commit()
    db.refresh(user)

    fixture = BenchmarkFixture(
        name='fixture-engine',
        agent_name='technical-analyst',
        version=1,
        hash='f' * 64,
        inputs={'symbol': 'EURUSD.PRO', 'timeframe': 'H1', 'context': 'benchmark-context'},
        config={'llm_enabled': True},
        created_by_id=user.id,
    )
    db.add(fixture)
    db.commit()
    db.refresh(fixture)
    return fixture


def test_execute_run_single_agent_creates_expected_attempt_count(monkeypatch) -> None:
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(bind=engine)

    with Session(engine) as db:
        fixture = _build_user_and_fixture(db)
        run = BenchmarkRun(
            fixture_id=fixture.id,
            fixture_hash=fixture.hash,
            model_spec={'provider': 'ollama', 'model_name': 'deepseek-v3.2', 'parameters': {}},
            scenario_type='single-agent',
            status='PENDING',
            repetitions=3,
            created_by_id=fixture.created_by_id,
        )
        db.add(run)
        db.commit()
        db.refresh(run)

        async def _fake_build_agent(self, **kwargs):
            async def _agent(_context):
                return _FakeAgentMessage(
                    {
                        'structural_bias': 'bullish',
                        'local_momentum': 'bullish',
                        'setup_quality': 'medium',
                        'summary': 'ok',
                        'tradability': 'high',
                        'symbol': 'EURUSD.PRO',
                        'timeframe': 'H1',
                    }
                )

            return _agent

        monkeypatch.setattr(BenchmarkEngine, '_build_agent', _fake_build_agent)

        benchmark_engine = BenchmarkEngine()
        result_run = asyncio.run(benchmark_engine.execute_run(db, run))
        db.refresh(result_run)

        assert result_run.status == BenchmarkRunStatus.COMPLETED
        attempts_count = sum(len(case.attempts) for case in result_run.cases)
        assert attempts_count == 3


def test_execute_run_debate_bundle_skipped_when_llm_disabled(monkeypatch) -> None:
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(bind=engine)

    with Session(engine) as db:
        fixture = _build_user_and_fixture(db)
        fixture.config = {'llm_enabled': False}
        db.commit()
        db.refresh(fixture)

        run = BenchmarkRun(
            fixture_id=fixture.id,
            fixture_hash=fixture.hash,
            model_spec={'provider': 'ollama', 'model_name': 'deepseek-v3.2', 'parameters': {}},
            scenario_type='debate-bundle',
            status='PENDING',
            repetitions=2,
            created_by_id=fixture.created_by_id,
        )
        db.add(run)
        db.commit()
        db.refresh(run)

        async def _fake_build_agent(self, **kwargs):
            async def _agent(_context):
                return _FakeAgentMessage({'summary': 'debate'})

            return _agent

        monkeypatch.setattr(BenchmarkEngine, '_build_agent', _fake_build_agent)

        benchmark_engine = BenchmarkEngine()
        result_run = asyncio.run(benchmark_engine.execute_run(db, run))
        db.refresh(result_run)

        assert result_run.status == BenchmarkRunStatus.SKIPPED_DEBATE
        assert len(result_run.cases) == 0
