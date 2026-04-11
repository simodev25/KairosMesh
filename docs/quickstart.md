# Quickstart

Minimum steps to run a simulation analysis. Assumes Docker is installed.

## 1. Configure

```bash
cp backend/.env.example backend/.env
```

Open `backend/.env` and set `LLM_PROVIDER` to your choice (`ollama`, `openai`, or `mistral`) and the corresponding API key or base URL.

- **Ollama (local):** Set `OLLAMA_BASE_URL=http://localhost:11434`, ensure Ollama is running, and pull your model: `ollama pull <model-name>`
- **Ollama (remote/custom):** Set `OLLAMA_BASE_URL` to your hosted Ollama instance URL. Set `OLLAMA_API_KEY` if your instance requires it. The `.env.example` default (`https://ollama.com`) is a placeholder — replace it with your actual server address.
- **OpenAI:** Set `OPENAI_API_KEY`
- **Mistral:** Set `MISTRAL_API_KEY`

## 2. Start

```bash
docker compose up --build -d
```

Wait for the backend to be ready:

```bash
docker compose logs backend --follow
# Look for: "Application startup complete"
```

## 3. Log in

Open http://localhost:5173 and log in with `admin@local.dev` / `admin1234`.

## 4. Run a simulation

1. Navigate to **Terminal**
2. Select pair: `EURUSD`, timeframe: `H1`, mode: **Simulation**
3. Click **Run Analysis**
4. Watch agent progress update in real time

Simulation mode makes no broker connection. Orders are recorded in the database only.

## What happens

```
POST /api/v1/runs
  → Celery queue
    → Phase 1: technical-analyst, news-analyst, market-context (parallel)
    → Phase 2+3: debate (if LLM enabled for all 3 debate agents)
    → Phase 4: trader decision → risk validation → preflight → execution
  → Results persisted to DB
  → WebSocket streams progress to UI
```

Full pipeline detail: [Runtime Flow](runtime-flow.md)

## Run a paper trade (requires MetaAPI)

Add to `backend/.env`:
```
METAAPI_TOKEN=your-token
METAAPI_ACCOUNT_ID=your-account-id
```

Restart:
```bash
docker compose up -d backend worker
```

In the UI: Terminal → mode **Paper** → Run Analysis.

## Enable live trading

> Live trading is disabled by default (`ALLOW_LIVE_TRADING=false`). Before enabling, read [Paper vs Live](paper-vs-live.md) and work through the safety checklist.

To enable:
1. Set `ALLOW_LIVE_TRADING=true` in `backend/.env`
2. Ensure your user has the `trader-operator` role. The default `admin@local.dev` user has `super_admin` which includes this permission. For other users, assign via:
   ```sql
   UPDATE "user" SET role = 'trader-operator' WHERE email = 'your@email.com';
   ```
3. Restart the backend
4. In the UI: Terminal → mode **Live** → Run Analysis
