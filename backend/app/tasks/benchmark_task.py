import logging
from datetime import datetime, timezone

from app.core.config import get_settings
from app.db.models.benchmark_run import BenchmarkRun
from app.db.session import SessionLocal
from app.services.benchmark.constants import BenchmarkRunStatus
from app.services.benchmark.engine import BenchmarkEngine
from app.tasks.celery_app import celery_app


logger = logging.getLogger(__name__)
settings = get_settings()


@celery_app.task(
    name='app.tasks.benchmark_task.execute_benchmark_run',
    soft_time_limit=settings.celery_benchmark_soft_time_limit_seconds,
    time_limit=settings.celery_benchmark_time_limit_seconds,
)
def execute_benchmark_run(run_id: int) -> None:
    db = SessionLocal()
    try:
        run = db.get(BenchmarkRun, run_id)
        if not run:
            return
        if run.status in {BenchmarkRunStatus.COMPLETED, BenchmarkRunStatus.FAILED, BenchmarkRunStatus.CANCELLED, BenchmarkRunStatus.SKIPPED_DEBATE}:
            return

        run.status = BenchmarkRunStatus.RUNNING
        run.started_at = datetime.now(timezone.utc)
        run.error = None
        db.commit()
        db.refresh(run)

        engine = BenchmarkEngine()
        import asyncio

        result_run = asyncio.run(engine.execute_run(db, run))
        if result_run.status not in {BenchmarkRunStatus.COMPLETED, BenchmarkRunStatus.SKIPPED_DEBATE}:
            result_run.status = BenchmarkRunStatus.COMPLETED
        result_run.completed_at = datetime.now(timezone.utc)
        db.commit()
    except Exception as exc:
        logger.exception('benchmark task failed run_id=%s', run_id)
        db.rollback()
        run = db.get(BenchmarkRun, run_id)
        if run is not None:
            run.status = BenchmarkRunStatus.FAILED
            run.error = str(exc)
            run.completed_at = datetime.now(timezone.utc)
            db.commit()
    finally:
        db.close()
