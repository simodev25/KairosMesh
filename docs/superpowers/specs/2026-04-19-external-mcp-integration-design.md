# External MCP Integration — Design Spec

**Date:** 2026-04-19  
**Feature:** Add support for external MCP servers (HTTP/SSE) in the AI model system config  
**Scope:** ConnectorsPage UI + backend connector API + toolkit builder

---

## Summary

Add the ability to connect external MCP servers (HTTP/SSE transport) to specific agents in the system. External MCP tools appear alongside internal tools in the agent configuration section, with the same activate/deactivate toggle mechanism.

---

## 1. Data Model

External MCP servers are stored inside the existing `connector_configs.settings` JSON (no new DB table). A new top-level key `external_mcps` holds all registered servers.

### Schema

```json
{
  "external_mcps": [
    {
      "id": "uuid-v4",
      "name": "My Finance MCP",
      "url": "http://localhost:8001/sse",
      "headers": { "Authorization": "Bearer xxx" },
      "assigned_agents": ["technical-analyst", "risk-manager"],
      "discovered_tools": [
        {
          "tool_id": "ext__my-finance-mcp__get_earnings",
          "label": "Get Earnings",
          "description": "Fetch earnings data for a symbol",
          "discovery_status": "ok"
        }
      ],
      "last_discovery_at": "2026-04-19T10:00:00Z",
      "discovery_status": "ok | error | pending"
    }
  ],
  "agent_tools": {
    "technical-analyst": {
      "indicator_bundle": true,
      "ext__my-finance-mcp__get_earnings": false
    }
  }
}
```

### Key decisions

- **Tool ID prefix:** `ext__{mcp_name}__{tool_name}` — prevents collisions with internal tool IDs. If two external MCPs share the same name, the first 4 chars of the UUID are appended as suffix.
- **Tool cache:** `discovered_tools` stores the last known tool list so the agent toolkit can be built even when the MCP server is temporarily unavailable.
- **agent_tools extension:** External tool IDs are merged into the existing `agent_tools` per-agent map — same toggle mechanism as internal tools.
- **Headers:** Stored as-is in the JSON settings, same security level as other credentials in the system.

---

## 2. Backend

### New files

**`backend/app/services/mcp/external_client.py`**

Async HTTP/SSE client for external MCP servers.

```python
class ExternalMCPClient:
    async def discover_tools(url: str, headers: dict) -> list[ToolMeta]
    async def call_tool(url: str, headers: dict, tool_id: str, kwargs: dict) -> dict
```

- Uses `httpx` async client
- `discover_tools` calls `POST /tools/list` (MCP standard spec)
- `call_tool` calls `POST /tools/call`
- Raises `ExternalMCPUnavailableError` on connection failure

**`backend/app/services/mcp/external_registry.py`**

Process-level cache/registry that maps tool IDs to their MCP server config.

```python
class ExternalMCPRegistry:
    def get_tools_for_agent(agent_name: str, settings: dict) -> list[ToolMeta]
    async def call_tool(tool_id: str, kwargs: dict, settings: dict) -> dict
```

- Resolves which MCP server owns a given `ext__*` tool ID via prefix parsing
- Called by `build_toolkit()` during agent initialization

### Modified files

**`backend/app/api/routes/connectors.py`** — 2 new endpoints:

| Endpoint | Method | Body | Purpose |
|----------|--------|------|---------|
| `/connectors/external-mcp/discover` | POST | `{url, headers}` | Query remote MCP, return tool list |
| `/connectors/external-mcp` | PUT | `{id?, name, url, headers, assigned_agents}` | Save MCP server + merge tool IDs into agent_tools |

The existing `_sanitize_ollama_settings()` is extended to handle `external_mcps` normalization.

**`backend/app/services/llm/model_selector.py`**

`resolve_enabled_tools(db, agent_name)` extended to include external tool IDs that are enabled for the given agent.

**`backend/app/services/agentscope/toolkit.py`**

`build_toolkit(agent_name, ...)` extended: after registering internal tools, iterates external MCP servers assigned to the agent, wraps their tools via `ExternalMCPClient.call_tool`, registers them in the toolkit.

If a MCP server is unreachable at toolkit build time, the tool is registered with a wrapper that returns a clear error message to the LLM (agent does not crash).

### Save flow

