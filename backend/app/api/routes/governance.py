"""Governance API — endpoints for position monitoring and approval workflow.

Endpoints:
  GET  /governance/recommendations     List recent governance run recommendations
  GET  /governance/recommendations/{id} Get a single governance run detail
  POST /governance/{id}/approve        Approve a pending governance recommendation
  POST /governance/{id}/reject         Reject a pending governance recommendation
  GET  /governance/config              Get governance configuration
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.security import Role, get_current_user, require_roles
from app.db.models.governance_run import GovernanceRun
from app.db.models.user import User
from app.db.session import get_db

router = APIRouter(prefix='/governance', tags=['governance'])
logger = logging.getLogger(__name__)


def _serialize_gov_run(r: GovernanceRun) -> dict[str, Any]:
    return {
        "id": r.id,
        "position_ticket": r.position_ticket,
        "symbol": r.symbol,
        "side": r.side,
        "origin_run_id": r.origin_run_id,
        "status": r.status,
        "action": r.action,
        "new_sl": r.new_sl,
        "new_tp": r.new_tp,
        "conviction": r.conviction,
        "urgency": r.urgency,
        "reasoning": r.reasoning,
        "requires_approval": r.requires_approval,
        "approval_status": r.approval_status,
        "approved_by": r.approved_by,
        "approved_at": r.approved_at.isoformat() if r.approved_at else None,
        "executed": r.executed,
        "executed_at": r.executed_at.isoformat() if r.executed_at else None,
        "execution_error": r.execution_error,
        "error": r.error,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }


@router.get('/recommendations')
def list_recommendations(
    limit: int = Query(default=50, ge=1, le=200),
    symbol: str | None = Query(default=None),
    status: str | None = Query(default=None),
    approval_status: str | None = Query(default=None),
    db: Session = Depends(get_db),
    _=Depends(require_roles(Role.SUPER_ADMIN, Role.ADMIN, Role.TRADER_OPERATOR, Role.ANALYST, Role.VIEWER)),
) -> list[dict]:
    """List recent governance recommendations, optionally filtered."""
    query = db.query(GovernanceRun).order_by(GovernanceRun.created_at.desc())
    if symbol:
        query = query.filter(GovernanceRun.symbol == symbol.upper().strip())
    if status:
        query = query.filter(GovernanceRun.status == status.lower().strip())
    if approval_status:
        query = query.filter(GovernanceRun.approval_status == approval_status.lower().strip())
    rows = query.limit(limit).all()
    return [_serialize_gov_run(r) for r in rows]


@router.get('/recommendations/{gov_run_id}')
def get_recommendation(
    gov_run_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_roles(Role.SUPER_ADMIN, Role.ADMIN, Role.TRADER_OPERATOR, Role.ANALYST, Role.VIEWER)),
) -> dict:
    """Get a single governance run with full trace."""
    run = db.query(GovernanceRun).filter(GovernanceRun.id == gov_run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail=f"GovernanceRun {gov_run_id} not found")
    result = _serialize_gov_run(run)
    result["trace"] = run.trace or {}
    return result


@router.post('/{gov_run_id}/approve')
def approve_recommendation(
    gov_run_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _=Depends(require_roles(Role.SUPER_ADMIN, Role.ADMIN, Role.TRADER_OPERATOR)),
) -> dict:
    """Approve a pending governance recommendation and queue its execution."""
    from app.tasks.governance_task import approve_and_execute_governance

    run = db.query(GovernanceRun).filter(GovernanceRun.id == gov_run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail=f"GovernanceRun {gov_run_id} not found")

    if run.status != "completed":
        raise HTTPException(
            status_code=409,
            detail=f"GovernanceRun is not completed (status={run.status}). Cannot approve.",
        )

    if run.approval_status not in ("pending", "rejected"):
        raise HTTPException(
            status_code=409,
            detail=f"GovernanceRun is already {run.approval_status}. Cannot approve again.",
        )

    if run.executed:
        raise HTTPException(status_code=409, detail="GovernanceRun already executed.")

    # Mark approved
    run.approval_status = "approved"
    run.approved_by = user.email
    run.approved_at = datetime.now(timezone.utc)
    run.updated_at = datetime.now(timezone.utc)
    try:
        db.add(run)
        db.commit()
    except Exception as exc:
        logger.error("approve_recommendation: DB commit failed: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to save approval")

    # Dispatch execution to Celery worker
    try:
        approve_and_execute_governance.delay(gov_run_id, user.email)
    except Exception as exc:
        logger.error("approve_recommendation: failed to dispatch execution task: %s", exc)
        # Don't fail the API call — approval is saved; execution can be retried

    logger.info("governance recommendation #%d approved by %s", gov_run_id, user.email)
    return {"approved": True, "gov_run_id": gov_run_id, "approved_by": user.email}


@router.post('/{gov_run_id}/reject')
def reject_recommendation(
    gov_run_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _=Depends(require_roles(Role.SUPER_ADMIN, Role.ADMIN, Role.TRADER_OPERATOR)),
) -> dict:
    """Reject a pending governance recommendation."""
    run = db.query(GovernanceRun).filter(GovernanceRun.id == gov_run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail=f"GovernanceRun {gov_run_id} not found")

    if run.approval_status == "approved" and run.executed:
        raise HTTPException(status_code=409, detail="Already approved and executed — cannot reject.")

    run.approval_status = "rejected"
    run.approved_by = user.email
    run.approved_at = datetime.now(timezone.utc)
    run.updated_at = datetime.now(timezone.utc)
    try:
        db.add(run)
        db.commit()
    except Exception as exc:
        logger.error("reject_recommendation: DB commit failed: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to save rejection")

    logger.info("governance recommendation #%d rejected by %s", gov_run_id, user.email)
    return {"rejected": True, "gov_run_id": gov_run_id, "rejected_by": user.email}


@router.post('/force')
def force_governance(
    _user: User = Depends(get_current_user),
    __=Depends(require_roles(Role.SUPER_ADMIN, Role.ADMIN, Role.TRADER_OPERATOR)),
) -> dict:
    """Manually trigger an immediate governance evaluation, bypassing timeframe cooldown."""
    from app.tasks.governance_task import force_governance_loop
    try:
        force_governance_loop.delay()
    except Exception as exc:
        logger.error("force_governance: failed to dispatch task: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to dispatch governance task")
    logger.info("governance force-triggered via API")
    return {"triggered": True}


@router.get('/config')
def get_governance_config(
    _=Depends(require_roles(Role.SUPER_ADMIN, Role.ADMIN, Role.TRADER_OPERATOR, Role.ANALYST, Role.VIEWER)),
) -> dict:
    """Return current governance configuration."""
    from app.core.config import get_settings
    settings = get_settings()
    return {
        "enabled": True,
        "loop_interval_seconds": 60,
        "supervised_mode": True,  # Always supervised — human approval required
        "paper_trading_enabled": settings.enable_paper_execution,
        "live_trading_enabled": settings.allow_live_trading,
        "actions_available": ["HOLD", "ADJUST_SL", "ADJUST_TP", "ADJUST_SL_TP", "CLOSE"],
        "approval_roles": ["super_admin", "admin", "trader_operator"],
    }
