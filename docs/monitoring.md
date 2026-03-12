# Monitoring

## Logs

- Journalisation standard Python côté backend

## Metrics Prometheus

- `/metrics` exposé par FastAPI
- Exemples:
  - `analysis_runs_total`
  - `orchestrator_step_duration_seconds`
  - `llm_calls_total`
  - `llm_latency_seconds`
  - `llm_cost_usd_total`
  - `llm_prompt_tokens_total`
  - `llm_completion_tokens_total`

## Dashboards

- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000`
- Dashboard provisionné: `Forex Platform - LLM & Orchestrator`
