"""Main AgentScope orchestration — 4-phase pipeline for trading analysis."""
from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any

from agentscope.message import Msg
from agentscope.pipeline import fanout_pipeline

from app.db.models.agent_step import AgentStep
from app.services.agentscope.agents import ALL_AGENT_FACTORIES
from app.services.agentscope.debate import DebateConfig, run_debate
from app.services.agentscope.formatter_factory import build_formatter
from app.services.agentscope.model_factory import build_model
from app.services.agentscope.schemas import (
    DebateResult,
    ExecutionPlanResult,
    MarketContextResult,
    NewsAnalysisResult,
    RiskAssessmentResult,
    TechnicalAnalysisResult,
    TraderDecisionDraft,
)
from app.services.agentscope.toolkit import build_toolkit

# Map agent name -> structured output schema for LLM agents
AGENT_STRUCTURED_MODELS: dict[str, type] = {
    "technical-analyst": TechnicalAnalysisResult,
    "news-analyst": NewsAnalysisResult,
    "market-context-analyst": MarketContextResult,
    "trader-agent": TraderDecisionDraft,
    "risk-manager": RiskAssessmentResult,
    "execution-manager": ExecutionPlanResult,
}

logger = logging.getLogger(__name__)


async def _extract_tool_invocations(agent) -> dict[str, dict[str, Any]]:
    """Extract tool call results from an agent's memory after execution."""
    invocations: dict[str, dict[str, Any]] = {}
    if not hasattr(agent, "memory") or agent.memory is None:
        return invocations

    try:
        msgs = await agent.memory.get_memory()
    except Exception:
        return invocations

    # Collect tool_use and tool_result pairs by id
    tool_uses: dict[str, dict] = {}
    tool_results: dict[str, dict] = {}

    for msg in msgs:
        try:
            blocks = msg.get_content_blocks()
        except Exception:
            continue
        for block in blocks:
            if not isinstance(block, dict):
                continue
            block_type = block.get("type")
            block_id = block.get("id", "")
            if block_type == "tool_use":
                tool_uses[block_id] = block
            elif block_type == "tool_result":
                tool_results[block_id] = block

    # Merge into invocations keyed by tool name
    for call_id, use_block in tool_uses.items():
        tool_name = use_block.get("name", "unknown")
        result_block = tool_results.get(call_id, {})

        # Parse output text as JSON if possible
        output_data: Any = {}
        raw_output = result_block.get("output", "")
        if isinstance(raw_output, list):
            # AgentScope format: [{"type": "text", "text": "..."}]
            texts = [item.get("text", "") for item in raw_output if isinstance(item, dict)]
            raw_text = " ".join(texts)
            try:
                output_data = json.loads(raw_text)
            except (json.JSONDecodeError, ValueError):
                output_data = {"raw": raw_text[:500]}
        elif isinstance(raw_output, str):
            try:
                output_data = json.loads(raw_output)
            except (json.JSONDecodeError, ValueError):
                output_data = {"raw": raw_output[:500]}

        invocations[tool_name] = {
            "tool_id": tool_name,
            "status": "error" if isinstance(output_data, dict) and "error" in output_data else "ok",
            "input": use_block.get("input", {}),
            "data": output_data,
        }

    return invocations


def _try_extract_json(text: str) -> dict[str, Any]:
    """Try to extract a JSON object from text (agent output or deterministic result)."""
    if not text:
        return {}
    # Strip deterministic prefix
    clean = text.strip()
    if clean.startswith("[deterministic]"):
        clean = clean[len("[deterministic]"):].strip()
    # Try to parse as JSON
    try:
        parsed = json.loads(clean)
        if isinstance(parsed, dict):
            return parsed
    except (json.JSONDecodeError, ValueError):
        pass
    # Try to find JSON block in text
    start = clean.find("{")
    if start >= 0:
        end = clean.rfind("}")
        if end > start:
            try:
                parsed = json.loads(clean[start:end + 1])
                if isinstance(parsed, dict):
                    return parsed
            except (json.JSONDecodeError, ValueError):
                pass
    return {}


