# Contributing

## Development setup

See [Getting Started](docs/getting-started.md) for the full setup guide.

Quick path:
```bash
cp backend/.env.example backend/.env
docker compose up postgres redis rabbitmq -d
make backend-install && make backend-run
make frontend-install && make frontend-run
```

## Running tests

```bash
# All backend tests
make backend-test

# Specific test file
cd backend && python -m pytest tests/unit/test_risk_engine.py -v

# With coverage
cd backend && python -m pytest --cov=app tests/
```

Tests require PostgreSQL and Redis running (start with `docker compose up postgres redis -d`).

## Code organization

| Area | Directory |
|------|-----------|
| Agent pipeline | `backend/app/services/agentscope/` |
| MCP tools | `backend/app/services/mcp/` |
| Risk engine | `backend/app/services/risk/` |
| Execution | `backend/app/services/execution/` |
| API routes | `backend/app/api/routes/` |
| Celery tasks | `backend/app/tasks/` |
| Config | `backend/app/core/config.py` |
| Frontend pages | `frontend/src/pages/` |

## Adding an agent

1. Define a factory function in `backend/app/services/agentscope/agents.py` following the pattern of existing agents
2. Register it in `ALL_AGENT_FACTORIES` dict in `agents.py`
3. Add it to the relevant phase in `AgentScopeRegistry.execute()` in `registry.py`
4. Define its output schema in `schemas.py`
5. Add tests in `backend/tests/`

## Adding an MCP tool

1. Add the tool function to the appropriate module in `backend/app/services/mcp/`
2. Register it in the MCP server initialization
3. Add the tool name to the relevant agent's `tools` list in `agents.py`
4. Add tests for the tool in `backend/tests/`

## Pull request guidelines

- Open an issue before starting large changes
- Keep PRs focused — one concern per PR
- Include tests for new behavior
- Do not change `ALLOW_LIVE_TRADING` defaults in PRs
- Do not add LLM-based execution decision paths — risk governance must remain deterministic

## Commit style

Use conventional commits:
```
feat: add new tool for volatility analysis
fix: correct risk limit calculation for crypto
docs: update configuration reference
refactor: extract decision weights to constants
test: add risk engine edge case tests
```

## Non-goals

Contributions in these areas will be declined without significant prior discussion:
- Removing the deterministic risk layer
- Adding execution paths that bypass preflight
- Storing live credentials or API keys in repository files
- LLM-driven live order submission without additional deterministic gates
