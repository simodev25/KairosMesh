# External MCP Integration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow users to connect external MCP servers (HTTP/SSE transport) to specific agents via the ConnectorsPage, with dynamic tool discovery and the same activate/deactivate toggle as internal tools.

**Architecture:** External MCPs are stored in `connector_configs.settings.external_mcps` (same DB, no new table). Tools are discovered via JSON-RPC POST at save time, cached in settings, and injected into `build_toolkit()` via a new optional parameter. External tool IDs are prefixed `ext__{name-slug}__{tool_name}` to prevent collisions.

**Tech Stack:** Python (FastAPI, httpx, agentscope), React + TypeScript (frontend)

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `backend/app/services/mcp/external_client.py` | HTTP JSON-RPC client for external MCP servers |
| Create | `backend/tests/unit/test_external_mcp_client.py` | Unit tests for ExternalMCPClient |
| Modify | `backend/app/services/llm/model_selector.py` | normalize/validate/catalog for ext__ tools |
| Modify | `backend/tests/unit/test_agent_model_selector.py` | Tests for ext__ tool handling |
| Modify | `backend/app/api/routes/connectors.py` | 2 new endpoints + sanitize external_mcps |
| Modify | `backend/tests/unit/test_connectors_settings_sanitization.py` | Tests for new endpoints and sanitization |
| Modify | `backend/app/services/agentscope/toolkit.py` | external_mcp_configs param + wrapper |
| Modify | `backend/tests/unit/test_agentscope_toolkit.py` | Tests for external tool injection |
| Modify | `backend/app/services/agentscope/registry.py` | Pass external MCPs to build_toolkit |
| Modify | `backend/app/services/governance/registry.py` | Pass external MCPs to build_toolkit |
| Modify | `frontend/src/types/index.ts` | ExternalMcpConfig, ExternalMcpTool types |
| Modify | `frontend/src/api/client.ts` | discoverExternalMcp, saveExternalMcp, deleteExternalMcp |
| Create | `frontend/src/components/ExternalMcpPanel.tsx` | Per-agent external MCP list + toggles |
| Create | `frontend/src/components/AddExternalMcpModal.tsx` | Add/discover MCP server modal |
| Modify | `frontend/src/pages/ConnectorsPage.tsx` | Wire state + render ExternalMcpPanel |

---

## Task 1: ExternalMCPClient — HTTP JSON-RPC client

**Files:**
- Create: `backend/app/services/mcp/external_client.py`
- Create: `backend/tests/unit/test_external_mcp_client.py`

- [ ] **Step 1.1: Write the failing tests**

```python
# backend/tests/unit/test_external_mcp_client.py
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
    # No special chars in slug
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
        mock_resp.raise_for_status = MagicMock(side_effect=httpx.HTTPStatusError("404", request=MagicMock(), response=MagicMock()))
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
```

- [ ] **Step 1.2: Run tests to verify they fail**

```bash
cd /Users/mbensass/projetPreso/MultiAgentTrading/backend
python -m pytest tests/unit/test_external_mcp_client.py -v 2>&1 | head -30
```
Expected: `ModuleNotFoundError: No module named 'app.services.mcp.external_client'`

- [ ] **Step 1.3: Implement ExternalMCPClient**

Create `backend/app/services/mcp/external_client.py`:

```python
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
```

- [ ] **Step 1.4: Run tests to verify they pass**

```bash
cd /Users/mbensass/projetPreso/MultiAgentTrading/backend
python -m pytest tests/unit/test_external_mcp_client.py -v
```
Expected: 5 tests PASSED

- [ ] **Step 1.5: Commit**

```bash
git add backend/app/services/mcp/external_client.py backend/tests/unit/test_external_mcp_client.py
git commit -m "feat: add ExternalMCPClient for HTTP JSON-RPC external MCP servers"
```

---

## Task 2: Extend model_selector for external tool IDs

External tool IDs (`ext__*`) must pass through `normalize_agent_tools_settings()` and `validate_agent_tools_payload()` without being rejected. We also need a helper to load external MCP configs from settings.

**Files:**
- Modify: `backend/app/services/llm/model_selector.py`
- Modify: `backend/tests/unit/test_agent_model_selector.py`

- [ ] **Step 2.1: Write the failing tests**

Open `backend/tests/unit/test_agent_model_selector.py` and add at the end:

```python
# --- External MCP tool ID tests ---

from app.services.llm.model_selector import (
    get_external_tools_for_agent,
    normalize_external_mcps,
    validate_agent_tools_payload,
)


def test_validate_agent_tools_allows_ext_prefix():
    """ext__ prefixed tool IDs must not trigger validation errors."""
    payload = {
        "technical-analyst": {
            "indicator_bundle": True,
            "ext__my-finance-mcp__get_earnings": False,
        }
    }
    issues = validate_agent_tools_payload(payload)
    assert issues == [], f"Unexpected issues: {issues}"


def test_normalize_external_mcps_returns_empty_on_none():
    result = normalize_external_mcps(None)
    assert result == []


def test_normalize_external_mcps_filters_invalid():
    raw = [
        {"id": "abc", "name": "Good MCP", "url": "http://localhost:8001", "headers": {}, "assigned_agents": ["technical-analyst"], "discovered_tools": []},
        {"name": "missing url"},  # invalid — no url
        "not a dict",
    ]
    result = normalize_external_mcps(raw)
    assert len(result) == 1
    assert result[0]["name"] == "Good MCP"


def test_get_external_tools_for_agent_filters_by_assignment():
    settings = {
        "external_mcps": [
            {
                "id": "abc",
                "name": "Finance MCP",
                "url": "http://localhost:8001",
                "headers": {},
                "assigned_agents": ["technical-analyst"],
                "discovered_tools": [
                    {"tool_id": "ext__finance-mcp__get_earnings", "label": "Get Earnings", "description": "...", "input_schema": {}, "discovery_status": "ok"}
                ],
                "discovery_status": "ok",
            }
        ],
        "agent_tools": {
            "technical-analyst": {"ext__finance-mcp__get_earnings": True}
        }
    }
    tools = get_external_tools_for_agent("technical-analyst", settings)
    assert len(tools) == 1
    assert tools[0]["tool_id"] == "ext__finance-mcp__get_earnings"
    assert tools[0]["enabled"] is True
    assert tools[0]["url"] == "http://localhost:8001"


def test_get_external_tools_for_agent_excludes_other_agents():
    settings = {
        "external_mcps": [
            {
                "id": "abc",
                "name": "Finance MCP",
                "url": "http://localhost:8001",
                "headers": {},
                "assigned_agents": ["news-analyst"],  # NOT technical-analyst
                "discovered_tools": [
                    {"tool_id": "ext__finance-mcp__get_earnings", "label": "Get Earnings", "description": "...", "input_schema": {}, "discovery_status": "ok"}
                ],
                "discovery_status": "ok",
            }
        ],
        "agent_tools": {}
    }
    tools = get_external_tools_for_agent("technical-analyst", settings)
    assert tools == []
```

