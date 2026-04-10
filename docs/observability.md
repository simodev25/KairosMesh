# Observability

Kairos Mesh exposes four observability mechanisms: Prometheus metrics, structured run records in PostgreSQL, WebSocket real-time events to the frontend, and debug trade trace files. A Grafana instance is included in the default Docker Compose stack and is pre-provisioned with dashboards. OpenTelemetry / distributed tracing exists as a configuration option but is not wired to a trace backend by default.

---

## 1. Prometheus Metrics

**Default:** enabled (`PROMETHEUS_ENABLED=true`)

Metrics are served on two endpoints:

| Endpoint | Source | Default address |
|---|---|---|
| `GET /metrics` | FastAPI backend (HTTP middleware) | `http://backend:8000/metrics` |
| `GET /metrics` | Celery worker (standalone HTTP server) | `http://worker:9101/metrics` (`PROMETHEUS_WORKER_PORT`) |

The worker metrics server is started once per process and supports `prometheus_client` multiprocess mode when `PROMETHEUS_MULTIPROC_DIR` is set. Configuration is in `backend/app/observability/prometheus.py`.

### Metric catalogue

All metric definitions live in `backend/app/observability/metrics.py`.

#### HTTP

| Metric | Type | Labels |
|---|---|---|
| `backend_http_requests_total` | Counter | `method`, `route`, `status` |
| `backend_http_request_duration_seconds` | Histogram | `method`, `route` |

#### Analysis runs (legacy path)

| Metric | Type | Labels |
|---|---|---|
| `analysis_runs_total` | Counter | `status` |
| `orchestrator_step_duration_seconds` | Histogram | `agent` |

#### Agentic runtime

| Metric | Type | Labels |
|---|---|---|
| `agentic_runtime_runs_total` | Counter | `status`, `mode`, `resumed` |
| `agentic_runtime_tool_selections_total` | Counter | `tool`, `source`, `degraded` |
| `agentic_runtime_planner_calls_total` | Counter | `status`, `source` |
| `agentic_runtime_planner_duration_seconds` | Histogram | `status`, `source` |
| `agentic_runtime_tool_calls_total` | Counter | `tool`, `status` |
| `agentic_runtime_tool_duration_seconds` | Histogram | `tool`, `status` |
| `agentic_runtime_subagent_sessions_total` | Counter | `source_tool`, `session_mode`, `status`, `resumed` |
| `agentic_runtime_final_decisions_total` | Counter | `decision`, `mode` |
| `agentic_runtime_execution_outcomes_total` | Counter | `status`, `mode` |
| `agentic_runtime_session_messages_total` | Counter | `resume_requested` |

#### LLM

| Metric | Type | Labels |
|---|---|---|
| `llm_calls_total` | Counter | `provider`, `status` |
| `llm_prompt_tokens_total` | Counter | `provider`, `model` |
| `llm_completion_tokens_total` | Counter | `provider`, `model` |
| `llm_cost_usd_total` | Counter | `provider`, `model` |
| `llm_latency_seconds` | Histogram | `provider`, `model`, `status` |
| `external_provider_failures_total` | Counter | `provider` |

#### Cache

| Metric | Type | Labels |
|---|---|---|
| `metaapi_cache_hits_total` | Counter | `resource` |
| `metaapi_cache_misses_total` | Counter | `resource` |
| `yfinance_cache_hits_total` | Counter | `resource` |
| `yfinance_cache_misses_total` | Counter | `resource` |
| `metaapi_sdk_circuit_open_total` | Counter | `region`, `operation` |

#### MCP tool layer

| Metric | Type | Labels |
|---|---|---|
| `mcp_tool_calls_total` | Counter | `tool`, `status` |
| `mcp_tool_duration_seconds` | Histogram | `tool`, `status` |

#### Decision quality / risk engine

| Metric | Type | Labels |
|---|---|---|
| `debate_impact_abs` | Histogram | `decision`, `strong_conflict` |
| `contradiction_detection_total` | Counter | `level` |
| `decision_gate_blocks_total` | Counter | `gate` |
| `risk_evaluation_total` | Counter | `accepted`, `asset_class`, `mode` |

### Prometheus scrape configuration

The default scrape config (`infra/docker/prometheus.yml`) scrapes both targets every 15 seconds:

```yaml
scrape_configs:
  - job_name: forex_backend
    static_configs:
      - targets: ['backend:8000']
    metrics_path: /metrics
  - job_name: forex_worker
    static_configs:
      - targets: ['worker:9101']
    metrics_path: /metrics
```

### Env vars

