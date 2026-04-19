"""HTTP JSON-RPC client for external MCP servers (Streamable HTTP / SSE transport)."""
from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

logger = logging.getLogger(__name__)

DISCOVER_TIMEOUT = 10.0
CALL_TIMEOUT = 30.0


class ExternalMCPUnavailableError(Exception):
    """Raised when an external MCP server cannot be reached."""


def _normalize_base_url(url: str) -> str:
    """Strip trailing /sse from URL — we POST JSON-RPC directly to the base."""
    return url.rstrip("/").removesuffix("/sse")


def make_tool_id(mcp_name: str, tool_name: str, suffix: str = "") -> str:
    """Build a collision-safe tool ID: ext__{name-slug}__{tool_name}."""
    slug = re.sub(r"[^a-z0-9-]", "-", mcp_name.lower()).strip("-")
    slug = re.sub(r"-+", "-", slug)
    if suffix:
        slug = f"{slug}-{suffix}"
    return f"ext__{slug}__{tool_name}"


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


class ExternalMCPClient:
    """Async HTTP client for external MCP servers using JSON-RPC 2.0."""

    async def discover_tools(self, url: str, headers: dict[str, str]) -> list[dict[str, Any]]:
        """Call tools/list on the MCP server and return raw tool dicts.

        Returns list of dicts with keys: name, description, inputSchema.
        Raises ExternalMCPUnavailableError on connection or HTTP errors.
        """
        base = _normalize_base_url(url)
        payload = {"jsonrpc": "2.0", "method": "tools/list", "params": {}, "id": 1}
        try:
            async with httpx.AsyncClient(timeout=DISCOVER_TIMEOUT) as client:
                resp = await client.post(base, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPStatusError as exc:
            raise ExternalMCPUnavailableError(f"HTTP {exc.response.status_code} from {base}") from exc
        except (httpx.ConnectError, httpx.TimeoutException, httpx.RequestError) as exc:
            raise ExternalMCPUnavailableError(f"Cannot reach MCP server at {base}: {exc}") from exc

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
    ) -> dict[str, Any]:
        """Call a tool on the MCP server. Returns parsed result dict.

        On connection failure returns {"error": "..."} instead of raising,
        so the agent toolkit degrades gracefully.
        """
        base = _normalize_base_url(url)
        payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": kwargs},
            "id": 1,
        }
        try:
            async with httpx.AsyncClient(timeout=CALL_TIMEOUT) as client:
                resp = await client.post(base, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
        except (httpx.ConnectError, httpx.TimeoutException, httpx.RequestError) as exc:
            return {"error": f"MCP server unavailable at {base}: {exc}"}
        except httpx.HTTPStatusError as exc:
            return {"error": f"HTTP {exc.response.status_code} from {base}"}

        if "error" in data:
            err = data["error"]
            return {"error": f"MCP error: {err.get('message', err)}"}

        result = data.get("result", {})
        content = result.get("content", [])
        if content:
            return _extract_text_content(content)
        return result