- [ ] **Step 2.2: Run tests to verify they fail**

```bash
cd /Users/mbensass/projetPreso/MultiAgentTrading/backend
python -m pytest tests/unit/test_agent_model_selector.py -v -k "ext or external" 2>&1 | tail -20
```
Expected: ImportError on `get_external_tools_for_agent`, `normalize_external_mcps`

- [ ] **Step 2.3: Implement changes in model_selector.py**

**Change 1** — In `validate_agent_tools_payload()`, allow `ext__` prefixed tool IDs (currently line ~355 raises error for unknown tools):

Find this block in `validate_agent_tools_payload()`:
```python
        for raw_tool_id, raw_tool_payload in raw_agent_tools_map.items():
            tool_id = str(raw_tool_id or '').strip()
            if not tool_id:
                continue
            if tool_id in allowed_tools:
                continue
            if _extract_tool_enabled_value(raw_tool_payload, fallback=False):
                issues.append(
                    f"Tool '{tool_id}' is not allowed for agent '{agent_name}'."
                )
```

Replace the last 3 lines with:
```python
            if tool_id in allowed_tools:
                continue
            if tool_id.startswith("ext__"):
                continue  # External MCP tools are always allowed
            if _extract_tool_enabled_value(raw_tool_payload, fallback=False):
                issues.append(
                    f"Tool '{tool_id}' is not allowed for agent '{agent_name}'."
                )
```

**Change 2** — Add two new functions at the end of the module (before the `AgentModelSelector` class):

```python
def normalize_external_mcps(raw: object) -> list[dict]:
    """Validate and return list of well-formed external MCP server configs."""
    if not isinstance(raw, list):
        return []
    result = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        if not item.get("url") or not item.get("name"):
            continue
        result.append({
            "id": str(item.get("id") or ""),
            "name": str(item["name"]),
            "url": str(item["url"]),
            "headers": dict(item.get("headers") or {}),
            "assigned_agents": [str(a) for a in (item.get("assigned_agents") or []) if a],
            "discovered_tools": list(item.get("discovered_tools") or []),
            "discovery_status": str(item.get("discovery_status") or "pending"),
            "last_discovery_at": item.get("last_discovery_at"),
        })
    return result


def get_external_tools_for_agent(agent_name: str, settings: dict) -> list[dict]:
    """Return enabled external tool descriptors for an agent.

    Each returned dict has: tool_id, label, description, input_schema,
    url, headers, enabled (bool).
    """
    external_mcps = normalize_external_mcps(settings.get("external_mcps"))
    agent_tool_state: dict[str, bool] = {}
    raw_agent_tools = settings.get("agent_tools")
    if isinstance(raw_agent_tools, dict):
        raw_for_agent = raw_agent_tools.get(agent_name, {})
        if isinstance(raw_for_agent, dict):
            agent_tool_state = {k: bool(v) for k, v in raw_for_agent.items() if k.startswith("ext__")}

    result = []
    for mcp in external_mcps:
        if agent_name not in mcp["assigned_agents"]:
            continue
        for tool in mcp["discovered_tools"]:
            if not isinstance(tool, dict):
                continue
            tool_id = str(tool.get("tool_id") or "")
            if not tool_id:
                continue
            enabled = agent_tool_state.get(tool_id, False)
            result.append({
                "tool_id": tool_id,
                "label": str(tool.get("label") or tool_id),
                "description": str(tool.get("description") or ""),
                "input_schema": tool.get("input_schema") or {},
                "url": mcp["url"],
                "headers": mcp["headers"],
                "enabled": enabled,
            })
    return result
```

- [ ] **Step 2.4: Run tests to verify they pass**

```bash
cd /Users/mbensass/projetPreso/MultiAgentTrading/backend
python -m pytest tests/unit/test_agent_model_selector.py -v -k "ext or external"
```
Expected: 5 tests PASSED

- [ ] **Step 2.5: Run full test suite to check for regressions**

```bash
cd /Users/mbensass/projetPreso/MultiAgentTrading/backend
python -m pytest tests/unit/test_agent_model_selector.py tests/unit/test_connectors_settings_sanitization.py -v 2>&1 | tail -20
```
Expected: all PASSED

- [ ] **Step 2.6: Commit**

```bash
git add backend/app/services/llm/model_selector.py backend/tests/unit/test_agent_model_selector.py
git commit -m "feat: allow ext__ tool IDs in model_selector + add external MCP helpers"
```

---

## Task 3: API endpoints — discover and save external MCPs

**Files:**
- Modify: `backend/app/api/routes/connectors.py`
- Modify: `backend/tests/unit/test_connectors_settings_sanitization.py`

- [ ] **Step 3.1: Write the failing tests**

Add at the end of `backend/tests/unit/test_connectors_settings_sanitization.py`:

```python
# --- External MCP endpoint tests ---
import uuid
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from app.main import app


def _auth_headers():
    """Return auth headers for test (uses existing test auth setup)."""
    # The test suite uses dependency overrides for auth — just pass a dummy token
    return {"Authorization": "Bearer test-token"}


def test_sanitize_ollama_settings_preserves_external_mcps():
    settings = {
        "provider": "ollama",
        "external_mcps": [
            {
                "id": "test-id",
                "name": "Finance MCP",
                "url": "http://localhost:8001",
                "headers": {},
                "assigned_agents": ["technical-analyst"],
                "discovered_tools": [],
                "discovery_status": "ok",
            }
        ],
    }
    result = _sanitize_ollama_settings(settings)
    assert "external_mcps" in result
    assert len(result["external_mcps"]) == 1
    assert result["external_mcps"][0]["name"] == "Finance MCP"


def test_sanitize_ollama_settings_filters_invalid_external_mcps():
    settings = {
        "provider": "ollama",
        "external_mcps": [
            {"name": "no url"},  # invalid
            {"url": "http://localhost:8001", "name": "valid", "assigned_agents": [], "headers": {}, "discovered_tools": [], "id": "x"},
        ],
    }
    result = _sanitize_ollama_settings(settings)
    assert len(result["external_mcps"]) == 1


@pytest.mark.asyncio
async def test_discover_external_mcp_endpoint_returns_tools():
    """POST /connectors/external-mcp/discover returns tools from MCP server."""
    from app.api.routes.connectors import discover_external_mcp

    mock_tools = [
        {"name": "get_earnings", "description": "Fetch earnings", "inputSchema": {"type": "object", "properties": {}}}
    ]
    with patch("app.api.routes.connectors.ExternalMCPClient") as MockClient:
        instance = MockClient.return_value
        instance.discover_tools = AsyncMock(return_value=mock_tools)

        from app.schemas.connector import ExternalMcpDiscoverRequest
        req = ExternalMcpDiscoverRequest(url="http://localhost:8001", headers={})
        result = await discover_external_mcp(req)

    assert result["status"] == "ok"
    assert len(result["tools"]) == 1
    assert result["tools"][0]["name"] == "get_earnings"


@pytest.mark.asyncio
async def test_discover_external_mcp_endpoint_returns_error_on_unavailable():
    from app.api.routes.connectors import discover_external_mcp
    from app.services.mcp.external_client import ExternalMCPUnavailableError

    with patch("app.api.routes.connectors.ExternalMCPClient") as MockClient:
        instance = MockClient.return_value
        instance.discover_tools = AsyncMock(side_effect=ExternalMCPUnavailableError("Connection refused"))

        from app.schemas.connector import ExternalMcpDiscoverRequest
        req = ExternalMcpDiscoverRequest(url="http://bad-host:9999", headers={})
        with pytest.raises(Exception) as exc_info:
            await discover_external_mcp(req)
        assert "502" in str(exc_info.value) or "unavailable" in str(exc_info.value).lower()
```

