# Configuration

Kairos Mesh is configured entirely via environment variables. Copy `backend/.env.example` to `backend/.env` and set values before starting the stack.

**Sources:**
- `backend/.env.example` — every variable with its shipped default
- `backend/app/core/config.py` — Pydantic `Settings` model (types, validation, computed defaults)

Variables are loaded at startup through `pydantic-settings`. Names are case-insensitive. Unknown variables are ignored.

---

> ⚠️ **Dangerous variables** that can result in live capital loss or broken authentication are called out inline and collected again in [Section 15](#15-dangerous--operator-only).

---

## 1. Application

| Variable | Type | Default | Description |
|---|---|---|---|
| `APP_NAME` | `str` | `Kairos Mesh` | Display name used in logs and the OpenAPI title. |
| `ENV` | `str` | `dev` | Runtime environment label. Set to `production` to enable production-level log severity and stricter checks. |
| `API_PREFIX` | `str` | `/api/v1` | URL prefix for all REST endpoints. |
| `SECRET_KEY` | `str` | `` (empty) | ⚠️ **Secret.** Signs JWT tokens. If empty or `change-me` at startup the application generates a random key — tokens are invalidated on every restart. Must be set to a stable random string in production. Note: `.env.example` ships `change-me` as a placeholder — this is not the code default. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `int` | `720` | JWT lifetime in minutes (default: 12 hours). |
| `CORS_ORIGINS` | `List[str]` | `http://localhost:5173` | Comma-separated list (or JSON array) of origins allowed by the CORS middleware. |

---

## 2. Database

| Variable | Type | Default | Description |
|---|---|---|---|
| `POSTGRES_USER` | `str` | `trading` | PostgreSQL username (used when constructing the connection string outside of Docker). |
| `POSTGRES_PASSWORD` | `str` | `trading` | PostgreSQL password. |
| `POSTGRES_DB` | `str` | `trading_platform` | Database name. |
| `POSTGRES_HOST` | `str` | `postgres` | Hostname of the PostgreSQL server. |
| `POSTGRES_PORT` | `int` | `5432` | Port of the PostgreSQL server. |
| `DATABASE_URL` | `str` | `postgresql+psycopg2://trading:trading@postgres:5432/trading_platform` | Full SQLAlchemy connection URL. Overrides the individual `POSTGRES_*` vars when set. Falls back to `sqlite:///./trading.db` if omitted entirely. |
| `DB_POOL_SIZE` | `int` | `12` | Number of persistent connections in the SQLAlchemy connection pool. |
| `DB_MAX_OVERFLOW` | `int` | `24` | Maximum number of connections allowed above `DB_POOL_SIZE` during peak load. |
| `DB_POOL_TIMEOUT_SECONDS` | `int` | `30` | Seconds to wait for a free connection before raising an error. |
| `DB_POOL_RECYCLE_SECONDS` | `int` | `1800` | Seconds after which idle connections are recycled to avoid stale TCP sessions. |

---

## 3. Message Queue

### Core URLs

| Variable | Type | Default | Description |
|---|---|---|---|
| `REDIS_URL` | `str` | `redis://redis:6379/0` | Redis URL used for caching, rate limiting, and distributed locks. |
| `CELERY_BROKER_URL` | `str` | `amqp://guest:guest@rabbitmq:5672//` | Celery broker. RabbitMQ is the default; Redis is also supported. |
| `CELERY_RESULT_BACKEND` | `str` | `redis://redis:6379/1` | Backend for storing Celery task results. |

### Celery behaviour

| Variable | Type | Default | Description |
|---|---|---|---|
| `CELERY_IGNORE_RESULT` | `bool` | `true` | Discard task results after execution to reduce backend write load. |
| `CELERY_ANALYSIS_QUEUE` | `str` | `analysis` | Queue name for market-analysis tasks. |
| `CELERY_SCHEDULER_QUEUE` | `str` | `scheduler` | Queue name for scheduler tasks. |
| `CELERY_BACKTEST_QUEUE` | `str` | `backtests` | Queue name for backtest tasks. |
| `CELERY_WORKER_QUEUES` | `str` | `analysis,scheduler,backtests` | Comma-separated list of queues consumed by a worker. |
| `CELERY_TASK_ACKS_LATE` | `bool` | `true` | Acknowledge tasks only after execution, preventing message loss on worker crash. |
| `CELERY_TASK_REJECT_ON_WORKER_LOST` | `bool` | `true` | Requeue a task if the worker process dies mid-execution. |
| `CELERY_TASK_TRACK_STARTED` | `bool` | `true` | Emit a `STARTED` state so the API can report in-progress tasks. |
| `CELERY_WORKER_CONCURRENCY` | `int` | `2` | Number of concurrent worker processes per Celery node. |
| `CELERY_WORKER_PREFETCH_MULTIPLIER` | `int` | `1` | Prefetch factor per worker process. Keep at `1` for long-running tasks. |
| `CELERY_WORKER_MAX_TASKS_PER_CHILD` | `int` | `100` | Recycle a worker process after this many tasks to reclaim memory. |

> **Note:** Some Celery worker tuning variables (`CELERY_WORKER_CONCURRENCY`, `CELERY_WORKER_PREFETCH_MULTIPLIER`, `CELERY_WORKER_MAX_TASKS_PER_CHILD`, etc.) are passed directly to Celery via Docker Compose environment configuration and are not loaded by the application's Pydantic Settings model.

### Celery time limits

| Variable | Type | Default | Description |
|---|---|---|---|
| `CELERY_ANALYSIS_SOFT_TIME_LIMIT_SECONDS` | `int` | `300` | Soft limit for analysis tasks — raises `SoftTimeLimitExceeded`. |
| `CELERY_ANALYSIS_TIME_LIMIT_SECONDS` | `int` | `360` | Hard kill limit for analysis tasks. |
| `CELERY_SCHEDULER_SOFT_TIME_LIMIT_SECONDS` | `int` | `20` | Soft limit for scheduler tasks. |
| `CELERY_SCHEDULER_TIME_LIMIT_SECONDS` | `int` | `30` | Hard kill limit for scheduler tasks. |
| `CELERY_BACKTEST_SOFT_TIME_LIMIT_SECONDS` | `int` | `1200` | Soft limit for backtest tasks. |
| `CELERY_BACKTEST_TIME_LIMIT_SECONDS` | `int` | `1500` | Hard kill limit for backtest tasks. |

---

## 4. LLM Providers

### Provider selection

| Variable | Type | Default | Description |
|---|---|---|---|
| `LLM_PROVIDER` | `str` | `ollama` | Active LLM backend. Accepted values: `ollama`, `openai`, `mistral`. Only the selected provider's credentials need to be set. |

### Decision mode

| Variable | Type | Default | Description |
|---|---|---|---|
| `DECISION_MODE` | `str` | `balanced` | Controls how aggressively the trader agent acts. See mode descriptions below. Invalid values are silently normalised to `balanced`. |

**Mode descriptions:**

| Mode | Intended use | Behaviour |
|---|---|---|
| `conservative` | Cautious live accounts, regulated environments | Strict convergence required. At least 2 aligned sources must agree. No single-source override. High confidence and evidence thresholds. Fewest signals acted on. |
| `balanced` | Default — general-purpose production use | Moderate thresholds. One aligned source is sufficient. Single-source technical override is allowed when the score exceeds 0.25. |
| `permissive` | Research, paper trading, high-throughput scanning | Opportunistic but still prudent. Lower thresholds. Technical override allowed. Major contradictions between sources still block a signal. |

### Ollama

| Variable | Type | Default | Description |
|---|---|---|---|
| `OLLAMA_BASE_URL` | `str` | `https://ollama.com` | Base URL for the Ollama API. |
| `OLLAMA_API_KEY` | `str` | `` (empty) | API key if your Ollama endpoint requires authentication. |
| `OLLAMA_MODEL` | `str` | `deepseek-v3.2` | Model tag to use. Override to any model served by your Ollama instance. (`.env.example` ships `gpt-oss:120b-cloud` as an example model.) |
| `OLLAMA_TIMEOUT_SECONDS` | `int` | `30` | HTTP request timeout for Ollama calls. |
| `OLLAMA_INPUT_COST_PER_1M_TOKENS` | `float` | `0.0` | Cost per 1 M input tokens in USD, used for cost tracking only. |
| `OLLAMA_OUTPUT_COST_PER_1M_TOKENS` | `float` | `0.0` | Cost per 1 M output tokens in USD, used for cost tracking only. |

### OpenAI

| Variable | Type | Default | Description |
|---|---|---|---|
| `OPENAI_BASE_URL` | `str` | `https://api.openai.com/v1` | Base URL. Override to point at a compatible proxy or Azure endpoint. |
| `OPENAI_API_KEY` | `str` | `` (empty) | OpenAI API key. Required when `LLM_PROVIDER=openai`. |
| `OPENAI_MODEL` | `str` | `gpt-4o-mini` | Model name passed to the API. |
| `OPENAI_TIMEOUT_SECONDS` | `int` | `30` | HTTP request timeout. |
| `OPENAI_INPUT_COST_PER_1M_TOKENS` | `float` | `0.0` | Cost per 1 M input tokens in USD, for cost tracking. |
| `OPENAI_OUTPUT_COST_PER_1M_TOKENS` | `float` | `0.0` | Cost per 1 M output tokens in USD, for cost tracking. |

### Mistral

| Variable | Type | Default | Description |
|---|---|---|---|
| `MISTRAL_BASE_URL` | `str` | `https://api.mistral.ai/v1` | Base URL for the Mistral API. |
| `MISTRAL_API_KEY` | `str` | `` (empty) | Mistral API key. Required when `LLM_PROVIDER=mistral`. |
| `MISTRAL_MODEL` | `str` | `mistral-small-latest` | Model name. |
| `MISTRAL_TIMEOUT_SECONDS` | `int` | `30` | HTTP request timeout. |
| `MISTRAL_INPUT_COST_PER_1M_TOKENS` | `float` | `0.0` | Cost per 1 M input tokens in USD, for cost tracking. |
| `MISTRAL_OUTPUT_COST_PER_1M_TOKENS` | `float` | `0.0` | Cost per 1 M output tokens in USD, for cost tracking. |

---

## 5. Broker — MetaAPI

MetaAPI connects Kairos Mesh to MetaTrader 4/5 accounts.

| Variable | Type | Default | Description |
|---|---|---|---|
| `METAAPI_TOKEN` | `str` | `` (empty) | ⚠️ MetaAPI account token. Required for any live or paper broker connectivity. Legacy alias: `API_TOKEN`. |
| `METAAPI_ACCOUNT_ID` | `str` | `` (empty) | MetaAPI account ID. Legacy alias: `ACCOUNT_ID`. |
| `METAAPI_REGION` | `str` | `new-york` | Deployment region for the MetaAPI cloud gateway. |
| `METAAPI_BASE_URL` | `str` | `https://mt-client-api-v1.london.agiliumtrade.ai` | REST endpoint for MetaAPI client operations. Legacy alias: `BASE_URL`. |
| `METAAPI_MARKET_BASE_URL` | `str` | `https://mt-market-data-client-api-v1.london.agiliumtrade.ai` | REST endpoint for MetaAPI market data. Legacy alias: `BASE_MARKET_URL`. |
| `METAAPI_AUTH_HEADER` | `str` | `auth-token` | HTTP header name used to pass the MetaAPI token. |
| `ENABLE_METAAPI_REAL_TRADES_DASHBOARD` | `bool` | `false` | Enable the live-trades dashboard widget. Has no effect on trade execution. |
| `METAAPI_USE_SDK_FOR_MARKET_DATA` | `bool` | `false` | Use the MetaAPI WebSocket SDK for market data instead of the REST API. |

### Connection and cache tuning

| Variable | Type | Default | Description |
|---|---|---|---|
| `METAAPI_CACHE_ENABLED` | `bool` | `true` | Enable the in-process MetaAPI response cache. |
| `METAAPI_CACHE_CONNECT_TIMEOUT_SECONDS` | `float` | `0.25` | Timeout to acquire a cache connection. |
| `METAAPI_SDK_CONNECT_TIMEOUT_SECONDS` | `float` | `30.0` | Timeout for initial WebSocket SDK connection (seconds). Note: `.env.example` ships `6` as a tighter example value. |
| `METAAPI_SDK_SYNC_TIMEOUT_SECONDS` | `float` | `30.0` | Timeout for MetaAPI account state sync. Note: `.env.example` ships `6` as a tighter example value. |
| `METAAPI_SDK_REQUEST_TIMEOUT_SECONDS` | `float` | `30.0` | Per-request timeout for SDK calls. Note: `.env.example` ships `8` as a tighter example value. |
| `METAAPI_REST_TIMEOUT_SECONDS` | `float` | `30.0` | HTTP timeout for REST API calls. |
| `METAAPI_SDK_CIRCUIT_BREAKER_SECONDS` | `float` | `20.0` | Seconds the circuit breaker waits before retrying a failed SDK connection. |
| `METAAPI_ACCOUNT_INFO_CACHE_TTL_SECONDS` | `int` | `5` | TTL for cached account info. |
| `METAAPI_MARKET_CANDLES_CACHE_MIN_TTL_SECONDS` | `int` | `2` | Minimum TTL for cached candle data. |
| `METAAPI_MARKET_CANDLES_CACHE_MAX_TTL_SECONDS` | `int` | `12` | Maximum TTL for cached candle data. |
| `METAAPI_CACHE_LOCK_TTL_SECONDS` | `float` | `3.0` | TTL for distributed cache locks. |
| `METAAPI_CACHE_WAIT_TIMEOUT_SECONDS` | `float` | `1.2` | Maximum time to wait for a cache lock before giving up. |

---

## 6. Trading

| Variable | Type | Default | Description |
|---|---|---|---|
| `ALLOW_LIVE_TRADING` | `bool` | `false` | ⚠️ **Dangerous.** Set to `true` to allow the execution layer to place real orders on a live broker account. The authenticated user must also hold the `trader-operator` role. Leaving this `false` means all generated signals are logged but never sent to the broker. |
| `ENABLE_PAPER_EXECUTION` | `bool` | `true` | Enable paper-mode order submission to MetaAPI. When `true`, paper-mode runs send orders to a MetaAPI demo account (no real capital at risk). When `false`, paper-mode runs are blocked. Requires `METAAPI_TOKEN` and `METAAPI_ACCOUNT_ID`. |
| `DEFAULT_FOREX_PAIRS` | `List[str]` | `EURUSD.PRO,GBPUSD.PRO,...` (10 pairs) | Comma-separated list of Forex instrument symbols loaded into the default watchlist. Values are uppercased automatically. |
| `DEFAULT_CRYPTO_PAIRS` | `List[str]` | `BTCUSD,ETHUSD,...` (13 pairs) | Comma-separated list of crypto instrument symbols loaded into the default watchlist. |
| `DEFAULT_TIMEFRAMES` | `List[str]` | `M5,M15,H1,H4,D1` | Comma-separated list of analysis timeframes. |

---

## 7. Agent Skills Bootstrap

Agent skills can be seeded from a JSON file at startup. The default for `AGENT_SKILLS_BOOTSTRAP_FILE` is `''` (empty string) — the bootstrap is disabled unless the variable is explicitly set.

| Variable | Type | Default | Description |
|---|---|---|---|
| `AGENT_SKILLS_BOOTSTRAP_FILE` | `str` | `` (empty — **must be set explicitly**) | Absolute path to a JSON file containing agent skill definitions to load on startup. If empty, bootstrap is skipped. Note: `.env.example` ships `/app/config/agent-skills.json` as an example path — this is not the code default. |
| `AGENT_SKILLS_BOOTSTRAP_MODE` | `str` | `merge` | How to apply the bootstrap file. `merge` adds missing skills without overwriting existing ones; `replace` overwrites all skills with the file contents. |
| `AGENT_SKILLS_BOOTSTRAP_APPLY_ONCE` | `bool` | `true` | If `true`, the bootstrap is applied only when no skills exist in the database, preventing re-application on subsequent restarts. |

---

## 8. News Providers

News provider configuration is managed primarily through the UI (Connectors > News). API keys set here serve as environment-level fallbacks when no key has been saved in the database for a given provider.

| Variable | Type | Default | Description |
|---|---|---|---|
| `NEWSAPI_API_KEY` | `str` | `` (empty) | Fallback API key for [NewsAPI](https://newsapi.org). |
| `FINNHUB_API_KEY` | `str` | `` (empty) | Fallback API key for [Finnhub](https://finnhub.io). |
| `ALPHAVANTAGE_API_KEY` | `str` | `` (empty) | Fallback API key for [Alpha Vantage](https://www.alphavantage.co). |
| `TRADINGECONOMICS_API_KEY` | `str` | `` (empty) | Fallback API key for [Trading Economics](https://tradingeconomics.com). |

---

## 9. Observability

| Variable | Type | Default | Description |
|---|---|---|---|
| `PROMETHEUS_ENABLED` | `bool` | `true` | Expose a Prometheus `/metrics` endpoint on the API server. |
| `PROMETHEUS_WORKER_PORT` | `int` | `9101` | Port on which Celery workers expose their Prometheus metrics. |
| `OPEN_TELEMETRY_ENABLED` | `bool` | `false` | Enable OpenTelemetry tracing export. Requires a configured collector. |
| `LOG_AGENT_STEPS` | `bool` | `true` | Emit a log entry for each intermediate agent reasoning step. Useful for debugging; disable in high-throughput production to reduce log volume. |
| `WS_RUN_POLL_SECONDS` | `float` | `2.0` | Polling interval (seconds) for the WebSocket run-status feed. |
| `WS_TRADING_ORDERS_POLL_SECONDS` | `float` | `2.0` | Polling interval (seconds) for the WebSocket trading-orders feed. |

---

## 10. Backtest

| Variable | Type | Default | Description |
|---|---|---|---|
| `BACKTEST_AGENT_LOG_EVERY` | `int` | `25` | Log a progress message every N backtest candles. Reduce for more granular progress tracking at the cost of log volume. |
| `BACKTEST_ENABLE_LLM` | `bool` | `false` | Enable LLM-based reasoning during backtests. Disabled by default because LLM calls are slow and costly; use only when validating agent reasoning fidelity. |
| `BACKTEST_LLM_EVERY` | `int` | `24` | When `BACKTEST_ENABLE_LLM=true`, run the LLM every N candles instead of on every bar to limit API cost. |

---

## 11. Scheduler

| Variable | Type | Default | Description |
|---|---|---|---|
| `SCHEDULER_ENABLED` | `bool` | `true` | Enable the periodic analysis scheduler. When `false`, analysis tasks are only triggered manually or via the API. |
| `SCHEDULER_BATCH_SIZE` | `int` | `20` | Maximum number of instruments submitted to the analysis queue per scheduler tick. |

---

## 12. Orchestrator

| Variable | Type | Default | Description |
|---|---|---|---|
| `ORCHESTRATOR_PARALLEL_WORKERS` | `int` | `4` | Number of parallel worker coroutines the orchestrator uses when fanning out analysis tasks. Accepted range: 1–16. |

---

## 13. Market Data Cache

These variables control the in-process Redis cache used for yfinance-sourced market data (snapshots, news, historical OHLCV). Caching reduces repeated yfinance HTTP calls and smooths latency for the analysis pipeline.

| Variable | Type | Default | Description |
|---|---|---|---|
| `YFINANCE_CACHE_ENABLED` | `bool` | `true` | Enable the in-process yfinance response cache. |
| `YFINANCE_CACHE_CONNECT_TIMEOUT_SECONDS` | `float` | `0.25` | Timeout to acquire a cache connection. |
| `YFINANCE_SNAPSHOT_CACHE_MIN_TTL_SECONDS` | `int` | `2` | Minimum TTL for cached price snapshots. |
| `YFINANCE_SNAPSHOT_CACHE_MAX_TTL_SECONDS` | `int` | `30` | Maximum TTL for cached price snapshots. |
| `YFINANCE_NEWS_CACHE_TTL_SECONDS` | `int` | `120` | TTL for cached yfinance news results. |
| `YFINANCE_HISTORICAL_CACHE_TTL_SECONDS` | `int` | `900` | TTL for cached historical OHLCV data. |
| `YFINANCE_CACHE_FRAME_MAX_ROWS` | `int` | `5000` | Maximum number of rows stored per cached DataFrame. |
| `YFINANCE_CACHE_LOCK_TTL_SECONDS` | `float` | `3.0` | TTL for distributed cache locks. |
| `YFINANCE_CACHE_WAIT_TIMEOUT_SECONDS` | `float` | `1.2` | Maximum time to wait for a cache lock before giving up. |

---

## 14. Debug Traces

Debug traces write full JSON snapshots of trade-decision runs to disk. They include agent prompts, price history, and final decisions and are useful for post-mortem analysis and regression testing.

| Variable | Type | Default | Description |
|---|---|---|---|
| `DEBUG_TRADE_JSON_ENABLED` | `bool` | `false` | Enable writing trade-decision traces to `DEBUG_TRADE_JSON_DIR`. Note: `backend/.env.example` ships this as `true`; `config.py` defaults to `false`. Set explicitly in production. |
| `DEBUG_TRADE_JSON_DIR` | `str` | `./debug-traces` | Directory where trace files are written. Must be writable by the application process. |
| `DEBUG_TRADE_JSON_INCLUDE_PROMPTS` | `bool` | `true` | Include full LLM prompts in the trace. May contain sensitive market context; disable if traces are stored in shared locations. |
| `DEBUG_TRADE_JSON_INCLUDE_PRICE_HISTORY` | `bool` | `true` | Include the price history array in the trace. |
| `DEBUG_TRADE_JSON_PRICE_HISTORY_LIMIT` | `int` | `200` | Maximum number of price bars to include per trace. Accepted range: 20–5000. |
| `DEBUG_TRADE_JSON_INLINE_IN_RUN_TRACE` | `bool` | `false` | Embed the trade-decision trace inline in the run trace rather than writing a separate file. |

---

## 15. Dangerous / Operator-only

The following variables require elevated care. Misconfiguring them can result in live capital loss or broken authentication.

| Variable | Risk | Action required |
|---|---|---|
| `ALLOW_LIVE_TRADING=true` | Real orders will be submitted to a live broker account. | Only set on a deployment where the operator has verified MetaAPI connectivity, account credentials, and risk limits. The authenticated user must also hold the `trader-operator` role. Default is `false`. |
| `SECRET_KEY` | If left as `change-me` or empty in production, the application generates a random key on each restart. All issued JWTs are invalidated on restart, logging users out and disrupting API clients. | Set to a stable, cryptographically random string (minimum 48 characters). Do not share or commit this value. |
| `METAAPI_TOKEN` | Grants full control of the connected MetaTrader account, including order placement and account management. | Treat as a credential. Store in a secrets manager, not in a committed `.env` file. |
| `DECISION_MODE=permissive` | Lowers the signal quality bar — more trades will be attempted, increasing exposure. | Do not use with `ALLOW_LIVE_TRADING=true` unless you have reviewed position-sizing and risk limits. |
