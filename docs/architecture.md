# Architecture

## System overview

Kairos Mesh is a research-and-execution pipeline for structured trading analysis. Each run is a discrete, auditable workflow with deterministic governance applied at the risk and execution stages.

The system is not an autonomous trading bot. Every live order requires: a passing risk engine evaluation, a passing execution preflight, `ALLOW_LIVE_TRADING=true`, and a user with the `TRADER_OPERATOR` role.

```
┌─────────────────────────────────────────────────────────┐
│  React Frontend (Vite + MUI)                            │
│  Terminal · Strategies · Orders · Backtests · Config    │
└──────────────────────────┬──────────────────────────────┘
                           │ REST API + WebSocket
┌──────────────────────────▼──────────────────────────────┐
│  FastAPI Application (backend/app/main.py)              │
│                                                         │
│  ┌────────────────────────────────────────────────┐     │
│  │  AgentScopeRegistry                            │     │
│  │  4-phase pipeline · 8 agents · MCP tools       │     │
│  └─────────────────┬──────────────────────────────┘     │
│                    │                                     │
│  ┌─────────────────▼──────────────┐                     │
│  │  Risk Engine (deterministic)   │                     │
│  │  rules.py · limits.py          │                     │
│  └─────────────────┬──────────────┘                     │
│                    │                                     │
│  ┌─────────────────▼──────────────┐                     │
│  │  Execution Layer               │                     │
│  │  preflight.py · executor.py    │                     │
│  │  MetaAPI (paper / live)        │                     │
│  └────────────────────────────────┘                     │
│                                                         │
│  Strategy Engine · Backtest Engine · Scheduler          │
└──────────────────────────┬──────────────────────────────┘
                           │
         ┌─────────────────┼───────────────────┐
    PostgreSQL           Redis             RabbitMQ
    (runs, steps,      (market data,      (Celery tasks,
     orders, logs)      sessions)          Beat scheduler)
```

## Runtime process model

| Process | Role |
|---------|------|
| FastAPI (uvicorn) | HTTP + WebSocket API |
| Celery worker | Async run execution, backtests |
| Celery Beat | Strategy monitor (30s polling), scheduled runs |

Runs are enqueued as Celery tasks. The API responds immediately with a `run_id`; clients track progress via WebSocket at `/ws/runs/{run_id}`.

## Key subsystems

### AgentScopeRegistry (`services/agentscope/registry.py`)

The single orchestrator for all analysis runs. Owns the 4-phase pipeline, LLM provider resolution, agent construction, MCP tool injection, structured output validation, and DB persistence. The execute() method handles the complete lifecycle from market data fetch to final DB commit.

### MCP Tool Layer (`services/mcp/`)

18 computational tools exposed as a local in-process MCP server. Agents call tools via standard MCP protocol. Tools are pure functions — they do not call LLMs. Examples: `indicator_bundle`, `portfolio_risk_evaluation`, `decision_gating`, `sentiment_parser`.

### Risk Engine (`services/risk/`)

Deterministic Python code. Not an LLM. Evaluates position sizing, portfolio exposure, daily/weekly loss limits, margin requirements, and contract spec bounds. Called via the `portfolio_risk_evaluation` MCP tool with force-injected inputs — the LLM does not choose what to pass to this tool.

### Execution Layer (`services/execution/`)

Two components:
- `ExecutionPreflightEngine` (`preflight.py`) — validates symbol, volume, spread ratio, idempotency key
- `ExecutionService` (`executor.py`) — submits orders to MetaAPI or records them to DB (simulation)

### Strategy Engine (`services/strategy/`)

LLM-powered strategy generation using 4 templates (EMA crossover, RSI mean reversion, Bollinger breakout, MACD divergence). Strategies are validated against historical data via the backtest engine before promotion to paper or live.

### Strategy Monitor (`tasks/strategy_monitor_task.py`)

Celery Beat task running every 30 seconds. Checks active strategies for new signals using a deduplication key. When a new signal is detected, auto-creates a Run and enqueues it through the full agent pipeline. This can result in paper or live order submission depending on configuration — `ALLOW_LIVE_TRADING=false` is the default safeguard.

## Technology stack

| Layer | Technologies |
|-------|-------------|
| Frontend | React 19, TypeScript, Material-UI 7, Vite, Lightweight Charts |
| Backend | FastAPI, SQLAlchemy 2, Alembic, Celery, AgentScope |
| LLM | Ollama (default), OpenAI, Mistral — configurable at runtime |
| Data | PostgreSQL 16, Redis 7, RabbitMQ 3 |
| Broker | MetaAPI (MT4/MT5) |
| Infra | Docker Compose, Helm/Kubernetes, Prometheus, Grafana, Tempo |

## Data model (key tables)

| Table | Stores |
|-------|--------|
| `analysis_run` | Run request, status, decision, full agent trace (JSON) |
| `agent_step` | Per-agent input payload, output payload, error, timing |
| `execution_order` | Order request/response, mode, status |
| `llm_call_log` | Tokens, cost, latency per LLM call |
| `portfolio_snapshot` | Pre/post-trade account state |
| `strategy` | User strategies with backtest scores |
| `connector_config` | Runtime LLM and news provider config |
| `prompt_template` | Per-agent prompt customization |

## Trust boundaries

| Boundary | Enforcement |
|----------|-------------|
| LLM cannot submit orders directly | Execution only via `ExecutionService` after deterministic preflight |
| Risk tool result overrides LLM | `portfolio_risk_evaluation` result is authoritative; LLM disagreement is overridden |
| Live trading off by default | `ALLOW_LIVE_TRADING=false` in `.env.example` |
| Live trading requires role | `TRADER_OPERATOR` role required to request live mode |
| Order idempotency | Duplicate order replay prevented via idempotency key per run |

## Further reading

- [Runtime Flow](runtime-flow.md) — step-by-step pipeline execution
- [Agents](agents.md) — all 8 agents in detail
- [Risk & Governance](risk-and-governance.md) — deterministic risk enforcement
- [Execution](execution.md) — order flow and broker integration