- [ ] **Step 3.2: Run tests to verify they fail**

```bash
cd /Users/mbensass/projetPreso/MultiAgentTrading/backend
python -m pytest tests/unit/test_connectors_settings_sanitization.py -v -k "external_mcp or external" 2>&1 | tail -20
```
Expected: ImportError / AttributeError

- [ ] **Step 3.3: Add ExternalMcpDiscoverRequest schema**

Open `backend/app/schemas/connector.py`. Find the existing Pydantic models and add at the end:

```python
class ExternalMcpDiscoverRequest(BaseModel):
    url: str
    headers: dict[str, str] = {}


class ExternalMcpSaveRequest(BaseModel):
    id: str | None = None          # None = new server
    name: str
    url: str
    headers: dict[str, str] = {}
    assigned_agents: list[str] = []
    discovered_tools: list[dict] = []


class ExternalMcpDeleteRequest(BaseModel):
    id: str
    agent_name: str                # Remove from this agent's assignment
```

- [ ] **Step 3.4: Add new endpoints and extend _sanitize_ollama_settings in connectors.py**

**Change 1** — Add imports at the top of `backend/app/api/routes/connectors.py`:

After the existing imports, add:
```python
from app.services.mcp.external_client import ExternalMCPClient, ExternalMCPUnavailableError
from app.services.llm.model_selector import normalize_external_mcps
from app.schemas.connector import ExternalMcpDiscoverRequest, ExternalMcpSaveRequest, ExternalMcpDeleteRequest
```

**Change 2** — Extend `_sanitize_ollama_settings()`. Find the `return settings` at the end of the function and add before it:

```python
    # Preserve and normalize external MCP server configs
    settings['external_mcps'] = normalize_external_mcps(settings.get('external_mcps'))
    return settings
```

**Change 3** — Add two new route functions before the closing of the router. Add after the existing `list_connectors` function block (around line 260):

```python
@router.post('/external-mcp/discover')
async def discover_external_mcp(
    payload: ExternalMcpDiscoverRequest,
    _=Depends(require_roles(Role.SUPER_ADMIN, Role.ADMIN)),
) -> dict:
    """Query an external MCP server and return its tool list."""
    client = ExternalMCPClient()
    try:
        tools = await client.discover_tools(payload.url, payload.headers)
    except ExternalMCPUnavailableError as exc:
        raise HTTPException(status_code=502, detail=f"MCP server unavailable: {exc}")
    return {"status": "ok", "tools": tools, "count": len(tools)}


@router.put('/external-mcp')
def save_external_mcp(
    payload: ExternalMcpSaveRequest,
    db: Session = Depends(get_db),
    _=Depends(require_roles(Role.SUPER_ADMIN, Role.ADMIN)),
) -> dict:
    """Save or update an external MCP server config for the ollama connector.

    - Creates new entry if payload.id is None
    - Updates existing entry if payload.id matches
    - Merges discovered tool IDs into agent_tools (default: disabled)
    """
    import uuid as _uuid

    conn = db.query(ConnectorConfig).filter(ConnectorConfig.connector_name == 'ollama').first()
    if not conn:
        conn = ConnectorConfig(connector_name='ollama', enabled=True, settings={})
        db.add(conn)

    settings = dict(conn.settings or {})
    external_mcps: list[dict] = list(settings.get('external_mcps') or [])
    agent_tools: dict = dict(settings.get('agent_tools') or {})

    # Build the MCP entry
    mcp_id = payload.id or str(_uuid.uuid4())
    entry = {
        "id": mcp_id,
        "name": payload.name,
        "url": payload.url,
        "headers": payload.headers,
        "assigned_agents": payload.assigned_agents,
        "discovered_tools": payload.discovered_tools,
        "discovery_status": "ok" if payload.discovered_tools else "pending",
        "last_discovery_at": None,
    }

    # Replace or insert
    idx = next((i for i, m in enumerate(external_mcps) if m.get("id") == mcp_id), None)
    if idx is not None:
        external_mcps[idx] = entry
    else:
        external_mcps.append(entry)

    # Merge ext__ tool IDs into agent_tools (disabled by default)
    for agent_name in payload.assigned_agents:
        if agent_name not in agent_tools:
            agent_tools[agent_name] = {}
        for tool in payload.discovered_tools:
            tool_id = str(tool.get("tool_id") or "")
            if tool_id and tool_id not in agent_tools[agent_name]:
                agent_tools[agent_name][tool_id] = False  # off by default

    settings['external_mcps'] = external_mcps
    settings['agent_tools'] = agent_tools
    conn.settings = _sanitize_ollama_settings(settings)
    db.commit()
    db.refresh(conn)
    AgentModelSelector.clear_cache()
    return {"status": "ok", "id": mcp_id}


@router.delete('/external-mcp/{mcp_id}')
def delete_external_mcp(
    mcp_id: str,
    agent_name: str,
    db: Session = Depends(get_db),
    _=Depends(require_roles(Role.SUPER_ADMIN, Role.ADMIN)),
) -> dict:
    """Remove an external MCP server from an agent (or entirely if no agents remain)."""
    conn = db.query(ConnectorConfig).filter(ConnectorConfig.connector_name == 'ollama').first()
    if not conn:
        raise HTTPException(status_code=404, detail="Ollama connector not found")

    settings = dict(conn.settings or {})
    external_mcps: list[dict] = list(settings.get('external_mcps') or [])
    agent_tools: dict = dict(settings.get('agent_tools') or {})

    # Find the MCP entry
    entry = next((m for m in external_mcps if m.get("id") == mcp_id), None)
    if not entry:
        raise HTTPException(status_code=404, detail=f"External MCP {mcp_id} not found")

    # Remove agent from assigned_agents
    entry["assigned_agents"] = [a for a in entry.get("assigned_agents", []) if a != agent_name]

    # Remove ext__ tool IDs from this agent's tool state
    if agent_name in agent_tools and isinstance(agent_tools[agent_name], dict):
        tool_ids_to_remove = {t.get("tool_id") for t in entry.get("discovered_tools", [])}
        agent_tools[agent_name] = {
            k: v for k, v in agent_tools[agent_name].items()
            if k not in tool_ids_to_remove
        }

    # If no agents left, remove the MCP entry entirely
    if not entry["assigned_agents"]:
        external_mcps = [m for m in external_mcps if m.get("id") != mcp_id]

    settings['external_mcps'] = external_mcps
    settings['agent_tools'] = agent_tools
    conn.settings = _sanitize_ollama_settings(settings)
    db.commit()
    AgentModelSelector.clear_cache()
    return {"status": "ok"}
```

