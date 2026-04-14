# Risk and Governance

The risk engine is deterministic Python code in `backend/app/services/risk/`. It is not an LLM. Its result is authoritative — it cannot be overridden by any agent's LLM reasoning.

## Trade execution gate

A trade must pass all of these in sequence before any order is submitted:

1. Trader decision is not HOLD
2. Risk engine: `accepted=true`
3. Execution preflight: `can_execute=true`
4. `ALLOW_LIVE_TRADING=true` (live mode only)
5. User has `trader-operator` role (live mode only)

`ALLOW_LIVE_TRADING` defaults to `false` (see `backend/.env.example` and `backend/app/core/config.py`), so live execution is disabled unless explicitly opted in.

Failure at any step blocks execution with no appeal path.

## How risk evaluation works

```
Trader decision (side, entry, SL, TP, volume)
    ↓
portfolio_risk_evaluation MCP tool
    (inputs are force-injected by registry — LLM cannot alter them)
    ↓
RiskEngine.evaluate() — deterministic Python
    ↓
{ accepted: bool, suggested_volume: float, primary_rejection_reason: str | null }
```

The `portfolio_risk_evaluation` tool is called with `force_kwargs`: `backend/app/services/agentscope/toolkit.py` (called by the registry) injects all inputs (portfolio state, risk limits, trade parameters) before the tool runs. The risk-manager LLM receives the tool result as a fact — it cannot influence the tool's inputs.

## LLM override behavior

| Scenario | Outcome |
|----------|---------|
| Tool: accepted=true, LLM summary: approve | Trade proceeds |
| Tool: accepted=true, LLM summary: reject | **Tool wins** — trade proceeds |
| Tool: accepted=false, LLM summary: approve | **Tool wins** — trade blocked |
| Tool: accepted=false, LLM summary: reject | Trade blocked |

Source: `backend/app/services/agentscope/registry.py` (tool-accepts, LLM-rejects path triggers an explicit override; tool-rejects path reads `accepted=false` directly with no override branch).

## Per-mode risk limits

| Limit | Simulation | Paper | Live |
|-------|-----------|-------|------|
| `max_daily_loss_pct` | 10% | 6% | 3% |
| `max_weekly_loss_pct` | 15% | 10% | 5% |
| `max_open_risk_pct` | 15% | 10% | 6% |
| `max_positions` | 10 | 5 | 3 |
| `max_positions_per_symbol` | 3 | 2 | 1 |
| `min_free_margin_pct` | 20% | 30% | 50% |

Source: `backend/app/services/risk/limits.py`

## Risk checks applied

| Check | Blocks trade? | Notes |
|-------|--------------|-------|
| Daily loss limit exceeded | Yes | |
| Weekly loss limit exceeded | Yes | |
| Max open positions reached | Yes | |
| Max positions per symbol reached | Yes | |
| Insufficient free margin | Yes | |
| Currency notional exposure >= `max_currency_notional_exposure_pct_block` | Yes | simulation: 40%, paper: 25%, live: 15% (from `limits.py`) |
| NaN or Inf in price inputs | Yes | Validated via `_safe_float()` |
| Invalid price range | Yes | Entry, SL, TP validated |
| Volume below asset minimum | Yes | Per asset-class bounds |
| Volume above asset maximum | Yes | Per asset-class bounds |
| Spread-to-price ratio exceeds mode limit | Yes | simulation: 0.05% (5 bps), paper: 0.02% (2 bps), live: 0.01% (1 bp) — checked in preflight (not risk engine) |

## Asset class contract specs

These are hardcoded defaults in `backend/app/services/risk/rules.py`. They are NOT fetched from the broker at runtime.

| Asset class | pip_size | pip_value (per lot) | contract_size | min_vol | max_vol |
|-------------|----------|---------------------|--------------|---------|---------|
| Forex | 0.0001 (0.01 for JPY pairs) | 10.0 | 100,000 | 0.01 | 10.0 |
| Crypto | N/A (dynamic) | 1.0 | 1 | 0.01 | 100.0 |
| Index | 1.0 | 1.0 | 1 | 0.1 | 50.0 |
| Metal | 0.01 | 10.0 | 100 | 0.01 | 10.0 |
| Energy | 0.01 | 10.0 | 1,000 | 0.01 | 10.0 |
| Equity/ETF | 0.01 | 1.0 | 1 | 1.0 | 1,000.0 |

> **Note**: Exotic or non-standard instruments may use incorrect contract specs because classification is heuristic (pattern matching on symbol name).

## Governance gaps

| Gap | Implication |
|----|------------|
| No portfolio-level aggregation across concurrent runs | Multiple simultaneous runs can each pass per-run checks while combined exposure exceeds tolerance |
| No real-time broker margin check | Volume sizing uses locally-cached portfolio state, not live broker API |
| Contract specs are hardcoded defaults | Exotic instruments may silently use wrong pip values |
| No slippage or spread cost in sizing | Execution assumes exact fill |
| No correlation-based position limits | Correlated positions (e.g., EUR pairs) counted separately |

