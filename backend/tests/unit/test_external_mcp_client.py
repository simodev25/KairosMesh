import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.mcp.external_client import ExternalMCPClient, ExternalMCPUnavailableError, make_tool_id


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
    mock_response = {
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
        }
    }
    with patch("httpx.AsyncClient") as MockClient:
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json = MagicMock(return_value=mock_response)
        MockClient.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)

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
        MockClient.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)

        client = ExternalMCPClient()
        with pytest.raises(ExternalMCPUnavailableError):
            await client.discover_tools("http://localhost:8001", {})


@pytest.mark.asyncio
async def test_call_tool_returns_result():
    mock_response = {
        "result": {
            "content": [{"type": "text", "text": '{"earnings": 1.5}'}]
        }
    }
    with patch("httpx.AsyncClient") as MockClient:
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json = MagicMock(return_value=mock_response)
        MockClient.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)

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
    mock_response = {"error": {"code": -32601, "message": "Method not found"}}
    with patch("httpx.AsyncClient") as MockClient:
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json = MagicMock(return_value=mock_response)
        MockClient.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)

        client = ExternalMCPClient()
        with pytest.raises(ExternalMCPUnavailableError) as exc_info:
            await client.discover_tools("http://localhost:8001", {})
        assert "Method not found" in str(exc_info.value)
