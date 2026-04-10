# Documentation Refactor — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite all Kairos Mesh documentation to be technically precise, honest, and grounded in implementation reality — replacing the existing `docs/architecture/` tree with a clean flat `docs/` layout.

**Architecture:** Each task targets one documentation file. The workflow per task is: read relevant source files → write the doc with accurate claims → verify key assertions against code → commit. No code is modified; only `.md` files are written.

**Tech Stack:** Markdown, existing backend source files as ground truth, `backend/.env.example`, `docker-compose.yml`, `backend/app/services/agentscope/constants.py`, `backend/app/services/risk/rules.py`, `backend/app/services/execution/executor.py`, `backend/app/services/agentscope/registry.py`.

---

## Source Files Reference

Read these before writing the corresponding docs. Do not guess values — check the source.

| Source File | Used By |
|-------------|---------|
| `backend/app/services/agentscope/registry.py` | runtime-flow, agents, decision-pipeline |
| `backend/app/services/agentscope/agents.py` | agents |
| `backend/app/services/agentscope/constants.py` | decision-pipeline, risk-and-governance |
| `backend/app/services/agentscope/schemas.py` | agents, decision-pipeline |
| `backend/app/services/risk/rules.py` | risk-and-governance |
| `backend/app/services/risk/limits.py` | risk-and-governance, paper-vs-live |
| `backend/app/services/execution/executor.py` | execution |
| `backend/app/services/execution/preflight.py` | execution |
| `backend/app/api/routes/runs.py` | runtime-flow |
| `backend/app/core/config.py` | configuration |
| `backend/.env.example` | configuration, getting-started |
| `docker-compose.yml` | getting-started, architecture |
| `Makefile` | getting-started, quickstart |
| `backend/app/observability/metrics.py` | observability |
| `backend/app/main.py` | architecture, observability |
| `docs/architecture/LIMITATIONS.md` | limitations (source to improve, not copy) |

---

## Task 1: Write `README.md`

**Files:**
- Modify: `README.md`

The current README overclaims ("real-time execution", "autonomous") without qualification. Rewrite it as an honest first-contact document.

- [ ] **Step 1: Read current README and identify what to keep vs rewrite**

  Read `README.md`. Note:
  - Keep: logo, license badge, tech stack table, project structure, disclaimer
  - Fix: description line (add "paper-trading by default"), pipeline table (add note about debate being conditional), features list (remove "Safety" bullet marketing tone), architecture ASCII diagram (accurate, keep)
  - Add: "Current scope" section, docs navigation map, link to `docs/limitations.md`

- [ ] **Step 2: Write the new README.md**

  Replace `README.md` with this content (preserve the logo SVG reference and MIT badge):

  ```markdown
  # Kairos Mesh

  <p align="center">
    <img src="kairos_mesh_logo.svg" alt="Kairos Mesh" width="420">
  </p>

  [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

  A governed multi-agent trading system that orchestrates 8 specialized LLM agents through a structured research and decision workflow. Paper-trading mode is the default and safe starting point. Live execution requires explicit configuration.

  ---

  ## What is Kairos Mesh?

  Kairos Mesh is an open-source, structured trading research system. It runs a deterministic 4-phase pipeline per analysis request:

  1. **Analysis** — three agents run in parallel: technical indicators, news sentiment, macro context
  2. **Debate** — a bullish researcher and bearish researcher build opposing theses; a trader agent moderates
  3. **Decision** — the trader agent produces a BUY / SELL / HOLD with entry, stop-loss, and take-profit levels
  4. **Governance** — a deterministic risk engine validates the decision; an execution manager applies preflight checks before any order is submitted

  LLM agents provide reasoning and synthesis. Risk enforcement is deterministic Python code — not an LLM judgment.

  ## What it does not do

  - It does not trade autonomously or make unsupervised decisions
  - It does not learn from past outcomes — there is no feedback loop from trade results to future runs
  - It does not provide financial advice
  - It is not production-ready for live capital without additional hardening (see [Limitations](docs/limitations.md))
  - Live trading is disabled by default (`ALLOW_LIVE_TRADING=false`)

  ## Current scope

  | Area | Status |
  |------|--------|
  | Paper trading (MetaAPI paper account) | Implemented, default |
  | Simulation mode (DB only, no broker call) | Implemented |
  | Live trading | Implemented but off by default; requires `ALLOW_LIVE_TRADING=true` and `TRADER_OPERATOR` role |
  | 8-agent pipeline | Fully implemented |
  | Debate phase | Conditional — only runs if all 3 debate agents have LLM enabled |
  | Memory / learning loop | Not implemented — each run is stateless |
  | Strategy monitoring (auto-run on signal) | Implemented via Celery Beat |
  | Backtesting | Implemented (rule-based; LLM optional) |

  ## Architecture

  ```
  ┌────────────────────────────────────────────────────────────────┐
  │                     React Dashboard (Vite)                     │
  │  Terminal · Strategies · Orders · Backtests · Connectors       │
  └────────────────────────┬───────────────────────────────────────┘
                           │ REST + WebSocket
  ┌────────────────────────▼───────────────────────────────────────┐
  │                    FastAPI Backend                              │
  │  ┌──────────────┐  ┌──────────────┐  ┌───────────────────┐    │
  │  │  AgentScope  │  │  Risk Engine │  │  Execution Layer  │    │
  │  │  Registry    │  │ (determin.)  │  │  Paper / Live     │    │
  │  │  (8 Agents)  │  └──────────────┘  └───────────────────┘    │
  │  └──────┬───────┘                                              │
  │         │                                                      │
  │  ┌──────▼──────────────────────────────────────────────┐       │
  │  │           MCP Tool Layer (25+ tools)                │       │
  │  │  Indicators · Patterns · News · Risk · Sizing       │       │
  │  └─────────────────────────────────────────────────────┘       │
  └────────────────────────────────────────────────────────────────┘
           │              │              │
      PostgreSQL       Redis        RabbitMQ
      Runs / Steps     Cache       Celery Queue + Beat
  ```

  ## Agent pipeline

  | # | Agent | Role | Output advisory? |
  |---|-------|------|-----------------|
  | 1 | Technical Analyst | RSI, MACD, EMA, ATR, patterns, divergence, S/R | Advisory |
  | 2 | News Analyst | Sentiment scoring, relevance filtering | Advisory |
  | 3 | Market Context | Regime detection, session, macro | Advisory |
  | 4 | Bullish Researcher | Bull thesis construction | Advisory (debate) |
  | 5 | Bearish Researcher | Bear thesis construction | Advisory (debate) |
  | 6 | Trader | BUY / SELL / HOLD with entry, SL, TP | Decision-bearing |
  | 7 | Risk Manager | Position sizing, portfolio risk validation | Binding (tool overrides LLM) |
  | 8 | Execution Manager | Preflight checks + order submission | Binding (deterministic preflight) |

  Agents 4–5 (debate) only run when both have LLM enabled. If skipped, the trader agent decides without debate input.

  ## Quick start

  ```bash
  cp backend/.env.example backend/.env
  # Edit backend/.env — set LLM_PROVIDER and your API keys
  docker compose up --build
  ```

  Access points after startup:
  - Frontend: http://localhost:5173
  - Backend API + docs: http://localhost:8000/docs
  - Grafana: http://localhost:3000
  - Prometheus: http://localhost:9090

  Default credentials: `admin@local.dev` / `admin1234`

  See [Getting Started](docs/getting-started.md) for full setup instructions.

  ## Tech stack

  | Layer | Technologies |
  |-------|-------------|
  | Frontend | React 19, TypeScript, Material-UI 7, Vite, Lightweight Charts |
  | Backend | FastAPI, SQLAlchemy 2, Alembic, Celery, AgentScope |
  | Data | PostgreSQL 16, Redis 7, RabbitMQ 3 |
  | Infra | Docker Compose, Helm/K8s, Prometheus, Grafana |
  | LLM | Ollama (default), OpenAI, Mistral |
  | Broker | MetaAPI (MT4/MT5) |

  ## Configuration

  All configuration is via environment variables. Copy `backend/.env.example` to `backend/.env` and edit.

  | Variable | Description | Default |
  |----------|-------------|---------|
  | `LLM_PROVIDER` | LLM backend (`ollama`, `openai`, `mistral`) | `ollama` |
  | `DECISION_MODE` | Gating policy (`conservative`, `balanced`, `permissive`) | `balanced` |
  | `ALLOW_LIVE_TRADING` | Enable real broker execution | `false` |
  | `ENABLE_PAPER_EXECUTION` | Enable paper trading via MetaAPI | `true` |
  | `METAAPI_TOKEN` | MetaAPI authentication token | — |

  Full reference: [Configuration](docs/configuration.md)

  ## Project structure

  ```
  backend/app/
    api/routes/          # REST endpoints (runs, strategies, backtests, trading)
    services/
      agentscope/        # 4-phase agent pipeline (registry, debate, schemas, toolkit)
      mcp/               # MCP tool server (25+ computational tools)
      risk/              # Deterministic risk engine
      execution/         # Paper/live order execution
      strategy/          # Strategy designer and monitor
      market/            # Market data, news, instrument classification
      llm/               # LLM provider clients
    tasks/               # Celery tasks (analysis, backtest, strategy monitor)
    db/                  # SQLAlchemy models

  frontend/src/
    pages/               # Terminal, Strategies, RunDetail, Orders, Backtests
    components/          # TradingViewChart, PortfolioKPIs, Layout

  infra/
    docker/              # Prometheus config, Grafana dashboards
    helm/                # Kubernetes Helm charts
  ```

  ## Documentation

  | Document | Description |
  |----------|-------------|
  | [Getting Started](docs/getting-started.md) | Prerequisites, install, first run |
  | [Quickstart](docs/quickstart.md) | Minimal path to a working run |
  | [Architecture](docs/architecture.md) | System layers, component map |
  | [Runtime Flow](docs/runtime-flow.md) | Step-by-step: how a run executes |
  | [Agents](docs/agents.md) | All 8 agents: roles, inputs, outputs |
  | [Decision Pipeline](docs/decision-pipeline.md) | Analysis → debate → trade intent → gating |
  | [Risk & Governance](docs/risk-and-governance.md) | Deterministic risk engine, limits, gates |
  | [Execution](docs/execution.md) | Order flow, paper vs live, safeguards |
  | [Memory](docs/memory.md) | Storage backends, transient vs persistent |
  | [Configuration](docs/configuration.md) | Full environment variable reference |
  | [Observability](docs/observability.md) | Metrics, logs, audit trail |
  | [Paper vs Live](docs/paper-vs-live.md) | What differs, safety checklist |
  | [Limitations](docs/limitations.md) | Known constraints, incomplete features |

  ## Limitations

  This project has known limitations that affect production readiness. Read [docs/limitations.md](docs/limitations.md) before deploying in any environment involving real capital.

  Key constraints:
  - No learning loop — each run starts with fresh context
  - Paper trading assumes exact fill at requested price (no slippage model)
  - Live trading support is implemented but not hardened or audited for production
  - Single LLM provider per run (no per-agent model selection)
  - No rate limiting on API endpoints

  ## Contributing

  See [CONTRIBUTING.md](CONTRIBUTING.md).

  ## Security

  See [SECURITY.md](SECURITY.md) for the vulnerability reporting process and known security boundaries.

  ## Disclaimer

  This software is for educational and research purposes only. It does not constitute financial advice. Past performance does not indicate future results. Use at your own risk. The authors accept no responsibility for financial losses incurred through use of this software.

  ## License

  [MIT](LICENSE)
  ```

- [ ] **Step 3: Verify key claims against source**

  Check:
  - `ALLOW_LIVE_TRADING=false` default → `backend/.env.example` line ~136: `ALLOW_LIVE_TRADING=false` ✓
  - Debate conditional on `llm_enabled` → `backend/app/services/agentscope/registry.py` (search for `debate` and `llm_enabled`)
  - 8 agents confirmed → `backend/app/services/agentscope/agents.py` (count agent definitions)

- [ ] **Step 4: Commit**

  ```bash
  git add README.md
  git commit -m "docs: rewrite README with accurate scope, architecture, and limitations"
  ```

---

## Task 2: Write `docs/getting-started.md`

**Files:**
- Create: `docs/getting-started.md`

- [ ] **Step 1: Read source files**

  Read:
  - `docker-compose.yml` (service names, ports, volumes)
  - `backend/.env.example` (all variables with comments)
  - `Makefile` (available targets)
  - `backend/Dockerfile` (Python version)

