import asyncio

from app.db.models.run import AnalysisRun
from app.db.session import SessionLocal
from app.services.orchestrator.engine import ForexOrchestrator
from app.tasks.celery_app import celery_app


@celery_app.task(name='app.tasks.run_analysis_task.execute')
def execute(run_id: int, risk_percent: float, metaapi_account_ref: int | None = None) -> None:
    db = SessionLocal()
    try:
        run = db.get(AnalysisRun, run_id)
        if not run:
            return
        if metaapi_account_ref is None:
            metaapi_account_ref = int((run.trace or {}).get('requested_metaapi_account_ref', 0) or 0) or None
        orchestrator = ForexOrchestrator()
        asyncio.run(orchestrator.execute(db=db, run=run, risk_percent=risk_percent, metaapi_account_ref=metaapi_account_ref))
    finally:
        db.close()
