from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.core.security import Role, require_roles
from app.db.models.benchmark_fixture import BenchmarkFixture
from app.db.models.benchmark_case import BenchmarkCase
from app.db.models.benchmark_run import BenchmarkRun
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.benchmark import (
    BenchmarkFixtureCreateRequest,
    BenchmarkFixtureOut,
    BenchmarkFixturePatchRequest,
    BenchmarkRunCreateRequest,
    BenchmarkRunDetailOut,
    BenchmarkRunOut,
)
from app.services.benchmark.fixtures_service import (
    create_fixture,
    get_fixture_or_404,
    list_fixtures,
    patch_fixture_activation,
    soft_delete_fixture,
)
from app.services.benchmark.runs_service import cancel_pending_run, create_run, get_run_or_404, list_runs
from app.tasks.celery_app import celery_app


router = APIRouter(prefix='/benchmark', tags=['benchmark'])


@router.post('/fixtures', response_model=BenchmarkFixtureOut, status_code=201)
def create_benchmark_fixture(
    payload: BenchmarkFixtureCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.SUPER_ADMIN, Role.ADMIN)),
) -> BenchmarkFixtureOut:
    fixture = create_fixture(
        db,
        name=payload.name,
        agent_name=payload.agent_name,
        inputs=payload.inputs,
        config=payload.config,
        default_scoring_weights=payload.default_scoring_weights,
        created_by_id=user.id,
    )
    return BenchmarkFixtureOut.model_validate(fixture)


@router.get('/fixtures', response_model=list[BenchmarkFixtureOut])
def list_benchmark_fixtures(
    agent_name: str | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(Role.SUPER_ADMIN, Role.ADMIN, Role.ANALYST)),
) -> list[BenchmarkFixtureOut]:
    fixtures = list_fixtures(db, agent_name=agent_name, is_active=is_active, offset=offset, limit=limit)
    return [BenchmarkFixtureOut.model_validate(item) for item in fixtures]


@router.get('/fixtures/{fixture_id}', response_model=BenchmarkFixtureOut)
def get_benchmark_fixture(
    fixture_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(Role.SUPER_ADMIN, Role.ADMIN, Role.ANALYST)),
) -> BenchmarkFixtureOut:
    fixture = get_fixture_or_404(db, fixture_id)
    return BenchmarkFixtureOut.model_validate(fixture)


@router.patch('/fixtures/{fixture_id}', response_model=BenchmarkFixtureOut)
def patch_benchmark_fixture(
    fixture_id: int,
    payload: BenchmarkFixturePatchRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(Role.SUPER_ADMIN, Role.ADMIN)),
) -> BenchmarkFixtureOut:
    fixture = patch_fixture_activation(db, fixture_id, is_active=payload.is_active)
    return BenchmarkFixtureOut.model_validate(fixture)


@router.delete('/fixtures/{fixture_id}', status_code=204)
def delete_benchmark_fixture(
    fixture_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(Role.SUPER_ADMIN, Role.ADMIN)),
) -> None:
    soft_delete_fixture(db, fixture_id)


@router.post('/runs', response_model=BenchmarkRunOut, status_code=201)
def create_benchmark_run(
    payload: BenchmarkRunCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.SUPER_ADMIN, Role.ADMIN)),
) -> BenchmarkRunOut:
    fixture = get_fixture_or_404(db, payload.fixture_id)
    settings = get_settings()
    run = create_run(
        db,
        fixture=fixture,
        fixture_hash=payload.fixture_hash,
        model_spec=payload.model_spec.model_dump(),
        scenario_type=payload.scenario_type,
        repetitions=payload.repetitions,
        max_llm_calls=payload.max_llm_calls,
        scoring_weights=payload.scoring_weights,
        created_by_id=user.id,
        benchmark_queue=settings.celery_benchmark_queue,
    )
    return BenchmarkRunOut.model_validate(run)


@router.get('/runs', response_model=list[BenchmarkRunOut])
def list_benchmark_runs(
    fixture_id: int | None = Query(default=None),
    agent_name: str | None = Query(default=None),
    provider: str | None = Query(default=None),
    model_name: str | None = Query(default=None),
    status: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(Role.SUPER_ADMIN, Role.ADMIN, Role.ANALYST)),
) -> list[BenchmarkRunOut]:
    runs = list_runs(
        db,
        fixture_id=fixture_id,
        agent_name=agent_name,
        provider=provider,
        model_name=model_name,
        status=status,
        offset=offset,
        limit=limit,
    )
    return [BenchmarkRunOut.model_validate(run) for run in runs]


@router.get('/runs/{run_id}', response_model=BenchmarkRunDetailOut)
def get_benchmark_run(
    run_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(Role.SUPER_ADMIN, Role.ADMIN, Role.ANALYST)),
) -> BenchmarkRunDetailOut:
    run = (
        db.query(BenchmarkRun)
        .options(selectinload(BenchmarkRun.cases).selectinload(BenchmarkCase.attempts))
        .filter(BenchmarkRun.id == run_id)
        .first()
    )
    if run is None:
        raise HTTPException(status_code=404, detail='Benchmark run not found')
    return BenchmarkRunDetailOut.model_validate(run)


@router.delete('/runs/{run_id}', response_model=BenchmarkRunOut)
def cancel_benchmark_run(
    run_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(Role.SUPER_ADMIN, Role.ADMIN)),
) -> BenchmarkRunOut:
    run = get_run_or_404(db, run_id)
    run = cancel_pending_run(db, run, revoke_fn=celery_app.control.revoke)
    return BenchmarkRunOut.model_validate(run)