- [ ] **Step 2: Write `docs/getting-started.md`**

  ```markdown
  # Getting Started

  This guide covers local development setup using Docker Compose, the recommended path for new contributors and evaluators.

  ## Prerequisites

  | Dependency | Minimum version | Purpose |
  |------------|----------------|---------|
  | Docker | 24+ | Container runtime |
  | Docker Compose | 2.20+ | Local orchestration |
  | Python | 3.12+ | Backend dev (optional if using Docker only) |
  | Node.js | 22+ | Frontend dev (optional if using Docker only) |

  No broker account is required for simulation mode. A MetaAPI account is required for paper or live trading.

  ## Step 1 — Clone and configure

  ```bash
  git clone <repository-url> kairos-mesh
  cd kairos-mesh
  cp backend/.env.example backend/.env
  ```

  Open `backend/.env` and set at minimum:

  | Variable | What to set | Notes |
  |----------|-------------|-------|
  | `LLM_PROVIDER` | `ollama`, `openai`, or `mistral` | Ollama is the local option (no API key) |
  | `OLLAMA_MODEL` | e.g. `llama3.1:8b` | Only if using Ollama |
  | `OPENAI_API_KEY` | Your OpenAI key | Only if `LLM_PROVIDER=openai` |
  | `MISTRAL_API_KEY` | Your Mistral key | Only if `LLM_PROVIDER=mistral` |
  | `SECRET_KEY` | Any long random string | Required; change from default for anything non-local |

  All other variables have safe defaults for local development.

  ## Step 2 — Start the stack

  ```bash
  docker compose up --build
  ```

  This starts the following services:

  | Service | Port | Description |
  |---------|------|-------------|
  | `backend` | 8000 | FastAPI application |
  | `worker` | — | Celery worker + Beat scheduler |
  | `frontend` | 5173 | React dev server |
  | `postgres` | 5432 | PostgreSQL 16 |
  | `redis` | 6379 | Redis 7 |
  | `rabbitmq` | 5672 / 15672 | RabbitMQ (15672 = management UI) |
  | `prometheus` | 9090 | Metrics collection |
  | `grafana` | 3000 | Dashboards |

  Wait for `backend` to log `Application startup complete` before using the UI.

  ## Step 3 — Verify

  | URL | Expected |
  |-----|----------|
  | http://localhost:5173 | React dashboard (login page) |
  | http://localhost:8000/docs | FastAPI Swagger UI |
  | http://localhost:8000/health | `{"status": "ok"}` |
  | http://localhost:9090 | Prometheus |
  | http://localhost:3000 | Grafana (admin / admin) |

  Default credentials: `admin@local.dev` / `admin1234`

  ## Step 4 — Run a first analysis

  1. Open http://localhost:5173 and log in
  2. Navigate to **Connectors** → **AI Models** and confirm your LLM provider is configured
  3. Navigate to **Terminal**
  4. Select a pair (e.g. `EURUSD`) and timeframe (e.g. `H1`), set mode to **Simulation**
  5. Click **Run Analysis**
  6. Watch the pipeline progress in real time via WebSocket

  No broker account is needed for simulation mode — orders are recorded in the database only.

  ## Local development (without Docker)

  If you prefer to run the backend and frontend outside Docker, you still need PostgreSQL, Redis, and RabbitMQ. Start infrastructure only:

  ```bash
  docker compose up postgres redis rabbitmq -d
  ```

  Then in separate terminals:

  ```bash
  # Backend
  make backend-install
  make backend-run        # http://localhost:8000

  # Celery worker
  make worker-run

  # Frontend
  make frontend-install
  make frontend-run       # http://localhost:5173
  ```

  Available make targets:

  ```bash
  make backend-install    # Install Python dependencies
  make backend-run        # Start FastAPI dev server
  make worker-run         # Start Celery worker
  make frontend-install   # Install Node dependencies
  make frontend-run       # Start Vite dev server
  make backend-test       # Run backend tests
  ```

  ## Configuring LLM providers

  LLM providers can also be configured at runtime via the UI: **Connectors → AI Models**.

  Per-agent LLM enable/disable is also available there. Disabling LLM for an agent causes it to run in deterministic mode (tool-only, no LLM call).

  ## Infrastructure dependencies

  The backend will fail to start without PostgreSQL, Redis, and RabbitMQ. There is no embedded fallback for any of these.

  ## Next steps

  - [Quickstart](quickstart.md) — fastest path to a working simulation run
  - [Configuration](configuration.md) — full environment variable reference
  - [Paper vs Live](paper-vs-live.md) — what to check before connecting a broker account
  ```

- [ ] **Step 3: Verify port numbers against docker-compose.yml**

  Confirm all ports listed in the table match `docker-compose.yml` service definitions.

- [ ] **Step 4: Commit**

  ```bash
  git add docs/getting-started.md
  git commit -m "docs: add getting-started guide"
  ```

---

## Task 3: Write `docs/quickstart.md`

**Files:**
- Create: `docs/quickstart.md`

- [ ] **Step 1: Write `docs/quickstart.md`**

  ```markdown
  # Quickstart

  Minimum steps to run a paper-trading analysis in under 5 minutes. Assumes Docker is running.

  ```bash
  # 1. Configure
  cp backend/.env.example backend/.env
  # Set LLM_PROVIDER=ollama (or openai/mistral with corresponding API key)

  # 2. Start
  docker compose up --build -d

  # 3. Wait for backend
  docker compose logs backend --follow
  # Look for: "Application startup complete"
  ```

  Open http://localhost:5173 → log in with `admin@local.dev` / `admin1234`

  **Run a simulation (no broker required)**:
  1. Terminal → select pair `EURUSD`, timeframe `H1`, mode **Simulation**
  2. Click **Run Analysis**
  3. Watch agent progress in real time

  **Run a paper trade (requires MetaAPI)**:
  1. Add `METAAPI_TOKEN` and `METAAPI_ACCOUNT_ID` to `backend/.env`
  2. Restart: `docker compose up -d backend worker`
  3. Terminal → mode **Paper** → Run Analysis

  > Live trading requires `ALLOW_LIVE_TRADING=true` in `.env` and a user with the `TRADER_OPERATOR` role. See [Paper vs Live](paper-vs-live.md) before enabling.

  ## What happens during a run

  ```
  POST /api/v1/runs
    → Celery queue
      → Phase 1: technical-analyst, news-analyst, market-context (parallel)
      → Phase 2+3: bullish-researcher + bearish-researcher debate (if LLM enabled)
      → Phase 4: trader decision → risk validation → preflight → execution
    → Results persisted to DB
    → WebSocket broadcasts progress to UI
  ```

  Full pipeline detail: [Runtime Flow](runtime-flow.md)
  ```

- [ ] **Step 2: Commit**

  ```bash
  git add docs/quickstart.md
  git commit -m "docs: add quickstart guide"
  ```

---

## Task 4: Write `docs/architecture.md`

**Files:**
- Create: `docs/architecture.md`

- [ ] **Step 1: Read source files**

  Read `backend/app/main.py` (lifespan, middleware, routes), `docker-compose.yml` (service topology), `backend/app/services/agentscope/registry.py` (first ~100 lines for class structure).

- [ ] **Step 2: Write `docs/architecture.md`**

  ```markdown
  # Architecture

  ## System overview

  Kairos Mesh is a research-and-execution pipeline for structured trading analysis. It is not an autonomous trading bot. Each run is a discrete, auditable workflow with deterministic governance applied at the risk and execution stages.

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

  The single orchestrator for all analysis runs. Owns the 4-phase pipeline, LLM provider resolution, agent construction, MCP tool injection, structured output validation, and DB persistence. Approximately 1800 lines.

  ### MCP Tool Layer (`services/mcp/`)

  25+ computational tools exposed as a local in-process MCP server. Agents call tools via standard MCP protocol. Tools are pure functions — they do not call LLMs. Examples: `indicator_bundle`, `portfolio_risk_evaluation`, `decision_gating`, `sentiment_parser`.

  ### Risk Engine (`services/risk/`)

  Deterministic Python code. Not an LLM. Evaluates position sizing, portfolio exposure, daily/weekly loss limits, margin requirements, and contract spec bounds. Called via the `portfolio_risk_evaluation` MCP tool with force-injected inputs — the LLM does not choose what to pass.

  ### Execution Layer (`services/execution/`)

  Two components:
  - `ExecutionPreflightEngine` (preflight.py) — validates symbol, volume, spread, idempotency key
  - `ExecutionService` (executor.py) — submits orders to MetaAPI or records them to DB (simulation)

  ### Strategy Engine (`services/strategy/`)

  LLM-powered strategy generation using 4 templates (EMA crossover, RSI mean reversion, Bollinger breakout, MACD divergence). Strategies are validated against historical data via the backtest engine before promotion to paper or live.

  ### Strategy Monitor (`tasks/strategy_monitor_task.py`)

  Celery Beat task running every 30 seconds. Checks active strategies for new signals using a deduplication key. When a new signal is detected, auto-creates a Run and enqueues it through the full agent pipeline.

  ## Technology stack

  | Layer | Technologies |
  |-------|-------------|
  | Frontend | React 19, TypeScript, Material-UI 7, Vite, Lightweight Charts |
  | Backend | FastAPI, SQLAlchemy 2, Alembic, Celery, AgentScope |
  | LLM | Ollama (default), OpenAI, Mistral — configurable at runtime |
  | Data | PostgreSQL 16, Redis 7, RabbitMQ 3 |
  | Broker | MetaAPI (MT4/MT5) |
  | Infra | Docker Compose, Helm/Kubernetes, Prometheus, Grafana |

  ## Data model (key tables)

  | Table | Stores |
  |-------|--------|
  | `analysis_run` | Run request, status, decision, full trace (JSON) |
  | `agent_step` | Per-agent input, output, error, timing |
  | `execution_order` | Order request/response, mode, status |
  | `llm_call_log` | Tokens, cost, latency per LLM call |
  | `portfolio_snapshot` | Pre/post-trade account state |
  | `strategy` | User strategies with backtest scores |
  | `connector_config` | Runtime LLM and news provider config |
  | `prompt_template` | Per-agent prompt customization |

  ## Trust boundaries

  | Boundary | Enforcement |
  |----------|-------------|
  | LLM cannot submit orders directly | Execution only via `ExecutionService` after preflight |
  | Risk tool overrides LLM | `portfolio_risk_evaluation` result is authoritative; LLM disagreement is overridden |
  | Live trading off by default | `ALLOW_LIVE_TRADING=false` in `.env.example` |
  | Live trading requires role | `TRADER_OPERATOR` role required to request live mode |
  | Order idempotency | Duplicate run replay prevented via idempotency key |

  ## Further reading

  - [Runtime Flow](runtime-flow.md) — step-by-step pipeline execution
  - [Agents](agents.md) — all 8 agents in detail
  - [Risk & Governance](risk-and-governance.md) — deterministic risk enforcement
  - [Execution](execution.md) — order flow and broker integration
  ```

- [ ] **Step 3: Verify trust boundary table against source**

  Confirm `ALLOW_LIVE_TRADING=false` in `backend/.env.example` and `TRADER_OPERATOR` role reference in `backend/app/api/routes/runs.py`.

- [ ] **Step 4: Commit**

  ```bash
  git add docs/architecture.md
  git commit -m "docs: add architecture overview"
  ```

---

## Task 5: Write `docs/runtime-flow.md`

**Files:**
- Create: `docs/runtime-flow.md`

- [ ] **Step 1: Read source files**

  Read `backend/app/api/routes/runs.py` (entry point, async/sync paths), `backend/app/services/agentscope/registry.py` (execute() method, phase structure, progress markers, WebSocket broadcasts).

