# Execution

The execution layer is phase 4 of the Kairos Mesh pipeline. It receives the validated trade decision from the risk manager, runs a set of deterministic preflight checks, and then either records a simulation, submits to a MetaAPI paper account, or places a live order through a broker.

**Source:** `execution/executor.py` · `execution/preflight.py` · `agentscope/registry.py` (lines ~1493–1567) · `core/config.py`

## Execution modes

Three modes are supported. The active mode is set when a run is created and is attached to the `Run` record throughout the pipeline.

| Mode | Broker call | Requires | Default |
|------|------------|---------|---------|
| `simulation` | None — DB record only | Nothing extra | Yes |
| `paper` | MetaAPI paper account | `ENABLE_PAPER_EXECUTION=true` + MetaAPI credentials | No |
| `live` | Real broker order | `ALLOW_LIVE_TRADING=true` + `trader-operator` role | No |

**simulation** — No external call is made. A `ExecutionOrder` row is written with `status=simulated` and `executed=false`. This is the safe default for development and testing.

**paper** — Calls MetaAPI to place an order on a paper (demo) account. If MetaAPI is unreachable, the executor degrades gracefully: it records the order as `simulated` with `paper_fallback=true` in the response payload rather than failing the run. `ENABLE_PAPER_EXECUTION` defaults to `true` in `.env.example`.

**live** — Calls MetaAPI to place a real order. The `ALLOW_LIVE_TRADING` flag defaults to `false` and must be explicitly set. Additionally, the API route enforces a role check: requesting users must carry `super-admin`, `admin`, or `trader-operator` role (enforced in `backend/app/api/routes/runs.py`, line 93).

## Preflight checks

Before any order is constructed or submitted, `ExecutionPreflightEngine.validate()` (`backend/app/services/execution/preflight.py`) runs 8 sequential checks. The engine rejects on the first failure.

| # | Check | What it validates |
|---|-------|------------------|
| 1 | `decision_valid` | Decision is `BUY`, `SELL`, or `HOLD`. `HOLD` produces `status=skipped` immediately (no further checks). Any other value is blocked. |
| 2 | `risk_accepted` | The risk-manager output carries `accepted=true` (or `approved=true`). If false, the result is `status=refused` with the risk flags attached. |
| 3 | `params_complete` | `volume > 0`, `entry > 0`, `stop_loss > 0` are all present and finite. Take-profit is optional. |
| 4 | `side_consistent` | If the risk output also contains a directional decision, it must match the trader decision. Mismatches are blocked. |
| 5 | `market_open` | UTC wall-clock check against simplified market hours. Crypto is always open. Forex/metals/energy/commodities: Mon–Fri, closed Sat, opens Sun 22:00 UTC, closes Fri 22:00 UTC. Indices/equities: Mon–Fri 08:00–21:00 UTC. |
| 6 | `spread_ok` | Spread as a percentage of last price must be below mode-specific limits: simulation 0.05%, paper 0.02%, live 0.01%. Skipped if no spread data is available in the snapshot. |
| 7 | `volume_ok` | Volume must be within broker min/max bounds as returned by `RiskEngine._volume_limits()`. Skipped if `RiskEngine` cannot be imported. |
| 8 | `instrument_tradable` | For `paper` and `live` modes, the instrument's asset class must be in the supported set: `forex`, `crypto`, `metal`, `index`, `equity`, `etf`, `energy`, `commodity`. All asset classes pass in `simulation`. |

A `PreflightResult` dataclass is returned with `can_execute: bool`, the final `status`, a `reason` string, and lists of `checks_passed` and `checks_failed`. The executor only proceeds if `can_execute` is `true`.

## Order idempotency

Every order submission computes an idempotency key before touching the database or the broker.

**Key format** (`backend/app/services/execution/executor.py`, `_build_idempotency_key`):