```
POST /connectors/external-mcp/discover
  → ExternalMCPClient.discover_tools(url, headers)
  → returns [{tool_id, label, description}]

PUT /connectors/external-mcp
  → validates payload
  → stores in settings.external_mcps
  → merges ext__ tool IDs into settings.agent_tools[agent] (default: false)
  → rebuilds agent_tools_catalog
```

---

## 3. Frontend

### Layout change (ConnectorsPage.tsx)

In each agent's tool configuration section, a new subsection **"External MCPs"** is added below the internal tools list:

```
┌─ technical-analyst ──────────────────────────────────────────┐
│  Internal Tools                                               │
│  ● indicator_bundle        [ON ]                             │
│  ● divergence_detector     [OFF]                             │
│                                                               │
│  ── External MCPs ───────────────────────────────────────────│
│  [+ Add MCP Server]                                           │
│                                                               │
│  ▼ My Finance MCP  http://localhost:8001  [● OK]  [Refresh] [✕]│
│     ● ext__my-finance-mcp__get_earnings  [OFF]               │
│     ● ext__my-finance-mcp__get_balance   [ON ]               │
└───────────────────────────────────────────────────────────────┘
```

### New state

```typescript
const [externalMcps, setExternalMcps] = useState<ExternalMcpConfig[]>([])
const [mcpAddModal, setMcpAddModal] = useState<{ agent: string } | null>(null)
const [discoveringMcp, setDiscoveringMcp] = useState(false)
```

### New types

```typescript
interface ExternalMcpConfig {
  id: string
  name: string
  url: string
  headers: Record<string, string>
  assigned_agents: string[]
  discovered_tools: ExternalMcpTool[]
  discovery_status: 'ok' | 'error' | 'pending'
  last_discovery_at: string | null
}

interface ExternalMcpTool {
  tool_id: string
  label: string
  description: string
  discovery_status: 'ok' | 'error'
}
```

### New component: `ExternalMcpPanel`

Props: `agentName`, `mcps: ExternalMcpConfig[]`, `agentTools`, `onToggle`, `onAdd`, `onRemove`, `onRefresh`

Responsibilities:
- Lists MCP servers assigned to this agent with status badge
- "Add MCP" button → opens modal
- Per-tool toggle (reuses existing toggle component)
- "Refresh" button → calls `POST /discover` and updates tool list
- Delete button → removes MCP from agent

### "Add MCP Server" modal

```
┌─ Add External MCP ───────────────────┐
│ Name       [                       ] │
│ URL        [http://...             ] │
│                                      │
│ Headers                              │
│ [+ Add header]                       │
│   Key: [Authorization      ]         │
│   Val: [Bearer xxx         ]         │
│                                      │
│ [Discover Tools]                     │
│                                      │
│ ✓ get_earnings  Fetch earnings data  │
│ ✓ get_balance   Account balance      │
│                                      │
│              [Cancel]  [Save]        │
└──────────────────────────────────────┘
```

Flow:
1. User fills name + URL + headers
2. Clicks "Discover Tools" → `POST /connectors/external-mcp/discover`
3. Tool list appears (read-only in modal, all shown)
4. "Save" → `PUT /connectors/external-mcp` with `assigned_agents: [currentAgent]`
5. Tools appear in agent section as toggles (all off by default)

---

## 4. Error Handling & Edge Cases

| Scenario | Behavior |
|----------|----------|
| MCP down at discovery time | `POST /discover` returns 502 with message → modal shows "Serveur inaccessible" |
| MCP down at agent init | Tool registered with error-returning wrapper — agent continues, LLM gets error message on call |
| MCP down at tool call | `ExternalMCPUnavailableError` caught → returns `{"error": "MCP server unavailable: <url>"}` to LLM |
| Tool name collision (two MCPs same name) | Suffix with first 4 chars of UUID: `ext__my-mcp-a1b2__tool` |
| MCP removed while agent running | Tool wrapper returns error, agent continues |
| Re-discovery adds new tools | "Refresh" button → new tools added to catalog (off by default), removed tools marked stale |

---

## 5. Out of Scope

- MCP authentication beyond custom headers (OAuth, mTLS)
- stdio transport
- Per-call dynamic tool discovery (tools are cached at save time)
- MCP server health monitoring / alerting
- Sharing MCP servers across agents via a global registry (per-agent assignment only)
