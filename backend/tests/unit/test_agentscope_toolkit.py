import pytest

pytest.importorskip("agentscope")

from app.services.agentscope.toolkit import (
    AGENT_TOOL_MAP,
    _build_risk_tool_trader_decision,
    build_toolkit,
)
from app.services.mcp.client import get_mcp_client


def test_agent_tool_map_has_all_agents():
    expected = {
        "technical-analyst", "news-analyst", "market-context-analyst",
        "bullish-researcher", "bearish-researcher", "trader-agent",
        "risk-manager", "execution-manager", "strategy-designer",
    }
    assert set(AGENT_TOOL_MAP.keys()) == expected


def test_agent_tool_map_tools_exist_in_mcp():
    client = get_mcp_client()
    all_tools = client.list_tools()
    for agent_name, tool_ids in AGENT_TOOL_MAP.items():
        for tool_id in tool_ids:
            assert tool_id in all_tools, f"{tool_id} not found in MCP for {agent_name}"


@pytest.mark.asyncio
async def test_build_toolkit_returns_toolkit():
    toolkit = await build_toolkit("technical-analyst")
    schemas = toolkit.get_json_schemas()
    assert len(schemas) > 0
    tool_names = {s["function"]["name"] for s in schemas}
    assert "indicator_bundle" in tool_names


@pytest.mark.asyncio
async def test_build_toolkit_unknown_agent_empty():
    toolkit = await build_toolkit("unknown-agent")
    schemas = toolkit.get_json_schemas()
    assert len(schemas) == 0


def test_build_risk_tool_trader_decision_injects_runtime_modes():
    trader_out = {
        "decision": "BUY",
        "entry": 1.15535,
        "stop_loss": 1.15466,
        "take_profit": 1.1565,
        "pair": "EURUSD.PRO",
        "asset_class": "forex",
    }

    result = _build_risk_tool_trader_decision(
        trader_out,
        decision_mode="permissive",
        execution_mode="live",
    )

    assert result["decision"] == "BUY"
    assert result["mode"] == "live"
    assert result["decision_mode"] == "permissive"


# --- External MCP tool injection tests ---

@pytest.mark.asyncio
async def test_build_toolkit_with_external_mcp_tools():
    """External MCP tools appear in the toolkit when enabled."""
    from unittest.mock import AsyncMock, patch
    from app.services.mcp.external_client import ExternalMCPClient

    external_configs = [
        {
            'tool_id': 'ext__finance-mcp__get_earnings',
            'label': 'Get Earnings',
            'description': 'Fetch earnings data for a symbol.\n\nArgs:\n    symbol (str):\n        The stock symbol.',
            'input_schema': {
                'type': 'object',
                'properties': {'symbol': {'type': 'string', 'description': 'Stock symbol'}},
                'required': ['symbol'],
            },
            'url': 'http://localhost:8001',
            'headers': {},
            'enabled': True,
        }
    ]

    with patch.object(ExternalMCPClient, 'call_tool', new_callable=AsyncMock) as mock_call:
        mock_call.return_value = {'earnings': 1.5}
        toolkit = await build_toolkit('technical-analyst', external_mcp_tools=external_configs)
        schemas = toolkit.get_json_schemas()

    tool_names = {s['function']['name'] for s in schemas}
    assert 'ext__finance-mcp__get_earnings' in tool_names


@pytest.mark.asyncio
async def test_build_toolkit_skips_disabled_external_tools():
    """External MCP tools with enabled=False are not added to the toolkit."""
    external_configs = [
        {
            'tool_id': 'ext__finance-mcp__get_earnings',
            'label': 'Get Earnings',
            'description': 'Disabled tool.',
            'input_schema': {},
            'url': 'http://localhost:8001',
            'headers': {},
            'enabled': False,
        }
    ]
    toolkit = await build_toolkit('technical-analyst', external_mcp_tools=external_configs)
    schemas = toolkit.get_json_schemas()
    tool_names = {s['function']['name'] for s in schemas}
    assert 'ext__finance-mcp__get_earnings' not in tool_names
