"""GovernanceRegistry — runs the multi-agent governance pipeline for open positions.

Architecture
------------
The governance pipeline is a lightweight version of the main 4-phase pipeline:

  Phase 1 (parallel): technical-analyst, news-analyst, market-context-analyst
      — same agents, same tools, same OHLC data fetching
      — context message extended with open position details

  Phase 4 (governance): trader-agent in governance mode
      — uses GovernanceDecision schema instead of TraderDecisionDraft
      — system prompt swapped to position-evaluation framing
      — receives Phase 1 summaries + PositionHistoryContext as base_vars

  Phases 2-3 (debate) and Phase 5 (execution optimizer) are skipped:
      — debate is expensive and not needed for position management decisions
      — execution optimizer is only relevant for new entry orders

Usage::

    from app.services.governance.registry import GovernanceRegistry
    from app.services.governance.position_context_builder import PositionContextBuilder

    ctx = await PositionContextBuilder().build(position, db)
    result = await GovernanceRegistry().execute(db, gov_run, ctx)
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# ── Governance-specific prompts ──────────────────────────────────────────────
_GOVERNANCE_TRADER_SYSTEM = (
    "You are the trader agent operating in GOVERNANCE MODE.\n\n"
    "Your task is NOT to find a new trade entry. You must evaluate an EXISTING OPEN POSITION "
    "and decide what action to take: keep it, adjust its stop-loss/take-profit, or close it.\n\n"
    "POSITION CONTEXT you will receive:\n"
    "- Symbol, side (BUY/SELL), entry price, current price, unrealised PnL\n"
    "- Stop-loss and take-profit levels (current)\n"
    "- Max Favorable Excursion (MFE) and Max Adverse Excursion (MAE) since entry\n"
    "- Number of bars since the position was opened\n"
    "- Original entry reasoning (why this position was opened)\n"
    "- Phase 1 analysis summaries from the CURRENT market conditions\n"
    "- History of previous governance evaluations for this position\n\n"
    "ACTIONS:\n"
    "  HOLD        — the position is fine, no changes needed\n"
    "  ADJUST_SL   — move the stop-loss only (e.g. trail to lock in profit)\n"
    "  ADJUST_TP   — move the take-profit only (e.g. extend target)\n"
    "  ADJUST_SL_TP — move both stop-loss and take-profit\n"
    "  CLOSE       — close the position immediately\n\n"
    "DECISION FRAMEWORK (apply in order — stop at the first rule that fits):\n\n"
    "Step 1 — Assess thesis validity:\n"
    "  - Compare Phase 1 current analysis with the original entry reasoning.\n"
    "  - 'Thesis intact' = key signals still point in the trade direction.\n"
    "  - 'Thesis challenged' = some signals contradict but no decisive reversal.\n"
    "  - 'Thesis broken' = majority of signals invalidate the original rationale.\n\n"
    "Step 2 — Check proximity of current SL:\n"
    "  - If current price is already within 20% of the distance to the stop-loss,\n"
    "    the SL will do its job soon → prefer HOLD over CLOSE (let the SL execute).\n\n"
    "Step 3 — Protect captured profit when MFE was significant:\n"
    "  - If MFE ≥ 1% and the position has retraced back toward entry or into loss,\n"
    "    consider ADJUST_SL to break-even or trail at a level that locks in partial gain.\n"
    "  - Prefer ADJUST_SL over CLOSE in this case — there is still a recovery path.\n\n"
    "Step 4 — Extend target when momentum is strong:\n"
    "  - If thesis is intact, MFE ≥ 1.5%, and price still has technical room to run,\n"
    "    consider ADJUST_TP to a higher target, or ADJUST_SL_TP to do both at once.\n\n"
    "Step 5 — HOLD when in doubt and thesis is not broken:\n"
    "  - If the thesis is intact or only challenged, and no adjustment is clearly needed,\n"
    "    HOLD is a valid and often correct choice. Overtrading is a risk.\n\n"
    "Step 6 — CLOSE only as a last resort:\n"
    "  - Reserve CLOSE for: thesis fully broken AND current SL cannot adequately reduce\n"
    "    further downside AND position would need a significant recovery to be worthwhile.\n"
    "  - Do NOT use CLOSE just because the position is slightly adverse. Use ADJUST_SL or HOLD.\n\n"
    "PRIORITY ORDER: HOLD ≥ ADJUST_SL ≥ ADJUST_SL_TP ≥ ADJUST_TP >> CLOSE\n"
    "CLOSE should be rare — only when the trade thesis is comprehensively invalidated.\n\n"
    "Rules:\n"
    "- You CANNOT open a new position. Governance is for managing existing ones only.\n"
    "- If you ADJUST_SL, new_sl must be a valid price level (positive float).\n"
    "- If you ADJUST_TP, new_tp must be a valid price level (positive float).\n"
    "- The new_sl MUST be at least 10 pips away from current price: for SELL new_sl > current_price + 0.00100, for BUY new_sl < current_price - 0.00100 (use 0.100 for JPY pairs). Closer than this will be rejected by the broker.\n"
    "- Do NOT tighten the stop-loss so much that it would trigger immediately at current price.\n"
    "- conviction is your confidence in this governance decision (0.0 to 1.0).\n"
    "- urgency: low=routine, medium=watch closely, high=act soon, critical=act now.\n"
    "- Your reasoning must reference specific evidence from the position context and Phase 1 analysis.\n"
)

_GOVERNANCE_TRADER_USER = (
    "## Open Position\n"
    "Symbol: {position_symbol} | Side: {position_side} | Volume: {position_volume}\n"
    "Entry: {position_entry_price} | Current: {position_current_price} | "
    "Unrealised PnL: {position_unrealized_pnl}\n"
    "Stop-loss: {position_stop_loss} | Take-profit: {position_take_profit}\n"
    "Opened: {position_open_time}\n"
    "MFE: {mfe_pct}% | MAE: {mae_pct}% | Bars since entry: {bars_since_entry}\n\n"
    "## Original Entry Context\n"
    "Original run #{origin_run_id} | Pair: {origin_pair} | TF: {origin_timeframe}\n"
    "Original trader reasoning: {origin_trader_reasoning}\n\n"
    "## Technical context at entry\n"
    "Technical: {origin_technical_summary}\n"
    "News: {origin_news_summary}\n"
    "Market context: {origin_market_context_summary}\n\n"
    "## Current Market Analysis (Phase 1 — just completed)\n"
    "{current_analysis_summary}\n\n"
    "## Previous Governance Evaluations ({governance_history_count} prior runs)\n"
    "{previous_governance_runs_summary}\n\n"
    "Based on all of the above, decide what to do with this position.\n"
    "Your output must include:\n"
    "- action: HOLD|ADJUST_SL|ADJUST_TP|ADJUST_SL_TP|CLOSE\n"
    "- new_sl: new stop-loss price (required if ADJUST_SL or ADJUST_SL_TP, else null)\n"
    "- new_tp: new take-profit price (required if ADJUST_TP or ADJUST_SL_TP, else null)\n"
    "- conviction: 0.0 to 1.0\n"
    "- urgency: low|medium|high|critical\n"
    "- reasoning: why this action, referencing specific evidence\n"
)


class GovernanceRegistry:
    """Orchestrates the 4-agent governance pipeline for a single open position.

    Reuses the existing agentscope infrastructure: same LLM factory, same
    market-data resolver, same Phase-1 agents, same toolkit builder.
    Only the trader-agent is swapped to governance mode with a custom prompt
    and the ``GovernanceDecision`` structured schema.
    """

    def __init__(self, prompt_service=None, market_provider=None) -> None:
        self.prompt_service = prompt_service
        self.market_provider = market_provider

    # ── Public API ──────────────────────────────────────────────────────────

    async def execute(
        self,
        db: Any,
        gov_run: Any,  # GovernanceRun ORM model
        position_context: Any,  # PositionHistoryContext dataclass
        *,
        metaapi_account_ref: str | None = None,
        account_id: str | None = None,
        region: str | None = None,
    ) -> dict[str, Any]:
        """Run the governance pipeline for *position_context*.

        Updates *gov_run* in place with the decision fields and commits to DB.
        Returns a result dict with ``action``, ``decision``, ``trace``, ``error``.
        """
        from app.services.agentscope.agents import ALL_AGENT_FACTORIES
        from app.services.agentscope.formatter_factory import build_formatter
        from app.services.agentscope.model_factory import build_model
        from app.services.agentscope.schemas import (
            GovernanceDecision,
            MarketContextResult,
            NewsAnalysisResult,
            TechnicalAnalysisResult,
        )
        from app.services.agentscope.toolkit import build_toolkit
        from app.services.llm.model_selector import AgentModelSelector
        from agentscope.message import Msg

        start_time = time.time()
        symbol = position_context.symbol
        # Reuse origin timeframe when known, else default to H1 for governance scans
        timeframe = position_context.origin_timeframe or "1h"
        trace: dict[str, Any] = {}

        # Mark running
        try:
            gov_run.status = "running"
            db.add(gov_run)
            db.commit()
        except Exception as exc:
            logger.warning("GovernanceRegistry: failed to mark gov_run running: %s", exc)

        try:
            # ── LLM config ──────────────────────────────────────────────────
            selector = AgentModelSelector()
            provider, model_name, base_url, api_key = self._resolve_provider_config(db)
            llm_enabled = {
                name: selector.is_enabled(db, name)
                for name in ("technical-analyst", "news-analyst", "market-context-analyst", "trader-agent")
            }
            agent_model_names = {
                name: selector.resolve(db, name)
                for name in ("technical-analyst", "news-analyst", "market-context-analyst", "trader-agent")
            }
            chat_fmt = build_formatter(provider, multi_agent=False, base_url=base_url)

            # ── Market data ─────────────────────────────────────────────────
            market_data = await self._resolve_market_data(
                db, symbol, timeframe,
                metaapi_account_ref=metaapi_account_ref,
                account_id=account_id,
                region=region,
            )
            ohlc = market_data.get("ohlc", {})
            snapshot = market_data.get("snapshot", {})
            news = market_data.get("news", {})

            # ── Build toolkits ───────────────────────────────────────────────
            phase1_agents_names = ["technical-analyst", "news-analyst", "market-context-analyst"]
            toolkits: dict[str, Any] = {}
            for name in phase1_agents_names:
                agent_skills = selector.resolve_skills(db, name)
                toolkits[name] = await build_toolkit(
                    name, ohlc=ohlc, news=news, skills=agent_skills,
                    snapshot=snapshot, decision_mode="governance", execution_mode="governance",
                )
            # Governance trader: resolve skills under its own name "governance-trader"
            gov_trader_skills = selector.resolve_skills(db, "governance-trader")
            toolkits["trader-agent"] = await build_toolkit(
                "governance-trader", ohlc=ohlc, news=news, skills=gov_trader_skills,
                snapshot=snapshot, decision_mode="governance", execution_mode="governance",
            )

            # ── Build agents ─────────────────────────────────────────────────
            # Phase 1: reuse default system prompts
            phase1_sys_prompts = self._build_phase1_sys_prompts(db)
            agents: dict[str, Any] = {}
            for name in phase1_agents_names:
                if not llm_enabled.get(name):
                    continue
                factory = ALL_AGENT_FACTORIES[name]
                agents[name] = factory(
                    model=build_model(provider, agent_model_names[name], base_url, api_key),
                    formatter=chat_fmt,
                    toolkit=toolkits[name],
                    sys_prompt=phase1_sys_prompts[name],
                )

            # Governance trader: always LLM (governance only makes sense with LLM)
            if llm_enabled.get("trader-agent"):
                from agentscope.agent import ReActAgent
                from agentscope.memory import InMemoryMemory
                agents["trader-agent"] = ReActAgent(
                    name="governance-trader",
                    sys_prompt=_GOVERNANCE_TRADER_SYSTEM,
                    model=build_model(provider, agent_model_names["trader-agent"], base_url, api_key),
                    formatter=chat_fmt,
                    toolkit=toolkits["trader-agent"],
                    memory=InMemoryMemory(),
                    max_iters=4,
                    parallel_tool_calls=False,
                )

            # ── Phase 1: parallel ────────────────────────────────────────────
            context_msg = self._build_governance_context_msg(symbol, timeframe, market_data, position_context)
            phase1_schemas = {
                "technical-analyst": TechnicalAnalysisResult,
                "news-analyst": NewsAnalysisResult,
                "market-context-analyst": MarketContextResult,
            }

            from app.core.config import get_settings as _gs
            _agent_timeout = getattr(_gs(), "agentscope_agent_timeout_seconds", 60)

            async def _run_phase1_agent(name: str) -> tuple[str, dict]:
                if name not in agents:
                    return name, {"text": "", "metadata": {}, "llm_enabled": False, "degraded": True}
                schema = phase1_schemas.get(name)
                try:
                    if schema:
                        msg = await asyncio.wait_for(
                            agents[name](context_msg, structured_model=schema),
                            timeout=_agent_timeout,
                        )
                    else:
                        msg = await asyncio.wait_for(agents[name](context_msg), timeout=_agent_timeout)
                    return name, self._msg_to_dict(msg)
                except Exception as exc:
                    logger.warning("GovernanceRegistry: phase1 agent %s failed: %s", name, exc)
                    return name, {"text": "", "metadata": {}, "degraded": True, "error": str(exc)}

            phase1_results = await asyncio.gather(
                *[_run_phase1_agent(n) for n in phase1_agents_names],
                return_exceptions=False,
            )
            analysis_outputs: dict[str, dict] = dict(phase1_results)
            trace["phase1"] = {n: v.get("metadata", {}) for n, v in analysis_outputs.items()}

            # ── Build current analysis summary for governance trader ──────────
            current_analysis_summary = self._build_analysis_summary(analysis_outputs)

            # ── Trader agent — governance mode ───────────────────────────────
            governance_decision: GovernanceDecision | None = None
            if "trader-agent" in agents:
                pos_vars = position_context.to_prompt_dict()
                pos_vars["current_analysis_summary"] = current_analysis_summary
                governance_user_prompt = _GOVERNANCE_TRADER_USER.format(**pos_vars)
                governance_msg = Msg("user", governance_user_prompt, "user")

                try:
                    gov_msg = await asyncio.wait_for(
                        agents["trader-agent"](governance_msg, structured_model=GovernanceDecision),
                        timeout=_agent_timeout,
                    )
                    gov_dict = self._msg_to_dict(gov_msg)
                    trace["governance_decision_raw"] = gov_dict.get("metadata", {})
                    try:
                        governance_decision = GovernanceDecision(**gov_dict.get("metadata", {}))
                    except Exception as exc:
                        logger.warning("GovernanceRegistry: GovernanceDecision parse failed: %s", exc)
                        # Fallback: HOLD
                        governance_decision = GovernanceDecision(
                            action="HOLD",
                            conviction=0.0,
                            reasoning=f"Parse failed, defaulting to HOLD: {exc}",
                            degraded=True,
                        )
                except Exception as exc:
                    logger.warning("GovernanceRegistry: governance trader failed: %s", exc)
                    governance_decision = GovernanceDecision(
                        action="HOLD",
                        conviction=0.0,
                        reasoning=f"Governance trader agent failed: {exc}",
                        degraded=True,
                    )
            else:
                # LLM disabled for trader: default HOLD
                governance_decision = GovernanceDecision(
                    action="HOLD",
                    conviction=0.0,
                    reasoning="LLM disabled for trader-agent; defaulting to HOLD.",
                    degraded=True,
                )

            elapsed = round(time.time() - start_time, 2)
            trace["elapsed_seconds"] = elapsed
            trace["phase1_summary"] = current_analysis_summary

            # ── Persist decision on GovernanceRun ────────────────────────────
            try:
                gov_run.status = "completed"
                gov_run.action = governance_decision.action
                gov_run.new_sl = governance_decision.new_sl
                gov_run.new_tp = governance_decision.new_tp
                gov_run.conviction = governance_decision.conviction
                gov_run.urgency = governance_decision.urgency
                gov_run.reasoning = governance_decision.reasoning
                gov_run.trace = trace
                gov_run.updated_at = datetime.now(timezone.utc)
                db.add(gov_run)
                db.commit()
            except Exception as exc:
                logger.error("GovernanceRegistry: failed to persist decision: %s", exc)
                try:
                    db.rollback()
                except Exception:
                    pass

            result = {
                "action": governance_decision.action,
                "new_sl": governance_decision.new_sl,
                "new_tp": governance_decision.new_tp,
                "conviction": governance_decision.conviction,
                "urgency": governance_decision.urgency,
                "reasoning": governance_decision.reasoning,
                "degraded": governance_decision.degraded,
                "trace": trace,
                "elapsed_seconds": elapsed,
            }

            # Write debug trace (same format/setting as AgentScopeRegistry)
            self._write_debug_trace(
                gov_run=gov_run,
                position_context=position_context,
                market_data=market_data,
                analysis_outputs=analysis_outputs,
                governance_decision=governance_decision,
                elapsed=elapsed,
            )

            return result

        except Exception as exc:
            logger.exception("GovernanceRegistry: pipeline failed for ticket=%s: %s", gov_run.position_ticket, exc)
            try:
                gov_run.status = "failed"
                gov_run.error = str(exc)[:1000]
                gov_run.updated_at = datetime.now(timezone.utc)
                db.add(gov_run)
                db.commit()
            except Exception:
                pass
            return {"action": "HOLD", "error": str(exc), "degraded": True}

    # ── Private helpers ─────────────────────────────────────────────────────

    def _resolve_provider_config(self, db: Any) -> tuple[str, str, str, str]:
        from app.core.config import get_settings
        from app.services.llm.model_selector import AgentModelSelector
        selector = AgentModelSelector()
        provider = selector.resolve_provider(db)
        model_name = selector.resolve(db)
        s = get_settings()
        if provider == "openai":
            return provider, model_name, s.openai_base_url, s.openai_api_key
        if provider == "mistral":
            return provider, model_name, s.mistral_base_url, s.mistral_api_key
        return "ollama", model_name, s.ollama_base_url, s.ollama_api_key

    async def _resolve_market_data(
        self,
        db: Any,
        pair: str,
        timeframe: str,
        metaapi_account_ref: str | None = None,
        account_id: str | None = None,
        region: str | None = None,
    ) -> dict[str, Any]:
        """Minimal market data resolver — MetaAPI primary, YFinance fallback.

        If *account_id* and *region* are provided (already resolved by the caller)
        they are used directly, bypassing the DB account selector.
        """
        from app.core.config import get_settings
        from app.services.trading.metaapi_client import MetaApiClient
        from app.services.trading.account_selector import MetaApiAccountSelector

        settings = get_settings()
        snapshot: dict[str, Any] = {}
        ohlc: dict[str, list[float]] = {}
        news: dict[str, Any] = {}

        try:
            metaapi = MetaApiClient()
            # Use pre-resolved account credentials if provided; otherwise look up from DB.
            if not account_id:
                account = MetaApiAccountSelector().resolve(db, metaapi_account_ref)
                account_id = str(account.account_id) if account else None
                region = (account.region if account else None) or settings.metaapi_region
            if not region:
                region = settings.metaapi_region

            if account_id:
                candles_result, tick_result = await asyncio.gather(
                    metaapi.get_market_candles(
                        pair=pair, timeframe=timeframe, limit=240,
                        account_id=account_id, region=region,
                    ),
                    metaapi.get_current_tick(
                        symbol=pair, account_id=account_id, region=region,
                    ),
                    return_exceptions=True,
                )
                if isinstance(candles_result, dict) and not candles_result.get("degraded"):
                    candles = candles_result.get("candles", [])
                    if candles and len(candles) >= 30:
                        ohlc = {
                            "opens": [float(c.get("open", 0)) for c in candles[-200:]],
                            "highs": [float(c.get("high", 0)) for c in candles[-200:]],
                            "lows": [float(c.get("low", 0)) for c in candles[-200:]],
                            "closes": [float(c.get("close", 0)) for c in candles[-200:]],
                        }
                        snapshot["market_data_source"] = "metaapi"
                if isinstance(tick_result, dict) and not tick_result.get("degraded"):
                    snapshot.update({
                        "bid": tick_result.get("bid", 0),
                        "ask": tick_result.get("ask", 0),
                        "spread": tick_result.get("spread", 0),
                        "last_price": tick_result.get("bid", 0),
                    })
        except Exception as exc:
            logger.warning("GovernanceRegistry: MetaAPI market data failed: %s", exc)

        # YFinance fallback
        if not ohlc:
            try:
                import yfinance as yf
                # Translate MetaAPI/internal timeframe to yfinance interval format
                _YF_INTERVAL_MAP: dict[str, str] = {
                    "m1": "1m", "m5": "5m", "m15": "15m", "m30": "30m",
                    "h1": "60m", "1h": "60m", "h4": "60m", "4h": "60m",
                    "d1": "1d", "1d": "1d", "w1": "1wk",
                    "M1": "1m", "M5": "5m", "M15": "15m", "M30": "30m",
                    "H1": "60m", "H4": "60m", "D1": "1d", "W1": "1wk",
                }
                yf_interval = _YF_INTERVAL_MAP.get(timeframe, "60m")
                yf_period = "7d" if yf_interval in ("1m", "5m", "15m", "30m") else "3mo"
                ticker = yf.Ticker(pair)
                frame = ticker.history(period=yf_period, interval=yf_interval)
                if frame is not None and not frame.empty:
                    ohlc = {
                        "opens": [round(float(v), 6) for v in frame["Open"].tolist()[-200:]],
                        "highs": [round(float(v), 6) for v in frame["High"].tolist()[-200:]],
                        "lows": [round(float(v), 6) for v in frame["Low"].tolist()[-200:]],
                        "closes": [round(float(v), 6) for v in frame["Close"].tolist()[-200:]],
                    }
                    snapshot.setdefault("market_data_source", "yfinance")
            except Exception as exc:
                logger.warning("GovernanceRegistry: YFinance fallback failed: %s", exc)

        if self.market_provider:
            try:
                news = self.market_provider.get_news_context(pair) or {}
            except Exception as exc:
                logger.warning("GovernanceRegistry: news context failed: %s", exc)

        return {"snapshot": snapshot, "news": news, "ohlc": ohlc}

    def _build_phase1_sys_prompts(self, db: Any) -> dict[str, str]:
        """Resolve Phase-1 system prompts (DB → DEFAULT_PROMPTS fallback)."""
        from app.services.prompts.registry import DEFAULT_PROMPTS
        result = {}
        for name in ("technical-analyst", "news-analyst", "market-context-analyst"):
            fallback = DEFAULT_PROMPTS.get(name, {})
            sys = fallback.get("system", f"You are the {name} agent.")
            if self.prompt_service:
                try:
                    rendered = self.prompt_service.render(db, name, sys, "", {})
                    sys = rendered.get("system_prompt", sys)
                except Exception:
                    pass
            result[name] = sys
        return result

    def _build_governance_context_msg(
        self,
        symbol: str,
        timeframe: str,
        market_data: dict,
        position_context: Any,
    ):
        """Build context message that includes the open position summary."""
        from agentscope.message import Msg
        snapshot = market_data.get("snapshot", {})
        ohlc = market_data.get("ohlc", {})
        market_lines = []
        for key in ("last_price", "change_pct", "rsi", "ema_fast", "ema_slow", "macd_diff", "atr", "trend"):
            val = snapshot.get(key)
            if val is not None:
                market_lines.append(f"- {key}: {val}")

        pos_ctx = (
            f"\n\n## Open Position Being Governed\n"
            f"Ticket: {position_context.ticket} | {symbol} {position_context.side} "
            f"@ {position_context.entry_price} | Current: {position_context.current_price} | "
            f"Unrealised PnL: {position_context.unrealized_pnl}\n"
            f"SL: {position_context.stop_loss} | TP: {position_context.take_profit}\n"
            f"MFE: {position_context.mfe_pct:.2f}% | MAE: {position_context.mae_pct:.2f}% | "
            f"Bars since entry: {position_context.bars_since_entry}"
        )

        content = (
            f"You are analyzing {symbol} on the {timeframe} timeframe "
            f"in the context of an open position governance review.\n\n"
            f"Market snapshot ({snapshot.get('market_data_source', 'unknown')}):\n"
            + "\n".join(market_lines) + "\n"
            f"- bars available: {len(ohlc.get('closes', []))}"
            f"{pos_ctx}\n\n"
            f"IMPORTANT: Price data is pre-loaded in your tools. "
            f"Call indicator_bundle(), pattern_detector(), support_resistance_detector() directly."
        )
        return Msg("system", content, "system")

    @staticmethod
    def _build_analysis_summary(analysis_outputs: dict[str, dict]) -> str:
        """Build a readable summary of Phase-1 outputs for the governance trader."""
        lines = []
        for agent_name, label in [
            ("technical-analyst", "Technical"),
            ("news-analyst", "News"),
            ("market-context-analyst", "Market context"),
        ]:
            out = analysis_outputs.get(agent_name, {})
            meta = out.get("metadata", {})
            summary = meta.get("summary") or out.get("text", "")[:300]
            if summary:
                lines.append(f"{label}: {summary}")
            elif out.get("degraded"):
                lines.append(f"{label}: [degraded — no output]")
        return "\n".join(lines) if lines else "No current analysis available."

    def _write_debug_trace(
        self,
        gov_run: Any,
        position_context: Any,
        market_data: dict,
        analysis_outputs: dict,
        governance_decision: Any,
        elapsed: float,
    ) -> None:
        """Write governance debug trace JSON — same format/setting as AgentScopeRegistry."""
        import json
        import os
        from datetime import datetime, timezone
        from app.core.config import get_settings

        settings = get_settings()
        if not settings.debug_trade_json_enabled:
            return

        try:
            trace_dir = os.path.join(
                os.path.dirname(settings.debug_trade_json_dir or "./debug-traces"),
                "debug-governance",
            )
            os.makedirs(trace_dir, exist_ok=True)

            ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            filename = f"gov-{gov_run.id}-{ts}.json"
            filepath = os.path.join(trace_dir, filename)

            snapshot = market_data.get("snapshot", {})
            ohlc = market_data.get("ohlc", {})
            news = market_data.get("news", {})

            # Price history (same format as AgentScopeRegistry)
            price_history = []
            if settings.debug_trade_json_include_price_history:
                limit = settings.debug_trade_json_price_history_limit
                closes = ohlc.get("closes", [])[-limit:]
                opens = ohlc.get("opens", [])[-limit:]
                highs = ohlc.get("highs", [])[-limit:]
                lows = ohlc.get("lows", [])[-limit:]
                for i in range(len(closes)):
                    price_history.append({
                        "open": opens[i] if i < len(opens) else 0,
                        "high": highs[i] if i < len(highs) else 0,
                        "low": lows[i] if i < len(lows) else 0,
                        "close": closes[i] if i < len(closes) else 0,
                        "volume": None,
                    })

            # Agent steps — Phase 1 + governance trader
            workflow = ["technical-analyst", "news-analyst", "market-context-analyst", "governance-trader"]
            agent_steps = []
            for agent_name in workflow:
                out = analysis_outputs.get(agent_name, {})
                step_output = {**out.get("metadata", {})}
                step_output["llm_enabled"] = out.get("llm_enabled", True)
                step_output.setdefault("degraded", out.get("degraded", False))
                if out.get("text"):
                    step_output.setdefault("reasoning", out["text"][:2000])
                agent_steps.append({
                    "agent_name": agent_name,
                    "status": "completed" if not out.get("degraded") else "degraded",
                    "llm_enabled": out.get("llm_enabled", True),
                    "input_payload": {
                        "symbol": gov_run.symbol,
                        "timeframe": getattr(position_context, "origin_timeframe", None) or "1h",
                        "position_ticket": gov_run.position_ticket,
                    },
                    "output_payload": step_output,
                    "output_text": out.get("text", "")[:2000],
                })

            # Governance trader output
            gov_step_output = {
                "action": governance_decision.action,
                "new_sl": governance_decision.new_sl,
                "new_tp": governance_decision.new_tp,
                "conviction": governance_decision.conviction,
                "urgency": governance_decision.urgency,
                "reasoning": governance_decision.reasoning,
                "degraded": governance_decision.degraded,
            }
            # Replace placeholder governance-trader step with real output
            for step in agent_steps:
                if step["agent_name"] == "governance-trader":
                    step["output_payload"] = gov_step_output
                    step["output_text"] = governance_decision.reasoning or ""
                    break

            # Analysis bundle
            def _bundle(key: str) -> dict:
                out = analysis_outputs.get(key, {})
                meta = out.get("metadata", {})
                if not meta and out.get("text"):
                    meta = {"summary": out["text"][:1000]}
                return meta

            analysis_bundle = {
                "analysis_outputs": {
                    k: _bundle(k)
                    for k in ("technical-analyst", "news-analyst", "market-context-analyst")
                },
                "governance_decision": gov_step_output,
            }

            # Position context snapshot
            pos_ctx: dict = {}
            if position_context is not None:
                pos_ctx = {
                    "ticket": getattr(position_context, "ticket", gov_run.position_ticket),
                    "symbol": getattr(position_context, "symbol", gov_run.symbol),
                    "side": getattr(position_context, "side", gov_run.side),
                    "volume": getattr(position_context, "volume", None),
                    "entry_price": getattr(position_context, "entry_price", None),
                    "current_price": getattr(position_context, "current_price", None),
                    "unrealized_pnl": getattr(position_context, "unrealized_pnl", None),
                    "stop_loss": getattr(position_context, "stop_loss", None),
                    "take_profit": getattr(position_context, "take_profit", None),
                    "open_time": getattr(position_context, "open_time", None),
                    "mfe_pct": getattr(position_context, "mfe_pct", None),
                    "mae_pct": getattr(position_context, "mae_pct", None),
                    "bars_since_entry": getattr(position_context, "bars_since_entry", None),
                    "origin_run_id": getattr(position_context, "origin_run_id", gov_run.origin_run_id),
                    "origin_pair": getattr(position_context, "origin_pair", None),
                    "origin_timeframe": getattr(position_context, "origin_timeframe", None),
                }

            payload = {
                "schema_version": 2,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "runtime_engine": "governance_v1",
                "gov_run": {
                    "id": gov_run.id,
                    "position_ticket": gov_run.position_ticket,
                    "symbol": gov_run.symbol,
                    "side": gov_run.side,
                    "origin_run_id": gov_run.origin_run_id,
                    "status": gov_run.status,
                    "action": governance_decision.action,
                    "new_sl": governance_decision.new_sl,
                    "new_tp": governance_decision.new_tp,
                    "conviction": governance_decision.conviction,
                    "urgency": governance_decision.urgency,
                    "created_at": str(getattr(gov_run, "created_at", "")),
                    "updated_at": str(getattr(gov_run, "updated_at", "")),
                },
                "position_context": pos_ctx,
                "context": {
                    "market_snapshot": snapshot,
                    "price_history": price_history,
                    "news_context": news,
                },
                "workflow": workflow,
                "agent_steps": agent_steps,
                "analysis_bundle": analysis_bundle,
                "final_decision": {
                    "action": governance_decision.action,
                    "new_sl": governance_decision.new_sl,
                    "new_tp": governance_decision.new_tp,
                    "conviction": governance_decision.conviction,
                    "urgency": governance_decision.urgency,
                    "reasoning": governance_decision.reasoning,
                    "degraded": governance_decision.degraded,
                },
                "elapsed_seconds": round(elapsed, 1),
            }

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2, default=str)

            logger.info("Governance debug trace written: %s", filepath)

        except Exception as exc:
            logger.warning("GovernanceRegistry: failed to write debug trace: %s", exc)

    @staticmethod
    def _msg_to_dict(msg: Any) -> dict[str, Any]:
        text = ""
        try:
            text = msg.get_text_content() or ""
        except Exception:
            text = str(getattr(msg, "content", ""))
        metadata: dict = {}
        if hasattr(msg, "metadata") and isinstance(msg.metadata, dict):
            metadata = msg.metadata
        if not metadata:
            # Try to extract JSON from text
            clean = text.strip()
            start = clean.find("{")
            if start >= 0:
                end = clean.rfind("}")
                if end > start:
                    try:
                        parsed = json.loads(clean[start:end + 1])
                        if isinstance(parsed, dict):
                            metadata = parsed
                    except (json.JSONDecodeError, ValueError):
                        pass
        return {"text": text, "metadata": metadata, "name": getattr(msg, "name", "")}