| Var | Default | Effect |
|---|---|---|
| `PROMETHEUS_ENABLED` | `true` | Enables the `/metrics` endpoint on the backend |
| `PROMETHEUS_WORKER_PORT` | `9101` | Port for the worker's standalone metrics HTTP server |
| `PROMETHEUS_MULTIPROC_DIR` | _(unset)_ | When set, enables `prometheus_client` multiprocess aggregation across forked workers |

---

## 2. Structured Run Records (Audit Trail)

Every analysis run writes a structured record to PostgreSQL. This is an **audit trail**, not a learning store. Records are queryable via the UI or directly in the database.

### Tables

#### `analysis_runs`

One row per run. Defined in `backend/app/db/models/run.py`.

| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | Auto-increment |
| `pair` | String(20) | Canonical symbol, e.g. `EURUSD` |
| `timeframe` | String(10) | e.g. `H1` |
| `mode` | String(20) | `simulation`, `paper`, or `live` |
| `status` | String(30) | `pending`, `queued`, `running`, `completed`, `failed`, `cancelled` |
| `progress` | SmallInteger | 0–100 percentage |
| `decision` | JSON | Final trading decision object |
| `trace` | JSON | Runtime trace blob (events, debug_trace_meta, celery_task_id, etc.) |
| `error` | Text | Error message if failed |
| `created_by_id` | FK → `users` | Owning user |
| `created_at` | DateTime | Run creation time |
| `started_at` | DateTime | When execution began |
| `updated_at` | DateTime | Last modification |

#### `agent_steps`

One row per agent execution within a run. Controlled by `LOG_AGENT_STEPS`. Defined in `backend/app/db/models/agent_step.py`.

| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `run_id` | FK → `analysis_runs` | |
| `agent_name` | String(100) | e.g. `technical-analyst`, `trader-agent` |
| `status` | String(20) | `completed` or `failed` |
| `input_payload` | JSON | Inputs passed to the agent (pair, timeframe, context key) |
| `output_payload` | JSON | Agent output including `elapsed_ms` |
| `error` | Text | Error if agent failed |
| `created_at` | DateTime | Step timestamp |

When `LOG_AGENT_STEPS=false`, `_record_step()` in `backend/app/services/agentscope/registry.py` still executes but the setting is checked upstream in some task paths to skip step DB writes entirely.

#### `llm_call_logs`

One row per LLM API call. Defined in `backend/app/db/models/llm_call_log.py`.

| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `provider` | String(50) | e.g. `openai`, `ollama`, `mistral` |
| `model` | String(100) | Model identifier |
| `status` | String(20) | `success` or `error` |
| `prompt_tokens` | Integer | |
| `completion_tokens` | Integer | |
| `total_tokens` | Integer | |
| `cost_usd` | Float | Estimated cost using configured per-token rates |
| `latency_ms` | Float | End-to-end call latency |
| `error` | Text | Error string if call failed |
| `created_at` | DateTime | Call timestamp |

LLM call logs are not linked by foreign key to a run. Correlation is possible via `created_at` timestamp range.

#### `execution_orders`

One row per order attempt. Defined in `backend/app/db/models/execution_order.py`.

| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `run_id` | FK → `analysis_runs` | |
| `mode` | String(20) | `simulation`, `paper`, or `live` |
| `side` | String(10) | `buy` or `sell` |
| `symbol` | String(20) | |
| `volume` | Float | Lot size |
| `status` | String(30) | `created`, `submitted`, `filled`, `rejected`, etc. |
| `request_payload` | JSON | Full order request sent to broker |
| `response_payload` | JSON | Full broker response |
| `error` | Text | Error if order failed |
| `created_at` | DateTime | Order creation time |

---

## 3. WebSocket Protocol

The frontend receives real-time updates via WebSocket. All WebSocket endpoints require JWT authentication. The token can be sent in the `Authorization: Bearer <token>` header or, if `WS_ALLOW_QUERY_TOKEN=true`, as a `?token=` query parameter.

Endpoints are defined in `backend/app/main.py`.

### `/ws/runs/{run_id}`

Streams status updates for a single analysis run.

**Poll interval:** `WS_RUN_POLL_SECONDS` (default: `2.0` seconds, minimum enforced: `0.5` seconds)

The server polls the database on each tick and sends events only when state changes.

**Message types:**

| `type` field | When sent | Fields |
|---|---|---|
| `status` | When `(status, updated_at)` changes from the previous tick | `id`, `status`, `decision`, `updated_at` |
| `event` | When new runtime events appear in `run.trace.agentic_runtime.events` | `id`, `updated_at`, `event` (the raw event payload) |
| `{"error": "Run not found"}` | If `run_id` does not exist | — |

