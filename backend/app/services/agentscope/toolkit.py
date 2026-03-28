"""Per-agent Toolkit builder — maps agent names to MCP tool subsets."""
from __future__ import annotations

import functools
import inspect
import json
import logging
from typing import Any

from agentscope.tool import Toolkit, ToolResponse
from agentscope.message import TextBlock

from app.services.mcp.client import get_mcp_client

logger = logging.getLogger(__name__)

AGENT_TOOL_MAP: dict[str, list[str]] = {
    "technical-analyst": [
        "indicator_bundle", "divergence_detector", "pattern_detector",
        "support_resistance_detector", "multi_timeframe_context",
        "technical_scoring",
    ],
    "news-analyst": [
        "news_search", "macro_event_feed", "sentiment_parser",
        "symbol_relevance_filter", "news_evidence_scoring",
        "news_validation",
    ],
    "market-context-analyst": [
        "market_regime_detector", "session_context",
        "volatility_analyzer", "correlation_analyzer",
    ],
    "bullish-researcher": ["evidence_query", "thesis_support_extractor"],
    "bearish-researcher": ["evidence_query", "thesis_support_extractor"],
    "trader-agent": [
        "scenario_validation", "decision_gating",
        "contradiction_detector", "trade_sizing",
    ],
    "risk-manager": ["position_size_calculator", "risk_evaluation"],
    "execution-manager": ["market_snapshot"],
}


def _build_docstring(tool_id: str, original_fn) -> str:
    """Build a docstring with proper Args section from the original function signature."""
    sig = inspect.signature(original_fn)
    doc_lines = [original_fn.__doc__.strip().split("\n")[0] if original_fn.__doc__ else f"Execute the {tool_id} tool."]
    doc_lines.append("")
    doc_lines.append("Args:")

    for pname, p in sig.parameters.items():
        ann = p.annotation
        if ann is inspect.Parameter.empty:
            type_str = "Any"
        elif hasattr(ann, "__name__"):
            type_str = ann.__name__
        else:
            type_str = str(ann).replace("typing.", "")

        if p.default is not inspect.Parameter.empty:
            doc_lines.append(f"    {pname} ({type_str}):")
            doc_lines.append(f"        Default: {p.default!r}")
        else:
            doc_lines.append(f"    {pname} ({type_str}):")
            doc_lines.append(f"        Required parameter.")

    return "\n".join(doc_lines)


def _wrap_mcp_tool(tool_id: str, original_fn) -> Any:
    """Create an async wrapper that preserves the original function's signature.

    AgentScope parses function signatures and docstrings to build JSON schemas.
    By copying the real signature, the LLM sees the actual parameter names and types.
    """
    client = get_mcp_client()
    sig = inspect.signature(original_fn)

    @functools.wraps(original_fn)
    async def tool_fn(*args: Any, **kwargs: Any) -> ToolResponse:
        # Bind positional args to parameter names
        bound = sig.bind(*args, **kwargs)
        bound.apply_defaults()
        result = await client.call_tool(tool_id, dict(bound.arguments))
        return ToolResponse(
            content=[TextBlock(type="text", text=json.dumps(result, default=str))],
        )

    # Override docstring with a clean Args section for AgentScope parsing
    tool_fn.__doc__ = _build_docstring(tool_id, original_fn)
    return tool_fn


async def build_toolkit(agent_name: str) -> Toolkit:
    """Build a Toolkit with the MCP tools assigned to the given agent."""
    from app.services.mcp import trading_server

    toolkit = Toolkit()
    tool_ids = AGENT_TOOL_MAP.get(agent_name, [])

    for tool_id in tool_ids:
        original_fn = getattr(trading_server, tool_id, None)
        if original_fn is None:
            logger.warning("MCP tool %s not found in trading_server, skipping", tool_id)
            continue
        toolkit.register_tool_function(_wrap_mcp_tool(tool_id, original_fn))

    return toolkit
