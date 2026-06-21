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
        logger.info('benchmark run_id=%s task started', run_id)
        run = db.get(BenchmarkRun, run_id)
        if not run:
            logger.warning('benchmark run_id=%s task aborted reason=run_not_found', run_id)
            return
        if run.status in {BenchmarkRunStatus.COMPLETED, BenchmarkRunStatus.FAILED, BenchmarkRunStatus.CANCELLED, BenchmarkRunStatus.SKIPPED_DEBATE}:
            logger.info('benchmark run_id=%s task skipped status=%s', run_id, run.status)
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
        logger.info('benchmark run_id=%s task completed final_status=%s', run_id, result_run.status)
    except Exception as exc:
        logger.error('benchmark run_id=%s task failed with exception=%s', run_id, exc, exc_info=True)
        db.rollback()
        run = db.get(BenchmarkRun, run_id)
        if run is not None:
            run.status = BenchmarkRunStatus.FAILED
            run.error = str(exc)
            run.completed_at = datetime.now(timezone.utc)
            db.commit()
            logger.info('benchmark run_id=%s task finalized after error final_status=%s', run_id, run.status)
        else:
            logger.warning('benchmark run_id=%s task failed and run could not be reloaded for final status update', run_id)
    finally:
        db.close()
