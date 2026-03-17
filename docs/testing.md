# Tests

## Objectif

Ce document définit:
- les commandes de tests automatisés (backend/frontend),
- les smoke tests d'intégration minimum,
- un socle de tests de performance pour conserver une baseline exploitable.

## 1) Préparer l'environnement

### Local (dev/test)

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
docker compose up -d --build
```

### Production Docker locale

```bash
cp .env.prod.example .env.prod
./scripts/install-prod-docker.sh
```

## 2) Tests automatisés

### Backend

```bash
docker compose exec backend pytest -q
```

### Frontend

```bash
docker compose exec frontend npm run build
docker compose exec frontend npm run test:e2e
```

## 3) Smoke tests d'intégration (manuel)

1. Health API

```bash
curl -sS http://localhost:8000/api/v1/health
```

2. Auth (récupérer un JWT)

```bash
curl -sS -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@local.dev","password":"admin1234"}'
```

3. Lancer un run async multi-agent

```bash
curl -sS -X POST "http://localhost:8000/api/v1/runs?async_execution=true" \
  -H "Authorization: Bearer <JWT>" \
  -H "Content-Type: application/json" \
  -d '{"pair":"EURUSD","timeframe":"H1","mode":"simulation","risk_percent":1}'
```

4. Vérifier l'exécution worker et les appels externes

```bash
docker compose logs --tail 120 worker backend | rg "dispatch_due_schedules|ollama_chat_call|metaapi|qdrant|yfinance|succeeded"
```

5. Backtest `agents_v1`

```bash
curl -sS -X POST http://localhost:8000/api/v1/backtests \
  -H "Authorization: Bearer <JWT>" \
  -H "Content-Type: application/json" \
  -d '{"pair":"EURUSD","timeframe":"H1","start_date":"2025-01-01","end_date":"2025-03-01","strategy":"agents_v1"}'
```

6. Vérifier workflow source backtest
- `metrics.workflow_source` doit valoir `ForexOrchestrator.analyze_context`.

## 4) Plan d'intégration minimal à couvrir

| Test | Scope | Dépendances | Résultat attendu | Priorité |
|---|---|---|---|---|
| Run multi-agent complet | API + orchestrateur + worker | Postgres, Redis, RabbitMQ, Ollama, Qdrant | run passe `queued -> running -> completed/failed` avec `agent_steps` persistés | P0 |
| Pipeline trader + risk manager | Domain logic | worker, DB | décision finale cohérente et garde-fous risque appliqués | P0 |
| Cache Redis read/write | Cache providers | Redis | hit/miss cohérents, pas de crash en miss | P0 |
| Persistance PostgreSQL | ORM + migrations | Postgres | inserts/updates/queries sans erreur | P0 |
| RabbitMQ + Celery execution | Queue + workers | RabbitMQ, worker, beat | tâche reçue puis `succeeded`/`failed` tracée | P0 |
| Appel LLM mock puis réel | LLM connector | Ollama | fallback correct en mock, succès 200 en réel | P1 |
| Appel MetaApi mocké | Trading connector | MetaApi | gestion erreur/token et mapping réponse corrects | P1 |
| Fallback indisponibilité externe | Résilience | Ollama/MetaApi/yfinance down | run continue en mode dégradé selon règles | P0 |
| Dashboard -> API -> worker -> résultat | E2E UI | frontend + backend + worker | statut UI reflète l'état réel du run | P1 |

## 5) Plan de performance minimal

| Scénario | Composant cible | Métrique | Profil de charge | Critère de succès | Priorité |
|---|---|---|---|---|---|
| Latence endpoint health/login | FastAPI | p50/p95 ms | 50 req, 5 concurrents | pas d'erreur 5xx, p95 stable | P0 |
| Temps total run multi-agent | Orchestrateur + LLM | durée run (s) | 5 runs en série | variance contrôlée, pas de blocage queue | P0 |
| Charge concurrente workers | Celery/RabbitMQ | throughput tâches/min | 20 tâches async | backlog non divergent | P0 |
| Impact appels LLM multiples | Ollama | latency/call, timeout rate | 5 runs parallèles | timeout rate faible, fallback fonctionnel | P1 |
| Cache hit vs miss | Redis + providers | hit ratio, latence | alternance warm/cold | gain net sur latence en hit | P0 |
| WebSocket/SSE ou polling | Front/API | latence perçue UI | 20 clients dashboard | pas de surcharge DB excessive | P1 |
| Requêtes DB hot paths | PostgreSQL | durée requête, scan/index | 100 lectures ciblées | index utilisés, pas de seq scan critique | P0 |
| Débit RabbitMQ/Celery | Queue layer | messages/s, ack delay | burst de 200 messages | consommation sans saturation durable | P1 |

Exemple simple de mesure latence endpoint:

```bash
for i in $(seq 1 20); do
  /usr/bin/time -f "%e" curl -sS -o /dev/null http://localhost:8000/api/v1/health
done
```

## 6) Tests connecteurs

- `POST /api/v1/connectors/ollama/test`
- `POST /api/v1/connectors/metaapi/test`
- `POST /api/v1/connectors/yfinance/test`
- `POST /api/v1/connectors/qdrant/test`

## 7) Vérification observabilité

- API metrics: `http://localhost:8000/metrics`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000`

## 8) Rebuild ciblé (sans tout relancer)

Backend:

```bash
docker compose up -d --build backend
```

Worker:

```bash
docker compose up -d --build worker
```

Frontend:

```bash
docker compose up -d --build frontend
```

## 9) Mise à l'échelle workers Celery

```bash
docker compose up -d --scale worker=3 worker
```

## 10) Régressions à surveiller

- run bloqué en `running` sans étapes agents;
- absence d'appels LLM dans les logs malgré LLM activé;
- backtest `agents_v1` retombant sur workflow `ema_rsi`;
- exécution `paper/live` sans contrôle risque effectif.