```
run={run_id}|mode={mode}|symbol={SYMBOL}|side={SIDE}|vol={volume_4dp}|sl={sl_8dp}|tp={tp_8dp}|acct={account_ref}
```

Fields are normalized: symbol uppercased, side uppercased, volume rounded to 4 decimal places, stop-loss and take-profit to 8 decimal places, mode lowercased.

**Replay logic** — Before creating a new `ExecutionOrder` row, the executor queries the last 25 orders for the same `run_id`, `mode`, `symbol`, and `side`, then checks whether any of them carries a matching idempotency key and is in a terminal state (`submitted`, `simulated`, `paper-simulated`, or `blocked`). If a match is found, the prior response payload is returned directly with `idempotent_replay=true`. No new DB row is created and no broker call is made.

This prevents double submission if the pipeline retries or the execution function is called more than once within the same run.

## Execution manager agent

The execution manager is the third sequential agent in phase 4 (after `trader-agent` and `risk-manager`). Its role is primarily structural: it packages the preflight result and, optionally, produces a human-readable narrative.

**LLM is optional.** The setting `EXECUTION_MANAGER_LLM_ENABLED` (default `false`, `backend/app/core/config.py` line 123) controls whether the LLM is invoked.

| LLM enabled | Behaviour |
|-------------|----------|
| `false` (default) | Deterministic path. The agent builds a structured metadata dict from the `PreflightResult` and writes `status`, `reason`, `preflight.checks_passed`, `preflight.checks_failed`, `side`, and `volume` directly without any model call. |
| `true` | The preflight result and execution result are injected into `base_vars` and passed to the LLM. The model produces a narrative explanation (`ExecutionPlanResult` schema). The LLM output **does not** alter `can_execute` or override the preflight outcome. |

The actual `ExecutionService.execute()` call happens regardless of the LLM flag, as long as `_pf_result.can_execute` is `true` and the mode is not `simulation` (see `registry.py` lines 1507–1527).

After execution, when the risk manager accepted a trade, a `post_trade` portfolio snapshot is written to the `PortfolioSnapshot` table (lines 1714–1734).

## Order flow

```
preflight checks
      │
      ├── HOLD ──────────────────────────→ skipped (no order created)
      │
      ├── risk refused / checks failed ──→ PreflightResult(can_execute=False)
      │                                    ExecutionOrder(status=blocked|refused)
      │
      └── all checks passed
              │
              ├── idempotency key match ──→ replay prior response (no new row, no broker call)
              │
              ├── mode=simulation ────────→ ExecutionOrder(status=simulated, executed=false)
              │
              ├── mode=paper
              │       │
              │       ├── ENABLE_PAPER_EXECUTION=false ──→ status=blocked
              │       ├── MetaAPI success ────────────────→ status=executed, executed=true
              │       └── MetaAPI failure ────────────────→ status=simulated, paper_fallback=true
              │
              └── mode=live
                      │
                      ├── ALLOW_LIVE_TRADING=false ───────→ status=blocked
                      ├── MetaAPI success ────────────────→ status=executed, executed=true
                      └── MetaAPI failure ────────────────→ status=failed, error_class, retryable flag
```

All paths write an `ExecutionOrder` row and commit it. The run is subsequently marked `completed` with the execution status embedded in `run.decision.execution`.

Error classes on broker failure: `transient_network`, `rate_limited`, `auth_or_permission`, `account_funds`, `symbol_error`, `provider_error`. Only `transient_network` and `rate_limited` are flagged as `retryable=true`.

## Safeguards