**Close codes:**
- When `run_id` does not exist the server sends `{"error": "Run not found"}` and then closes the connection with code `1008` (Policy Violation).
- When `status` reaches `completed` or `failed` the server closes the connection with code `1000` (Normal Closure).

### `/ws/trading/orders`

Streams execution order updates.

**Poll interval:** `WS_TRADING_ORDERS_POLL_SECONDS` (default: `2.0` seconds)

| `type` field | When sent | Fields |
|---|---|---|
| `snapshot` | First message after connect (latest order at that moment) | `order` object |
| `execution-order` | Each subsequent new order detected | `order` object |

The `order` object contains: `id`, `run_id`, `mode`, `status`, `symbol`, `created_at`.

### `/ws/market/prices`

Streams real-time price ticks from the MetaAPI SDK. Accepts an optional `?symbol=` query parameter to filter by symbol. Sends a cached price immediately on connect if available. Does not use database polling — tick delivery is push-based via an internal asyncio queue.

### `/ws/portfolio`

Streams portfolio state (balance, equity, margins, drawdown, open positions, risk limits, currency exposure). Updates every 10 seconds. Not configurable via env var.

### Env vars

| Var | Default | Effect |
|---|---|---|
| `WS_RUN_POLL_SECONDS` | `2.0` | Poll interval for `/ws/runs/{run_id}` |
| `WS_TRADING_ORDERS_POLL_SECONDS` | `2.0` | Poll interval for `/ws/trading/orders` |
| `WS_REQUIRE_AUTH` | `true` | Require JWT on all WebSocket connections |
| `WS_ALLOW_QUERY_TOKEN` | `false` | Allow token as `?token=` query param (off by default for security) |

---

## 4. Debug Trade Trace Files

When enabled, the system writes a JSON file per run to the configured directory. This is useful for detailed post-run inspection of what each agent saw and decided. The files are self-contained — no database access is required to read them.

**Default:** disabled (`debug_trade_json_enabled=False` in `backend/app/core/config.py`; the `.env.example` shows `DEBUG_TRADE_JSON_ENABLED=true` for development convenience).

Trace files are written by `_write_debug_trace()` in `backend/app/services/agentscope/registry.py`. A metadata stub (`run.trace.debug_trace_meta`) is written back to the run's PostgreSQL record to record the filename and schema version.

### File naming

```
<DEBUG_TRADE_JSON_DIR>/run-<id>-<YYYYMMDDTHHMMSSz>.json
```

### Schema version 2 structure

| Top-level key | Contents |
|---|---|
| `schema_version` | `2` |
| `generated_at` | ISO-8601 UTC timestamp |
| `runtime_engine` | `agentscope_v1` |
| `trading_params_version` | Active config version integer |
| `trading_params` | Decision mode, execution mode, gating thresholds, risk limits, sizing parameters |
| `run` | Run ID, pair, timeframe, mode, status, risk_percent, timestamps |
| `context.market_snapshot` | Price snapshot at run time |
| `context.price_history` | OHLC candle list (controlled by `DEBUG_TRADE_JSON_INCLUDE_PRICE_HISTORY` and `DEBUG_TRADE_JSON_PRICE_HISTORY_LIMIT`) |
| `context.news_context` | News articles passed to the news analyst |
| `workflow` | Ordered list of agent names that ran |
| `agent_steps` | Per-agent: name, status, llm_enabled, input_payload, output_payload (includes indicators, patterns, divergences, structures, multi_timeframe), output_text excerpt, prompt_meta |
| `analysis_bundle` | Structured outputs from all agents keyed by role |
| `final_decision` | The `run.decision` JSON object |
| `execution` | Execution section of the final decision |
| `elapsed_seconds` | Total run wall-clock time |

### Env vars

| Var | Default | Effect |
|---|---|---|
| `DEBUG_TRADE_JSON_ENABLED` | `false` | Enable/disable trace file writing |
| `DEBUG_TRADE_JSON_DIR` | `./debug-traces` | Directory where files are written |
| `DEBUG_TRADE_JSON_INCLUDE_PROMPTS` | `true` | Include `prompt_meta` (rendered prompt templates) in agent step entries |
| `DEBUG_TRADE_JSON_INCLUDE_PRICE_HISTORY` | `true` | Include OHLC candle array in `context.price_history` |
| `DEBUG_TRADE_JSON_PRICE_HISTORY_LIMIT` | `200` | Maximum number of candles written (trailing N bars) |
| `DEBUG_TRADE_JSON_INLINE_IN_RUN_TRACE` | `false` | When true, embeds the trace payload directly into `run.trace` instead of writing a separate file |

