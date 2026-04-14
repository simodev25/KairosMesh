"""PositionContextBuilder — assembles historical context for the governance pipeline.

For each open position the governance Celery task needs to evaluate, this service
builds a rich `PositionHistoryContext` that is injected as `base_vars` into the
governance agents so they understand:

  1. How the position was originally opened (original run reasoning, agent summaries).
  2. How price has evolved since entry (candles, MFE, MAE).
  3. What the previous governance evaluations decided.

Design constraints
------------------
- Fully async: all DB queries and external calls are awaited.
- Graceful degradation: every external dependency can fail individually; the
  context is marked `degraded=True` but still returned so the pipeline can
  proceed with reduced context rather than failing entirely.
- No side effects: this is a read-only service.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# Number of previous governance runs to inject as history.
_GOVERNANCE_HISTORY_LIMIT = 5

# Timeframe used to fetch candles since entry.
# H1 gives a readable picture without too many candles for short positions.
_CANDLE_TIMEFRAME = "1h"

# Maximum candles to fetch (caps API calls for very old positions).
_MAX_CANDLES = 200


@dataclass
class PositionHistoryContext:
    """Full historical context for a single open position.

    Injected as ``base_vars`` into governance agents so every agent in the
    pipeline shares the same position narrative without needing to re-query.
    """

    # ── Position snapshot ───────────────────────────────────────────────────
    ticket: str
    symbol: str
    side: str
    volume: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    stop_loss: float | None
    take_profit: float | None
    open_time: str | None  # ISO-8601 UTC

    # ── Original run linkage ────────────────────────────────────────────────
    origin_run_id: int | None = None
    origin_pair: str | None = None
    origin_timeframe: str | None = None
    # Structured decision dict from AnalysisRun.decision
    origin_decision: dict[str, Any] = field(default_factory=dict)
    # Trader agent reasoning extracted from AgentStep output
    origin_trader_reasoning: str | None = None

    # ── Phase-1 analyst summaries from the origin run ───────────────────────
    origin_technical_summary: str | None = None
    origin_news_summary: str | None = None
    origin_market_context_summary: str | None = None

    # ── Price evolution since entry ──────────────────────────────────────────
    candles_since_entry: list[dict[str, Any]] = field(default_factory=list)
    bars_since_entry: int = 0
    # Max Favorable / Adverse Excursion as % of entry price
    mfe_pct: float = 0.0
    mae_pct: float = 0.0

    # ── Governance history ───────────────────────────────────────────────────
    previous_governance_runs: list[dict[str, Any]] = field(default_factory=list)

    # ── Meta ─────────────────────────────────────────────────────────────────
    degraded: bool = False
    degraded_reasons: list[str] = field(default_factory=list)

    def to_prompt_dict(self) -> dict[str, Any]:
        """Serialize context to a flat dict suitable for prompt template injection."""
        prev_govs = []
        for g in self.previous_governance_runs:
            prev_govs.append(
                f"[{g.get('created_at', '?')}] action={g.get('action', '?')} "
                f"urgency={g.get('urgency', '?')} conviction={g.get('conviction', '?')} "
                f"reasoning={str(g.get('reasoning', ''))[:200]}"
            )
        return {
            "position_ticket": self.ticket,
            "position_symbol": self.symbol,
            "position_side": self.side,
            "position_volume": self.volume,
            "position_entry_price": self.entry_price,
            "position_current_price": self.current_price,
            "position_unrealized_pnl": self.unrealized_pnl,
            "position_stop_loss": self.stop_loss,
            "position_take_profit": self.take_profit,
            "position_open_time": self.open_time or "unknown",
            "origin_run_id": self.origin_run_id,
            "origin_pair": self.origin_pair or self.symbol,
            "origin_timeframe": self.origin_timeframe or "unknown",
            "origin_decision": self.origin_decision,
            "origin_trader_reasoning": self.origin_trader_reasoning or "Not available",
            "origin_technical_summary": self.origin_technical_summary or "Not available",
            "origin_news_summary": self.origin_news_summary or "Not available",
            "origin_market_context_summary": self.origin_market_context_summary or "Not available",
            "bars_since_entry": self.bars_since_entry,
            "mfe_pct": round(self.mfe_pct, 3),
            "mae_pct": round(self.mae_pct, 3),
            "candles_count": len(self.candles_since_entry),
            "recent_candles": self.candles_since_entry[-10:] if self.candles_since_entry else [],
            "previous_governance_runs_summary": "\n".join(prev_govs) if prev_govs else "None — first evaluation.",
            "governance_history_count": len(self.previous_governance_runs),
        }


class PositionContextBuilder:
    """Assembles a :class:`PositionHistoryContext` for a single open position.

    Usage::

        from sqlalchemy.orm import Session
        ctx = await PositionContextBuilder().build(position, db)
        prompt_vars = ctx.to_prompt_dict()
    """

    # ── Public API ──────────────────────────────────────────────────────────

    async def build(
        self,
        position: Any,  # OpenPosition dataclass
        db: Any,        # SQLAlchemy Session
        *,
        account_id: str | None = None,
        region: str | None = None,
    ) -> PositionHistoryContext:
        """Build and return a :class:`PositionHistoryContext` for *position*.

        Each sub-step is wrapped in its own try/except so a single failure
        (e.g. MetaAPI candles unavailable) does not abort the entire context.
        """
        degraded_reasons: list[str] = []

        ctx = PositionHistoryContext(
            ticket=str(position.ticket or ""),
            symbol=str(position.symbol or ""),
            side=str(position.side or ""),
            volume=float(position.volume or 0),
            entry_price=float(position.entry_price or 0),
            current_price=float(position.current_price or 0),
            unrealized_pnl=float(position.unrealized_pnl or 0),
            stop_loss=position.stop_loss,
            take_profit=position.take_profit,
            open_time=getattr(position, "open_time", None),
        )

        # 1. Find origin run via ExecutionOrder.metaapi_position_id
        origin_run = None
        if ctx.ticket:
            try:
                origin_run = self._find_origin_run(db, ctx.ticket)
            except Exception as exc:
                degraded_reasons.append(f"origin_run_lookup_failed: {exc}")
                logger.warning("PositionContextBuilder: origin_run lookup failed ticket=%s: %s", ctx.ticket, exc)

        if origin_run is not None:
            ctx.origin_run_id = origin_run.id
            ctx.origin_pair = origin_run.pair
            ctx.origin_timeframe = origin_run.timeframe
            ctx.origin_decision = origin_run.decision or {}

            # 2. Extract Phase-1 + trader summaries from AgentStep records
            try:
                self._extract_agent_summaries(db, ctx, origin_run.id)
            except Exception as exc:
                degraded_reasons.append(f"agent_summaries_failed: {exc}")
                logger.warning("PositionContextBuilder: agent summaries failed run_id=%s: %s", origin_run.id, exc)

        # 3. Fetch candles since entry
        if ctx.open_time:
            try:
                candles = await self._fetch_candles_since_entry(
                    ctx.symbol,
                    ctx.open_time,
                    account_id=account_id,
                    region=region,
                )
                ctx.candles_since_entry = candles
                ctx.bars_since_entry = len(candles)
                if candles and ctx.entry_price > 0:
                    ctx.mfe_pct, ctx.mae_pct = self._compute_mfe_mae(
                        candles, ctx.entry_price, ctx.side
                    )
            except Exception as exc:
                degraded_reasons.append(f"candles_fetch_failed: {exc}")
                logger.warning(
                    "PositionContextBuilder: candle fetch failed symbol=%s open_time=%s: %s",
                    ctx.symbol, ctx.open_time, exc,
                )
        else:
            degraded_reasons.append("open_time_missing_candles_skipped")

        # 4. Previous governance runs
        if ctx.ticket:
            try:
                ctx.previous_governance_runs = self._fetch_governance_history(db, ctx.ticket)
            except Exception as exc:
                degraded_reasons.append(f"governance_history_failed: {exc}")
                logger.warning("PositionContextBuilder: governance history failed ticket=%s: %s", ctx.ticket, exc)

        ctx.degraded = len(degraded_reasons) > 0
        ctx.degraded_reasons = degraded_reasons
        return ctx

    # ── Private helpers ─────────────────────────────────────────────────────

    @staticmethod
    def _find_origin_run(db: Any, ticket: str) -> Any | None:
        """Resolve the AnalysisRun that opened the position via ExecutionOrder linkage."""
        from app.db.models.execution_order import ExecutionOrder
        from app.db.models.run import AnalysisRun

        order = (
            db.query(ExecutionOrder)
            .filter(ExecutionOrder.metaapi_position_id == ticket)
            .order_by(ExecutionOrder.id.desc())
            .first()
        )
        if order is None or order.run_id is None:
            return None
        return db.query(AnalysisRun).filter(AnalysisRun.id == order.run_id).first()

    @staticmethod
    def _extract_agent_summaries(db: Any, ctx: PositionHistoryContext, run_id: int) -> None:
        """Populate Phase-1 and trader summaries from the origin run's AgentStep records."""
        from app.db.models.agent_step import AgentStep

        steps = (
            db.query(AgentStep)
            .filter(AgentStep.run_id == run_id)
            .all()
        )
        for step in steps:
            output = step.output_payload or {}
            agent = (step.agent_name or "").lower()

            if "technical" in agent:
                ctx.origin_technical_summary = (
                    output.get("summary")
                    or output.get("result", {}).get("summary")
                    or str(output)[:500]
                )
            elif "news" in agent:
                ctx.origin_news_summary = (
                    output.get("summary")
                    or output.get("result", {}).get("summary")
                    or str(output)[:500]
                )
            elif "market" in agent and "context" in agent:
                ctx.origin_market_context_summary = (
                    output.get("summary")
                    or output.get("result", {}).get("summary")
                    or str(output)[:500]
                )
            elif "trader" in agent:
                ctx.origin_trader_reasoning = (
                    output.get("reasoning")
                    or output.get("result", {}).get("reasoning")
                    or str(output)[:500]
                )

    @staticmethod
    async def _fetch_candles_since_entry(
        symbol: str,
        open_time: str,
        *,
        account_id: str | None,
        region: str | None,
    ) -> list[dict[str, Any]]:
        """Fetch OHLCV candles from the position open time until now."""
        from app.services.trading.metaapi_client import MetaApiClient

        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
        # Normalise open_time — strip microseconds/timezone suffix for MetaAPI
        start_iso = open_time[:19] if len(open_time) >= 19 else open_time

        client = MetaApiClient()
        candles = await client.get_historical_candles_range(
            pair=symbol,
            timeframe=_CANDLE_TIMEFRAME,
            start_date=start_iso,
            end_date=now_iso,
            account_id=account_id,
            region=region,
        )
        # Cap to _MAX_CANDLES most recent bars
        if len(candles) > _MAX_CANDLES:
            candles = candles[-_MAX_CANDLES:]
        return candles

    @staticmethod
    def _compute_mfe_mae(
        candles: list[dict[str, Any]],
        entry_price: float,
        side: str,
    ) -> tuple[float, float]:
        """Compute Max Favorable and Max Adverse Excursion as % of entry_price.

        MFE: maximum unrealised profit the position could have taken.
        MAE: maximum unrealised loss the position faced.
        """
        if not candles or entry_price <= 0:
            return 0.0, 0.0

        is_long = side.upper() == "BUY"
        max_favorable = 0.0
        max_adverse = 0.0

        for c in candles:
            high = c.get("high") or c.get("h") or 0
            low = c.get("low") or c.get("l") or 0
            if not (isinstance(high, (int, float)) and math.isfinite(high) and high > 0):
                continue
            if not (isinstance(low, (int, float)) and math.isfinite(low) and low > 0):
                continue

            if is_long:
                favorable = (high - entry_price) / entry_price * 100
                adverse = (entry_price - low) / entry_price * 100
            else:
                favorable = (entry_price - low) / entry_price * 100
                adverse = (high - entry_price) / entry_price * 100

            max_favorable = max(max_favorable, favorable)
            max_adverse = max(max_adverse, adverse)

        return round(max_favorable, 4), round(max_adverse, 4)

    @staticmethod
    def _fetch_governance_history(db: Any, ticket: str) -> list[dict[str, Any]]:
        """Return the last N completed governance runs for this position ticket."""
        from app.db.models.governance_run import GovernanceRun

        rows = (
            db.query(GovernanceRun)
            .filter(GovernanceRun.position_ticket == ticket)
            .order_by(GovernanceRun.created_at.desc())
            .limit(_GOVERNANCE_HISTORY_LIMIT)
            .all()
        )
        result = []
        for r in reversed(rows):  # chronological order
            result.append({
                "id": r.id,
                "action": r.action,
                "urgency": r.urgency,
                "conviction": r.conviction,
                "reasoning": r.reasoning,
                "new_sl": r.new_sl,
                "new_tp": r.new_tp,
                "approval_status": r.approval_status,
                "executed": r.executed,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            })
        return result
