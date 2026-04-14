"""Celery Beat task — governance loop for open position monitoring.

Runs every 60 seconds. For each open position fetched from MetaAPI:
1. Creates a GovernanceRun DB record.
2. Builds PositionHistoryContext (origin run, candles, MFE/MAE, history).
3. Runs GovernanceRegistry pipeline (Phase 1 analysts + governance trader).
4. Persists the decision. If auto-execution is enabled and action != HOLD,
   immediately executes the modification/close via MetaAPI.

Supervised mode (default): the decision is persisted with
``approval_status='pending'`` — a human must approve it before execution.

Auto-execution mode: set ``requires_approval=False`` on the GovernanceRun
(controlled by governance settings in DB or config flag).
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from app.tasks.celery_app import celery_app
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)

_LOCK_TTL_SECONDS = 240  # Match soft_time_limit — prevents Beat from spawning a second run

# Minimum interval between governance evaluations per timeframe.
# The Beat fires every 60s, but each position is only re-evaluated once its
# timeframe candle has closed (M5 position → evaluate every 5 min, H1 → every hour).
_TIMEFRAME_COOLDOWN: dict[str, int] = {
    'M1': 60, 'M2': 120, 'M3': 180, 'M4': 240, 'M5': 300,
    'M10': 600, 'M15': 900, 'M30': 1800,
    'H1': 3600, 'H2': 7200, 'H3': 10800, 'H4': 14400,
    'H6': 21600, 'H8': 28800, 'H12': 43200,
    'D1': 86400, 'W1': 604800,
}
_DEFAULT_COOLDOWN = 300  # fallback when timeframe unknown


def _acquire_governance_lock() -> bool:
    """Acquire a Redis lock to prevent parallel governance executions."""
    try:
        import redis
        from app.core.config import get_settings
        r = redis.from_url(get_settings().redis_url)
        return bool(r.set("governance_loop_lock", "1", nx=True, ex=_LOCK_TTL_SECONDS))
    except Exception:
        return True  # Proceed if Redis is unavailable


@celery_app.task(
    name='app.tasks.governance_task.run_governance_loop',
    soft_time_limit=240,
    time_limit=250,
)
def run_governance_loop() -> None:
    """Main governance Beat task — evaluates all open positions."""
    if not _acquire_governance_lock():
        logger.debug("governance_loop skipped: another worker is already running it")
        return

    db = SessionLocal()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_async_governance_loop(db))
    except Exception as exc:
        logger.error("governance_loop failed: %s", exc, exc_info=True)
    finally:
        # Cancel all pending async tasks before closing the loop to avoid
        # "Event loop is closed" errors from httpx clients (triggered when
        # SoftTimeLimitExceeded interrupts asyncio.run mid-flight).
        try:
            pending = asyncio.all_tasks(loop)
            if pending:
                for task in pending:
                    task.cancel()
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        except Exception:
            pass
        finally:
            loop.close()
        db.close()


@celery_app.task(
    name='app.tasks.governance_task.force_governance_loop',
    soft_time_limit=240,
    time_limit=250,
)
def force_governance_loop() -> None:
    """Manually triggered governance evaluation — bypasses timeframe cooldown."""
    logger.info("governance_loop: forced evaluation triggered via API")
    db = SessionLocal()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_async_governance_loop(db, force=True))
    except Exception as exc:
        logger.error("governance_loop (forced) failed: %s", exc, exc_info=True)
    finally:
        try:
            pending = asyncio.all_tasks(loop)
            if pending:
                for task in pending:
                    task.cancel()
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        except Exception:
            pass
        finally:
            loop.close()
        db.close()


async def _async_governance_loop(db: Any, force: bool = False) -> None:
    """Async inner loop — can use await for MetaAPI and pipeline calls."""
    from app.core.config import get_settings
    from app.services.trading.metaapi_client import MetaApiClient
    from app.services.trading.account_selector import MetaApiAccountSelector

    settings = get_settings()

    # Only run in paper or live mode — governance on live positions
    if not (settings.enable_paper_execution or settings.allow_live_trading):
        logger.debug("governance_loop: no paper/live trading enabled, skipping")
        return

    # Resolve account
    account = MetaApiAccountSelector().resolve(db, None)
    account_id = str(account.account_id) if account else None
    region = (account.region if account else None) or settings.metaapi_region

    if not account_id:
        logger.debug("governance_loop: no MetaAPI account configured, skipping")
        return

    # Fetch open positions
    client = MetaApiClient()
    try:
        pos_result = await client.get_positions(account_id=account_id, region=region)
    except Exception as exc:
        logger.warning("governance_loop: get_positions failed: %s", exc)
        return

    if pos_result.get("degraded"):
        logger.warning("governance_loop: positions degraded: %s", pos_result.get("reason"))
        return

    positions = pos_result.get("positions", [])
    if not positions:
        logger.debug("governance_loop: no open positions to evaluate")
        return

    logger.info("governance_loop: evaluating %d open positions", len(positions))

    # Process positions sequentially (each runs a full LLM pipeline — don't parallel)
    for raw_pos in positions:
        try:
            await _evaluate_position(db, raw_pos, account_id=account_id, region=region, force=force)
        except Exception as exc:
            ticket = raw_pos.get("id", "?")
            logger.error("governance_loop: failed to evaluate position ticket=%s: %s", ticket, exc, exc_info=True)


async def _evaluate_position(
    db: Any,
    raw_pos: dict,
    *,
    account_id: str | None,
    region: str | None,
    force: bool = False,
) -> None:
    """Evaluate a single open position through the governance pipeline."""
    from app.db.models.governance_run import GovernanceRun
    from app.services.governance.position_context_builder import PositionContextBuilder, PositionHistoryContext
    from app.services.governance.registry import GovernanceRegistry
    from app.services.risk.portfolio_state import OpenPosition

    ticket = str(raw_pos.get("id") or raw_pos.get("positionId") or "")
    symbol = str(raw_pos.get("symbol") or "")
    side = "BUY" if str(raw_pos.get("type", "")).upper() in ("POSITION_TYPE_BUY", "BUY") else "SELL"

    if not ticket or not symbol:
        logger.warning("governance_loop: skipping position with missing ticket/symbol: %s", raw_pos)
        return

    # Check if we already have a RECENT pending/running run for this ticket.
    # Stale runs (> 3 min old) are marked failed and not considered blockers —
    # this prevents starvation if a previous run was killed mid-execution.
    try:
        from datetime import timedelta
        stale_threshold = datetime.now(timezone.utc) - timedelta(minutes=3)
        recent = (
            db.query(GovernanceRun)
            .filter(GovernanceRun.position_ticket == ticket)
            .filter(GovernanceRun.status.in_(["running", "pending"]))
            .filter(GovernanceRun.created_at > stale_threshold)
            .first()
        )
        if recent:
            logger.debug("governance_loop: position ticket=%s has a fresh pending/running run, skipping", ticket)
            return
        # Mark any older stale pending/running runs as failed so they don't linger
        stale_runs = (
            db.query(GovernanceRun)
            .filter(GovernanceRun.position_ticket == ticket)
            .filter(GovernanceRun.status.in_(["running", "pending"]))
            .filter(GovernanceRun.created_at <= stale_threshold)
            .all()
        )
        for stale in stale_runs:
            stale.status = "failed"
            stale.error = "stale: killed before pipeline completed"
            stale.updated_at = datetime.now(timezone.utc)
            db.add(stale)
        if stale_runs:
            db.commit()
            logger.info("governance_loop: marked %d stale run(s) as failed for ticket=%s", len(stale_runs), ticket)
    except Exception:
        pass

    # Timeframe cooldown: skip if the last completed run is too recent for this position's timeframe.
    # Bypassed when force=True (manual trigger from API).
    # The last completed run carries origin_run.timeframe via the ORM relationship.
    if force:
        logger.info("governance_loop: forced evaluation for ticket=%s, skipping cooldown", ticket)
    try:
        last_completed = (
            db.query(GovernanceRun)
            .filter(GovernanceRun.position_ticket == ticket)
            .filter(GovernanceRun.status == "completed")
            .order_by(GovernanceRun.created_at.desc())
            .first()
        )
        if last_completed is not None:
            tf: str | None = None
            try:
                if last_completed.origin_run is not None:
                    tf = str(last_completed.origin_run.timeframe or "")
            except Exception:
                pass
            cooldown = _TIMEFRAME_COOLDOWN.get((tf or "").upper().strip(), _DEFAULT_COOLDOWN)
            lc_ts = last_completed.created_at
            if lc_ts.tzinfo is None:
                lc_ts = lc_ts.replace(tzinfo=timezone.utc)
            elapsed = (datetime.now(timezone.utc) - lc_ts).total_seconds()
            if elapsed < cooldown and not force:
                logger.debug(
                    "governance_loop: skipping ticket=%s tf=%s cooldown=%ds elapsed=%ds",
                    ticket, tf or "?", cooldown, int(elapsed),
                )
                return
    except Exception:
        pass

    # Build OpenPosition dataclass from raw MetaAPI position
    raw_open_time = raw_pos.get("time") or raw_pos.get("openTime")
    open_time_iso: str | None = None
    if raw_open_time:
        try:
            if isinstance(raw_open_time, str):
                open_time_iso = raw_open_time
            elif isinstance(raw_open_time, (int, float)):
                open_time_iso = datetime.fromtimestamp(raw_open_time / 1000, tz=timezone.utc).isoformat()
        except Exception:
            pass

    position = OpenPosition(
        symbol=symbol,
        side=side,
        volume=float(raw_pos.get("volume", 0)),
        entry_price=float(raw_pos.get("openPrice", 0)),
        current_price=float(raw_pos.get("currentPrice", 0)),
        unrealized_pnl=float(raw_pos.get("profit", 0)),
        stop_loss=float(raw_pos.get("stopLoss", 0)) or None,
        take_profit=float(raw_pos.get("takeProfit", 0)) or None,
        ticket=ticket,
        open_time=open_time_iso,
    )

    # Create GovernanceRun record
    gov_run = GovernanceRun(
        position_ticket=ticket,
        symbol=symbol,
        side=side,
        status="pending",
        requires_approval=True,  # Supervised mode by default
        approval_status="pending",
        executed=False,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    try:
        db.add(gov_run)
        db.commit()
        db.refresh(gov_run)
    except Exception as exc:
        logger.error("governance_loop: failed to create GovernanceRun ticket=%s: %s", ticket, exc)
        try:
            db.rollback()
        except Exception:
            pass
        return

    # Build position history context
    try:
        ctx = await PositionContextBuilder().build(
            position, db, account_id=account_id, region=region,
        )
    except Exception as exc:
        logger.warning("governance_loop: PositionContextBuilder failed ticket=%s: %s", ticket, exc)
        ctx = PositionHistoryContext(
            ticket=ticket, symbol=symbol, side=side,
            volume=position.volume, entry_price=position.entry_price,
            current_price=position.current_price, unrealized_pnl=position.unrealized_pnl,
            stop_loss=position.stop_loss, take_profit=position.take_profit,
            open_time=open_time_iso, degraded=True,
            degraded_reasons=[f"context_build_failed: {exc}"],
        )

    # Link to origin run if context resolved it
    if ctx.origin_run_id is not None:
        try:
            gov_run.origin_run_id = ctx.origin_run_id
            db.add(gov_run)
            db.commit()
        except Exception:
            pass

    # Run governance pipeline
    registry = GovernanceRegistry()
    result = await registry.execute(
        db, gov_run, ctx,
        account_id=account_id,
        region=region,
    )

    logger.info(
        "governance_loop: ticket=%s symbol=%s action=%s conviction=%.2f urgency=%s",
        ticket, symbol,
        result.get("action", "HOLD"),
        result.get("conviction", 0.0),
        result.get("urgency", "low"),
    )

    # Auto-execution: if requires_approval=False, execute immediately
    # Currently always supervised — execution happens via API approval endpoint
    # (auto-execution can be enabled by setting gov_run.requires_approval=False above)


@celery_app.task(
    name='app.tasks.governance_task.approve_and_execute_governance',
    soft_time_limit=90,
    time_limit=110,
)
def approve_and_execute_governance(gov_run_id: int, approved_by: str) -> dict:
    """Execute a pre-approved governance action against the broker.

    Called by the API endpoint POST /governance/{id}/approve.
    Runs in a Celery worker so the API call returns immediately.
    """
    db = SessionLocal()
    try:
        return asyncio.run(_async_execute_governance(db, gov_run_id, approved_by))
    except Exception as exc:
        logger.error("approve_and_execute_governance failed run_id=%s: %s", gov_run_id, exc, exc_info=True)
        return {"error": str(exc)}
    finally:
        db.close()


async def _async_execute_governance(db: Any, gov_run_id: int, approved_by: str) -> dict:
    """Execute the governance action for an approved GovernanceRun."""
    from datetime import datetime, timezone
    from app.db.models.governance_run import GovernanceRun
    from app.services.trading.metaapi_client import MetaApiClient
    from app.services.trading.account_selector import MetaApiAccountSelector
    from app.core.config import get_settings

    gov_run = db.query(GovernanceRun).filter(GovernanceRun.id == gov_run_id).first()
    if not gov_run:
        return {"error": f"GovernanceRun {gov_run_id} not found"}

    if gov_run.executed:
        return {"error": "Already executed", "gov_run_id": gov_run_id}

    if gov_run.approval_status != "approved":
        return {"error": "Not approved", "gov_run_id": gov_run_id}

    action = str(gov_run.action or "HOLD").upper()
    if action == "HOLD":
        gov_run.executed = True
        gov_run.executed_at = datetime.now(timezone.utc)
        db.add(gov_run)
        db.commit()
        return {"executed": True, "action": "HOLD", "note": "HOLD requires no broker action"}

    settings = get_settings()
    account = MetaApiAccountSelector().resolve(db, None)
    account_id = str(account.account_id) if account else None
    region = (account.region if account else None) or settings.metaapi_region

    client = MetaApiClient()
    result: dict = {}

    try:
        if action == "CLOSE":
            result = await client.close_position(
                position_id=gov_run.position_ticket,
                symbol=gov_run.symbol,
                account_id=account_id,
                region=region,
            )
        elif action in ("ADJUST_SL", "ADJUST_TP", "ADJUST_SL_TP"):
            result = await client.modify_position(
                position_id=gov_run.position_ticket,
                stop_loss=gov_run.new_sl,
                take_profit=gov_run.new_tp,
                account_id=account_id,
                region=region,
            )

        if result.get("executed"):
            gov_run.executed = True
            gov_run.executed_at = datetime.now(timezone.utc)
        else:
            gov_run.execution_error = str(result.get("reason") or result.get("error") or "Unknown broker error")

    except Exception as exc:
        gov_run.execution_error = str(exc)[:500]
        logger.error("governance execution failed gov_run_id=%s: %s", gov_run_id, exc, exc_info=True)

    gov_run.updated_at = datetime.now(timezone.utc)
    db.add(gov_run)
    try:
        db.commit()
    except Exception as exc:
        logger.error("governance commit failed: %s", exc)
        try:
            db.rollback()
        except Exception:
            pass

    return {
        "executed": gov_run.executed,
        "action": action,
        "execution_error": gov_run.execution_error,
        "broker_result": result,
    }