- [ ] **Step 3.5: Run the tests**

```bash
cd /Users/mbensass/projetPreso/MultiAgentTrading/backend
python -m pytest tests/unit/test_connectors_settings_sanitization.py -v -k "external_mcp or external" 2>&1 | tail -20
```
Expected: 4 tests PASSED

- [ ] **Step 3.6: Run broader regression check**

```bash
cd /Users/mbensass/projetPreso/MultiAgentTrading/backend
python -m pytest tests/unit/test_connectors_settings_sanitization.py tests/unit/test_agent_model_selector.py -v 2>&1 | tail -15
```
Expected: all PASSED

- [ ] **Step 3.7: Commit**

```bash
git add backend/app/api/routes/connectors.py backend/app/schemas/connector.py backend/tests/unit/test_connectors_settings_sanitization.py
git commit -m "feat: add external MCP discover/save/delete endpoints"
```

---

## Task 4: Extend build_toolkit for external tools

**Files:**
- Modify: `backend/app/services/agentscope/toolkit.py`
- Modify: `backend/tests/unit/test_agentscope_toolkit.py`

- [ ] **Step 4.1: Write the failing tests**

Add at the end of `backend/tests/unit/test_agentscope_toolkit.py`:

```python
# --- External MCP tool injection tests ---

@pytest.mark.asyncio
async def test_build_toolkit_with_external_mcp_tools():
    """External MCP tools appear in the toolkit when enabled."""
    from unittest.mock import AsyncMock, patch
    from app.services.mcp.external_client import ExternalMCPClient

    external_configs = [
        {
            "tool_id": "ext__finance-mcp__get_earnings",
            "label": "Get Earnings",
            "description": "Fetch earnings data for a symbol.\n\nArgs:\n    symbol (str):\n        The stock symbol.",
            "input_schema": {
                "type": "object",
                "properties": {"symbol": {"type": "string", "description": "Stock symbol"}},
                "required": ["symbol"],
            },
            "url": "http://localhost:8001",
            "headers": {},
            "enabled": True,
        }
    ]

    with patch.object(ExternalMCPClient, "call_tool", new_callable=AsyncMock) as mock_call:
        mock_call.return_value = {"earnings": 1.5}
        toolkit = await build_toolkit("technical-analyst", external_mcp_tools=external_configs)
        schemas = toolkit.get_json_schemas()

    tool_names = {s["function"]["name"] for s in schemas}
    assert "ext__finance-mcp__get_earnings" in tool_names


@pytest.mark.asyncio
async def test_build_toolkit_skips_disabled_external_tools():
    """External MCP tools with enabled=False are not added to the toolkit."""
    external_configs = [
        {
            "tool_id": "ext__finance-mcp__get_earnings",
            "label": "Get Earnings",
            "description": "Disabled tool.",
            "input_schema": {},
            "url": "http://localhost:8001",
            "headers": {},
            "enabled": False,  # disabled
        }
    ]
    toolkit = await build_toolkit("technical-analyst", external_mcp_tools=external_configs)
    schemas = toolkit.get_json_schemas()
    tool_names = {s["function"]["name"] for s in schemas}
    assert "ext__finance-mcp__get_earnings" not in tool_names
```

- [ ] **Step 4.2: Run tests to verify they fail**

```bash
cd /Users/mbensass/projetPreso/MultiAgentTrading/backend
python -m pytest tests/unit/test_agentscope_toolkit.py -v -k "external" 2>&1 | tail -15
```
Expected: TypeError — `build_toolkit()` got unexpected keyword argument `external_mcp_tools`

- [ ] **Step 4.3: Implement external tool wrapping in toolkit.py**

**Change 1** — Add import at top of `backend/app/services/agentscope/toolkit.py`:

After `from app.services.mcp.client import get_mcp_client`, add:
```python
from app.services.mcp.external_client import ExternalMCPClient
```

**Change 2** — Add the external tool wrapper function after `_wrap_mcp_tool`:

```python
def _wrap_external_mcp_tool(tool_descriptor: dict) -> Any:
    """Create an async wrapper for a remote MCP tool.

    Unlike internal tools, external tools have no local function signature.
    We build a docstring from the MCP inputSchema and accept **kwargs.
    """
    tool_id = tool_descriptor["tool_id"]
    url = tool_descriptor["url"]
    headers = tool_descriptor["headers"]
    # Extract bare tool name (part after last __)
    bare_name = tool_id.split("__")[-1] if "__" in tool_id else tool_id
    description = tool_descriptor.get("description") or f"Call external MCP tool {bare_name}."
    input_schema = tool_descriptor.get("input_schema") or {}
    properties = input_schema.get("properties") or {}
    required = set(input_schema.get("required") or [])

    # Build Args docstring for AgentScope
    doc_lines = [description, "", "Args:"]
    for param_name, param_meta in properties.items():
        type_str = param_meta.get("type", "Any")
        param_desc = param_meta.get("description", "")
        req_note = "Required." if param_name in required else "Optional."
        doc_lines.append(f"    {param_name} ({type_str}):")
        doc_lines.append(f"        {param_desc} {req_note}".strip())
    docstring = "\n".join(doc_lines)

    ext_client = ExternalMCPClient()

    async def tool_fn(**kwargs: Any) -> ToolResponse:
        try:
            result = await ext_client.call_tool(url, headers, bare_name, kwargs)
            return ToolResponse(
                content=[TextBlock(type="text", text=json.dumps(result, default=str))],
            )
        except Exception as exc:
            logger.warning("External MCP tool %s failed: %s", tool_id, exc, exc_info=True)
            error_result = {"error": f"{type(exc).__name__}: {exc}", "tool_id": tool_id}
            return ToolResponse(
                content=[TextBlock(type="text", text=json.dumps(error_result, default=str))],
            )

    tool_fn.__name__ = tool_id
    tool_fn.__doc__ = docstring
    return tool_fn
```

**Change 3** — Add `external_mcp_tools` parameter to `build_toolkit()`:

Find the function signature:
```python
async def build_toolkit(
    agent_name: str,
    ohlc: dict[str, list[float]] | None = None,
    ...
    execution_mode: str | None = None,
) -> Toolkit:
```

