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
| `LLM_PROVIDER` | `ollama`, `openai`, or `mistral` | Ollama can run locally (`http://localhost:11434`) or via cloud (`https://ollama.com`). Local requires Ollama installed; cloud requires `OLLAMA_API_KEY`. The `.env.example` default points to cloud. |
| `OLLAMA_MODEL` | e.g. `llama3.1:8b` | Only if using Ollama. For local Ollama: model must be pulled with `ollama pull <model-name>` before use. |
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
| `redis` | 6380 | Redis 7 |
| `rabbitmq` | 5672 / 15672 | RabbitMQ (15672 = management UI) |
| `prometheus` | 9090 | Metrics collection |
| `tempo` | 3200 | Grafana Tempo (distributed tracing) |
| `grafana` | 3000 | Dashboards |

Wait for `backend` to log `Application startup complete` before using the UI.

## Step 3 — Verify

| URL | Expected |
|-----|----------|
| http://localhost:5173 | React dashboard (login page) |
| http://localhost:8000/docs | FastAPI Swagger UI |
| http://localhost:8000/health | JSON with `"status": "ok"` and service states (`api`, `postgres`, `llm`, `llm_provider`, `ollama`, `metaapi`) |
| http://localhost:9090 | Prometheus |
| http://localhost:3000 | Grafana (admin / admin) |

Default credentials: `admin@local.dev` / `admin1234`

## Step 4 — Run a first analysis

1. Open http://localhost:5173 and log in
2. Navigate to **Connectors** → **AI Models** and confirm your LLM provider is configured
3. Navigate to **Terminal**
4. Select a pair (e.g. `EURUSD`), timeframe (e.g. `H1`), and mode **Simulation**
5. Click **Run Analysis**
6. Watch the pipeline progress in real time via WebSocket

Simulation mode requires no broker account — orders are recorded in the database only and no broker connection is made.

## Local development (without Docker for backend/frontend)

If you prefer to run the backend and frontend outside Docker, you still need PostgreSQL, Redis, and RabbitMQ. Start infrastructure only:

```bash
docker compose up postgres redis rabbitmq -d
```

Then in separate terminals:

```bash
# Backend
make backend-install
```

> **Note:** After running `make backend-install`, activate the virtual environment before running subsequent commands:
> ```bash
> source backend/.venv/bin/activate
> ```

```bash
make backend-run        # http://localhost:8000

# Celery worker
celery -A app.tasks.celery_app.celery_app worker --loglevel=warning -B -Q analysis,scheduler,backtests

# Frontend
make frontend-install
make frontend-run       # http://localhost:5173
```

Available make targets:

```bash
make backend-install    # Install Python dependencies
make backend-run        # Start FastAPI dev server
make frontend-install   # Install Node dependencies
make frontend-run       # Start Vite dev server
make backend-test       # Run backend tests
```

## Configuring LLM providers

LLM providers can also be configured at runtime via the UI: **Connectors → AI Models**.

Per-agent LLM enable/disable is also available there. Disabling LLM for an agent switches it to deterministic mode (tool-only execution, no LLM call for that agent).

## Infrastructure dependencies

The backend will not start without PostgreSQL, Redis, and RabbitMQ. There is no embedded fallback for any of these services.

## Next steps

- [Quickstart](quickstart.md) — fastest path to a working simulation run
- [Configuration](configuration.md) — full environment variable reference
- [Paper vs Live](paper-vs-live.md) — what to check before connecting a broker account
