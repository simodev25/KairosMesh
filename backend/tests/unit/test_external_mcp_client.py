import json

import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.mcp.external_client import ExternalMCPClient, ExternalMCPUnavailableError, make_tool_id


def _sse_text(payload: dict) -> str:
    """Wrap a JSON-RPC payload as SSE text (event: message\\ndata: ...)."""
    return f"event: message\ndata: {json.dumps(payload)}\n\n"


def _mock_handshake_resp(session_id: str = "test-session-123") -> MagicMock:
    """Return a mock response that satisfies the MCP initialize handshake."""
    init_resp = MagicMock()
    init_resp.raise_for_status = MagicMock()
    init_resp.headers = {"mcp-session-id": session_id}
    init_resp.text = _sse_text({
        "jsonrpc": "2.0",
        "id": 1,
        "result": {"protocolVersion": "2024-11-05", "capabilities": {}, "serverInfo": {"name": "test", "version": "1.0"}},
    })
    return init_resp


def _mock_notif_resp() -> MagicMock:
    """Return a mock response for the notifications/initialized POST."""
    notif_resp = MagicMock()
    notif_resp.raise_for_status = MagicMock()
    notif_resp.headers = {}
    notif_resp.text = ""
    return notif_resp


def test_make_tool_id_basic():
    result = make_tool_id("My Finance MCP", "get_earnings")
    assert result == "ext__my-finance-mcp__get_earnings"


def test_make_tool_id_strips_special_chars():
    result = make_tool_id("Finance & Co!", "fetch_data")
    assert result.startswith("ext__")
    assert "__fetch_data" in result
    slug = result.split("__")[1]
    assert all(c.isalnum() or c == "-" for c in slug)


@pytest.mark.asyncio
async def test_discover_tools_parses_mcp_response():
    tools_payload = {
        "jsonrpc": "2.0",
        "id": 2,
        "result": {
            "tools": [
                {
                    "name": "get_earnings",
                    "description": "Fetch earnings data",
                    "inputSchema": {
                        "type": "object",
                        "properties": {"symbol": {"type": "string"}},
                        "required": ["symbol"],
                    },
                }
            ]
        },
    }
    tools_resp = MagicMock()
    tools_resp.raise_for_status = MagicMock()
    tools_resp.headers = {}
    tools_resp.text = _sse_text(tools_payload)

    # 3-call sequence: initialize → notifications/initialized → tools/list
    with patch("httpx.AsyncClient") as MockClient:
        MockClient.return_value.__aenter__.return_value.post = AsyncMock(
            side_effect=[_mock_handshake_resp(), _mock_notif_resp(), tools_resp]
        )
        client = ExternalMCPClient()
        tools = await client.discover_tools("http://localhost:8001", {})

    assert len(tools) == 1
    assert tools[0]["name"] == "get_earnings"
    assert tools[0]["description"] == "Fetch earnings data"
    assert "inputSchema" in tools[0]


@pytest.mark.asyncio
async def test_discover_tools_raises_on_http_error():
    with patch("httpx.AsyncClient") as MockClient:
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError("404", request=MagicMock(), response=MagicMock())
        )
        mock_resp.headers = {}
        MockClient.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)

        client = ExternalMCPClient()
        with pytest.raises(ExternalMCPUnavailableError):
            await client.discover_tools("http://localhost:8001", {})


@pytest.mark.asyncio
async def test_call_tool_returns_result():
    tool_result_payload = {
        "jsonrpc": "2.0",
        "id": 2,
        "result": {
            "content": [{"type": "text", "text": '{"earnings": 1.5}'}]
        },
    }
    tool_resp = MagicMock()
    tool_resp.raise_for_status = MagicMock()
    tool_resp.headers = {}
    tool_resp.text = _sse_text(tool_result_payload)

    with patch("httpx.AsyncClient") as MockClient:
        MockClient.return_value.__aenter__.return_value.post = AsyncMock(
            side_effect=[_mock_handshake_resp(), _mock_notif_resp(), tool_resp]
        )
        client = ExternalMCPClient()
        result = await client.call_tool("http://localhost:8001", {}, "get_earnings", {"symbol": "AAPL"})

    assert result == {"earnings": 1.5}


@pytest.mark.asyncio
async def test_call_tool_returns_error_dict_on_unavailable():
    with patch("httpx.AsyncClient") as MockClient:
        MockClient.return_value.__aenter__.return_value.post = AsyncMock(
            side_effect=httpx.ConnectError("Connection refused")
        )
        client = ExternalMCPClient()
        result = await client.call_tool("http://localhost:8001", {}, "get_earnings", {"symbol": "AAPL"})

    assert "error" in result
    assert "unavailable" in result["error"].lower()


@pytest.mark.asyncio
async def test_discover_tools_raises_on_jsonrpc_error():
    error_payload = {"jsonrpc": "2.0", "id": 2, "error": {"code": -32601, "message": "Method not found"}}
    error_resp = MagicMock()
    error_resp.raise_for_status = MagicMock()
    error_resp.headers = {}
    error_resp.text = _sse_text(error_payload)

    with patch("httpx.AsyncClient") as MockClient:
        MockClient.return_value.__aenter__.return_value.post = AsyncMock(
            side_effect=[_mock_handshake_resp(), _mock_notif_resp(), error_resp]
        )
        client = ExternalMCPClient()
        with pytest.raises(ExternalMCPUnavailableError) as exc_info:
            await client.discover_tools("http://localhost:8001", {})
    assert "Method not found" in str(exc_info.value)


@pytest.mark.asyncio
async def test_discover_tools_raises_on_missing_session_id():
    """Handshake fails when server returns no mcp-session-id header."""
    bad_init_resp = MagicMock()
    bad_init_resp.raise_for_status = MagicMock()
    bad_init_resp.headers = {}  # No mcp-session-id
    bad_init_resp.text = ""

    with patch("httpx.AsyncClient") as MockClient:
        MockClient.return_value.__aenter__.return_value.post = AsyncMock(return_value=bad_init_resp)
        client = ExternalMCPClient()
        with pytest.raises(ExternalMCPUnavailableError) as exc_info:
            await client.discover_tools("http://localhost:8001", {})
    assert "mcp-session-id" in str(exc_info.value).lower()
