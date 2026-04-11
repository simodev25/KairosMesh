"""Celery tasks for governance position monitoring.

Two tasks:
- check_all: periodic Beat task that triggers governance analysis for all open positions
- run_governance_task: per-run task that executes the governance pipeline for one run
"""
import logging

logger = logging.getLogger(__name__)

# Import celery_app lazily to avoid pulling the full task dependency chain
# (agentscope, etc.) when this module is imported in test environments.
try:
    from app.tasks.celery_app import celery_app as _celery_app, run_async
    _CELERY_AVAILABLE = True
except Exception:  # pragma: no cover
    import asyncio
    _CELERY_AVAILABLE = False
    _celery_app = None  # type: ignore[assignment]
    run_async = asyncio.run  # type: ignore[assignment]


def _check_all_impl() -> None:
    """Check all open positions and create governance runs for those without one."""
    from app.db.session import SessionLocal
    from app.services.governance.service import GovernanceService
    from app.services.governance.settings_crud import get_governance_settings
    from app.db.models.user import User

    db = SessionLocal()
    try:
        settings = get_governance_settings(db)
        if not settings.get('enabled', False):
            return

        system_user = db.query(User).filter(User.id == 1).first()
        system_user_id = system_user.id if system_user else 1

        depth = settings.get('analysis_depth', 'light')
        service = GovernanceService()
        run_ids = run_async(
            service.analyze_open_positions(db, depth=depth, system_user_id=system_user_id)
        )
        if run_ids:
            logger.info('governance_monitor_check created_runs=%d run_ids=%s', len(run_ids), run_ids)
    except Exception:
        logger.error('governance_monitor_check_failed', exc_info=True)
    finally:
        db.close()


def _run_governance_task_impl(run_id: int) -> None:
    """Execute the governance pipeline for a single governance run."""
    from app.db.session import SessionLocal
    from app.db.models.run import AnalysisRun
    from app.services.agentscope.registry import AgentScopeRegistry

    db = SessionLocal()
    try:
        run = db.query(AnalysisRun).filter(AnalysisRun.id == run_id).first()
        if not run:
            logger.error('governance_run_not_found run_id=%d', run_id)
            return

        registry = AgentScopeRegistry()
        run_async(
            registry.execute(
                db, run,
                pair=run.pair,
                timeframe=run.timeframe,
                risk_percent=1.0,
            )
        )
    except Exception:
        logger.error('governance_run_task_failed run_id=%d', run_id, exc_info=True)
    finally:
        db.close()


if _CELERY_AVAILABLE and _celery_app is not None:
    check_all = _celery_app.task(
        name='app.tasks.governance_monitor_task.check_all',
        soft_time_limit=120,
        time_limit=180,
    )(_check_all_impl)

    run_governance_task = _celery_app.task(
        name='app.tasks.governance_monitor_task.run_governance_task',
        soft_time_limit=300,
        time_limit=360,
    )(_run_governance_task_impl)
else:  # pragma: no cover - only in environments without Celery/agentscope
    check_all = _check_all_impl  # type: ignore[assignment]
    run_governance_task = _run_governance_task_impl  # type: ignore[assignment]