- [ ] **Step 2: Write `docs/runtime-flow.md`**

  ```markdown
  # Runtime Flow

  This document describes exactly how an analysis run executes from API request to database commit.

  ## Entry point

  **`POST /api/v1/runs`** (`backend/app/api/routes/runs.py`)

  Request body:
  ```json
  {
    "pair": "EURUSD",
    "timeframe": "H1",
    "mode": "simulation",       // simulation | paper | live
    "risk_percent": 1.0,
    "metaapi_account_ref": null  // optional; required for paper/live
  }
  ```

  Response (async, default):
  ```json
  { "run_id": "uuid", "status": "queued" }
  ```

  ## Dispatch

  ```
  POST /api/v1/runs
    ├─ Create AnalysisRun record (status=pending)
    ├─ if async_execution=true (default):
    │    enqueue run_analysis_task.execute(run_id) → RabbitMQ
    │    set status=queued, store celery_task_id
    │    return { run_id, status: "queued" }
    └─ if async_execution=false (testing only):
         execute AgentScopeRegistry inline
  ```

  The Celery worker picks up the task and calls `AgentScopeRegistry().execute()`.

  ## Strategy monitor (auto-triggered runs)

  Celery Beat polls active strategies every 30 seconds via `strategy_monitor_task.check_all()`. When a strategy's computed signal changes (deduplication via `last_signal_key`), a Run is auto-created and dispatched identically to a manual request.

  ## AgentScopeRegistry.execute()

  All four phases run inside this method. Progress is broadcast to WebSocket subscribers at each phase boundary.

  ### Pre-pipeline: Market data resolution

  ```
  1. Fetch OHLC candles: MetaAPI primary, YFinance fallback
     - Minimum bars required: AGENTSCOPE_MIN_BARS (default: 30)
     - Candle limit: AGENTSCOPE_CANDLE_LIMIT (default: 240)
  2. Fetch market snapshot (current price, spread, ATR)
  3. Fetch news items (configured providers: NewsAPI, Finnhub, AlphaVantage, etc.)
  4. Fetch portfolio state (balance, equity, margin, open positions)
  5. Resolve LLM provider config from DB (Connectors settings)
  6. Build per-agent context packages (injected as force_kwargs into MCP tools)
  ```

  If market data fetch fails, the run is marked `failed` and no agents run.

  ### Phase 1 — Parallel analysis (progress 0% → 10%)

  Three agents run concurrently via `asyncio.gather()`:

  | Agent | Timeout |
  |-------|---------|
  | `technical-analyst` | `AGENTSCOPE_AGENT_TIMEOUT_SECONDS` (default: 60s) |
  | `news-analyst` | same |
  | `market-context-analyst` | same |

  Each agent:
  1. Constructs a ReActAgent with its tool set and system prompt
  2. Calls MCP tools (in parallel where tools allow `parallel_tool_calls=true`)
  3. Produces a structured `Msg` with `metadata` (confidence, score, direction, reasoning)

  On timeout or error: the agent's step is marked `failed`; the run continues with whatever outputs are available (partial analysis).

  Outputs are concatenated into `analysis_summary` and injected into Phase 2 prompts.

  ### Phase 2+3 — Debate (progress 10% → 35%)

  **Condition**: Debate only runs if all three debate agents (`bullish-researcher`, `bearish-researcher`, `trader-agent`) have `llm_enabled=true` in the DB config.

  If condition is false: debate is skipped; returns `DebateResult(winner="no_edge", conviction="weak")`. The run continues without debate input.

  If condition is true:

  ```
  1. Build MsgHub with bullish-researcher, bearish-researcher, trader-agent (moderator)
  2. Run 1–3 rounds (DEBATE_MIN_ROUNDS=1, DEBATE_MAX_ROUNDS=3)
  3. Each round:
       bullish-researcher presents evidence → bearish-researcher counters →
       trader-agent evaluates and may call decision_gating tool
  4. Produce DebateResult:
       winner: "bullish" | "bearish" | "no_edge"
       conviction: "strong" | "moderate" | "weak"
       key_argument: str
       weakness: str
  ```

  On timeout during debate: returns `DebateResult(winner="no_edge", conviction="weak")`.

  ### Phase 4 — Decision and governance (progress 35% → 90%)

  #### Trader agent (progress 35% → 65%)

  Receives: Phase 1 analysis, debate result, portfolio state, decision gating policy.

  Produces: `TraderDecisionDraft`
  ```json
  {
    "decision": "BUY | SELL | HOLD",
    "conviction": 0.0,      // 0.0–1.0
    "entry": 1.0800,
    "stop_loss": 1.0750,
    "take_profit": 1.0880,
    "reasoning": "..."
  }
  ```

  If trader fails to produce a valid decision:
  - Debate winner is `bullish` → use BUY (with warning in trace)
  - Debate winner is `bearish` → use SELL (with warning)
  - Otherwise → HOLD

  If entry/SL/TP are missing, `trade_sizing` MCP tool is auto-called to compute ATR-based levels.

  #### Risk manager (progress 65% → 80%)

  Skipped entirely if decision is HOLD.

  Calls `portfolio_risk_evaluation` MCP tool with force-injected inputs (trader decision, portfolio state, risk limits). The LLM cannot alter these inputs.

  Tool output:
  ```json
  {
    "accepted": true,
    "suggested_volume": 0.01,
    "rejection_reason": null
  }
  ```

  **If tool returns `accepted=false`**: run is blocked, no execution. LLM cannot override.
  **If tool returns `accepted=true` but LLM summary says reject**: tool wins, execution proceeds.

  #### Execution manager (progress 80% → 90%)

  Runs `ExecutionPreflightEngine.validate()` — fully deterministic, no LLM call unless `EXECUTION_MANAGER_LLM_ENABLED=true`.

  Preflight checks:
  - Idempotency key collision (prevents duplicate orders)
  - Symbol validity
  - Volume within asset-class bounds
  - Spread-to-price ratio (warn > 1%, block > 5%)
  - Margin availability

  If preflight passes: `ExecutionService.execute()` is called.

  Execution paths:
  - `simulation`: Order recorded to DB as `status=simulated`. No broker call.
  - `paper`: Order submitted to MetaAPI paper account.
  - `live`: Order submitted to MetaAPI live account. Only available if `ALLOW_LIVE_TRADING=true`.

  ## Post-pipeline

  ```
  1. Batch-commit all AgentStep records to DB
  2. Update AnalysisRun with:
       - status: completed | failed
       - decision: (structured JSON)
       - trace: (full agentic_runtime structure)
  3. Broadcast final WebSocket event to subscribers
  4. Write debug trace JSON if DEBUG_TRADE_JSON_ENABLED=true
  ```

  ## Progress events (WebSocket)

  Subscribe at `ws://localhost:8000/ws/runs/{run_id}` to receive:

  | Progress | Event |
  |----------|-------|
  | 5% | Run started |
  | 10% | Phase 1 complete |
  | 35% | Debate complete |
  | 65% | Trader decision ready |
  | 80% | Risk assessment complete |
  | 90% | Execution complete |
  | 100% | Run finalized |

  ## Timeout and error handling

  | Scenario | Behavior |
  |----------|----------|
  | Agent LLM timeout | Step marked failed; run continues with partial outputs |
  | Debate timeout | Returns `no_edge` result; trader decides independently |
  | Market data unavailable | Run marked failed immediately |
  | Risk rejection | Run completes as `completed` but no order submitted |
  | Preflight block | Run completes as `completed` but no order submitted |
  | Celery hard timeout (360s) | Run marked failed by Celery |

  ## Further reading

  - [Agents](agents.md) — what each agent does and produces
  - [Decision Pipeline](decision-pipeline.md) — how scores and votes combine
  - [Risk & Governance](risk-and-governance.md) — risk engine detail
  - [Execution](execution.md) — order submission and idempotency
  ```

- [ ] **Step 3: Verify timing constants and defaults**

  Check `backend/app/core/config.py` for:
  - `AGENTSCOPE_AGENT_TIMEOUT_SECONDS` default = 60
  - `DEBATE_MAX_ROUNDS` default = 3
  - `DEBATE_MIN_ROUNDS` default = 1
  - `CELERY_ANALYSIS_TIME_LIMIT_SECONDS` default = 360

- [ ] **Step 4: Commit**

  ```bash
  git add docs/runtime-flow.md
  git commit -m "docs: add runtime flow documentation"
  ```

---

## Task 6: Write `docs/agents.md`

**Files:**
- Create: `docs/agents.md`

- [ ] **Step 1: Read source files**

  Read `backend/app/services/agentscope/agents.py` (agent factory definitions, tool lists, max_iters), `backend/app/services/agentscope/schemas.py` (output schema shapes).

- [ ] **Step 2: Write `docs/agents.md`**

  ```markdown
  # Agents

  Kairos Mesh runs 8 agents across a 4-phase pipeline. This document describes each agent's role, inputs, outputs, and the tools it can call.

  ## Agent inventory

  | # | Name | Phase | LLM-driven | Output type |
  |---|------|-------|-----------|-------------|
  | 1 | technical-analyst | 1 (parallel) | Yes (configurable) | Advisory |
  | 2 | news-analyst | 1 (parallel) | Yes (configurable) | Advisory |
  | 3 | market-context-analyst | 1 (parallel) | Yes (configurable) | Advisory |
  | 4 | bullish-researcher | 2 (debate) | Yes — skipped if disabled | Advisory (debate) |
  | 5 | bearish-researcher | 2 (debate) | Yes — skipped if disabled | Advisory (debate) |
  | 6 | trader-agent | 3+4 | Yes (configurable) | Decision-bearing |
  | 7 | risk-manager | 4 | Hybrid (tool is authoritative) | Binding |
  | 8 | execution-manager | 4 | Optional (preflight is deterministic) | Binding |

  **LLM-configurable**: Each agent's `llm_enabled` flag is set per-agent in the UI (Connectors → AI Models) or via per-agent DB config. If disabled, the agent runs in deterministic mode (tool calls only, no LLM inference).

  ---

  ## 1. Technical Analyst

  **Role**: Compute technical indicators and patterns from OHLC data. Produce a directional score and confidence estimate.

  **Inputs** (injected at construction):
  - OHLC candles (up to `AGENTSCOPE_CANDLE_LIMIT` bars)
  - Current pair, timeframe
  - Higher timeframes for multi-timeframe context

  **MCP tools available**:
  | Tool | Purpose |
  |------|---------|
  | `indicator_bundle` | RSI, MACD, EMA, ATR, volume |
  | `pattern_detector` | Candlestick pattern recognition |
  | `divergence_detector` | RSI/MACD divergence |
  | `support_resistance_detector` | Key price levels |
  | `multi_timeframe_context` | Higher-timeframe trend alignment |

  Tools called in parallel (`parallel_tool_calls=true`). Max iterations: 5.

  **Output schema** (`TechnicalAnalysisResult`):
  ```json
  {
    "score": -1.0,         // -1.0 (bearish) to +1.0 (bullish)
    "confidence": 0.72,    // 0.0–1.0
    "direction": "bullish | bearish | neutral",
    "reasoning": "...",
    "indicators": { "rsi": 58.2, "macd_signal": "bullish_cross", ... },
    "patterns": [...],
    "key_levels": { "support": 1.0750, "resistance": 1.0850 }
  }
  ```

  **Downstream consumer**: Score and confidence are injected into Phase 2 prompts and used in `decision_gating` weighted average (weight: 0.50).

  ---

  ## 2. News Analyst

  **Role**: Score news relevance and sentiment for the target instrument. Identify macro events.

  **Inputs** (injected at construction):
  - News items from configured providers (NewsAPI, Finnhub, AlphaVantage, etc.)
  - Target pair (for relevance filtering)

  **MCP tools available**:
  | Tool | Purpose |
  |------|---------|
  | `symbol_relevance_filter` | Filter news to instrument-relevant items |
  | `sentiment_parser` | Positive/negative/neutral sentiment score |
  | `news_search` | Additional targeted search if providers return few results |
  | `macro_event_feed` | Upcoming macro events (FOMC, CPI, etc.) |

  Tools called in parallel. Max iterations: 4.

  **Output schema** (`NewsAnalysisResult`):
  ```json
  {
    "score": 0.35,
    "confidence": 0.60,
    "direction": "bullish",
    "reasoning": "...",
    "relevant_count": 5,
    "sentiment_breakdown": { "positive": 3, "negative": 1, "neutral": 1 }
  }
  ```

  **Downstream consumer**: Score and confidence used in `decision_gating` weighted average (weight: 0.25).

  **Constraint**: If no relevant news items are found, score defaults to neutral (0.0) with low confidence.

  ---

  ## 3. Market Context Analyst

  **Role**: Assess macro regime, trading session, and volatility context.

  **Inputs** (injected at construction):
  - Market snapshot (current price, ATR, session)
  - Pair and timeframe metadata

  **MCP tools available**:
  | Tool | Purpose |
  |------|---------|
  | `market_regime_detector` | Trending, ranging, or choppy regime |
  | `session_context` | Active trading session (London, NY, Asia, overlap) |
  | `volatility_analyzer` | ATR percentile, recent volatility regime |
  | `correlation_analyzer` | Correlation with major pairs or indices |

  Tools called in parallel. Max iterations: 5.

  **Output schema** (`MarketContextResult`):
  ```json
  {
    "score": 0.20,
    "confidence": 0.65,
    "direction": "bullish",
    "regime": "trending",
    "session": "london_ny_overlap",
    "volatility_state": "normal",
    "reasoning": "..."
  }
  ```

  **Downstream consumer**: Score and confidence used in `decision_gating` weighted average (weight: 0.25).

  ---

  ## 4. Bullish Researcher

  **Role**: Build the best possible bull case from Phase 1 evidence. Advocate during debate.

  **Inputs** (injected at construction):
  - Phase 1 analysis outputs
  - Debate context (opponent theses from prior rounds)

  **MCP tools available**:
  | Tool | Purpose |
  |------|---------|
  | `evidence_query` | Retrieve supporting evidence from Phase 1 outputs |
  | `thesis_support_extractor` | Extract strongest supporting signals |
  | `scenario_validation` | Validate scenario against market conditions |

  Max iterations: 4. Sequential tool calls.

  **Output schema** (`DebateThesis`):
  ```json
  {
    "conviction": "strong | moderate | weak",
    "key_argument": "...",
    "evidence": [...],
    "weakness_acknowledged": "..."
  }
  ```

  **Advisory only**: Output is advisory input to the trader-agent's decision. The trader is the authoritative decision-maker.

  **Condition**: Only active if `llm_enabled=true` for this agent in DB config. If disabled or if any debate agent is disabled, the entire debate phase is skipped.

  ---

  ## 5. Bearish Researcher

  **Role**: Build the best possible bear case from Phase 1 evidence. Counter bullish arguments.

  Same structure as Bullish Researcher but constructs the opposing thesis.

  **Condition**: Same as bullish-researcher — debate skipped if either researcher has `llm_enabled=false`.

  ---

  ## 6. Trader Agent

  **Role**: Produce the authoritative trading decision (BUY / SELL / HOLD) with full trade parameters.

  **Inputs** (injected at construction):
  - Phase 1 analysis outputs (technical, news, market context)
  - Debate result (if debate ran; otherwise `no_edge`)
  - Portfolio state (balance, equity, open positions)
  - Decision gating policy (thresholds for the configured `DECISION_MODE`)

  **MCP tools available**:
  | Tool | Purpose |
  |------|---------|
  | `decision_gating` | Evaluate signals against mode thresholds; return guidance |
  | `contradiction_detector` | Identify major contradictions between Phase 1 outputs |
  | `trade_sizing` | Compute ATR-based entry, SL, TP if missing |

  Max iterations: 5.

  **Output schema** (`TraderDecisionDraft`):
  ```json
  {
    "decision": "BUY | SELL | HOLD",
    "conviction": 0.78,
    "entry": 1.0812,
    "stop_loss": 1.0762,
    "take_profit": 1.0892,
    "reasoning": "...",
    "aligned_sources_count": 2,
    "combined_score": 0.34
  }
  ```

  **Fallback chain**: If trader fails to produce a valid decision:
  1. Debate winner is bullish → BUY (recorded as fallback in trace)
  2. Debate winner is bearish → SELL (recorded as fallback)
  3. Otherwise → HOLD

  **Decision-bearing**: This agent's output is the primary input to risk validation. It is not purely advisory.

  ---

  ## 7. Risk Manager

  **Role**: Validate the trader's decision against portfolio state and risk limits. Compute final position size.

  **Skipped entirely** if trader decision is HOLD.

  **Inputs** (force-injected — LLM cannot alter these):
  - Trader decision and trade parameters
  - Current portfolio state (balance, equity, open positions, margin)
  - Risk limits for the run mode (simulation / paper / live)

  **MCP tools**:
  | Tool | Purpose | Inputs |
  |------|---------|--------|
  | `portfolio_risk_evaluation` | Deterministic risk check | Force-injected from registry |

  The LLM does not choose what to pass to this tool. All inputs are injected by the registry.

  **Tool output** (authoritative):
  ```json
  {
    "accepted": true,
    "suggested_volume": 0.01,
    "rejection_reason": null,
    "checks_applied": ["daily_loss_limit", "margin_requirement", "max_positions"]
  }
  ```

  **Override logic**: If the tool returns `accepted=false`, the run is blocked regardless of any LLM reasoning. If the tool returns `accepted=true` but the LLM summary attempts to reject, the tool result wins.

  **Output schema** (`RiskAssessmentResult`):
  ```json
  {
    "accepted": true,
    "suggested_volume": 0.01,
    "risk_percent_used": 0.8,
    "reasoning": "..."
  }
  ```

  ---

  ## 8. Execution Manager

  **Role**: Run preflight checks and submit the order to the broker (or record it in simulation).

  **Inputs**:
  - Risk assessment result (accepted, suggested_volume)
  - Trader decision (side, entry, SL, TP)
  - Market snapshot (current price, spread)

  **Execution**: Preflight is entirely deterministic (`ExecutionPreflightEngine`). No MCP tools are called. LLM is optional and disabled by default (`EXECUTION_MANAGER_LLM_ENABLED=false`). When enabled, LLM produces a narrative summary only — it does not influence the execution decision.

  **Output schema** (`ExecutionPlanResult`):
  ```json
  {
    "can_execute": true,
    "side": "BUY",
    "volume": 0.01,
    "status": "submitted | blocked | simulated",
    "checks_passed": ["idempotency", "symbol_valid", "spread_ok", "margin_ok"],
    "checks_failed": [],
    "order_id": "uuid"
  }
  ```

  See [Execution](execution.md) for full order flow detail.

  ---

  ## Agent skills bootstrap

  At startup, the registry loads an optional `agent-skills.json` file (path: `AGENT_SKILLS_BOOTSTRAP_FILE`) containing behavioral guidelines injected into agent system prompts. This is a soft influence on LLM behavior — agents may deviate from skills at their discretion.

  Mode is controlled by `AGENT_SKILLS_BOOTSTRAP_MODE` (`merge` or `replace`) and `AGENT_SKILLS_BOOTSTRAP_APPLY_ONCE` (default: `true`).

  ---

  ## Deterministic fallback mode

  Each agent has a `_run_deterministic()` code path. This activates when `llm_enabled=false` for the agent (set in DB config). In this mode:
  - No LLM call is made
  - MCP tools are called directly with pre-computed inputs
  - A structured output is built from tool results

  This is a configurable mode, not an error fallback. On LLM timeout or error, the registry retries (up to `AGENTSCOPE_RETRY_COUNT` times) and then propagates the error — it does **not** silently fall back to deterministic mode.

  ---

  ## Further reading

  - [Decision Pipeline](decision-pipeline.md) — how agent outputs combine
  - [Risk & Governance](risk-and-governance.md) — risk-manager detail
  - [Execution](execution.md) — execution-manager detail
  - [Runtime Flow](runtime-flow.md) — phase timing and conditions
  ```

- [ ] **Step 3: Verify agent tool lists and max_iters**

  Check `backend/app/services/agentscope/agents.py` for each agent's `max_iters` value and tool list.

- [ ] **Step 4: Commit**

  ```bash
  git add docs/agents.md
  git commit -m "docs: add agents reference"
  ```

---

## Task 7: Write `docs/decision-pipeline.md`

**Files:**
- Create: `docs/decision-pipeline.md`

- [ ] **Step 1: Read source files**

  Read `backend/app/services/agentscope/constants.py` (decision mode thresholds, scoring weights), `backend/app/services/agentscope/schemas.py` (structured output contracts).

- [ ] **Step 2: Write `docs/decision-pipeline.md`**

  ```markdown
  # Decision Pipeline

  This document describes how agent outputs are combined, scored, gated, and translated into a trade intent.

  ## Pipeline stages

  ```
  Market data + News
      ↓
  Phase 1: Parallel analysis (technical, news, market-context)
      ↓
  Weighted score + confidence aggregation
      ↓
  Phase 2+3: Debate (if LLM enabled for all 3 debate agents)
      ↓
  Phase 4: Trader decision → risk gate → preflight → execution
  ```

  ## Phase 1 aggregation

  Each Phase 1 agent produces a `score` (-1.0 to +1.0) and `confidence` (0.0 to 1.0).

  **Weighted average confidence**:
  ```
  combined_confidence = (
    tech_confidence * 0.50 +
    news_confidence * 0.25 +
    context_confidence * 0.25
  )
  ```

  **Combined score** (same weights):
  ```
  combined_score = (
    tech_score * 0.50 +
    news_score * 0.25 +
    context_score * 0.25
  )
  ```

  Weights are defined in `backend/app/services/agentscope/constants.py`.

  **Aligned sources count**: Count of Phase 1 agents whose direction (bullish/bearish/neutral) matches the combined direction. Used in gating.

  ## Decision gating policy

  The `decision_gating` MCP tool evaluates combined score, confidence, and aligned sources against the thresholds for the configured `DECISION_MODE`. It returns guidance to the trader-agent; the trader is the final arbiter.

  ### Mode thresholds

  Defined in `backend/app/services/agentscope/constants.py`:

  | Parameter | Conservative | Balanced (default) | Permissive |
  |-----------|-------------|-------------------|------------|
  | `min_combined_score` | 0.32 | 0.22 | 0.13 |
  | `min_confidence` | 0.38 | 0.28 | 0.25 |
  | `min_aligned_sources` | 2 | 1 | 1 |
  | `allow_technical_single_source_override` | false | true (if score ≥ 0.25) | true |
  | `block_major_contradiction` | true | true | true |

  ### Contradiction penalties

  When Phase 1 agents disagree significantly, confidence is penalized:

  | Contradiction level | Conservative | Balanced | Permissive |
  |--------------------|-------------|---------|------------|
  | Weak (minor disagreement) | -0.00 | -0.00 | -0.01 |
  | Moderate | confidence × 0.80 | confidence × 0.85 | confidence × 0.90 |
  | Major | confidence × 0.60 | confidence × 0.70 | confidence × 0.75 |

  Major contradictions block the trade in all three modes (`block_major_contradiction=true`).

  ## Technical scoring weights

  The `indicator_bundle` tool scores are combined using these weights (must sum to 1.0):

  | Signal | Weight |
  |--------|--------|
  | Trend direction | 0.22 |
  | Multi-timeframe alignment | 0.14 |
  | MACD | 0.16 |
  | RSI | 0.13 |
  | EMA crossover | 0.10 |
  | Divergence | 0.07 |
  | Price change | 0.06 |
  | Pattern detection | 0.06 |
  | Support/resistance levels | 0.06 |

  ## Debate mechanism

  The debate phase is a multi-turn MsgHub conversation between bullish-researcher, bearish-researcher, and trader-agent (as moderator). Debate runs 1–3 rounds (configurable via `DEBATE_MIN_ROUNDS`, `DEBATE_MAX_ROUNDS`).

  **Conditions for debate to run**:
  - `llm_enabled=true` for `bullish-researcher`, `bearish-researcher`, AND `trader-agent`
  - No timeout during Phase 1 that would make debate inputs inadequate

  **If any condition fails**: `DebateResult(winner="no_edge", conviction="weak")` is returned. The trader agent receives no debate input and decides based on Phase 1 analysis alone.

  **Debate output**:
  ```json
  {
    "winner": "bullish | bearish | no_edge",
    "conviction": "strong | moderate | weak",
    "key_argument": "...",
    "weakness": "..."
  }
  ```

  The debate result is advisory input to the trader. It does not override the trader's decision.

  ## Trader decision formation

  The trader-agent receives:
  - Phase 1 `analysis_summary` (concatenated text)
  - `DebateResult`
  - `combined_score`, `combined_confidence`, `aligned_sources_count`
  - Decision gating guidance (from `decision_gating` tool)

  The trader produces `TraderDecisionDraft` with:
  - `decision` (BUY / SELL / HOLD)
  - `conviction` (0.0–1.0)
  - `entry`, `stop_loss`, `take_profit`
  - `reasoning`

  If `entry`, `stop_loss`, or `take_profit` are missing, the `trade_sizing` tool is auto-called to compute ATR-based levels:
  - Stop loss: entry ± ATR × 1.5
  - Take profit: entry ± ATR × 2.5
  - Fallback (no ATR): SL = 0.3% from entry, TP = 0.6% from entry

  ## Structured output validation

  All agent outputs are Pydantic-validated. Invalid values are handled:
  - `NaN` or `Inf` in float fields → rejected, run fails
  - Out-of-range floats → clamped to schema bounds (e.g. confidence clamped to [0.0, 1.0])
  - Missing required fields → agent step marked failed; run may continue with partial data

  ## What happens to HOLD decisions

  If trader decides HOLD:
  - Risk manager is skipped entirely
  - Execution manager is skipped
  - Run completes as `completed` with no order created
  - The run trace records the HOLD reasoning

  ## Further reading

  - [Agents](agents.md) — per-agent output schemas
  - [Risk & Governance](risk-and-governance.md) — what happens after trade intent is formed
  - [Runtime Flow](runtime-flow.md) — phase timing
  ```

- [ ] **Step 3: Verify threshold values**

  Confirm all threshold values match `backend/app/services/agentscope/constants.py`.
  Confirm ATR multipliers (`SL_ATR_MULTIPLIER=1.5`, `TP_ATR_MULTIPLIER=2.5`) and fallback percentages.

- [ ] **Step 4: Commit**

  ```bash
  git add docs/decision-pipeline.md
  git commit -m "docs: add decision pipeline documentation with exact threshold values"
  ```

---

## Task 8: Write `docs/risk-and-governance.md`

**Files:**
- Create: `docs/risk-and-governance.md`

- [ ] **Step 1: Read source files**

  Read `backend/app/services/risk/rules.py` (risk checks, contract specs), `backend/app/services/risk/limits.py` (per-mode limits).

- [ ] **Step 2: Write `docs/risk-and-governance.md`**

  ```markdown
  # Risk and Governance

  The risk engine is deterministic Python code. It is not an LLM. Its decisions are authoritative — they cannot be overridden by any agent.

  ## Architecture

  ```
  Trader decision (BUY/SELL + entry/SL/TP/conviction)
      ↓
  portfolio_risk_evaluation MCP tool
      (force-injected inputs: portfolio state, risk limits, trade params)
      ↓
  RiskEngine.evaluate() — deterministic Python
      ↓
  { accepted: bool, suggested_volume: float, rejection_reason: str | null }
      ↓
  If accepted=false → run blocked, no execution (LLM cannot appeal)
  If accepted=true  → ExecutionPreflightEngine
  ```

  The MCP tool call uses `force_kwargs` — the registry injects all inputs directly. The LLM agent cannot alter what is passed to the tool.

  ## Per-mode risk limits

  Limits are defined in `backend/app/services/risk/limits.py`:

  | Limit | Simulation | Paper | Live |
  |-------|-----------|-------|------|
  | `max_daily_loss_pct` | 10% | 5% | 2% |
  | `max_weekly_loss_pct` | 15% | 10% | 5% |
  | `max_open_risk_pct` | 2% | 2% | 2% |
  | `max_positions` | 10 | 10 | 10 |
  | `max_positions_per_symbol` | 3 | 3 | 3 |
  | `min_free_margin_pct` | 30% | 30% | 30% |

  ## Checks applied

  | Check | Blocks trade? | Notes |
  |-------|--------------|-------|
  | Daily loss limit exceeded | Yes | Uses `daily_realized_pnl` from portfolio snapshot |
  | Weekly loss limit exceeded | Yes | Cumulative realized P&L for current week |
  | Max positions reached | Yes | Count of open positions vs limit |
  | Max positions per symbol | Yes | Count of open positions for this symbol |
  | Insufficient free margin | Yes | Free margin < required for position |
  | Currency exposure > 75% | Yes | Blocked (configurable threshold) |
  | Currency exposure > 50% | Warning only | Not a blocker by default |
  | NaN or Inf in price inputs | Yes | All float inputs validated via `_safe_float()` |
  | Invalid price range | Yes | Entry, SL, TP checked for realistic values |
  | Volume below asset minimum | Yes | Clamped/rejected per asset class |
  | Volume above asset maximum | Yes | Clamped/rejected per asset class |
  | Spread-to-price ratio > 5% | Yes | Checked in preflight (ExecutionPreflightEngine) |

  ## Asset class contract specs

  Defined in `backend/app/services/risk/rules.py`:

  | Asset class | pip_size | pip_value | contract_size | min_vol | max_vol |
  |-------------|----------|-----------|--------------|---------|---------|
  | Forex | 0.0001 (JPY: 0.01) | 10.0 | 100,000 | 0.01 | 10.0 |
  | Crypto | adaptive | 1.0 | 1 | 0.001 | 100 |
  | Index | 1.0 | 1.0 | 1 | 0.1 | 50 |
  | Metal/Energy | 0.01 | 10.0 | 1 | 0.01 | 10 |
  | Equity/ETF | 0.01 | 1.0 | 1 | 1.0 | 1000 |

  These are hardcoded defaults. They are not fetched from the broker at runtime. Exotic or non-standard instruments may use incorrect specs.

  ## LLM override behavior

  The risk-manager agent calls `portfolio_risk_evaluation` with force-injected inputs. The LLM produces a natural language summary but the tool result is what governs:

  | Scenario | Outcome |
  |----------|---------|
  | Tool: accepted=true, LLM summary: approve | Trade proceeds |
  | Tool: accepted=true, LLM summary: reject | **Tool wins** — trade proceeds |
  | Tool: accepted=false, LLM summary: approve | **Tool wins** — trade blocked |
  | Tool: accepted=false, LLM summary: reject | Trade blocked |

  This behavior is enforced in `backend/app/services/agentscope/registry.py`.

  ## What governance does NOT cover

  These gaps exist and are not silently assumed away:

  | Gap | Implication |
  |----|------------|
  | No portfolio-level aggregation across concurrent runs | Multiple simultaneous runs may each pass per-run risk checks while exceeding combined portfolio exposure |
  | No real-time broker margin check | Volume calculation uses local portfolio state, not live broker margin API |
  | Contract specs are hardcoded defaults | Exotic instruments may silently use wrong pip values |
  | No slippage or spread cost in sizing | Paper/live execution assumes exact fill |
  | No correlation-based position limits | Correlated positions (EUR pairs) count separately against per-symbol limits |

  ## Execution gating summary

  For a trade to execute, it must pass all of these in sequence:

  1. Trader decision is not HOLD
  2. Risk engine: `accepted=true`
  3. Preflight: `can_execute=true`
  4. `ALLOW_LIVE_TRADING=true` (live mode only)
  5. User has `TRADER_OPERATOR` role (live mode only)

  Failure at any step blocks execution. There is no appeal path.

  ## Further reading

  - [Execution](execution.md) — preflight and order submission
  - [Paper vs Live](paper-vs-live.md) — how limits differ by mode
  - [Limitations](limitations.md) — known gaps in risk coverage
  ```

- [ ] **Step 3: Verify limit values**

  Check `backend/app/services/risk/limits.py` for the per-mode values in the table. Confirm they match exactly.

- [ ] **Step 4: Commit**

  ```bash
  git add docs/risk-and-governance.md
  git commit -m "docs: add risk and governance documentation"
  ```

---

## Task 9: Write `docs/execution.md`

**Files:**
- Create: `docs/execution.md`

- [ ] **Step 1: Read source files**

  Read `backend/app/services/execution/executor.py`, `backend/app/services/execution/preflight.py`. Note idempotency key construction, mode-specific paths, MetaAPI call patterns.

- [ ] **Step 2: Write `docs/execution.md`**

  ```markdown
  # Execution

  The execution layer handles order submission after risk validation passes. It is composed of two sequential components: `ExecutionPreflightEngine` and `ExecutionService`.

  ## Execution modes

  | Mode | Description | Broker call? |
  |------|-------------|-------------|
  | `simulation` | Order recorded to DB as `status=simulated` | No |
  | `paper` | Order submitted to MetaAPI paper account | Yes (paper) |
  | `live` | Order submitted to MetaAPI live account | Yes (live) |

  Mode is set per-run at creation time. It cannot change mid-run.

  **Live trading is off by default.** `ALLOW_LIVE_TRADING=false` in `.env.example`. Even if set to `true`, the requesting user must have the `TRADER_OPERATOR` role.

  ## Preflight engine

  `ExecutionPreflightEngine` (`services/execution/preflight.py`) runs before any order is submitted. It is fully deterministic — no LLM call.

  Checks performed:

  | Check | Blocks? | Notes |
  |-------|---------|-------|
  | Idempotency key exists | No (replay) | Replays cached response instead of re-submitting |
  | Symbol validity | Yes | Symbol must be a recognized instrument |
  | Volume within asset bounds | Yes | Per asset class min/max |
  | Volume step compliance | Yes | e.g. Forex: 0.01 increments |
  | Spread-to-price ratio > 1% | Warning only | Logged, not blocked |
  | Spread-to-price ratio > 5% | Yes | Blocked |
  | Risk assessment accepted | Yes | Risk engine result must be `accepted=true` |

  Output:
  ```json
  {
    "can_execute": true,
    "side": "BUY",
    "volume": 0.01,
    "status": "PENDING",
    "checks_passed": ["idempotency_clear", "symbol_valid", "volume_ok", "spread_ok"],
    "checks_failed": []
  }
  ```

  ## Idempotency

  Each order is associated with an idempotency key:
  ```
  run={run_id}|mode={mode}|symbol={symbol}|side={side}|vol={vol}|sl={sl}|tp={tp}|acct={account}
  ```

  If an order with the same key already exists in the DB, the preflight returns `can_execute=false` with a replay response. This prevents duplicate orders when a run is retried or requeued.

  ## Order submission flow

  ```
  ExecutionPreflightEngine.validate() → { can_execute: true }
      ↓
  ExecutionService.execute()
      ↓
  Create ExecutionOrder record in DB (status=pending)
      ↓
  if mode == simulation:
      update status=simulated, no broker call
  if mode == paper:
      MetaApiClient.place_market_order(symbol, side, volume, sl, tp)
  if mode == live:
      MetaApiClient.place_market_order(symbol, side, volume, sl, tp)
      (only if ALLOW_LIVE_TRADING=true AND user has TRADER_OPERATOR role)
      ↓
  Store response_payload in DB
  Update order status (submitted | failed)
  ```

  ## Error handling

  | Error type | Behavior |
  |-----------|----------|
  | Network error / 5xx | Retry with exponential backoff (up to 3 attempts) |
  | 401 Unauthorized | Fail immediately — invalid MetaAPI credentials |
  | 429 Too Many Requests | 65-second cooldown (MetaAPI rate limit), then retry |
  | Invalid symbol | Fail immediately |
  | Insufficient funds | Fail immediately |
  | DB commit error | Rollback, run marked failed |

  ## Audit trail

  Every order is persisted to the `execution_order` table:

  ```sql
  id, run_id, mode, symbol, side, volume,
  stop_loss, take_profit, status,
  request_payload (JSON), response_payload (JSON),
  created_at, executed_at
  ```

  The request payload records what was sent; the response payload records what the broker returned. Both are queryable.

  ## MetaAPI integration

  Broker integration uses MetaAPI (MT4/MT5). Required configuration:

  | Variable | Description |
  |----------|-------------|
  | `METAAPI_TOKEN` | Authentication token |
  | `METAAPI_ACCOUNT_ID` | Default account ID |
  | `METAAPI_REGION` | API region (`new-york`, `london`, etc.) |

  Market data (`METAAPI_USE_SDK_FOR_MARKET_DATA=false` by default) uses the REST API, not the SDK, for candle/snapshot fetches.

  ## Known limitations

  - No partial fill handling — orders assumed to fill completely or fail
  - No order modification after placement — no trailing stop or SL/TP adjustment
  - No slippage modeling — paper and live execution assume exact fill at requested price
  - No commission modeling — P&L calculations do not account for broker fees
  - MetaAPI rate limiting can cause 65-second delays with stale market data in the UI

  See [Limitations](limitations.md) for the full list.

  ## Further reading

  - [Risk & Governance](risk-and-governance.md) — what must pass before preflight
  - [Paper vs Live](paper-vs-live.md) — what changes between modes
  - [Configuration](configuration.md) — MetaAPI settings
  ```

- [ ] **Step 3: Verify idempotency key format**

  Confirm idempotency key construction against `backend/app/services/execution/executor.py`.

- [ ] **Step 4: Commit**

  ```bash
  git add docs/execution.md
  git commit -m "docs: add execution documentation"
  ```

---

## Task 10: Write `docs/memory.md`

**Files:**
- Create: `docs/memory.md`

- [ ] **Step 1: Write `docs/memory.md`**

  ```markdown
  # Memory

  "Memory" in Kairos Mesh refers to two distinct things with very different behaviors: transient in-run agent memory, and persistent database storage. They serve different purposes and should not be confused.

  ## Transient agent memory (per-run)

  Each agent is initialized with an `InMemoryMemory` instance from the AgentScope framework. This memory:
  - Exists only for the duration of a single run
  - Stores the agent's message history within that run (tool calls, LLM responses)
  - Is cleared when the run completes
  - Is not shared between runs
  - Is not persisted to disk or database

  **There is no cross-run memory.** Each run starts with fresh agent context. Past decisions, outcomes, and patterns do not automatically influence future runs.

  ## Context injection (not retrieval)

  Before each run, the registry pre-loads and injects context into agents as structured inputs:
  - OHLC candles (fetched from MetaAPI or YFinance)
  - News items (fetched from configured news providers)
  - Portfolio state (fetched from MetaAPI account)
  - Phase 1 analysis outputs (passed to Phase 2+ agents)

  This is not memory retrieval. It is fresh data fetched at run start, not recalled from past runs.

  ## Persistent storage (PostgreSQL)

  All run data is persisted to PostgreSQL after each run completes:

  | Table | What is stored |
  |-------|---------------|
  | `analysis_run` | Run metadata, final decision, full agent trace (JSON) |
  | `agent_step` | Per-agent input payload, output payload, error, timing |
  | `execution_order` | Order requests, broker responses, status |
  | `llm_call_log` | Token counts, latency, cost per LLM call |
  | `portfolio_snapshot` | Pre/post-trade account state |

  This data is available for:
  - UI inspection (RunDetail page)
  - Analytics queries (LLM usage, win/loss rates)
  - Backtesting reference
  - Audit and debugging

  **It is not fed back to agents as training or context for future runs.**

  ## `MEMORI_*` environment variables

  The `.env.example` contains `MEMORI_*` prefixed variables. These are **not currently wired into application code**. They represent a potential future integration with a long-term memory store. No memory retrieval from an external vector database or persistent store is active in the current implementation.

  ## Write-back and outcome feedback

  There is no automated write-back path from trade outcomes to future agent behavior. Specifically:
  - No LLM fine-tuning from trade results
  - No RAG (retrieval-augmented generation) from historical decisions
  - No embedding store for past analyses
  - No reinforcement signal that modifies agent prompts or tool behavior based on P&L

  Win/loss rates and P&L data are queryable via the analytics API and visible in Grafana, but they do not flow back into the agent pipeline automatically.

  ## What this means in practice

  - The system does not "learn" from experience
  - Running the same pair/timeframe/config twice in a row with the same market data will produce the same agent behavior (modulo LLM nondeterminism)
  - Historical run data is useful for human review and manual strategy adjustment — not for automated improvement

  ## Future memory work

  If a memory retrieval path is implemented, the recommended integration point is context injection in `AgentScopeRegistry.execute()` before Phase 1, where agent context packages are assembled. No changes to agent code would be required.

  ## Further reading

  - [Architecture](architecture.md) — data model overview
  - [Observability](observability.md) — what run data is queryable
  - [Limitations](limitations.md) — incomplete memory feedback loop
  ```

- [ ] **Step 2: Verify MEMORI_ vars**

  Search `backend/app/` for any usage of `MEMORI_` prefix: `grep -r "MEMORI_" backend/app/ --include="*.py"`. Confirm it is absent from application code (only in `.env.example`).

- [ ] **Step 3: Commit**

  ```bash
  git add docs/memory.md
  git commit -m "docs: add memory documentation (transient vs persistent, no feedback loop)"
  ```

---

## Task 11: Write `docs/configuration.md`

**Files:**
- Create: `docs/configuration.md`

- [ ] **Step 1: Read source files**

  Read `backend/.env.example` (all variables), `backend/app/core/config.py` (defaults, types, aliases).

- [ ] **Step 2: Write `docs/configuration.md`**

  ```markdown
  # Configuration

  All configuration is via environment variables. Copy `backend/.env.example` to `backend/.env` and edit.

  For production, use `.env.prod.example` at the repository root.

  Variables are loaded via Pydantic Settings in `backend/app/core/config.py`.

  ---

  ## Application

  | Variable | Default | Required | Description |
  |----------|---------|----------|-------------|
  | `APP_NAME` | `Kairos Mesh` | No | Application name |
  | `ENV` | `dev` | No | `dev` or `prod` |
  | `SECRET_KEY` | `change-me` | **Yes (prod)** | JWT signing key — change before any non-local deployment |
  | `ACCESS_TOKEN_EXPIRE_MINUTES` | `720` | No | JWT token lifetime |
  | `CORS_ORIGINS` | `http://localhost:5173` | No | Comma-separated allowed origins |

  ---

  ## Database (PostgreSQL)

  | Variable | Default | Required | Description |
  |----------|---------|----------|-------------|
  | `DATABASE_URL` | `postgresql+psycopg2://...` | **Yes** | PostgreSQL connection string |
  | `POSTGRES_USER` | `trading` | No | Used to construct DATABASE_URL in Docker |
  | `POSTGRES_PASSWORD` | `trading` | No | Change in production |
  | `POSTGRES_DB` | `trading_platform` | No | Database name |
  | `DB_POOL_SIZE` | `12` | No | SQLAlchemy connection pool size |
  | `DB_MAX_OVERFLOW` | `24` | No | Max overflow connections |

  ---

  ## Message queue and cache

  | Variable | Default | Required | Description |
  |----------|---------|----------|-------------|
  | `REDIS_URL` | `redis://redis:6379/0` | **Yes** | Redis connection string |
  | `CELERY_BROKER_URL` | `amqp://guest:guest@rabbitmq:5672//` | **Yes** | RabbitMQ broker URL |
  | `CELERY_RESULT_BACKEND` | `redis://redis:6379/1` | **Yes** | Celery result backend |
  | `CELERY_WORKER_CONCURRENCY` | `2` | No | Parallel Celery worker threads |
  | `CELERY_ANALYSIS_SOFT_TIME_LIMIT_SECONDS` | `300` | No | Soft timeout per analysis task |
  | `CELERY_ANALYSIS_TIME_LIMIT_SECONDS` | `360` | No | Hard timeout per analysis task |

  ---

  ## LLM providers

  | Variable | Default | Required | Description |
  |----------|---------|----------|-------------|
  | `LLM_PROVIDER` | `ollama` | **Yes** | Active provider: `ollama`, `openai`, `mistral` |
  | `DECISION_MODE` | `balanced` | No | Gating policy: `conservative`, `balanced`, `permissive` |
  | `OLLAMA_BASE_URL` | `https://ollama.com` | No | Ollama API base URL |
  | `OLLAMA_MODEL` | `gpt-oss:120b-cloud` | No | Model name for Ollama |
  | `OLLAMA_API_KEY` | — | No | Ollama API key (if required) |
  | `OLLAMA_TIMEOUT_SECONDS` | `30` | No | Request timeout |
  | `OPENAI_API_KEY` | — | If using OpenAI | OpenAI API key |
  | `OPENAI_MODEL` | `gpt-4o-mini` | No | OpenAI model name |
  | `MISTRAL_API_KEY` | — | If using Mistral | Mistral API key |
  | `MISTRAL_MODEL` | `mistral-small-latest` | No | Mistral model name |

  ---

  ## Agent behavior

  | Variable | Default | Description |
  |----------|---------|-------------|
  | `AGENTSCOPE_AGENT_TIMEOUT_SECONDS` | `60` | Per-agent LLM call timeout (10–300s) |
  | `AGENTSCOPE_MAX_ITERS` | `3` | Max ReAct iterations per agent |
  | `AGENTSCOPE_CANDLE_LIMIT` | `240` | Max OHLC candles fetched per run |
  | `AGENTSCOPE_MIN_BARS` | `30` | Minimum bars required to proceed |
  | `AGENTSCOPE_RETRY_COUNT` | `3` | LLM call retry attempts on error |
  | `DEBATE_MAX_ROUNDS` | `3` | Maximum debate rounds |
  | `DEBATE_MIN_ROUNDS` | `1` | Minimum debate rounds |
  | `EXECUTION_MANAGER_LLM_ENABLED` | `false` | Enable LLM narrative for execution manager (does not affect execution decision) |

  ---

  ## Trading and execution

  | Variable | Default | ⚠️ Risk | Description |
  |----------|---------|---------|-------------|
  | `ALLOW_LIVE_TRADING` | `false` | **High** | Enable real broker order submission. Keep `false` unless explicitly setting up live trading. |
  | `ENABLE_PAPER_EXECUTION` | `true` | Medium | Enable paper trading via MetaAPI |
  | `METAAPI_TOKEN` | — | If using MetaAPI | MetaAPI authentication token |
  | `METAAPI_ACCOUNT_ID` | — | If using MetaAPI | Default MetaAPI account ID |
  | `METAAPI_REGION` | `new-york` | No | MetaAPI region |
  | `METAAPI_USE_SDK_FOR_MARKET_DATA` | `false` | No | Use MetaAPI SDK vs REST for candle/snapshot fetches |

  ---

  ## News providers

  Managed at runtime via UI (Connectors → News). Environment variables provide default keys if no DB config exists.

  | Variable | Description |
  |----------|-------------|
  | `NEWSAPI_API_KEY` | NewsAPI.org key |
  | `FINNHUB_API_KEY` | Finnhub key |
  | `ALPHAVANTAGE_API_KEY` | AlphaVantage key |
  | `TRADINGECONOMICS_API_KEY` | TradingEconomics key |

  ---

  ## Observability

  | Variable | Default | Description |
  |----------|---------|-------------|
  | `PROMETHEUS_ENABLED` | `true` | Enable Prometheus metrics at `/metrics` |
  | `OPEN_TELEMETRY_ENABLED` | `false` | Enable OpenTelemetry tracing export |
  | `LOG_AGENT_STEPS` | `true` | Log per-agent step details |
  | `DEBUG_TRADE_JSON_ENABLED` | `true` | Write full run trace to JSON file |
  | `DEBUG_TRADE_JSON_DIR` | `./debug-traces` | Directory for debug trace files |
  | `DEBUG_TRADE_JSON_INCLUDE_PROMPTS` | `true` | Include LLM prompts in trace files |

  ---

  ## Scheduler and orchestrator

  | Variable | Default | Description |
  |----------|---------|-------------|
  | `SCHEDULER_ENABLED` | `true` | Enable strategy monitor Celery Beat task |
  | `SCHEDULER_BATCH_SIZE` | `20` | Max strategies checked per Beat tick |
  | `ORCHESTRATOR_AUTONOMY_ENABLED` | `true` | Enable multi-cycle orchestrator (experimental) |
  | `ORCHESTRATOR_AUTONOMY_MAX_CYCLES` | `3` | Max autonomous re-runs per trigger |
  | `ORCHESTRATOR_PARALLEL_WORKERS` | `4` | Parallel orchestrator workers |

  > **Note**: `ORCHESTRATOR_AUTONOMY_ENABLED=true` is the default, but the multi-cycle autonomy path is not exercised in the main analysis flow. It is experimental. Treat as disabled until verified in code.

  ---

  ## Backtest

  | Variable | Default | Description |
  |----------|---------|-------------|
  | `BACKTEST_ENABLE_LLM` | `false` | Enable LLM calls during backtest (much slower) |
  | `BACKTEST_LLM_EVERY` | `24` | If LLM enabled, call every N candles |
  | `BACKTEST_AGENT_LOG_EVERY` | `25` | Log agent progress every N candles |

  ---

  ## Agent skills bootstrap

  | Variable | Default | Description |
  |----------|---------|-------------|
  | `AGENT_SKILLS_BOOTSTRAP_FILE` | `/app/config/agent-skills.json` | Path to skills JSON file |
  | `AGENT_SKILLS_BOOTSTRAP_MODE` | `merge` | `merge` or `replace` existing skills |
  | `AGENT_SKILLS_BOOTSTRAP_APPLY_ONCE` | `true` | Apply skills only on first startup |

  ---

  ## Settings that materially affect runtime behavior

  | Setting | Impact |
  |---------|--------|
  | `DECISION_MODE` | Changes score/confidence thresholds; affects how often trades are approved |
  | `ALLOW_LIVE_TRADING` | Enables real capital orders |
  | `AGENTSCOPE_AGENT_TIMEOUT_SECONDS` | Short values cause more agent timeouts → more partial/degraded runs |
  | `LLM_PROVIDER` + model | Different models produce meaningfully different reasoning quality |
  | `DEBATE_MAX_ROUNDS` | Affects run latency and debate depth |
  | `CELERY_WORKER_CONCURRENCY` | Parallel run throughput |
  ```

- [ ] **Step 3: Verify defaults**

  Cross-check all default values against `backend/app/core/config.py` Field definitions.

- [ ] **Step 4: Commit**

  ```bash
  git add docs/configuration.md
  git commit -m "docs: add full configuration reference"
  ```

---

## Task 12: Write `docs/observability.md`

**Files:**
- Create: `docs/observability.md`

- [ ] **Step 1: Read source files**

  Read `backend/app/observability/metrics.py`, `backend/app/main.py` (lifespan, middleware, telemetry setup).

- [ ] **Step 2: Write `docs/observability.md`**

  ```markdown
  # Observability

  ## What is instrumented

  | Signal | Tool | Status |
  |--------|------|--------|
  | HTTP request metrics | Prometheus | Enabled by default |
  | Risk evaluation metrics | Prometheus | Enabled by default |
  | Agent step logs | Structured log (stdout) | `LOG_AGENT_STEPS=true` |
  | Run trace (full JSON) | File on disk | `DEBUG_TRADE_JSON_ENABLED=true` |
  | LLM call logs | PostgreSQL | Always enabled |
  | Distributed tracing | OpenTelemetry | Disabled by default |
  | Grafana dashboards | Grafana | Configured in `infra/docker/` |
  | Alerting rules | Prometheus | Not configured |

  ## Prometheus metrics

  Endpoint: `GET /metrics` (Prometheus text format)

  Available metrics (defined in `backend/app/observability/metrics.py`):

  | Metric | Type | Labels | Description |
  |--------|------|--------|-------------|
  | `backend_http_requests_total` | Counter | method, route, status | Total HTTP requests |
  | `backend_http_request_duration_seconds` | Histogram | method, route | Request latency |
  | `risk_evaluation_total` | Counter | outcome (accepted/rejected) | Risk engine decisions |

  Prometheus scrapes `/metrics` in the Docker Compose setup. Grafana is preconfigured with dashboards at http://localhost:3000.

  **No alerting rules are configured by default.** Prometheus collects metrics but does not page on any condition.

  ## Run audit trail

  Every run produces a queryable audit trail in PostgreSQL:

  **`analysis_run` table**:
  ```
  id, pair, timeframe, mode, status (pending/queued/running/completed/failed),
  progress (0–100), decision (JSON), trace (JSON), error, created_at, updated_at
  ```

  The `trace` JSON contains the full `agentic_runtime` structure:
  - Per-agent message history
  - All tool invocations with inputs and outputs
  - Event timeline with timestamps
  - Celery task ID

  **`agent_step` table**:
  ```
  id, run_id, agent_name, status (success/failed),
  input_payload (JSON), output_payload (JSON), error, created_at
  ```

  **`execution_order` table**:
  ```
  id, run_id, mode, symbol, side, volume, stop_loss, take_profit,
  status, request_payload (JSON), response_payload (JSON), created_at, executed_at
  ```

  **`llm_call_log` table**:
  ```
  id, agent_id, provider, model, prompt_tokens, completion_tokens,
  total_tokens, cost_usd, latency_ms, response_status, error, created_at
  ```

  LLM usage is queryable via `GET /api/v1/analytics/llm-calls`. Aggregate stats (token counts, costs, latency) are available per run or per agent.

  ## Debug trace files

  When `DEBUG_TRADE_JSON_ENABLED=true` (default), each run writes a full trace JSON to `DEBUG_TRADE_JSON_DIR` (default: `./debug-traces/`):

  ```
  debug-traces/
    run-{id}-{timestamp}.json
  ```

  These files contain:
  - Full agent message history
  - All LLM prompts (if `DEBUG_TRADE_JSON_INCLUDE_PROMPTS=true`)
  - All tool call inputs and outputs
  - OHLC price history (if `DEBUG_TRADE_JSON_INCLUDE_PRICE_HISTORY=true`, up to `DEBUG_TRADE_JSON_PRICE_HISTORY_LIMIT` candles)
  - Final decision and risk/execution outcomes

  Files are written to local disk only — they are not centralized or shipped to an external system.

  ## OpenTelemetry tracing

  Disabled by default (`OPEN_TELEMETRY_ENABLED=false`).

  When enabled:
  - Instruments FastAPI via `FastAPIInstrumentor`
  - Exports spans to `AGENTSCOPE_TRACING_URL` (default: `http://tempo:4318/v1/traces`)
  - Compatible with Grafana Tempo

  Celery workers are traced separately via worker_tracing configuration. Cross-worker correlation IDs are propagated but span-level tracing across Celery workers is not fully implemented.

  ## WebSocket event stream

  Clients can subscribe to live run progress at:
  ```
  ws://localhost:8000/ws/runs/{run_id}
  ```

  Events are broadcast at each pipeline phase boundary (see [Runtime Flow](runtime-flow.md) progress table).

  ## Known gaps

  | Gap | Impact |
  |----|--------|
  | No alerting rules | Prometheus metrics are passive — no on-call notifications |
  | Debug traces written to local disk | Not available across worker replicas or after container restart |
  | No structured JSON log format | Logs are plain text stdout (not JSON lines) |
  | LLM prompts not logged to DB | Prompt content in debug JSON only (privacy trade-off) |
  | No distributed trace correlation | Cross-Celery spans not linked |

  ## Further reading

  - [Limitations](limitations.md) — observability limitations
  - [Architecture](architecture.md) — data model
  ```

- [ ] **Step 3: Verify metric names**

  Confirm metric names in `backend/app/observability/metrics.py` match what is documented.

- [ ] **Step 4: Commit**

  ```bash
  git add docs/observability.md
  git commit -m "docs: add observability documentation"
  ```

---

## Task 13: Write `docs/paper-vs-live.md`

**Files:**
- Create: `docs/paper-vs-live.md`

- [ ] **Step 1: Read source files**

  Read `backend/app/services/risk/limits.py` (per-mode limits), `backend/app/services/execution/executor.py` (mode-specific paths).

- [ ] **Step 2: Write `docs/paper-vs-live.md`**

  ```markdown
  # Paper Trading vs Live Trading

  Kairos Mesh supports three execution modes. Understanding what changes between them is essential before considering live use.

  ## Mode comparison

  | Aspect | Simulation | Paper | Live |
  |--------|-----------|-------|------|
  | Broker connection | None | MetaAPI paper account | MetaAPI live account |
  | Orders submitted to broker | No | Yes (paper) | Yes (real) |
  | Capital at risk | No | No | **Yes** |
  | Risk limits | Relaxed (10% daily loss) | Moderate (5% daily loss) | Strict (2% daily loss) |
  | DB order record created | Yes | Yes | Yes |
  | Default enabled | Yes | Yes (`ENABLE_PAPER_EXECUTION=true`) | **No** (`ALLOW_LIVE_TRADING=false`) |
  | Requires `TRADER_OPERATOR` role | No | No | **Yes** |

  ## What is shared between all modes

  - The full 8-agent analysis pipeline runs identically
  - Risk engine checks the same set of rules (different limits)
  - Execution preflight runs with the same checks
  - All run data, agent steps, and decisions are persisted to DB
  - WebSocket progress events are identical

  ## What differs in live mode

  1. **`ALLOW_LIVE_TRADING` must be `true`** in the backend environment. Default: `false`.
  2. **User must have `TRADER_OPERATOR` role**. This is not a default role.
  3. **Stricter risk limits**: 2% max daily loss (vs 5% paper, 10% simulation).
  4. **Real broker execution**: Orders go to a live MetaAPI account with real capital.

  Setting `ALLOW_LIVE_TRADING=true` without proper testing is strongly discouraged. See the checklist below.

  ## Simulation mode

  No broker connection is required. Useful for:
  - Evaluating the pipeline without MetaAPI credentials
  - Testing strategy configurations
  - Debugging agent behavior

  Orders are recorded in the `execution_order` table as `status=simulated`. No order reaches MetaAPI.

  ## Paper mode

  Requires:
  - `ENABLE_PAPER_EXECUTION=true` (default)
  - `METAAPI_TOKEN` and `METAAPI_ACCOUNT_ID` configured
  - A MetaAPI paper account (created in MetaAPI dashboard)

  Orders are submitted to the MetaAPI paper account. They are treated as real orders by MetaAPI but have no financial consequence. Fills are simulated.

  **Limitations of paper mode**:
  - Assumes exact fill at requested price — no slippage
  - No spread cost in P&L
  - No broker commissions
  - Paper account fill behavior may differ from live execution (especially at limit prices or during high volatility)

  ## Checklist before enabling live trading

  Work through this checklist before setting `ALLOW_LIVE_TRADING=true`:

  - [ ] You have run ≥ 50 analysis runs in simulation mode and reviewed agent outputs
  - [ ] You have run ≥ 20 analysis runs in paper mode and compared decisions to market outcomes
  - [ ] You understand the risk limits for live mode and have set appropriate `risk_percent` defaults
  - [ ] You have reviewed the [Limitations](limitations.md) page — specifically the execution and risk gaps
  - [ ] You have confirmed contract specs in `risk/rules.py` match your broker's instrument specifications
  - [ ] You understand that no slippage, spread, or commission is modeled
  - [ ] You have set a hard per-run `risk_percent` appropriate for your account size
  - [ ] You have a process for monitoring open orders and positions
  - [ ] You have tested the full pipeline end-to-end with `ALLOW_LIVE_TRADING=false` and confirmed it works correctly
  - [ ] You have reviewed the `SECURITY.md` document

  **This system does not manage live capital without human oversight.** There is no automated stop-loss monitoring, no trailing stop, no order modification, and no emergency stop mechanism beyond the per-run risk limits.

  ## Further reading

  - [Execution](execution.md) — order flow detail
  - [Risk & Governance](risk-and-governance.md) — limits and checks
  - [Limitations](limitations.md) — execution limitations
  - [Configuration](configuration.md) — `ALLOW_LIVE_TRADING`, `ENABLE_PAPER_EXECUTION`, `METAAPI_*`
  ```

- [ ] **Step 3: Verify risk limits**

  Confirm simulation/paper/live daily/weekly loss limits against `backend/app/services/risk/limits.py`.

- [ ] **Step 4: Commit**

  ```bash
  git add docs/paper-vs-live.md
  git commit -m "docs: add paper vs live trading comparison with safety checklist"
  ```

---

## Task 14: Write `docs/limitations.md`

**Files:**
- Create: `docs/limitations.md`

- [ ] **Step 1: Read source files**

  Read `docs/architecture/LIMITATIONS.md` (existing — use as source, improve and expand). Cross-reference against the codebase audit findings.

- [ ] **Step 2: Write `docs/limitations.md`**

  ```markdown
  # Limitations

  This document catalogues known limitations, incomplete features, and operational constraints. It is maintained to prevent overestimation of the system's current capabilities.

  **Reading this before deploying for any purpose involving real capital is mandatory.**

  ---

  ## Agent pipeline

  | Limitation | Impact | Status |
  |-----------|--------|--------|
  | No cross-run memory | Each run starts with fresh context. Past decisions, outcomes, and patterns do not influence future runs. | By design (stateless runs) |
  | Debate is conditional | Debate phase only runs when all 3 debate agents have LLM enabled in DB config. With default Ollama or partial config, debate is frequently skipped. | Known behavior |
  | Agent skills are soft guidelines | LLMs may deviate from `agent-skills.json` behavioral rules at any time. | Inherent to LLM-based agents |
  | Structured output degradation | Schema validation uses clamping/normalization that can mask low-quality LLM outputs. NaN/Inf fields are rejected, but near-threshold values may pass. | Graceful with guards |
  | Single LLM provider per run | All agents in a run use the same provider (Ollama/OpenAI/Mistral). Per-agent model selection is not supported. | Not implemented |
  | Deterministic fallback is not an error recovery | `_run_deterministic()` activates only when `llm_enabled=false`. LLM failures retry and then propagate as errors — they do not silently fall back. | By design |
  | `ORCHESTRATOR_AUTONOMY_ENABLED` flag exists but autonomy path is untested | The multi-cycle orchestrator flag is `true` by default but the code path is not exercised in the main analysis flow. | Experimental |

  ---

  ## Risk and execution

  | Limitation | Impact | Status |
  |-----------|--------|--------|
  | No portfolio-level risk aggregation | Multiple concurrent runs can each pass per-run risk checks while combined exposure exceeds portfolio tolerance. | Not implemented |
  | No real-time broker margin check | Volume sizing uses locally-fetched portfolio state, not live broker margin API. | Not implemented |
  | Contract specs are hardcoded defaults | Pip sizes, contract sizes, volume limits are static in `risk/rules.py`. Not fetched from broker. Exotic or non-standard instruments may use incorrect specs. | Known gap |
  | No slippage modeling | All modes assume exact fill at the requested price. | Not implemented |
  | No partial fill handling | Orders are assumed to fill completely or fail. | Not implemented |
  | No order modification | Positions cannot be modified after placement (no trailing stop, no SL/TP adjustment). | Not implemented |
  | No spread modeling in backtest | Backtest P&L ignores bid-ask spread. | Not implemented |
  | No commission modeling | Backtest, paper, and live P&L calculations ignore broker commissions. | Not implemented |
  | No emergency stop mechanism | There is no automated kill switch to close all positions or halt future runs. | Not implemented |

  ---

  ## Memory and learning

  | Limitation | Impact | Status |
  |-----------|--------|--------|
  | No automated feedback loop | Trade outcomes (win/loss, P&L) are stored in DB but do not flow back to agent behavior, prompts, or decision thresholds. | By design (current version) |
  | No RAG or vector retrieval | No retrieval from past decisions or analyses during runs. | Not implemented |
  | `MEMORI_*` env vars are not wired | Variables appear in `.env.example` but are not used in application code. | Planned |

  ---

  ## Strategy engine

  | Limitation | Impact | Status |
  |-----------|--------|--------|
  | 4 templates only | Strategy generation is limited to EMA crossover, RSI mean reversion, Bollinger breakout, MACD divergence. | By design |
  | No walk-forward testing | Backtests use in-sample data only. No out-of-sample validation. | Not implemented |
  | No Monte Carlo simulation | No confidence intervals on backtest results. | Not implemented |
  | Promotion is manual | VALIDATED → PAPER → LIVE strategy promotion requires manual action. | By design |

  ---

  ## Market data

  | Limitation | Impact | Status |
  |-----------|--------|--------|
  | MetaAPI primary, YFinance fallback | Different providers may return different candle granularity or timing. Results may differ depending on which provider serves the request. | Known inconsistency |
  | News API dependency | News tools depend on external API availability and rate limits. | External dependency |
  | No real-time tick data | Analysis uses candle snapshots, not tick-by-tick data. | By design |
  | No order book data | No depth-of-market or level 2 data integration. | Not implemented |
  | Instrument classification is heuristic | `InstrumentClassifier` uses pattern matching. May misclassify exotic symbols, leading to wrong contract specs. | Known gap |

  ---

  ## Observability

  | Limitation | Impact | Status |
  |-----------|--------|--------|
  | No alerting rules | Prometheus metrics exist but no default alert rules are configured. | Not implemented |
  | Debug traces written to local disk | Not available across replicas or after container restart without volume mount. | Known gap |
  | No structured JSON log format | Logs are plain text stdout. | Known gap |
  | No LLM prompt logging to DB | Full prompts only in debug JSON trace files (privacy consideration). | Intentional |
  | Cross-Celery trace correlation incomplete | Correlation IDs propagated but span-level tracing across workers not fully connected. | Partial |

  ---

  ## Security

  | Limitation | Impact | Status |
  |-----------|--------|--------|
  | JWT stored in localStorage | Standard SPA pattern; vulnerable to XSS attacks. | Known trade-off |
  | No API key rotation mechanism | MetaAPI and LLM API keys stored in DB, no automated rotation. | Not implemented |
  | No rate limiting on endpoints | Login, LLM, and backtest endpoints are unprotected against brute force or DoS. | Not implemented |
  | Connector config changes not audited | UI changes to LLM/news provider settings are not tracked in the audit log. | Not implemented |

  ---

  ## Frontend

  | Limitation | Impact | Status |
  |-----------|--------|--------|
  | Polling-based updates for most data | Most data fetches use polling (3–5s), not pure push. WebSocket is used for run progress only. | Known trade-off |
  | No mobile layout | Dashboard is designed for desktop monitors. | Not implemented |
  | `ENABLE_METAAPI_REAL_TRADES_DASHBOARD` is `false` by default | Real trades dashboard feature is incomplete. | Experimental |

  ---

  ## What this system is not

  - **Not a high-frequency trading system** — analysis runs take seconds to minutes due to LLM latency
  - **Not a portfolio management system** — single-position, single-instrument per run
  - **Not a regulated trading platform** — no compliance tooling, no regulatory audit trail
  - **Not a backtesting framework** — backtesting is a validation utility, not a primary feature
  - **Not autonomous** — requires human oversight for strategy promotion and live trading enablement
  - **Not production-hardened** — the codebase has not undergone security or load-testing at scale

  ---

  ## Legacy items

  | Item | Location | Notes |
  |------|----------|-------|
  | French signal parsing tokens | `agents.py` (via agentscope schemas) | Parses legacy LLM outputs that may contain French text |
  | `_normalize_legacy_market_wording` | `registry.py` | Normalizes French text from user-stored prompt templates |
  | `forex.db` | Repository root | Legacy SQLite database — not used by the application |
  ```

- [ ] **Step 3: Cross-reference with codebase audit**

  Verify the `MEMORI_*` / `ORCHESTRATOR_AUTONOMY_ENABLED` notes against actual code. Confirm `forex.db` at repo root, `ENABLE_METAAPI_REAL_TRADES_DASHBOARD=false` in `.env.example`.

- [ ] **Step 4: Commit**

  ```bash
  git add docs/limitations.md
  git commit -m "docs: add honest limitations document"
  ```

---

## Task 15: Write `CONTRIBUTING.md`

**Files:**
- Create: `CONTRIBUTING.md`

- [ ] **Step 1: Read source files**

  Read `Makefile` (available targets), `backend/tests/` structure, `docker-compose.yml` (dev setup).

- [ ] **Step 2: Write `CONTRIBUTING.md`**

  ```markdown
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
  ```

- [ ] **Step 3: Commit**

  ```bash
  git add CONTRIBUTING.md
  git commit -m "docs: add CONTRIBUTING guide"
  ```

---

## Task 16: Write `SECURITY.md`

**Files:**
- Create: `SECURITY.md`

- [ ] **Step 1: Write `SECURITY.md`**

  ```markdown
  # Security

  ## Reporting vulnerabilities

  If you discover a security vulnerability, please do not open a public GitHub issue.

  Report it privately via GitHub's [Security Advisories](../../security/advisories/new) feature or by emailing the maintainers directly.

  Include:
  - Description of the vulnerability
  - Steps to reproduce
  - Potential impact
  - Any suggested mitigation

  We will acknowledge receipt within 48 hours and aim to release a fix within 14 days for critical issues.

  ## Security model

  Kairos Mesh is designed for research and evaluation use. It has not been audited or hardened for production deployment with real capital.

  ### Trust boundaries

  | Boundary | Enforcement | Notes |
  |----------|-------------|-------|
  | LLM cannot submit orders directly | Orders go through `ExecutionService` after deterministic preflight | Enforced in code |
  | Risk tool overrides LLM | `portfolio_risk_evaluation` result is authoritative | Enforced in code |
  | Live trading off by default | `ALLOW_LIVE_TRADING=false` | Environment variable |
  | Live trading requires role | `TRADER_OPERATOR` role checked at API | Enforced in code |

  ### Known security limitations

  | Issue | Severity | Notes |
  |-------|----------|-------|
  | JWT in localStorage | Medium | Vulnerable to XSS; standard SPA trade-off |
  | No rate limiting on API endpoints | Medium | Login, LLM, backtest endpoints unprotected |
  | No API key rotation | Medium | LLM and broker keys stored in DB |
  | Connector config changes not audited | Low | UI changes to LLM/news config not logged |
  | `SECRET_KEY` default in `.env.example` | **High** | Must be changed before any non-local deployment |
  | Default PostgreSQL credentials | **High** | `trading`/`trading` — must be changed in production |

  ## Deployment security notes

  Before deploying to any environment accessible beyond localhost:

  1. **Change `SECRET_KEY`** — the default value in `.env.example` is public
  2. **Change PostgreSQL credentials** — default `trading`/`trading` is not acceptable
  3. **Restrict CORS** — update `CORS_ORIGINS` to your specific frontend origin
  4. **Keep `ALLOW_LIVE_TRADING=false`** unless you have completed the checklist in [Paper vs Live](docs/paper-vs-live.md)
  5. **Do not expose MetaAPI tokens** in environment files committed to version control

  ## Supported versions

  This project does not yet have a formal versioning or LTS policy. Security fixes are applied to the main branch.
  ```

- [ ] **Step 2: Commit**

  ```bash
  git add SECURITY.md
  git commit -m "docs: add SECURITY.md with vulnerability reporting and security model"
  ```

---

## Task 17: Remove `docs/architecture/` subdirectory

**Files:**
- Delete: `docs/architecture/` (all 16 files)

All content has been absorbed into the new flat `docs/` layout in tasks 4–14.

- [ ] **Step 1: Verify all content is absorbed**

  Before deleting, confirm each file in `docs/architecture/` has its key content covered in the new docs:
  - `ARCHITECTURE.md` → `docs/architecture.md` ✓
  - `AGENTS.md` → `docs/agents.md` ✓
  - `RUNTIME_FLOW.md` → `docs/runtime-flow.md` ✓
  - `RISK_AND_EXECUTION.md` → `docs/risk-and-governance.md` + `docs/execution.md` ✓
  - `decision-modes.md` → `docs/decision-pipeline.md` ✓
  - `OBSERVABILITY.md` → `docs/observability.md` ✓
  - `LIMITATIONS.md` → `docs/limitations.md` ✓
  - `MODULES.md` → absorbed into `docs/architecture.md` project structure ✓
  - `STRATEGY_ENGINE.md` → referenced in `README.md` and `docs/architecture.md` ✓
  - `BACKTEST_AND_VALIDATION.md` → not reproduced (strategy backtesting is out of scope for this refactor) — leave for a follow-up
  - `FUTURE_ROADMAP.md` → deliberately not reproduced (roadmaps are aspirational; conflicts with accuracy-first goal)
  - `NAMING_AND_TERMINOLOGY.md` → integrated into relevant docs
  - `DOCUMENTATION_SCOPE_AND_LIMITS.md` → replaced by `docs/limitations.md`
  - `STRATEGIES_WORKFLOW.md` → not reproduced in this refactor (strategy workflow is a follow-up)
  - `custom-strategy-engine-v2.md` → not reproduced (implementation detail, not user doc)

- [ ] **Step 2: Delete the directory**

  ```bash
  git rm -r docs/architecture/
  ```

- [ ] **Step 3: Commit**

  ```bash
  git commit -m "docs: remove docs/architecture/ — content absorbed into flat docs/ layout"
  ```

---

## Task 18: Final cross-check pass

- [ ] **Step 1: Verify all links in README.md resolve**

  Check every `docs/` link in `README.md` points to a file that now exists:
  ```bash
  for f in docs/getting-started.md docs/quickstart.md docs/architecture.md docs/runtime-flow.md \
    docs/agents.md docs/decision-pipeline.md docs/risk-and-governance.md docs/execution.md \
    docs/memory.md docs/configuration.md docs/observability.md docs/paper-vs-live.md \
    docs/limitations.md; do
    [ -f "$f" ] && echo "OK: $f" || echo "MISSING: $f"
  done
  ```

- [ ] **Step 2: Verify `ALLOW_LIVE_TRADING=false` is the actual default**

  ```bash
  grep "ALLOW_LIVE_TRADING" backend/.env.example
  ```
  Expected: `ALLOW_LIVE_TRADING=false`

- [ ] **Step 3: Verify debate conditional logic**

  ```bash
  grep -n "llm_enabled\|debate\|no_edge" backend/app/services/agentscope/registry.py | head -20
  ```
  Confirm debate is skipped when `llm_enabled=false` for debate agents.

- [ ] **Step 4: Verify decision mode threshold values**

  ```bash
  grep -A 5 "CONSERVATIVE\|BALANCED\|PERMISSIVE" backend/app/services/agentscope/constants.py
  ```
  Confirm values match the tables in `docs/decision-pipeline.md`.

- [ ] **Step 5: Check for any remaining `docs/architecture/` references**

  ```bash
  grep -r "docs/architecture/" . --include="*.md" | grep -v ".git"
  ```
  Should return no matches (except the spec file).

- [ ] **Step 6: Final commit**

  ```bash
  git add -A
  git commit -m "docs: final cross-check — verify all links and claims"
  ```

---

## Self-review against spec

**Spec coverage check**:

| Spec requirement | Task |
|-----------------|------|
| README with "current scope / reality check" | Task 1 |
| `docs/getting-started.md` | Task 2 |
| `docs/quickstart.md` | Task 3 |
| `docs/architecture.md` | Task 4 |
| `docs/runtime-flow.md` | Task 5 |
| `docs/agents.md` (all 8 agents, advisory vs binding) | Task 6 |
| `docs/decision-pipeline.md` (thresholds, debate conditions) | Task 7 |
| `docs/risk-and-governance.md` (tool-overrides-LLM) | Task 8 |
| `docs/execution.md` (idempotency, paper/live) | Task 9 |
| `docs/memory.md` (transient vs persistent, no feedback loop) | Task 10 |
| `docs/configuration.md` (full env var tables) | Task 11 |
| `docs/observability.md` | Task 12 |
| `docs/paper-vs-live.md` (safety checklist) | Task 13 |
| `docs/limitations.md` | Task 14 |
| `CONTRIBUTING.md` | Task 15 |
| `SECURITY.md` | Task 16 |
| Retire `docs/architecture/` | Task 17 |
| Verification pass | Task 18 |

**Placeholder scan**: No TBDs, TODOs, or vague steps found.

**Type consistency**: No cross-task type references; each task is self-contained.

**Scope check**: Documentation only — no code changes. All 15 deliverables from spec are covered.
