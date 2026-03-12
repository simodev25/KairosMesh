# Forex Multi-Agent Trading Platform (V1)

Plateforme IA multi-agent dédiée au Forex avec:
- Orchestration multi-agent (analystes, débat bullish/bearish, trader, risk manager, execution manager)
- API FastAPI sécurisée (JWT + RBAC)
- Intégration Ollama Cloud (LLM), MetaApi (trading), yfinance (news + contexte)
- Séparation simulation / paper / live (live désactivé par défaut)
- Frontend React TypeScript dark premium
- Asynchrone Celery + RabbitMQ + Redis
- Observabilité minimale (Prometheus + Grafana)
- Docker Compose local + Helm minimal
- Mémoire long-terme vectorielle (Qdrant + pgvector fallback)
- Prompts versionnés en base pour enrichir le débat agents
- Backtesting avancé (Sharpe, Sortino, drawdown, profit factor)
- Support multi-comptes MetaApi
- Dashboard Grafana enrichi latence/coûts LLM

## Structure

- `backend/`: API, orchestration, agents, risk, execution, tests
- `frontend/`: UI React/Vite
- `infra/`: Docker monitoring + chart Helm
- `docs/`: architecture, UX/UI, connecteurs, monitoring, tests

## Démarrage rapide

1. Copier l'environnement backend:
```bash
cp backend/.env.example backend/.env
```

2. Lancer en local conteneurisé:
```bash
docker compose up --build
```

3. Accéder aux services:
- Frontend: `http://localhost:5173`
- API docs: `http://localhost:8000/docs`
- Grafana: `http://localhost:3000` (`admin/admin`)
- RabbitMQ UI: `http://localhost:15672` (`guest/guest`)

Compte seed local:
- email: `admin@local.dev`
- mot de passe: `admin1234`

## Modes d'exécution

- `simulation`: exécution simulée locale
- `paper`: tentative MetaApi, fallback simulation si indisponible
- `live`: bloqué par défaut (`ALLOW_LIVE_TRADING=false`)

## API principales

- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`
- `POST /api/v1/runs`
- `GET /api/v1/runs`
- `GET /api/v1/runs/{id}`
- `GET /api/v1/trading/orders`
- `GET/POST/PATCH /api/v1/trading/accounts`
- `GET /api/v1/connectors`
- `PUT /api/v1/connectors/{name}`
- `POST /api/v1/connectors/{name}/test`
- `GET/POST /api/v1/prompts`
- `POST /api/v1/prompts/{id}/activate`
- `POST /api/v1/memory/search`
- `GET/POST /api/v1/backtests`
- `GET /api/v1/analytics/llm-summary`

## Tests

Backend:
```bash
cd backend
pytest -q
```

Frontend e2e minimal:
```bash
cd frontend
npm install
npm run test:e2e
```

## Documentation

- [Architecture](docs/architecture.md)
- [UX/UI](docs/ux-ui.md)
- [Ollama Cloud](docs/ollama-cloud.md)
- [MetaApi](docs/metaapi.md)
- [Données et news](docs/data-news.md)
- [Orchestration](docs/orchestration.md)
- [Monitoring](docs/monitoring.md)
- [Tests](docs/testing.md)
- [Limites](docs/limits.md)