---

## 5. OpenTelemetry — Partial / Not Wired by Default

`OPEN_TELEMETRY_ENABLED=false` by default (`backend/app/core/config.py`, line 165).

When set to `true`, `FastAPIInstrumentor.instrument_app(app)` is called in `backend/app/main.py`, which attaches the OpenTelemetry FastAPI middleware. However, no OTLP exporter is configured in code — spans will be produced in-process but not exported anywhere unless the operator configures an OTLP exporter via standard OpenTelemetry SDK environment variables (e.g. `OTEL_EXPORTER_OTLP_ENDPOINT`).

A **Tempo** service is included in the Docker Compose stack (`infra/docker/tempo.yml`), listening on OTLP gRPC (`0.0.0.0:4317`) and HTTP (`0.0.0.0:4318`). Grafana is provisioned to use it as a Tempo datasource. However, the Celery worker and the agentic runtime do not send traces to Tempo in the default setup.

The worker has a helper `backend/app/tasks/worker_tracing.py` that calls `agentscope.init()` with a tracing URL (`AGENTSCOPE_TRACING_URL`, default `http://tempo:4318/v1/traces`). This runs per-process but is only invoked if `agentscope` is importable and `init()` succeeds — the surrounding `try/except` swallows failures silently.

**Summary:** the infrastructure for distributed tracing exists (Tempo, OTLP receiver, Grafana datasource, FastAPI instrumentation hook, AgentScope tracing init), but it is not activated or validated in the default configuration. Treat this as scaffolding, not a working feature.

| Var | Default | Effect |
|---|---|---|
| `OPEN_TELEMETRY_ENABLED` | `false` | Activates FastAPI OTLP instrumentation |
| `AGENTSCOPE_TRACING_URL` | `http://tempo:4318/v1/traces` | OTLP HTTP endpoint used by the worker tracing init helper. Read via `os.environ.get()` in `backend/app/tasks/worker_tracing.py` (line 16) — **not** part of the Pydantic settings model in `config.py`, so it is not validated by the app settings system. |

---

## 6. Grafana

Grafana is included in the default Docker Compose stack (`docker-compose.yml`).

| Property | Value |
|---|---|
| Access URL | `http://localhost:3000` |
| Default credentials | `admin` / `admin` |
| Image | `grafana/grafana:11.2.2` |

Provisioning files are mounted from `infra/docker/grafana/provisioning/`. Dashboards are mounted from `infra/docker/grafana/dashboards/` and loaded automatically on startup.

### Pre-provisioned dashboards

| File | Purpose |
|---|---|
| `agent-runtime-overview.json` | Overview of agentic runtime run counts, decisions, tool usage |
| `agent-runtime-sessions.json` | Subagent session lifecycle metrics |
| `agentscope-tracing.json` | Tempo-backed tracing view (requires OTel to be wired) |
| `backend-performance.json` | HTTP request rates, latencies, error rates |
| `llm-observability.json` | LLM call volumes, token consumption, costs, latencies |

Datasources (Prometheus at `http://prometheus:9090`, Tempo at `http://tempo:3200`) are provisioned from `infra/docker/grafana/provisioning/datasources/datasource.yml`.

---

## 7. Logging

The application uses Python's standard `logging` module, configured at startup in `backend/app/core/logging.py`. All output goes to stdout at `INFO` level using the format:

```
%(asctime)s %(levelname)s %(name)s %(message)s
```

MetaAPI SDK loggers (`engineio`, `socketio`) are silenced to `ERROR` to suppress WebSocket reconnection noise.

### `LOG_AGENT_STEPS`

| Var | Default | Effect |
|---|---|---|
| `LOG_AGENT_STEPS` | `true` | Controls whether per-agent step records are written to `agent_steps` in PostgreSQL. When `false`, step-level inputs and outputs are not persisted, which reduces DB write volume at the cost of losing per-step audit detail. |

When `LOG_AGENT_STEPS=true`, each agent phase (technical analyst, news analyst, market context analyst, bullish researcher, bearish researcher, trader agent, risk manager, execution manager) records its input context, output payload including `elapsed_ms`, and error state to the `agent_steps` table. Steps are batch-committed after all phases complete to reduce database round-trips.

### Correlation and causation IDs

`backend/app/observability/trace_context.py` implements a lightweight `contextvars`-based correlation ID system. A `correlation_id` (ties all events in a request) and a `causation_id` stack (ties each event to its direct parent) are propagated through async tasks. These IDs appear in log records and trace payloads, allowing any run, agent step, or tool call to be correlated back to its root trigger. This is a log-level correlation mechanism, not distributed tracing.