## Governance Monitor architecture

The Governance Monitor is a post-trade supervision loop that runs independently of the entry decision pipeline. It continuously evaluates every open broker position and recommends adjustments (SL, TP) or early close when market conditions change.

### Components

```
Celery Beat (every 60 s)
    └── run_governance_loop task
            └── MetaApiClient.get_positions()   ← live broker state
            └── for each position:
                    └── PositionContextBuilder      ← history, candles, MFE/MAE
                    └── GovernanceRegistry.execute()
                            ├── Phase 1 analysts (parallel LLM agents)
                            │       ├── TechnicalAnalyst
                            │       ├── SentimentAnalyst
                            │       └── MacroAnalyst
                            └── GovernanceTrader (LLM, GovernanceDecision schema)
                                    → action: HOLD | ADJUST_SL | ADJUST_TP | ADJUST_SL_TP | CLOSE
                                    → conviction: 0.0–1.0
                                    → urgency: low | medium | high | critical
                                    → new_sl, new_tp (when relevant)
```

### Key files

| File | Role |
|------|------|
| `backend/app/tasks/governance_task.py` | Celery Beat task — orchestrates the loop |
| `backend/app/services/governance/registry.py` | `GovernanceRegistry` — runs analysts + governance trader |
| `backend/app/services/governance/position_context_builder.py` | Builds `PositionHistoryContext` (origin run, candles, MFE/MAE) |
| `backend/app/db/models/governance_run.py` | `GovernanceRun` DB model — one record per evaluation |
| `backend/app/api/routes/governance.py` | REST endpoints: list, approve, reject |
| `backend/app/api/ws/governance_ws.py` | WebSocket — pushes `governance_update` events to the UI |
| `frontend/src/components/governance/GovernanceMonitorPanel.tsx` | UI panel embedded in OrdersPage |

### GovernanceRun lifecycle

```
created (status=pending, approval_status=pending)
    ↓
GovernanceRegistry runs (status=running)
    ↓
Pipeline completes (status=completed)
    ├── action=HOLD  → approval_status=n/a, no execution needed
    └── action=CLOSE|ADJUST_*
            └── requires human approval (approval_status=pending)
                    ├── POST /governance/{id}/approve
                    │       → approval_status=approved
                    │       → approve_and_execute_governance Celery task
                    │       → MetaApiClient.close_position() or .modify_position()
                    │       → executed=true
                    └── POST /governance/{id}/reject
                            → approval_status=rejected, no broker action
```

### Supervised mode (default)

Every non-HOLD recommendation is held at `approval_status=pending` until a human approves or rejects it from the UI. The broker is never touched without explicit confirmation. This is enforced in `governance_task.py`:

```python
gov_run = GovernanceRun(
    requires_approval=True,
    approval_status='pending',
    ...
)
```

Auto-execution (removing the approval gate) requires setting `requires_approval=False` on the `GovernanceRun` — this is not exposed in the UI and must be done by code change.

### Anti-starvation mechanism

The loop uses a 3-minute staleness window to prevent stale `pending/running` records from blocking future evaluations of the same position. Records older than 3 minutes are automatically marked `failed` before a new evaluation is created.

### Celery timing

| Parameter | Value | Reason |
|-----------|-------|--------|
| Beat interval | 60 s | Frequent enough to catch rapid moves |
| `soft_time_limit` | 240 s | Each LLM pipeline takes ~30–60 s; 2–4 positions fit |
| `time_limit` | 250 s | Hard kill after soft limit |
| Redis lock TTL | 240 s | Matches soft limit — prevents Beat spawning a second run |

### EXECUTION_HISTORY integration

Governance runs appear in the `EXECUTION_HISTORY` table on the Terminal page alongside regular analysis runs. They are distinguished by:

- **Source badge**: teal `GOVERNANCE` label (vs purple `STRATEGY` or grey `MANUAL`)
- **ID prefix**: displayed as `G{n}` (e.g. `G42`) — internally mapped via `id = 10_000_000 + gov_run.id`
- **Timeframe**: `GOV`
- **Mode**: `governance`
- **Decision / execution**: shows the governance action and urgency (e.g. `HOLD · low`)
- **Signal**: shows position side (BUY/SELL)

The backend merges governance runs into the `/runs` response when `?include_governance=true` is passed (default in the UI client).

## Further reading

- [Execution](execution.md) — preflight checks, idempotency, and order submission
- [Paper vs Live](paper-vs-live.md) — how limits differ by mode and the pre-live checklist
- [Limitations](limitations.md) — known gaps in risk coverage
