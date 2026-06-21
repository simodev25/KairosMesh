from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models.llm_call_log import LlmCallLog
from app.db.models.run import AnalysisRun
from app.db.models.user import User
from app.services.llm.base_llm_helpers import persist_llm_call_log
from app.services.llm.call_context import use_analysis_run_id


def test_persist_llm_call_log_propagates_analysis_run_id_from_context(monkeypatch) -> None:
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(bind=engine)

    with Session(engine) as db:
        user = User(email='trace@local.dev', hashed_password='x', role='admin', is_active=True)
        db.add(user)
        db.commit()
        db.refresh(user)

        analysis_run = AnalysisRun(
            pair='EURUSD.PRO',
            timeframe='H1',
            mode='simulation',
            status='running',
            progress=0,
            decision={},
            trace={},
            created_by_id=user.id,
        )
        db.add(analysis_run)
        db.commit()
        db.refresh(analysis_run)

        monkeypatch.setattr('app.services.llm.base_llm_helpers.SessionLocal', lambda: Session(engine))

        with use_analysis_run_id(int(analysis_run.id)):
            persist_llm_call_log(
                provider='openai',
                model='gpt-4o-mini',
                status='success',
                prompt_tokens=10,
                completion_tokens=5,
                cost_usd=0.01,
                latency_ms=123.4,
                error=None,
            )

    with Session(engine) as db:
        logs = db.query(LlmCallLog).all()
        assert len(logs) == 1
        assert logs[0].analysis_run_id == analysis_run.id