Add the new parameter after `execution_mode`:
```python
    external_mcp_tools: list[dict] | None = None,
```

**Change 4** — Add external tool registration at the end of `build_toolkit()`, just before `return toolkit`:

```python
    # Register external MCP tools (if any)
    if external_mcp_tools:
        for ext_tool in external_mcp_tools:
            if not ext_tool.get("enabled"):
                continue
            try:
                wrapped = _wrap_external_mcp_tool(ext_tool)
                toolkit.register_tool_function(wrapped)
            except Exception as exc:
                logger.warning("Failed to register external MCP tool %s: %s", ext_tool.get("tool_id"), exc)

    return toolkit
```

- [ ] **Step 4.4: Run tests to verify they pass**

```bash
cd /Users/mbensass/projetPreso/MultiAgentTrading/backend
python -m pytest tests/unit/test_agentscope_toolkit.py -v -k "external" 2>&1 | tail -15
```
Expected: 2 tests PASSED

- [ ] **Step 4.5: Run full toolkit test suite**

```bash
cd /Users/mbensass/projetPreso/MultiAgentTrading/backend
python -m pytest tests/unit/test_agentscope_toolkit.py -v 2>&1 | tail -15
```
Expected: all PASSED

- [ ] **Step 4.6: Commit**

```bash
git add backend/app/services/agentscope/toolkit.py backend/tests/unit/test_agentscope_toolkit.py
git commit -m "feat: inject external MCP tools into agent toolkit via external_mcp_tools param"
```

---

## Task 5: Wire external MCPs into agentscope and governance registries

Both `agentscope/registry.py` and `governance/registry.py` call `build_toolkit()`. We need to load external MCPs from settings and pass them.

**Files:**
- Modify: `backend/app/services/agentscope/registry.py` (lines ~1140, ~1308, ~1707, ~2089)
- Modify: `backend/app/services/governance/registry.py` (lines ~208, ~214)

- [ ] **Step 5.1: Add helper to AgentModelSelector**

In `backend/app/services/llm/model_selector.py`, add this method to the `AgentModelSelector` class (after `resolve_skills`):

```python
    def resolve_external_mcp_tools(self, db: Session | None, agent_name: str) -> list[dict]:
        """Return list of enabled external MCP tool descriptors for an agent."""
        from app.services.llm.model_selector import get_external_tools_for_agent
        settings = self._load_llm_settings(db)
        return get_external_tools_for_agent(agent_name, settings)
```

- [ ] **Step 5.2: Update agentscope/registry.py call sites**

In `backend/app/services/agentscope/registry.py`, find every `await build_toolkit(name, ...)` call.

For each call site that builds toolkits for named agents, add `external_mcp_tools=model_selector.resolve_external_mcp_tools(db, name)` (or `rname` / the appropriate agent name variable) to the call.

**Example — around line 1141:**
```python
# Before:
toolkits[name] = await build_toolkit(
    name, ohlc=ohlc, news=market_data.get("news", {}),
    skills=agent_skills,
    snapshot=snapshot,
    decision_mode=_resolved_decision_mode,
    execution_mode=_resolved_execution_mode,
)

# After:
toolkits[name] = await build_toolkit(
    name, ohlc=ohlc, news=market_data.get("news", {}),
    skills=agent_skills,
    snapshot=snapshot,
    decision_mode=_resolved_decision_mode,
    execution_mode=_resolved_execution_mode,
    external_mcp_tools=model_selector.resolve_external_mcp_tools(db, name),
)
```

Apply the same pattern to the other 3 call sites in agentscope/registry.py (lines ~1308, ~1707, ~2089). For each, use the agent name variable that's in scope for that loop.

- [ ] **Step 5.3: Update governance/registry.py call sites**

In `backend/app/services/governance/registry.py`, update the two `build_toolkit` calls (around lines 208 and 214):

```python
# Around line 208 (inside the for name in phase1_agents_names loop):
toolkits[name] = await build_toolkit(
    name, ohlc=ohlc, news=news, skills=agent_skills,
    snapshot=snapshot, decision_mode="governance", execution_mode="governance",
    external_mcp_tools=selector.resolve_external_mcp_tools(db, name),
)

# Around line 214 (governance-trader):
toolkits["trader-agent"] = await build_toolkit(
    "governance-trader", ohlc=ohlc, news=news, skills=gov_trader_skills,
    snapshot=snapshot, decision_mode="governance", execution_mode="governance",
    external_mcp_tools=selector.resolve_external_mcp_tools(db, "governance-trader"),
)
```

- [ ] **Step 5.4: Run the toolkit tests again to confirm nothing broke**

```bash
cd /Users/mbensass/projetPreso/MultiAgentTrading/backend
python -m pytest tests/unit/test_agentscope_toolkit.py tests/unit/test_agentscope_registry.py -v 2>&1 | tail -15
```
Expected: all PASSED

- [ ] **Step 5.5: Commit**

```bash
git add backend/app/services/agentscope/registry.py backend/app/services/governance/registry.py backend/app/services/llm/model_selector.py
git commit -m "feat: pass external MCP tools to build_toolkit in agentscope and governance registries"
```

---

## Task 6: Frontend — types and API client

**Files:**
- Modify: `frontend/src/types/index.ts`
- Modify: `frontend/src/api/client.ts`

- [ ] **Step 6.1: Add types to frontend/src/types/index.ts**

Find `export interface ConnectorConfig` and add before it:

```typescript
export interface ExternalMcpTool {
  tool_id: string;
  label: string;
  description: string;
  input_schema: Record<string, unknown>;
  discovery_status: 'ok' | 'error';
}

export interface ExternalMcpConfig {
  id: string;
  name: string;
  url: string;
  headers: Record<string, string>;
  assigned_agents: string[];
  discovered_tools: ExternalMcpTool[];
  discovery_status: 'ok' | 'error' | 'pending';
  last_discovery_at: string | null;
}

export interface ExternalMcpDiscoverResult {
  status: string;
  tools: Array<{
    name: string;
    description: string;
    inputSchema: Record<string, unknown>;
  }>;
  count: number;
}
```

- [ ] **Step 6.2: Add API client methods to frontend/src/api/client.ts**

Find `updateConnector:` in `client.ts` and add after it:

```typescript
  discoverExternalMcp: (
    token: string,
    url: string,
    headers: Record<string, string>,
  ) =>
    request<{ status: string; tools: Array<{ name: string; description: string; inputSchema: Record<string, unknown> }>; count: number }>(
      '/connectors/external-mcp/discover',
      { method: 'POST', body: JSON.stringify({ url, headers }) },
      token,
    ),
  saveExternalMcp: (
    token: string,
    payload: {
      id?: string;
      name: string;
      url: string;
      headers: Record<string, string>;
      assigned_agents: string[];
      discovered_tools: Array<{ tool_id: string; label: string; description: string; input_schema: Record<string, unknown>; discovery_status: string }>;
    },
  ) =>
    request<{ status: string; id: string }>('/connectors/external-mcp', {
      method: 'PUT',
      body: JSON.stringify(payload),
    }, token),
  deleteExternalMcp: (token: string, mcpId: string, agentName: string) =>
    request<{ status: string }>(`/connectors/external-mcp/${mcpId}?agent_name=${encodeURIComponent(agentName)}`, {
      method: 'DELETE',
    }, token),
```