| Safeguard | Where | Notes |
|-----------|-------|-------|
| `ALLOW_LIVE_TRADING=false` default | `config.py:121` | Live trading is opt-in. Must be explicitly set to `true`. |
| `trader-operator` role check | `routes/runs.py:93` | API layer rejects live-mode run creation from users without the required role. |
| Preflight check 1 — decision valid | `preflight.py:98–113` | Rejects any decision that is not BUY, SELL, or HOLD. |
| Preflight check 2 — risk accepted | `preflight.py:116–130` | Blocks execution if risk manager rejected the trade. |
| Preflight check 3 — params complete | `preflight.py:132–150` | Blocks if volume, entry, or stop-loss is missing or invalid. |
| Preflight check 4 — side consistency | `preflight.py:152–162` | Blocks if trader and risk disagree on direction. |
| Preflight check 5 — market open | `preflight.py:164–173` | Blocks if the market is closed for the instrument class. |
| Preflight check 6 — spread | `preflight.py:175–190` | Tighter limits on paper and live modes (0.02% and 0.01%). |
| Preflight check 7 — volume limits | `preflight.py:192–213` | Rejects volume outside broker min/max. |
| Preflight check 8 — instrument tradable | `preflight.py:215–232` | Blocks unsupported asset classes on paper/live. |
| Order idempotency key | `executor.py:71–87` | Prevents double submission within the same run. |
| Input validation (NaN/Inf/negative) | `executor.py:174–188` | Rejects before any DB write if volume, stop-loss, or take-profit is non-finite. |
| Paper/simulation as safe defaults | `executor.py:245–318` | No real money is at risk unless explicitly configured. |
| Paper fallback on MetaAPI failure | `executor.py:302–318` | Paper mode degrades to simulated rather than failing the run. |

## MetaAPI integration

Kairos Mesh connects to MT4/MT5 brokers through the MetaAPI cloud service. The `MetaApiClient` (`backend/app/services/trading/metaapi_client.py`) handles both REST and SDK-based connections.

| Variable | Default | Purpose |
|----------|---------|---------|
| `METAAPI_TOKEN` | _(empty)_ | Required for paper and live modes. |
| `METAAPI_ACCOUNT_ID` | _(empty)_ | Default account ID. Can be overridden per-run via `metaapi_account_ref`. |
| `METAAPI_REGION` | `new-york` | MetaAPI region for the trading account. |
| `METAAPI_BASE_URL` | `https://mt-client-api-v1.london.agiliumtrade.ai` | REST API base URL. |
| `METAAPI_MARKET_BASE_URL` | `https://mt-market-data-client-api-v1.london.agiliumtrade.ai` | Market data endpoint. |
| `METAAPI_USE_SDK_FOR_MARKET_DATA` | `false` | Use the MetaAPI SDK instead of REST for market data. |
| `METAAPI_SDK_CONNECT_TIMEOUT_SECONDS` | `30` | SDK connection timeout. |
| `METAAPI_REST_TIMEOUT_SECONDS` | `30` | REST call timeout. |
| `METAAPI_SDK_CIRCUIT_BREAKER_SECONDS` | `20` | Circuit breaker hold-off after SDK failure. |
| `ENABLE_PAPER_EXECUTION` | `true` | Enable paper-mode order submission to MetaAPI. |
| `ALLOW_LIVE_TRADING` | `false` | Enable live order submission. Must be explicitly set. |
| `EXECUTION_MANAGER_LLM_ENABLED` | `false` | Enable LLM narrative in the execution-manager agent. |

The `MetaApiAccountSelector` resolves the target account from the DB at execution time. If `metaapi_account_ref` is provided in the run request, that specific account is used; otherwise the selector falls back to the configured default.

Supported MetaAPI success codes: `ERR_NO_ERROR`, `TRADE_RETCODE_DONE`, `TRADE_RETCODE_DONE_PARTIAL`, `TRADE_RETCODE_PLACED`, `TRADE_RETCODE_NO_CHANGES` (and numeric equivalents 0, 10008, 10009, 10010, 10025). Any other response is treated as a failure.

## Further reading

- [Risk & Governance](risk-and-governance.md) — risk engine checks that gate execution
- [Paper vs Live](paper-vs-live.md) — mode comparison and pre-live checklist
- [Runtime Flow](runtime-flow.md) — how execution fits into the 4-phase pipeline