def _msg_to_dict(msg: Msg | None, tool_invocations: dict | None = None) -> dict[str, Any]:
    if msg is None:
        return {}
    text = ""
    try:
        text = msg.get_text_content() or ""
    except Exception:
        text = str(getattr(msg, "content", ""))
    metadata = {}
    if hasattr(msg, "metadata") and isinstance(msg.metadata, dict) and msg.metadata:
        metadata = msg.metadata
    # If metadata is empty, try to extract structured data from text
    if not metadata:
        metadata = _try_extract_json(text)

    result: dict[str, Any] = {"text": text, "metadata": metadata, "name": getattr(msg, "name", "")}

    # Attach tool invocation data if available
    if tool_invocations:
        result["tooling"] = {
            "invocations": tool_invocations,
            "evidence_used": list(tool_invocations.keys()),
            "evidence_total_count": len(tool_invocations),
        }
        # Merge tool output data into metadata for richer output_payload
        for tool_name, inv in tool_invocations.items():
            data = inv.get("data", {})
            if isinstance(data, dict) and data and "error" not in data:
                # Store individual tool results
                result.setdefault("tool_results", {})[tool_name] = data

    return result


class AgentScopeRegistry:
    """Orchestrates 8 trading agents through 4 phases."""

    def __init__(self, prompt_service=None, market_provider=None, execution_service=None) -> None:
        self.prompt_service = prompt_service
        self.market_provider = market_provider
        self.execution_service = execution_service

    def _resolve_provider_config(self, db) -> tuple[str, str, str, str]:
        from app.core.config import get_settings
        from app.services.llm.model_selector import AgentModelSelector
        selector = AgentModelSelector()
        provider = selector.resolve_provider(db)
        s = get_settings()
        if provider == "openai":
            return provider, s.openai_model, s.openai_base_url, s.openai_api_key
        if provider == "mistral":
            return provider, s.mistral_model, s.mistral_base_url, s.mistral_api_key
        return "ollama", s.ollama_model, s.ollama_base_url, s.ollama_api_key

    async def _resolve_market_data(
        self, db, pair: str, timeframe: str, metaapi_account_ref: str | None = None,
    ) -> dict[str, Any]:
        """Fetch market data from MetaAPI (primary) with YFinance fallback."""
        from app.core.config import get_settings
        from app.services.trading.metaapi_client import MetaApiClient
        from app.services.trading.account_selector import MetaApiAccountSelector

        settings = get_settings()
        snapshot: dict[str, Any] = {}
        ohlc: dict[str, list[float]] = {}
        news: dict[str, Any] = {}
        market_source = "none"

        # ── Try MetaAPI first ──
        try:
            metaapi = MetaApiClient()
            account = MetaApiAccountSelector().resolve(db, metaapi_account_ref)
            account_id = str(account.account_id) if account else None
            region = (account.region if account else None) or settings.metaapi_region

            if account_id:
                logger.info("Fetching market data from MetaAPI for %s/%s (account=%s)", pair, timeframe, account_id)

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

                # Process candles
                if isinstance(candles_result, dict) and not candles_result.get("degraded"):
                    candles = candles_result.get("candles", [])
                    if candles and len(candles) >= 30:
                        ohlc = {
                            "opens": [float(c.get("open", 0)) for c in candles[-200:]],
                            "highs": [float(c.get("high", 0)) for c in candles[-200:]],
                            "lows": [float(c.get("low", 0)) for c in candles[-200:]],
                            "closes": [float(c.get("close", 0)) for c in candles[-200:]],
                        }
                        market_source = "metaapi"

                # Process tick for snapshot
                if isinstance(tick_result, dict) and not tick_result.get("degraded"):
                    snapshot["bid"] = tick_result.get("bid", 0)
                    snapshot["ask"] = tick_result.get("ask", 0)
                    snapshot["spread"] = tick_result.get("spread", 0)
                    snapshot["last_price"] = tick_result.get("bid", 0)

                # Build snapshot from candles if we have them
                if ohlc.get("closes"):
                    from ta.momentum import RSIIndicator
                    from ta.trend import EMAIndicator, MACD
                    from ta.volatility import AverageTrueRange
                    import pandas as pd

                    close = pd.Series(ohlc["closes"])
                    high = pd.Series(ohlc["highs"])
                    low = pd.Series(ohlc["lows"])

                    rsi_val = RSIIndicator(close=close, window=14).rsi().iloc[-1]
                    ema_fast = EMAIndicator(close=close, window=20).ema_indicator().iloc[-1]
                    ema_slow = EMAIndicator(close=close, window=50).ema_indicator().iloc[-1]
                    macd_diff = MACD(close=close).macd_diff().iloc[-1]
                    atr_val = AverageTrueRange(high=high, low=low, close=close).average_true_range().iloc[-1]

                    latest = float(close.iloc[-1])
                    prev = float(close.iloc[-2]) if len(close) > 1 else latest
                    pct_change = ((latest - prev) / prev) * 100 if prev else 0.0

                    trend = "bullish" if ema_fast > ema_slow else "bearish"
                    if abs(ema_fast - ema_slow) < latest * 0.0003:
                        trend = "neutral"

                    snapshot.update({
                        "last_price": snapshot.get("last_price") or latest,
                        "rsi": round(float(rsi_val), 3),
                        "ema_fast": round(float(ema_fast), 6),
                        "ema_slow": round(float(ema_slow), 6),
                        "macd_diff": round(float(macd_diff), 6),
                        "atr": round(float(atr_val), 6),
                        "change_pct": round(float(pct_change), 5),
                        "trend": trend,
                        "degraded": False,
                    })
        except Exception as exc:
            logger.warning("MetaAPI market data failed for %s: %s", pair, exc)

        # ── Fallback to YFinance ──
        if not ohlc.get("closes") and self.market_provider:
            logger.info("Falling back to YFinance for %s/%s", pair, timeframe)
            market_source = "yfinance"
            try:
                yf_snapshot = self.market_provider.get_market_snapshot(pair, timeframe) or {}
                snapshot.update(yf_snapshot)
            except Exception as exc:
                logger.warning("YFinance snapshot failed: %s", exc)
            try:
                frame = self.market_provider._prepare_frame(pair, timeframe)
                if frame is not None and not frame.empty:
                    ohlc = {
                        "opens": [round(float(v), 6) for v in frame["Open"].tolist()[-200:]],
                        "highs": [round(float(v), 6) for v in frame["High"].tolist()[-200:]],
                        "lows": [round(float(v), 6) for v in frame["Low"].tolist()[-200:]],
                        "closes": [round(float(v), 6) for v in frame["Close"].tolist()[-200:]],
                    }
            except Exception as exc:
                logger.warning("YFinance OHLC failed: %s", exc)

        # News context
        if self.market_provider:
            try:
                news = self.market_provider.get_news_context(pair) or {}
            except Exception as exc:
                logger.warning("News context failed: %s", exc)

        snapshot["market_data_source"] = market_source
        return {"snapshot": snapshot, "news": news, "ohlc": ohlc}

    def _get_sys_prompt(self, agent_name: str, db) -> str:
        if self.prompt_service:
            try:
                rendered = self.prompt_service.render(db, agent_name)
                if rendered and rendered[0]:
                    return rendered[0]
            except Exception:
                pass
        return f"You are the {agent_name} agent in a multi-agent trading system."

    def _build_context_msg(self, pair: str, timeframe: str, market_data: dict) -> Msg:
        snapshot = market_data.get("snapshot", {})
        ohlc = market_data.get("ohlc", {})
        news = market_data.get("news", {})
        context = {
            "pair": pair, "timeframe": timeframe,
            "market_snapshot": {
                "last_price": snapshot.get("last_price", 0),
                "change_pct": snapshot.get("change_pct", 0),
                "rsi": snapshot.get("rsi", 50),
                "ema_fast": snapshot.get("ema_fast", 0),
                "ema_slow": snapshot.get("ema_slow", 0),
                "macd_diff": snapshot.get("macd_diff", 0),
                "atr": snapshot.get("atr", 0),
                "trend": snapshot.get("trend", "neutral"),
                "degraded": snapshot.get("degraded", True),
                "market_data_source": snapshot.get("market_data_source", "unknown"),
            },
            "ohlc_bars_available": len(ohlc.get("closes", [])),
            "news_context": news,
        }
        return Msg(
            "system",
            f"You are analyzing {pair} on the {timeframe} timeframe.\n\n"
            f"Market summary:\n```json\n{json.dumps(context, default=str)}\n```\n\n"
            f"IMPORTANT: Price data (closes, opens, highs, lows) is pre-loaded into your tools. "
            f"Just call indicator_bundle(), pattern_detector(), divergence_detector(), "
            f"support_resistance_detector() directly — they already have the price arrays.",
            "system",
        )

    def _record_step(self, db, run, agent_name: str, input_data: dict, output_data: dict,
                     status: str = "completed", error: str | None = None, elapsed_ms: float = 0) -> None:
        try:
            step = AgentStep(
                run_id=run.id, agent_name=agent_name, status=status,
                input_payload={"context": "agentscope_v1", **input_data},
                output_payload={"elapsed_ms": round(elapsed_ms, 1), **output_data},
                error=error,
            )
            db.add(step)
            db.flush()
        except Exception as exc:
            logger.warning("Failed to record step for %s: %s", agent_name, exc)

    def _write_debug_trace(
        self, run, pair: str, timeframe: str, risk_percent: float,
        market_data: dict, analysis_outputs: dict, elapsed: float,
    ) -> None:
        """Write debug trace JSON file compatible with schema v1 format."""
        from app.core.config import get_settings
        import os

        settings = get_settings()
        if not settings.debug_trade_json_enabled:
            return

        try:
            trace_dir = settings.debug_trade_json_dir or "./debug-traces"
            os.makedirs(trace_dir, exist_ok=True)

            ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            filename = f"run-{run.id}-{ts}.json"
            filepath = os.path.join(trace_dir, filename)

            snapshot = market_data.get("snapshot", {})
            ohlc = market_data.get("ohlc", {})
            news = market_data.get("news", {})

            # Build price_history in v1 format (list of candle dicts)
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

            # Build agent_steps in v1 format
            agent_steps = []
            workflow = []
            for agent_name in [
                "technical-analyst", "news-analyst", "market-context-analyst",
                "bullish-researcher", "bearish-researcher",
                "trader-agent", "risk-manager", "execution-manager",
            ]:
                workflow.append(agent_name)
                out = analysis_outputs.get(agent_name, {})
                # Build rich output_payload matching v1 format
                step_output = {**out.get("metadata", {})}
                # Merge tool results into output_payload
                if out.get("tool_results"):
                    for tool_name, tool_data in out["tool_results"].items():
                        if isinstance(tool_data, dict):
                            # Flatten key tool data into output_payload
                            if tool_name == "indicator_bundle":
                                step_output.setdefault("indicators", tool_data)
                            elif tool_name == "pattern_detector":
                                step_output.setdefault("patterns", tool_data.get("patterns", []))
                            elif tool_name == "divergence_detector":
                                step_output.setdefault("divergences", tool_data.get("divergences", []))
                            elif tool_name == "support_resistance_detector":
                                step_output.setdefault("structure", tool_data)
                            elif tool_name == "multi_timeframe_context":
                                step_output.setdefault("multi_timeframe", tool_data)
                # Add tooling section
                if out.get("tooling"):
                    step_output["tooling"] = out["tooling"]
                step_output["llm_enabled"] = out.get("llm_enabled", False)
                step_output.setdefault("degraded", False)

                agent_steps.append({
                    "agent_name": agent_name,
                    "status": "completed",
                    "llm_enabled": out.get("llm_enabled", False),
                    "input_payload": {"pair": pair, "timeframe": timeframe},
                    "output_payload": step_output,
                    "output_text": out.get("text", "")[:2000],
                })

            # Build analysis_bundle in v1 format
            analysis_bundle = {
                "analysis_outputs": {
                    k: v.get("metadata", {})
                    for k, v in analysis_outputs.items()
                    if k in ("technical-analyst", "news-analyst", "market-context-analyst")
                },
                "bullish": analysis_outputs.get("bullish-researcher", {}).get("metadata", {}),
                "bearish": analysis_outputs.get("bearish-researcher", {}).get("metadata", {}),
                "trader_decision": analysis_outputs.get("trader-agent", {}).get("metadata", {}),
                "risk": analysis_outputs.get("risk-manager", {}).get("metadata", {}),
                "execution_manager": analysis_outputs.get("execution-manager", {}).get("metadata", {}),
            }

            payload = {
                "schema_version": 2,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "runtime_engine": "agentscope_v1",
                "run": {
                    "id": run.id,
                    "pair": pair,
                    "timeframe": timeframe,
                    "mode": getattr(run, "mode", "simulation"),
                    "status": run.status,
                    "risk_percent": risk_percent,
                    "created_at": str(getattr(run, "created_at", "")),
                    "updated_at": str(getattr(run, "updated_at", "")),
                },
                "context": {
                    "market_snapshot": snapshot,
                    "price_history": price_history,
                    "news_context": news,
                },
                "workflow": workflow,
                "agent_steps": agent_steps,
                "analysis_bundle": analysis_bundle,
                "final_decision": run.decision,
                "execution": run.decision.get("execution", {}),
                "elapsed_seconds": round(elapsed, 1),
            }

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2, default=str)

            logger.info("Debug trace written: %s", filepath)

            run.trace["debug_trace_meta"] = {
                "enabled": True,
                "file": filepath,
                "file_written": True,
                "schema_version": 2,
                "steps_count": len(agent_steps),
            }
        except Exception as exc:
            logger.warning("Failed to write debug trace: %s", exc)

    async def _run_deterministic(self, agent_name: str, toolkit, context_msg: Msg) -> Msg:
        """Run agent tools deterministically without LLM — returns raw tool results."""
        from app.services.agentscope.toolkit import AGENT_TOOL_MAP
        from app.services.mcp.client import get_mcp_client

        client = get_mcp_client()
        tool_ids = AGENT_TOOL_MAP.get(agent_name, [])
        results = {}
        for tool_id in tool_ids:
            try:
                # Call with empty kwargs — preset_kwargs will fill OHLC
                result = await client.call_tool(tool_id, {})
                results[tool_id] = result
            except Exception as exc:
                results[tool_id] = {"error": str(exc)}

        text = json.dumps(results, default=str)
        return Msg(agent_name, f"[deterministic] {text}", "assistant")

    async def execute(self, db, run, pair: str, timeframe: str, risk_percent: float,
                      metaapi_account_ref: str | None = None):
        start_time = time.time()

        try:
            from app.services.llm.model_selector import AgentModelSelector
            model_selector = AgentModelSelector()

            provider, model_name, base_url, api_key = self._resolve_provider_config(db)
            logger.info("LLM config: provider=%s, model=%s, base_url=%s", provider, model_name, base_url)
            model = build_model(provider, model_name, base_url, api_key)
            chat_fmt = build_formatter(provider, multi_agent=False, base_url=base_url)
            debate_fmt = build_formatter(provider, multi_agent=True, base_url=base_url)

            # Resolve market data (MetaAPI primary, YFinance fallback)
            market_data = await self._resolve_market_data(db, pair, timeframe, metaapi_account_ref)
            context_msg = self._build_context_msg(pair, timeframe, market_data)
            ohlc = market_data.get("ohlc", {})
            snapshot = market_data.get("snapshot", {})

            logger.info(
                "Market data: pair=%s, tf=%s, bars=%d, source=%s, degraded=%s",
                pair, timeframe, len(ohlc.get("closes", [])),
                snapshot.get("market_data_source", "unknown"),
                snapshot.get("degraded", True),
            )

            # Check LLM enabled per agent
            llm_enabled: dict[str, bool] = {}
            for name in ALL_AGENT_FACTORIES:
                enabled = model_selector.is_enabled(db, name)
                llm_enabled[name] = enabled
                if not enabled:
                    logger.info("LLM disabled for agent %s — will run deterministic", name)

            # Build toolkits with OHLC preset
            toolkits = {}
            for name in ALL_AGENT_FACTORIES:
                toolkits[name] = await build_toolkit(name, ohlc=ohlc)

            # Build agents (only for LLM-enabled agents)
            agents: dict[str, Any] = {}
            for name, factory in ALL_AGENT_FACTORIES.items():
                if not llm_enabled.get(name, False):
                    continue  # Skip — will use deterministic path
                is_debate = name in ("bullish-researcher", "bearish-researcher", "trader-agent")
                agents[name] = factory(
                    model=model,
                    formatter=debate_fmt if is_debate else chat_fmt,
                    toolkit=toolkits[name],
                    sys_prompt=self._get_sys_prompt(name, db),
                )

            analysis_outputs: dict[str, dict] = {}

            # Store tool invocations per agent (filled after each call)
            agent_tool_invocations: dict[str, dict] = {}

            async def _call_agent(name: str, msg: Msg) -> Msg:
                """Call agent via LLM (with structured output) or deterministic."""
                if name in agents:
                    schema = AGENT_STRUCTURED_MODELS.get(name)
                    if schema:
                        result = await agents[name](msg, structured_model=schema)
                    else:
                        result = await agents[name](msg)
                    # Extract tool invocations from agent memory
                    agent_tool_invocations[name] = await _extract_tool_invocations(agents[name])
                    return result
                return await self._run_deterministic(name, toolkits.get(name), msg)

            # ── Phase 1: Parallel analysts ──
            logger.info("Phase 1: Running 3 analysts in parallel for %s/%s", pair, timeframe)
            t0 = time.time()
            analyst_names = ["technical-analyst", "news-analyst", "market-context-analyst"]

            # Use fanout for LLM agents, gather for mixed
            phase1_tasks = [_call_agent(n, context_msg) for n in analyst_names]
            phase1_results = await asyncio.gather(*phase1_tasks)
            phase1_ms = (time.time() - t0) * 1000

            for i, name in enumerate(analyst_names):
                invocations = agent_tool_invocations.get(name, {})
                msg_dict = _msg_to_dict(
                    phase1_results[i] if i < len(phase1_results) else None,
                    tool_invocations=invocations,
                )
                msg_dict["llm_enabled"] = llm_enabled.get(name, False)
                analysis_outputs[name] = msg_dict
                self._record_step(db, run, name,
                    {"pair": pair, "timeframe": timeframe, "llm_enabled": llm_enabled.get(name, False)},
                    msg_dict, elapsed_ms=phase1_ms / len(analyst_names))

            analysis_summary = "\n\n".join(
                f"[{msg.name}]\n{msg.get_text_content()}" for msg in phase1_results
            )
            research_msg = Msg("system",
                f"Analysis results from Phase 1:\n{analysis_summary}\n\n"
                f"Original context:\n{context_msg.get_text_content()}", "system")

            # ── Phase 2+3: Researchers + Debate ──
            logger.info("Phase 2+3: Running debate for %s/%s", pair, timeframe)
            t0 = time.time()

            # Check if debate agents have LLM — if any is disabled, skip debate
            debate_agents_enabled = all(
                llm_enabled.get(n, False)
                for n in ("bullish-researcher", "bearish-researcher", "trader-agent")
            )

            if debate_agents_enabled:
                bullish_msg, bearish_msg, debate_result = await run_debate(
                    bullish=agents["bullish-researcher"],
                    bearish=agents["bearish-researcher"],
                    moderator=agents["trader-agent"],
                    context_msg=research_msg, config=DebateConfig(),
                )
            else:
                # Deterministic: run researchers without debate
                bullish_msg = await _call_agent("bullish-researcher", research_msg)
                bearish_msg = await _call_agent("bearish-researcher", research_msg)
                debate_result = DebateResult(
                    finished=True, winning_side="neutral", confidence=0.5,
                    reason="Debate skipped — LLM disabled for debate agents",
                )
            debate_ms = (time.time() - t0) * 1000

            for name, msg in [("bullish-researcher", bullish_msg), ("bearish-researcher", bearish_msg)]:
                d = _msg_to_dict(msg, tool_invocations=agent_tool_invocations.get(name, {}))
                d["llm_enabled"] = llm_enabled.get(name, False)
                analysis_outputs[name] = d
                self._record_step(db, run, name,
                    {"phase": "debate", "llm_enabled": llm_enabled.get(name, False)},
                    d, elapsed_ms=debate_ms / 2)

            # ── Phase 4: Sequential decision ──
            logger.info("Phase 4: Trader -> Risk -> Execution for %s/%s", pair, timeframe)
            decision_context = (
                f"Make a trading decision for {pair} on {timeframe}.\n\n"
                f"Debate result: {debate_result.winning_side} "
                f"(confidence={debate_result.confidence}, reason={debate_result.reason})\n\n"
                f"Bullish thesis:\n{bullish_msg.get_text_content()}\n\n"
                f"Bearish thesis:\n{bearish_msg.get_text_content()}\n\n"
                f"Phase 1 analysis:\n{analysis_summary}"
            )
            current_msg = Msg("system", decision_context, "system")
            for name in ["trader-agent", "risk-manager", "execution-manager"]:
                t0 = time.time()
                current_msg = await _call_agent(name, current_msg)
                step_ms = (time.time() - t0) * 1000
                d = _msg_to_dict(current_msg, tool_invocations=agent_tool_invocations.get(name, {}))
                d["llm_enabled"] = llm_enabled.get(name, False)
                analysis_outputs[name] = d
                self._record_step(db, run, name,
                    {"phase": "decision", "llm_enabled": llm_enabled.get(name, False)},
                    d, elapsed_ms=step_ms)

            # ── Build decision in frontend-compatible format ──
            elapsed = time.time() - start_time
            logger.info("Pipeline completed for %s/%s in %.1fs", pair, timeframe, elapsed)

            trader_out = analysis_outputs.get("trader-agent", {})
            risk_out = analysis_outputs.get("risk-manager", {})
            exec_out = analysis_outputs.get("execution-manager", {})

            # Determine trade decision from debate + trader output
            signal = debate_result.winning_side or "neutral"
            trade_decision = "HOLD"
            if signal == "bullish":
                trade_decision = "BUY"
            elif signal == "bearish":
                trade_decision = "SELL"

            run.status = "completed"
            run.decision = {
                # Frontend reads these exact fields
                "decision": trade_decision,
                "signal": signal,
                "confidence": debate_result.confidence,
                "execution_allowed": trade_decision != "HOLD",
                "execution": {
                    "status": "skipped" if trade_decision == "HOLD" else "simulation",
                },
                # Debate details
                "debate": {
                    "finished": debate_result.finished,
                    "winning_side": debate_result.winning_side,
                    "confidence": debate_result.confidence,
                    "reason": debate_result.reason,
                },
                # Agent summaries
                "trader_summary": trader_out.get("text", "")[:500],
                "risk_summary": risk_out.get("text", "")[:500],
                "execution_summary": exec_out.get("text", "")[:500],
                # Merge trader metadata if structured output was used
                **trader_out.get("metadata", {}),
            }
            run.trace = {
                "runtime_engine": "agentscope_v1",
                "elapsed_seconds": round(elapsed, 1),
                "market_data_source": snapshot.get("market_data_source", "unknown"),
                "market_data_bars": len(ohlc.get("closes", [])),
                "market_snapshot": snapshot,
                "debate_rounds": 3,
                "debate_finished": debate_result.finished,
                "debate_winner": debate_result.winning_side,
                "analysis_outputs": {
                    k: {"text": v.get("text", "")[:300]} for k, v in analysis_outputs.items()
                },
            }

            # ── Debug trace JSON file ──
            self._write_debug_trace(run, pair, timeframe, risk_percent,
                                    market_data, analysis_outputs, elapsed)

            db.commit()

        except Exception as exc:
            logger.exception("Pipeline failed for %s/%s: %s", pair, timeframe, exc)
            run.status = "failed"
            run.error = str(exc)
            db.commit()
            raise

        return run
