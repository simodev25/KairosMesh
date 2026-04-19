"""HTTP JSON-RPC client for external MCP servers (Streamable HTTP transport).

MCP Streamable HTTP protocol requires a 3-step handshake before each session:
  1. POST initialize  → server returns mcp-session-id in response header
  2. POST notifications/initialized  → tells server client is ready
  3. POST tools/list | tools/call  → actual request, same session ID

Responses arrive as SSE (text/event-stream), parsed as:
  event: message\\ndata: {"jsonrpc":"2.0",...}
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

logger = logging.getLogger(__name__)

DISCOVER_TIMEOUT = 15.0
CALL_TIMEOUT = 30.0

_MCP_ACCEPT = "application/json, text/event-stream"
_MCP_CLIENT_INFO = {"name": "MultiAgentTrading", "version": "1.0"}


class ExternalMCPUnavailableError(Exception):
    """Raised when an external MCP server cannot be reached."""


def _normalize_base_url(url: str) -> str:
    """Normalise URL: add trailing slash (required by Streamable HTTP), strip /sse suffix."""
    url = url.rstrip("/").removesuffix("/sse")
    return url + "/"


def make_tool_id(mcp_name: str, tool_name: str, suffix: str = "") -> str:
    """Build a collision-safe tool ID: ext__{name-slug}__{tool_name}."""
    slug = re.sub(r"[^a-z0-9-]", "-", mcp_name.lower()).strip("-")
    slug = re.sub(r"-+", "-", slug)
    slug = slug or "unknown"
    if suffix:
        slug = f"{slug}-{suffix}"
    return f"ext__{slug}__{tool_name}"


def _parse_sse_data(text: str) -> dict[str, Any]:
    """Parse first data line from SSE response body."""
    for line in text.splitlines():
        if line.startswith("data:"):
            raw = line[5:].strip()
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                pass
    # Fallback: try parsing entire text as JSON (non-SSE servers)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}


def _extract_text_content(content: list[dict]) -> Any:
    """Extract parsed value from MCP content array."""
    for block in content:
        if block.get("type") == "text":
            text = block.get("text", "")
            try:
                return json.loads(text)
            except (json.JSONDecodeError, TypeError):
                return text
    return {}


async def _mcp_handshake(
    client: httpx.AsyncClient,
    base: str,
    extra_headers: dict[str, str],
) -> str:
    """Perform MCP initialize handshake, return session ID."""
    init_payload = {
        "jsonrpc": "2.0",
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": _MCP_CLIENT_INFO,
        },
        "id": 1,
    }
    resp = await client.post(
        base,
        json=init_payload,
        headers={"Accept": _MCP_ACCEPT, **extra_headers},
    )
    resp.raise_for_status()
    session_id = resp.headers.get("mcp-session-id", "")
    if not session_id:
        raise ExternalMCPUnavailableError(
            f"MCP server at {base} did not return mcp-session-id — "
            "may not support Streamable HTTP transport"
        )

    # Notify server that client initialisation is complete
    notif_payload = {
        "jsonrpc": "2.0",
        "method": "notifications/initialized",
        "params": {},
    }
    await client.post(
        base,
        json=notif_payload,
        headers={"Accept": _MCP_ACCEPT, "mcp-session-id": session_id, **extra_headers},
    )
    return session_id


async def _mcp_request(
    client: httpx.AsyncClient,
    base: str,
    session_id: str,
    payload: dict,
    extra_headers: dict[str, str],
) -> dict[str, Any]:
    """Send a JSON-RPC request in an established MCP session, return parsed response."""
    resp = await client.post(
        base,
        json=payload,
        headers={"Accept": _MCP_ACCEPT, "mcp-session-id": session_id, **extra_headers},
    )
    resp.raise_for_status()
    return _parse_sse_data(resp.text)


class ExternalMCPClient:
    """Async Streamable-HTTP client for external MCP servers (JSON-RPC 2.0)."""

    async def discover_tools(self, url: str, headers: dict[str, str]) -> list[dict[str, Any]]:
        """Initialize a session with the MCP server and return its tool list.

        Returns list of dicts with keys: name, description, inputSchema.
        Raises ExternalMCPUnavailableError on connection or protocol errors.
        """
        base = _normalize_base_url(url)
        try:
            async with httpx.AsyncClient(timeout=DISCOVER_TIMEOUT, follow_redirects=True) as client:
                session_id = await _mcp_handshake(client, base, headers)
                data = await _mcp_request(
                    client, base, session_id,
                    {"jsonrpc": "2.0", "method": "tools/list", "id": 2},
                    headers,
                )
        except ExternalMCPUnavailableError:
            raise
        except httpx.HTTPStatusError as exc:
            raise ExternalMCPUnavailableError(f"HTTP {exc.response.status_code} from {base}") from exc
        except (httpx.ConnectError, httpx.TimeoutException, httpx.RequestError) as exc:
            raise ExternalMCPUnavailableError(f"Cannot reach MCP server at {base}: {exc}") from exc

        if "error" in data:
            err = data.get("error", {})
            msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
            raise ExternalMCPUnavailableError(f"MCP server returned JSON-RPC error: {msg}")

        result = data.get("result", {})
        tools = result.get("tools", [])
        if not isinstance(tools, list):
            raise ExternalMCPUnavailableError(f"Unexpected tools/list response from {base}")
        return tools

    async def call_tool(
        self,
        url: str,
        headers: dict[str, str],
        tool_name: str,
        kwargs: dict[str, Any],
    ) -> Any:
        """Initialize a session and call a tool. Returns parsed result.

        On connection failure returns {"error": "..."} instead of raising,
        so the agent toolkit degrades gracefully.
        """
        base = _normalize_base_url(url)
        try:
            async with httpx.AsyncClient(timeout=CALL_TIMEOUT, follow_redirects=True) as client:
                session_id = await _mcp_handshake(client, base, headers)
                data = await _mcp_request(
                    client, base, session_id,
                    {
                        "jsonrpc": "2.0",
                        "method": "tools/call",
                        "params": {"name": tool_name, "arguments": kwargs},
                        "id": 2,
                    },
                    headers,
                )
        except (httpx.ConnectError, httpx.TimeoutException, httpx.RequestError) as exc:
            return {"error": f"MCP server unavailable at {base}: {exc}"}
        except httpx.HTTPStatusError as exc:
            return {"error": f"HTTP {exc.response.status_code} from {base}"}
        except ExternalMCPUnavailableError as exc:
            return {"error": str(exc)}

        if "error" in data:
            err = data["error"]
            return {"error": f"MCP error: {err.get('message', err)}"}

        result = data.get("result", {})
        content = result.get("content", [])
        if content:
            return _extract_text_content(content)
        return result
