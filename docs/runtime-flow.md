# Runtime Flow

This document describes how an analysis run executes from API request to database commit.

## Entry point

**`POST /api/v1/runs`** (`backend/app/api/routes/runs.py`)

Request body:
```json
{
  "pair": "EURUSD",
  "timeframe": "H1",
  "mode": "simulation",
  "risk_percent": 1.0,
  "metaapi_account_ref": null
}
```

`mode` options: `simulation` (default), `paper`, `live`.

Response (async, default):
```json
{ "run_id": "uuid", "status": "queued" }
```

## Dispatch

```
POST /api/v1/runs
  ├─ Create AnalysisRun record in DB (status=pending)
  ├─ if async_execution=true (default):
  │    enqueue run_analysis_task → RabbitMQ
  │    set status=queued, store celery_task_id
  │    return { run_id, status: "queued" }
  └─ if async_execution=false (testing only):
       execute AgentScopeRegistry inline
```

The Celery worker picks up the task and calls `AgentScopeRegistry().execute()`.

## Strategy monitor (auto-triggered runs)

Celery Beat runs `strategy_monitor_task.check_all()` every 30 seconds. When a monitored strategy's computed signal changes (deduplication via `last_signal_key`), a Run is auto-created and dispatched through the same path as a manual request. This can result in paper or live order submission depending on active configuration.

## AgentScopeRegistry.execute()

All four phases execute inside this method. WebSocket events are broadcast at each phase boundary.

### Pre-pipeline: Data resolution

```
1. Fetch OHLC candles: MetaAPI primary, YFinance fallback
   - Minimum bars: AGENTSCOPE_MIN_BARS (default: 30)
   - Candle limit: AGENTSCOPE_CANDLE_LIMIT (default: 240)
2. Fetch market snapshot (current price, spread, ATR)
3. Fetch news items from configured providers
4. Fetch portfolio state (balance, equity, margin, open positions)
5. Resolve LLM provider config from DB (Connectors settings)
6. Build per-agent context packages
```

If market data fetch fails, the run is marked `failed` and no agents execute.

### Phase 1 — Parallel analysis (progress 0% → 10%)

Three agents run concurrently via `asyncio.gather()`:

| Agent | Timeout |
|-------|---------|
| `technical-analyst` | `AGENTSCOPE_AGENT_TIMEOUT_SECONDS` (default: 60s) |
| `news-analyst` | same |
| `market-context-analyst` | same |

Each agent calls its MCP tool set and produces a structured `Msg` with `metadata` (score, confidence, direction, reasoning).

On agent timeout or error: the step is marked `failed`; the run continues with partial outputs. The registry does **not** fall back to deterministic mode on LLM error — it retries up to 3 times (the `AGENTSCOPE_RETRY_COUNT` config setting exists but is not currently wired to this retry loop) and then propagates the error.

Phase 1 outputs are concatenated into `analysis_summary` and injected into Phase 2+3 prompts.

### Phase 2+3 — Debate (progress 10% → 35%)

**Condition**: Only runs if all three debate agents (`bullish-researcher`, `bearish-researcher`, `trader-agent`) have `llm_enabled=true` in the DB config.

**If condition is false**: the bullish and bearish researcher agents still run in deterministic mode (tool calls, no LLM). There is no multi-turn debate exchange. Returns `DebateResult(winner="no_edge", conviction="weak")`. The trader agent receives Phase 1 analysis without debate input.

**If condition is true**:

```
1. Build MsgHub with bullish-researcher, bearish-researcher, trader-agent (moderator)
2. Run DEBATE_MIN_ROUNDS–DEBATE_MAX_ROUNDS rounds (defaults: 1–3)
3. Each round:
     bullish-researcher presents evidence
     → bearish-researcher counters
     → trader-agent evaluates and may call decision_gating tool
4. Produce DebateResult:
     winner: "bullish" | "bearish" | "no_edge"
     conviction: "strong" | "moderate" | "weak"
     key_argument: str
     weakness: str
```

On debate timeout: returns `DebateResult(winner="no_edge", conviction="weak")`.

### Phase 4 — Decision and governance (progress 35% → 90%)

#### Trader agent (progress 35% → 65%)

Receives Phase 1 analysis, debate result, portfolio state, and decision gating policy.

Produces `TraderDecisionDraft`:
```json
{
  "decision": "BUY | SELL | HOLD",
  "conviction": 0.78,
  "entry": 1.0812,
  "stop_loss": 1.0762,
  "take_profit": 1.0892,
  "reasoning": "..."
}
```

If `entry`, `stop_loss`, or `take_profit` are missing, the `trade_sizing` tool is auto-called to compute ATR-based levels.

**Fallback if trader fails to decide**:
1. Debate winner is `bullish` → BUY (recorded as fallback in trace)
2. Debate winner is `bearish` → SELL (recorded as fallback)
3. Otherwise → HOLD

#### Risk manager (progress 65% → 80%)

**Skipped entirely if decision is HOLD.**

Calls `portfolio_risk_evaluation` MCP tool with force-injected inputs. The LLM cannot alter what is passed to this tool.

If tool returns `accepted=false` → run blocked. LLM cannot override.
If tool returns `accepted=true` but LLM summary disagrees → **tool wins**.

#### Execution manager (progress 80% → 90%)

Runs `ExecutionPreflightEngine.validate()` — fully deterministic.

An optional LLM narrative summary can be generated if `EXECUTION_MANAGER_LLM_ENABLED=true` (default: `false`). The LLM summary is informational only — it does not affect the execution decision. The preflight and order submission are always deterministic.

If preflight passes: `ExecutionService.execute()` is called.

| Mode | Behavior |
|------|----------|
| `simulation` | Order recorded to DB, `status=simulated`. No broker call. |
| `paper` | Order submitted to MetaAPI paper account. |
| `live` | Order submitted to MetaAPI live account. Requires `ALLOW_LIVE_TRADING=true`. |

## Post-pipeline

```
1. Batch-commit all AgentStep records to DB
2. Update AnalysisRun:
     status: completed | failed
     decision: (structured JSON)
     trace: (full agentic_runtime structure with message history and tool calls)
3. Broadcast final WebSocket event
4. Write debug trace JSON (if DEBUG_TRADE_JSON_ENABLED=true)
```

## Progress events (WebSocket)

Subscribe at `ws://localhost:8000/ws/runs/{run_id}`:

| Progress | Meaning |
|----------|---------|
| 0% | Run accepted by worker, starting |
| 10% | Phase 1 (analysts) starting |
| 35% | Phase 1 complete, debate starting (or skip if LLM disabled) |
| 65% | Phase 2+3 complete, Phase 4 starting |
| 70% | Trader agent complete |
| 80% | Risk manager complete |
| 90% | Execution manager complete |
| 100% | Run finalized |

## Timeout and error handling

| Scenario | Behavior |
|----------|----------|
| Individual agent LLM timeout | Step marked failed; run continues with partial outputs |
| Debate timeout | Returns `no_edge`; trader decides independently |
| Market data unavailable | Run marked failed immediately, no agents run |
| Risk rejection | Run completes as `completed`, no order submitted |
| Preflight block | Run completes as `completed`, no order submitted |
| Celery hard timeout (360s default) | Run marked failed by Celery |

## Further reading

- [Agents](agents.md) — what each agent does and produces
- [Decision Pipeline](decision-pipeline.md) — how scores and votes combine
- [Risk & Governance](risk-and-governance.md) — risk engine detail
- [Execution](execution.md) — order submission and idempotency
