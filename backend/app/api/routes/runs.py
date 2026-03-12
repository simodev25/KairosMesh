from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import Role, get_current_user, require_roles
from app.db.models.metaapi_account import MetaApiAccount
from app.db.models.run import AnalysisRun
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.run import CreateRunRequest, RunDetailOut, RunOut
from app.services.orchestrator.engine import ForexOrchestrator
from app.tasks.run_analysis_task import execute as run_analysis_task

router = APIRouter(prefix='/runs', tags=['runs'])


@router.get('', response_model=list[RunOut])
def list_runs(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[RunOut]:
    runs = db.query(AnalysisRun).order_by(AnalysisRun.created_at.desc()).limit(limit).all()
    return [RunOut.model_validate(run) for run in runs]


@router.post('', response_model=RunOut)
async def create_run(
    payload: CreateRunRequest,
    async_execution: bool = Query(default=True),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.SUPER_ADMIN, Role.ADMIN, Role.TRADER_OPERATOR, Role.ANALYST)),
) -> RunOut:
    settings = get_settings()
    pair = payload.pair.upper()
    timeframe = payload.timeframe.upper()

    if pair not in settings.default_forex_pairs:
        raise HTTPException(status_code=400, detail=f'Unsupported pair {pair} for V1 scope')
    if timeframe not in settings.default_timeframes:
        raise HTTPException(status_code=400, detail=f'Unsupported timeframe {timeframe} for V1 scope')
    if payload.mode == 'live' and user.role not in {Role.SUPER_ADMIN, Role.ADMIN, Role.TRADER_OPERATOR}:
        raise HTTPException(status_code=403, detail='Live mode requires elevated trading role')
    if payload.metaapi_account_ref is not None:
        account = db.get(MetaApiAccount, payload.metaapi_account_ref)
        if not account or not account.enabled:
            raise HTTPException(status_code=400, detail='Invalid or disabled metaapi_account_ref')

    run = AnalysisRun(
        pair=pair,
        timeframe=timeframe,
        mode=payload.mode,
        status='pending',
        trace={'requested_metaapi_account_ref': payload.metaapi_account_ref},
        created_by_id=user.id,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    if async_execution:
        try:
            run_analysis_task.apply_async(
                args=[run.id, payload.risk_percent, payload.metaapi_account_ref],
                queue='analysis',
                ignore_result=True,
            )
            run.status = 'queued'
            db.commit()
            db.refresh(run)
            return RunOut.model_validate(run)
        except Exception:
            pass

    orchestrator = ForexOrchestrator()
    run = await orchestrator.execute(db, run, payload.risk_percent, metaapi_account_ref=payload.metaapi_account_ref)
    return RunOut.model_validate(run)


@router.get('/{run_id}', response_model=RunDetailOut)
def get_run(
    run_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> RunDetailOut:
    run = db.get(AnalysisRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail='Run not found')
    return RunDetailOut.model_validate(run)