- [ ] **Step 6.3: Check TypeScript compiles**

```bash
cd /Users/mbensass/projetPreso/MultiAgentTrading/frontend
npx tsc --noEmit 2>&1 | head -20
```
Expected: no errors related to ExternalMcp types

- [ ] **Step 6.4: Commit**

```bash
git add frontend/src/types/index.ts frontend/src/api/client.ts
git commit -m "feat: add ExternalMcpConfig types and API client methods"
```

---

## Task 7: ExternalMcpPanel component

**Files:**
- Create: `frontend/src/components/ExternalMcpPanel.tsx`

- [ ] **Step 7.1: Create the component**

Create `frontend/src/components/ExternalMcpPanel.tsx`:

```tsx
import { useState } from 'react';
import type { ExternalMcpConfig } from '../types';

interface Props {
  agentName: string;
  mcps: ExternalMcpConfig[];
  agentTools: Record<string, boolean>;  // tool_id -> enabled
  onToggleTool: (toolId: string, enabled: boolean) => void;
  onAddMcp: () => void;
  onDeleteMcp: (mcpId: string) => void;
  onRefreshMcp: (mcp: ExternalMcpConfig) => void;
}

export function ExternalMcpPanel({
  agentName,
  mcps,
  agentTools,
  onToggleTool,
  onAddMcp,
  onDeleteMcp,
  onRefreshMcp,
}: Props) {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const agentMcps = mcps.filter((m) => m.assigned_agents.includes(agentName));

  return (
    <div style={{ marginTop: '1rem', borderTop: '1px solid #334155', paddingTop: '0.75rem' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
        <span style={{ fontSize: '0.75rem', fontWeight: 600, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          External MCPs
        </span>
        <button
          onClick={onAddMcp}
          style={{
            fontSize: '0.75rem',
            padding: '2px 10px',
            background: '#1e293b',
            border: '1px solid #334155',
            borderRadius: '4px',
            color: '#60a5fa',
            cursor: 'pointer',
          }}
        >
          + Add MCP
        </button>
      </div>

      {agentMcps.length === 0 && (
        <p style={{ fontSize: '0.75rem', color: '#475569', fontStyle: 'italic' }}>No external MCPs connected.</p>
      )}

      {agentMcps.map((mcp) => {
        const isExpanded = expandedId === mcp.id;
        const statusColor = mcp.discovery_status === 'ok' ? '#22c55e' : mcp.discovery_status === 'error' ? '#ef4444' : '#94a3b8';

        return (
          <div key={mcp.id} style={{ marginBottom: '0.5rem', background: '#0f172a', borderRadius: '6px', border: '1px solid #1e293b' }}>
            <div
              style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.5rem 0.75rem', cursor: 'pointer' }}
              onClick={() => setExpandedId(isExpanded ? null : mcp.id)}
            >
              <span style={{ fontSize: '0.7rem', color: statusColor }}>●</span>
              <span style={{ fontSize: '0.8rem', fontWeight: 600, color: '#e2e8f0', flex: 1 }}>{mcp.name}</span>
              <span style={{ fontSize: '0.65rem', color: '#475569', flex: 2 }}>{mcp.url}</span>
              <button
                onClick={(e) => { e.stopPropagation(); onRefreshMcp(mcp); }}
                title="Re-discover tools"
                style={{ fontSize: '0.65rem', padding: '1px 6px', background: 'none', border: '1px solid #334155', borderRadius: '3px', color: '#60a5fa', cursor: 'pointer' }}
              >
                ↺
              </button>
              <button
                onClick={(e) => { e.stopPropagation(); onDeleteMcp(mcp.id); }}
                title="Remove from agent"
                style={{ fontSize: '0.65rem', padding: '1px 6px', background: 'none', border: '1px solid #334155', borderRadius: '3px', color: '#f87171', cursor: 'pointer' }}
              >
                ✕
              </button>
              <span style={{ color: '#475569', fontSize: '0.7rem' }}>{isExpanded ? '▲' : '▼'}</span>
            </div>

            {isExpanded && (
              <div style={{ padding: '0.25rem 0.75rem 0.75rem' }}>
                {mcp.discovered_tools.length === 0 && (
                  <p style={{ fontSize: '0.7rem', color: '#475569', fontStyle: 'italic' }}>No tools discovered.</p>
                )}
                {mcp.discovered_tools.map((tool) => {
                  const enabled = agentTools[tool.tool_id] ?? false;
                  return (
                    <div key={tool.tool_id} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '3px 0' }}>
                      <label style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', cursor: 'pointer', flex: 1 }}>
                        <input
                          type="checkbox"
                          checked={enabled}
                          onChange={(e) => onToggleTool(tool.tool_id, e.target.checked)}
                        />
                        <span style={{ fontSize: '0.75rem', color: '#cbd5e1' }}>{tool.label || tool.tool_id}</span>
                      </label>
                      <span style={{ fontSize: '0.65rem', color: '#475569', flex: 2 }}>{tool.description}</span>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 7.2: Check TypeScript compiles**

```bash
cd /Users/mbensass/projetPreso/MultiAgentTrading/frontend
npx tsc --noEmit 2>&1 | grep -i "ExternalMcpPanel\|error" | head -10
```
Expected: no errors

- [ ] **Step 7.3: Commit**

```bash
git add frontend/src/components/ExternalMcpPanel.tsx
git commit -m "feat: add ExternalMcpPanel component for per-agent external MCP display"
```

---

## Task 8: AddExternalMcpModal component

**Files:**
- Create: `frontend/src/components/AddExternalMcpModal.tsx`

- [ ] **Step 8.1: Create the modal component**

Create `frontend/src/components/AddExternalMcpModal.tsx`:

```tsx
import { useState } from 'react';
import { api } from '../api/client';

interface DiscoveredTool {
  name: string;
  description: string;
  inputSchema: Record<string, unknown>;
}

interface Props {
  agentName: string;
  token: string;
  onClose: () => void;
  onSaved: (mcpId: string) => void;
}

