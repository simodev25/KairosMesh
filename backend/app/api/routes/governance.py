"""Governance API routes."""
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.security import Role, require_roles
from app.db.models.run import AnalysisRun
from app.db.models.user import User
from app.db.session import get_db
from app.services.governance.service import GovernanceService
from app.services.governance.settings_crud import get_governance_settings, update_governance_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix='/governance', tags=['governance'])

_VIEWER = Depends(require_roles(Role.SUPER_ADMIN, Role.ADMIN, Role.TRADER_OPERATOR, Role.ANALYST, Role.VIEWER))
_ANALYST = Depends(require_roles(Role.SUPER_ADMIN, Role.ADMIN, Role.TRADER_OPERATOR, Role.ANALYST))
_OPERATOR = Depends(require_roles(Role.SUPER_ADMIN, Role.ADMIN, Role.TRADER_OPERATOR))


class GovernanceSettingsUpdate(BaseModel):
    enabled: bool
    execution_mode: str = Field(pattern='^(auto|confirmation)$')
    analysis_depth: str = Field(pattern='^(light|full)$')
    interval_minutes: int = Field(ge=5, le=1440)


@router.get('/settings')
async def get_settings(db: Session = Depends(get_db), _: User = _VIEWER):
    return get_governance_settings(db)


@router.put('/settings')
async def put_settings(
    body: GovernanceSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = _OPERATOR,
):
    return update_governance_settings(
        db,
        enabled=body.enabled,
        execution_mode=body.execution_mode,
        analysis_depth=body.analysis_depth,
        interval_minutes=body.interval_minutes,
        actor=current_user.email,
    )


@router.get('/positions')
async def get_positions(db: Session = Depends(get_db), _: User = _VIEWER):
    """Return open positions enriched with their latest governance run decision."""
    service = GovernanceService()
    try:
        positions = await service._fetch_open_positions()
    except Exception as exc:
        logger.warning('governance_positions_fetch_failed: %s', exc)
        positions = []

    result = []
    for pos in positions:
        pos_id = str(pos.get('id', ''))
        latest_run = (
            db.query(AnalysisRun)
            .filter(
                AnalysisRun.run_type == 'governance',
                AnalysisRun.governance_position_id == pos_id,
            )
            .order_by(AnalysisRun.created_at.desc())
            .first()
        )
        result.append({
            **pos,
            'latest_governance_run': {
                'run_id': latest_run.id if latest_run else None,
                'status': latest_run.status if latest_run else None,
                'decision': latest_run.decision if latest_run else None,
                'created_at': latest_run.created_at.isoformat() if latest_run else None,
            },
        })

    return result


@router.get('/stream')
async def get_stream(db: Session = Depends(get_db), _: User = _VIEWER):
    """Return last 50 completed governance run decisions."""
    runs = (
        db.query(AnalysisRun)
        .filter(
            AnalysisRun.run_type == 'governance',
            AnalysisRun.status.in_(['completed', 'failed', 'cancelled']),
        )
        .order_by(AnalysisRun.updated_at.desc())
        .limit(50)
        .all()
    )
    return [
        {
            'run_id': r.id,
            'position_id': r.governance_position_id,
            'symbol': r.pair,
            'status': r.status,
            'decision': r.decision,
            'created_at': r.created_at.isoformat(),
            'updated_at': r.updated_at.isoformat(),
            'rejected': 'rejected_by' in (r.trace or {}),
        }
        for r in runs
    ]


@router.post('/reevaluate')
async def reevaluate_all(db: Session = Depends(get_db), current_user: User = _ANALYST):
    """Trigger governance analysis for all open positions."""
    settings = get_governance_settings(db)
    depth = settings.get('analysis_depth', 'light')
    service = GovernanceService()
    run_ids = await service.analyze_open_positions(
        db, depth=depth, system_user_id=current_user.id
    )
    return {'created_runs': len(run_ids), 'run_ids': run_ids}


@router.post('/reevaluate/{position_id}')
async def reevaluate_one(
    position_id: str,
    db: Session = Depends(get_db),
    current_user: User = _ANALYST,
):
    """Trigger governance analysis for a single position."""
    service = GovernanceService()
    if service._has_active_governance_run(db, position_id):
        raise HTTPException(status_code=409, detail='Governance run already in progress for this position')

    settings = get_governance_settings(db)

    positions = await service._fetch_open_positions()
    position = next((p for p in positions if str(p.get('id', '')) == position_id), None)
    if not position:
        raise HTTPException(status_code=404, detail=f'Position {position_id} not found')

    from app.tasks.governance_monitor_task import run_governance_task

    run = AnalysisRun(
        pair=position.get('symbol', 'UNKNOWN'),
        timeframe='H1',
        mode='paper',
        status='pending',
        progress=0,
        run_type='governance',
        governance_position_id=position_id,
        decision={},
        trace={
            'governance_position': position,
            'analysis_depth': settings.get('analysis_depth', 'light'),
        },
        created_by_id=current_user.id,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    run_governance_task.delay(run.id)

    return {'run_id': run.id, 'position_id': position_id}


@router.post('/approve/{run_id}')
async def approve_action(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = _OPERATOR,
):
    """Execute the governance decision for a completed run (confirmation mode)."""
    service = GovernanceService()
    try:
        result = await service.approve_action(db, run_id=run_id, actor=current_user.email)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return result


@router.post('/reject/{run_id}')
async def reject_action(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = _OPERATOR,
):
    """Reject (cancel) a governance action."""
    service = GovernanceService()
    try:
        service.reject_action(db, run_id=run_id, actor=current_user.email)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {'status': 'rejected', 'run_id': run_id}
