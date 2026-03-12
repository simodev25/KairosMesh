# Architecture technique

## Découpage

- Backend FastAPI: API REST, auth, RBAC, runs, orchestration, exécution, audit
- Worker Celery: analyses longues non bloquantes
- PostgreSQL: persistance principale (runs, étapes, ordres, connecteurs, audit)
- Redis + RabbitMQ: backend asynchrone
- Qdrant + pgvector: mémoire vectorielle long-terme
- Frontend React: dashboard trading + admin
- Observabilité: métriques Prometheus + dashboard Grafana

## Modules backend

- `app/services/orchestrator`: moteur central + handoffs agents
- `app/services/llm`: client Ollama Cloud avec retry + fallback
- `app/services/market`: provider yfinance (indicateurs + news)
- `app/services/trading`: client MetaApi Cloud SDK
- `app/services/backtest`: moteur de backtesting et analytics
- `app/services/risk`: règles de risque, sizing, blocages
- `app/services/execution`: simulation/paper/live avec garde-fous
- `app/services/prompts`: templates versionnés en base
- `app/services/memory`: mémoire vectorielle et récupération contexte

## Flux principaux

1. L'utilisateur lance un run (`/runs`)
2. Run stocké `pending` puis `queued/running`
3. Orchestrateur récupère marché (yfinance) + news
4. Agents analysent et débattent
5. Trader propose BUY/SELL/HOLD
6. Risk manager valide/refuse
7. Execution manager simule ou envoie (paper/live)
8. Trace complète persistée (`analysis_runs`, `agent_steps`, `execution_orders`)

## Modes dégradés

- Ollama indisponible: fallback déterministe
- MetaApi indisponible: fallback paper simulé, live refusé
- yfinance indisponible: run possible avec signaux partiels