export function AddExternalMcpModal({ agentName, token, onClose, onSaved }: Props) {
  const [name, setName] = useState('');
  const [url, setUrl] = useState('');
  const [headers, setHeaders] = useState<Array<{ key: string; value: string }>>([]);
  const [discovering, setDiscovering] = useState(false);
  const [discoveredTools, setDiscoveredTools] = useState<DiscoveredTool[] | null>(null);
  const [discoverError, setDiscoverError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const headersDict = Object.fromEntries(headers.filter((h) => h.key).map((h) => [h.key, h.value]));

  const handleDiscover = async () => {
    if (!url.trim()) return;
    setDiscovering(true);
    setDiscoverError(null);
    setDiscoveredTools(null);
    try {
      const result = await api.discoverExternalMcp(token, url.trim(), headersDict);
      setDiscoveredTools(result.tools);
    } catch (err) {
      setDiscoverError(err instanceof Error ? err.message : 'Failed to reach MCP server');
    } finally {
      setDiscovering(false);
    }
  };

  const handleSave = async () => {
    if (!name.trim() || !url.trim() || !discoveredTools) return;
    setSaving(true);
    try {
      const mcpNameSlug = name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
      const discovered = discoveredTools.map((t) => ({
        tool_id: `ext__${mcpNameSlug}__${t.name}`,
        label: t.name,
        description: t.description,
        input_schema: t.inputSchema,
        discovery_status: 'ok' as const,
      }));
      const result = await api.saveExternalMcp(token, {
        name: name.trim(),
        url: url.trim(),
        headers: headersDict,
        assigned_agents: [agentName],
        discovered_tools: discovered,
      });
      onSaved(result.id);
    } catch (err) {
      setDiscoverError(err instanceof Error ? err.message : 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  const addHeader = () => setHeaders((h) => [...h, { key: '', value: '' }]);
  const updateHeader = (i: number, field: 'key' | 'value', val: string) =>
    setHeaders((h) => h.map((row, idx) => (idx === i ? { ...row, [field]: val } : row)));
  const removeHeader = (i: number) => setHeaders((h) => h.filter((_, idx) => idx !== i));

  const overlay: React.CSSProperties = {
    position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', display: 'flex',
    alignItems: 'center', justifyContent: 'center', zIndex: 1000,
  };
  const modal: React.CSSProperties = {
    background: '#0f172a', border: '1px solid #334155', borderRadius: '8px',
    padding: '1.5rem', width: '480px', maxHeight: '80vh', overflowY: 'auto',
    display: 'flex', flexDirection: 'column', gap: '0.75rem',
  };
  const inputStyle: React.CSSProperties = {
    width: '100%', background: '#1e293b', border: '1px solid #334155',
    borderRadius: '4px', padding: '6px 10px', color: '#e2e8f0', fontSize: '0.85rem',
    boxSizing: 'border-box',
  };
  const labelStyle: React.CSSProperties = { fontSize: '0.75rem', color: '#94a3b8', marginBottom: '2px', display: 'block' };
  const btnPrimary: React.CSSProperties = {
    padding: '6px 16px', background: '#2563eb', border: 'none', borderRadius: '4px',
    color: '#fff', fontSize: '0.85rem', cursor: 'pointer',
  };
  const btnSecondary: React.CSSProperties = {
    padding: '6px 16px', background: '#1e293b', border: '1px solid #334155', borderRadius: '4px',
    color: '#94a3b8', fontSize: '0.85rem', cursor: 'pointer',
  };

  return (
    <div style={overlay} onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div style={modal}>
        <h3 style={{ margin: 0, color: '#e2e8f0', fontSize: '1rem' }}>Add External MCP Server</h3>
        <p style={{ margin: 0, fontSize: '0.75rem', color: '#64748b' }}>Agent: <strong>{agentName}</strong></p>

        <div>
          <label style={labelStyle}>Name</label>
          <input style={inputStyle} value={name} onChange={(e) => setName(e.target.value)} placeholder="My Finance MCP" />
        </div>

        <div>
          <label style={labelStyle}>URL</label>
          <input style={inputStyle} value={url} onChange={(e) => setUrl(e.target.value)} placeholder="http://localhost:8001" />
        </div>

        <div>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
            <label style={{ ...labelStyle, marginBottom: 0 }}>Headers</label>
            <button onClick={addHeader} style={{ ...btnSecondary, padding: '2px 8px', fontSize: '0.7rem' }}>+ Add</button>
          </div>
          {headers.map((h, i) => (
            <div key={i} style={{ display: 'flex', gap: '6px', marginBottom: '4px' }}>
              <input
                style={{ ...inputStyle, flex: 1 }}
                placeholder="Key"
                value={h.key}
                onChange={(e) => updateHeader(i, 'key', e.target.value)}
              />
              <input
                style={{ ...inputStyle, flex: 2 }}
                placeholder="Value"
                value={h.value}
                onChange={(e) => updateHeader(i, 'value', e.target.value)}
              />
              <button onClick={() => removeHeader(i)} style={{ ...btnSecondary, padding: '2px 6px', color: '#f87171' }}>✕</button>
            </div>
          ))}
        </div>

        <button onClick={handleDiscover} disabled={!url.trim() || discovering} style={btnPrimary}>
          {discovering ? 'Discovering...' : 'Discover Tools'}
        </button>

        {discoverError && (
          <p style={{ margin: 0, fontSize: '0.75rem', color: '#ef4444' }}>{discoverError}</p>
        )}

        {discoveredTools !== null && (
          <div>
            <p style={{ margin: '0 0 6px', fontSize: '0.75rem', color: '#94a3b8' }}>
              {discoveredTools.length} tool{discoveredTools.length !== 1 ? 's' : ''} discovered (all disabled by default):
            </p>
            {discoveredTools.map((t) => (
              <div key={t.name} style={{ fontSize: '0.75rem', color: '#cbd5e1', padding: '3px 0', borderBottom: '1px solid #1e293b' }}>
                <strong>{t.name}</strong> — {t.description}
              </div>
            ))}
          </div>
        )}

        <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end', marginTop: '0.5rem' }}>
          <button onClick={onClose} style={btnSecondary}>Cancel</button>
          <button
            onClick={handleSave}
            disabled={!name.trim() || !discoveredTools || saving}
            style={{ ...btnPrimary, opacity: (!name.trim() || !discoveredTools || saving) ? 0.5 : 1 }}
          >
            {saving ? 'Saving...' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 8.2: Check TypeScript compiles**

```bash
cd /Users/mbensass/projetPreso/MultiAgentTrading/frontend
npx tsc --noEmit 2>&1 | grep -i "AddExternalMcpModal\|error" | head -10
```
Expected: no errors

- [ ] **Step 8.3: Commit**

```bash
git add frontend/src/components/AddExternalMcpModal.tsx
git commit -m "feat: add AddExternalMcpModal for discovering and saving external MCP servers"
```

---

## Task 9: Wire into ConnectorsPage

**Files:**
- Modify: `frontend/src/pages/ConnectorsPage.tsx`

- [ ] **Step 9.1: Add imports at the top of ConnectorsPage.tsx**

After the existing imports, add:
```typescript
import type { ExternalMcpConfig } from '../types';
import { ExternalMcpPanel } from '../components/ExternalMcpPanel';
import { AddExternalMcpModal } from '../components/AddExternalMcpModal';
```

- [ ] **Step 9.2: Add new state variables**

Find the block of `useState` declarations (around line 397 where `agentToolCatalog` is declared). Add after `agentTools` state:

```typescript
const [externalMcps, setExternalMcps] = useState<ExternalMcpConfig[]>([]);
const [mcpModal, setMcpModal] = useState<{ agentName: string } | null>(null);
```

- [ ] **Step 9.3: Load external MCPs from connector settings**

Find where `agentTools` is hydrated from the connector settings (search for `setAgentTools` or `agent_tools_catalog`). In the same `useEffect` that loads the `ollama` connector, add:

```typescript
// After the existing agent_tools loading:
const rawExternalMcps = ollamaSettings?.external_mcps;
if (Array.isArray(rawExternalMcps)) {
  setExternalMcps(rawExternalMcps as ExternalMcpConfig[]);
}
```

- [ ] **Step 9.4: Wire tool toggle to include ext__ tools**

The existing `handleToolToggle` (or equivalent) already sets `agentTools[agent][tool_id] = bool`. Since external tool IDs are in the same `agentTools` map, no change is needed here — confirm by searching for where tool toggles are applied.

If the save function constructs `agent_tools` from `agentTools` state before calling `api.updateConnector`, ensure `ext__` keys are NOT filtered out. Search for where `agent_tools` is assembled before the PUT call and verify no filtering excludes `ext__` keys.

- [ ] **Step 9.5: Add refresh handler for external MCPs**

Add this function in the ConnectorsPage component body (after the existing handlers):

```typescript
const handleRefreshExternalMcp = async (mcp: ExternalMcpConfig) => {
  try {
    const result = await api.discoverExternalMcp(token, mcp.url, mcp.headers);
    const mcpNameSlug = mcp.name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
    const discovered = result.tools.map((t) => ({
      tool_id: `ext__${mcpNameSlug}__${t.name}`,
      label: t.name,
      description: t.description,
      input_schema: t.inputSchema,
      discovery_status: 'ok' as const,
    }));
    await api.saveExternalMcp(token, {
      id: mcp.id,
      name: mcp.name,
      url: mcp.url,
      headers: mcp.headers,
      assigned_agents: mcp.assigned_agents,
      discovered_tools: discovered,
    });
    // Reload connector settings to get updated external_mcps
    const connectors = await api.listConnectors(token);
    const ollama = connectors.find((c) => c.connector_name === 'ollama');
    if (ollama && Array.isArray(ollama.settings?.external_mcps)) {
      setExternalMcps(ollama.settings.external_mcps as ExternalMcpConfig[]);
    }
  } catch (err) {
    setError(err instanceof Error ? err.message : 'Refresh failed');
  }
};
```

- [ ] **Step 9.6: Add delete handler**

```typescript
const handleDeleteExternalMcp = async (mcpId: string, agentName: string) => {
  try {
    await api.deleteExternalMcp(token, mcpId, agentName);
    setExternalMcps((prev) =>
      prev
        .map((m) =>
          m.id === mcpId
            ? { ...m, assigned_agents: m.assigned_agents.filter((a) => a !== agentName) }
            : m,
        )
        .filter((m) => m.assigned_agents.length > 0),
    );
  } catch (err) {
    setError(err instanceof Error ? err.message : 'Delete failed');
  }
};
```

- [ ] **Step 9.7: Add modal close/save handler**

```typescript
const handleMcpSaved = async (_mcpId: string) => {
  setMcpModal(null);
  // Reload external MCPs from backend
  try {
    const connectors = await api.listConnectors(token);
    const ollama = connectors.find((c) => c.connector_name === 'ollama');
    if (ollama && Array.isArray(ollama.settings?.external_mcps)) {
      setExternalMcps(ollama.settings.external_mcps as ExternalMcpConfig[]);
    }
    // Also update agentTools to include new ext__ keys
    if (ollama && typeof ollama.settings?.agent_tools === 'object') {
      const rawTools = ollama.settings.agent_tools as Record<string, Record<string, boolean>>;
      setAgentTools((prev) => {
        const updated = { ...prev };
        for (const [agent, tools] of Object.entries(rawTools)) {
          updated[agent] = { ...(updated[agent] || {}), ...tools };
        }
        return updated;
      });
    }
  } catch (_) {
    // Non-critical
  }
};
```

- [ ] **Step 9.8: Render ExternalMcpPanel in the agent section**

Find where agent tool toggles are rendered inside the agent configuration section (search for `agentToolCatalog[agentName]` or similar). After the internal tools toggle list, add:

```tsx
<ExternalMcpPanel
  agentName={agentName}
  mcps={externalMcps}
  agentTools={agentTools[agentName] || {}}
  onToggleTool={(toolId, enabled) =>
    setAgentTools((prev) => ({
      ...prev,
      [agentName]: { ...(prev[agentName] || {}), [toolId]: enabled },
    }))
  }
  onAddMcp={() => setMcpModal({ agentName })}
  onDeleteMcp={(mcpId) => handleDeleteExternalMcp(mcpId, agentName)}
  onRefreshMcp={handleRefreshExternalMcp}
/>
```

- [ ] **Step 9.9: Render the modal**

Near the end of the JSX return, add:

```tsx
{mcpModal && (
  <AddExternalMcpModal
    agentName={mcpModal.agentName}
    token={token}
    onClose={() => setMcpModal(null)}
    onSaved={handleMcpSaved}
  />
)}
```

- [ ] **Step 9.10: Check TypeScript compiles**

```bash
cd /Users/mbensass/projetPreso/MultiAgentTrading/frontend
npx tsc --noEmit 2>&1 | head -20
```
Expected: no errors

- [ ] **Step 9.11: Verify UI in browser**

Start the dev server if not already running:
```bash
cd /Users/mbensass/projetPreso/MultiAgentTrading/frontend
npm run dev
```

Navigate to `http://localhost:5173/connectors` → click the "models" tab → expand any agent section.

Verify:
- "External MCPs" section is visible below the internal tools
- "Add MCP" button opens the modal
- Modal has Name, URL, Headers fields and "Discover Tools" button

- [ ] **Step 9.12: Commit**

```bash
git add frontend/src/pages/ConnectorsPage.tsx
git commit -m "feat: wire ExternalMcpPanel and AddExternalMcpModal into ConnectorsPage"
```

---

## Final check

- [ ] **Run full backend unit test suite**

```bash
cd /Users/mbensass/projetPreso/MultiAgentTrading/backend
python -m pytest tests/unit/ -v --tb=short 2>&1 | tail -30
```
Expected: all PASSED (no new failures)

- [ ] **Run TypeScript check**

```bash
cd /Users/mbensass/projetPreso/MultiAgentTrading/frontend
npx tsc --noEmit 2>&1
```
Expected: no errors

- [ ] **Final integration commit if clean**

```bash
git tag feature/external-mcp-complete
```
