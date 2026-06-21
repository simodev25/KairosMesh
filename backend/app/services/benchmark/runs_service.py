from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.db.models.benchmark_run import BenchmarkRun
from app.db.models.benchmark_fixture import BenchmarkFixture
from app.services.benchmark.constants import BenchmarkRunStatus
from app.tasks.benchmark_task import execute_benchmark_run


def create_run(
    db: Session,
    *,
    fixture: BenchmarkFixture,
    fixture_hash: str,
    model_spec: dict,
    scenario_type: str,
    repetitions: int,
    created_by_id: int,
    max_llm_calls: int | None = None,
    scoring_weights: dict | None = None,
    benchmark_queue: str = 'benchmark',
) -> BenchmarkRun:
    if fixture.is_deleted:
        raise HTTPException(status_code=404, detail='Benchmark fixture not found')
    if not fixture.is_active:
        raise HTTPException(status_code=422, detail='Benchmark fixture is inactive')
    if fixture.hash != fixture_hash:
        raise HTTPException(status_code=409, detail='fixture_hash mismatch with stored fixture hash')

    run = BenchmarkRun(
        fixture_id=fixture.id,
        fixture_hash=fixture_hash,
        model_spec=model_spec,
        scenario_type=scenario_type,
        status=BenchmarkRunStatus.PENDING,
        repetitions=repetitions,
        max_llm_calls=max_llm_calls,
        effective_scoring_weights=scoring_weights or fixture.default_scoring_weights,
        created_by_id=created_by_id,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    task = execute_benchmark_run.apply_async(args=[run.id], queue=benchmark_queue, ignore_result=True)
    run.celery_task_id = task.id
    db.commit()
    db.refresh(run)
    return run


def list_runs(
    db: Session,
    *,
    fixture_id: int | None = None,
    agent_name: str | None = None,
    provider: str | None = None,
    model_name: str | None = None,
    status: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    offset: int = 0,
    limit: int = 50,
) -> list[BenchmarkRun]:
    query = db.query(BenchmarkRun)
    if fixture_id is not None:
        query = query.filter(BenchmarkRun.fixture_id == fixture_id)
    if status:
        query = query.filter(BenchmarkRun.status == status)
    if date_from:
        query = query.filter(BenchmarkRun.created_at >= date_from)
    if date_to:
        query = query.filter(BenchmarkRun.created_at <= date_to)
    if agent_name:
        query = query.join(BenchmarkFixture, BenchmarkFixture.id == BenchmarkRun.fixture_id).filter(BenchmarkFixture.agent_name == agent_name)

    runs = query.order_by(BenchmarkRun.created_at.desc()).all()

    if provider:
        runs = [run for run in runs if str((run.model_spec or {}).get('provider', '')).lower() == provider.lower()]
    if model_name:
        runs = [run for run in runs if str((run.model_spec or {}).get('model_name', '')) == model_name]

    return runs[offset: offset + limit]


def get_run_or_404(db: Session, run_id: int) -> BenchmarkRun:
    run = db.get(BenchmarkRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail='Benchmark run not found')
    return run


def cancel_pending_run(db: Session, run: BenchmarkRun, *, revoke_fn) -> BenchmarkRun:
    if run.status != BenchmarkRunStatus.PENDING:
        raise HTTPException(status_code=422, detail='Only PENDING runs can be cancelled')

    if run.celery_task_id:
        revoke_fn(run.celery_task_id, terminate=True, signal='SIGTERM')

    run.status = BenchmarkRunStatus.CANCELLED
    run.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(run)
    return run
