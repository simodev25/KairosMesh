# Monitoring

## Logs applicatifs

Sources:

- `backend` (FastAPI)
- `worker` (Celery)
- `qdrant`, `rabbitmq`, `redis`, `postgres`

Logs utiles en debug run:

```bash
docker compose logs -f worker | rg "agent_step|ollama_chat_call|orchestration failed|backtest_agent_cycle"
```

## Metrics Prometheus

Endpoint:

- `GET /metrics` (service backend)

Métriques clés:

- `analysis_runs_total{status=...}`
- `orchestrator_step_duration_seconds_*`
- `agentic_runtime_runs_total{status,mode,resumed}`
- `agentic_runtime_tool_selections_total{tool,source,degraded}`
- `agentic_runtime_tool_calls_total{tool,status}`
- `agentic_runtime_tool_duration_seconds_*`
- `agentic_runtime_subagent_sessions_total{source_tool,session_mode,status,resumed}`
- `agentic_runtime_final_decisions_total{decision,mode}`
- `agentic_runtime_execution_outcomes_total{status,mode}`
- `agentic_runtime_session_messages_total{resume_requested}`
- `agentic_runtime_memory_refresh_total{mode}`
- `llm_calls_total{provider,status}`
- `llm_latency_seconds_*`
- `llm_cost_usd_total{model}`
- `llm_prompt_tokens_total{model}`
- `llm_completion_tokens_total{model}`
- `external_provider_failures_total{provider}`
- `backend_http_requests_total{method,route,status}`
- `backend_http_request_duration_seconds_*`
- `metaapi_sdk_circuit_open_total{region,operation}`
- `metaapi_cache_hits_total{resource}`, `metaapi_cache_misses_total{resource}`
- `yfinance_cache_hits_total{resource}`, `yfinance_cache_misses_total{resource}`

## Grafana

- URL: `http://localhost:3000`
- Credentials local: `admin/admin`
- Dashboard provisionné:
  - `Forex Platform - Agent Runtime Overview`
  - fichier: `infra/docker/grafana/dashboards/agent-runtime-overview.json`
  - `Forex Platform - Agent Runtime Sessions & Failures`
  - fichier: `infra/docker/grafana/dashboards/agent-runtime-sessions.json`
  - `Forex Platform - LLM & Orchestrator`
  - fichier: `infra/docker/grafana/dashboards/llm-observability.json`
  - `Forex Platform - Backend Performance & Cache`
  - fichier: `infra/docker/grafana/dashboards/backend-performance.json`

Panels disponibles:

- Agentic runs/min, failure rate, planner degraded selections
- Final decisions BUY/SELL/HOLD par minute
- Tool selections/calls/failures par outil
- Latence p95 des outils runtime et des spécialistes
- Sessions sous-agents par `source_tool`
- Messages `sessions_send` et fréquence des refresh mémoire
- Statuts d'exécution (`filled`, `skipped`, `failed`, ...)
- LLM Calls/min par status
- LLM Latency p95
- LLM Estimated Cost USD/min par modèle
- Orchestrator Step Latency p95 par agent
- HTTP throughput/latence par route
- HTTP error rate 5xx
- MetaApi SDK circuit opens/min
- Cache hit ratio et volume d'opérations cache (MetaApi + yfinance)

## Analytics API (complément Grafana)

- `GET /api/v1/analytics/llm-summary`
  - total calls, success/fail, latence moyenne, coût, tokens.
- `GET /api/v1/analytics/llm-models`
  - modèles réellement utilisés, volume, taux succès, last seen.

## Alertes recommandées (V1)

- hausse de `agentic_runtime_runs_total{status="failed"}`.
- hausse de `agentic_runtime_tool_calls_total{status="error"}` sur un outil donné.
- hausse de `agentic_runtime_tool_selections_total{degraded="true"}`.
- `agentic_runtime_execution_outcomes_total{status="failed"}` en augmentation.
- hausse `external_provider_failures_total{provider="ollama"}`.
- `llm_calls_total{status="error"}` > seuil.
- p95 `orchestrator_step_duration_seconds` anormalement haute.
- run `failed` en hausse continue.
