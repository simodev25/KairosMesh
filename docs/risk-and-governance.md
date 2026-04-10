# Risk and Governance

The risk engine is deterministic Python code in `backend/app/services/risk/`. It is not an LLM. Its result is authoritative — it cannot be overridden by any agent's LLM reasoning.

## Execution gate

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

The `portfolio_risk_evaluation` tool is called with `force_kwargs`: the registry injects all inputs (portfolio state, risk limits, trade parameters) before the tool runs. The risk-manager LLM receives the tool result as a fact — it cannot influence the tool's inputs.

## LLM override behavior

| Scenario | Outcome |
|----------|---------|
| Tool: accepted=true, LLM summary: approve | Trade proceeds |
| Tool: accepted=true, LLM summary: reject | **Tool wins** — trade proceeds |
| Tool: accepted=false, LLM summary: approve | **Tool wins** — trade blocked |
| Tool: accepted=false, LLM summary: reject | Trade blocked |

Attribution:
- **Tool accepts, LLM would reject**: `backend/app/services/agentscope/registry.py` explicitly overrides the LLM and uses the tool result.
- **Tool rejects, LLM would approve**: the downstream execution gate reads the `accepted` field from the tool output and blocks execution regardless of LLM reasoning; the registry is not involved in this path.

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

## What governance does NOT cover

| Gap | Implication |
|----|------------|
| No portfolio-level aggregation across concurrent runs | Multiple simultaneous runs can each pass per-run checks while combined exposure exceeds tolerance |
| No real-time broker margin check | Volume sizing uses locally-cached portfolio state, not live broker API |
| Contract specs are hardcoded defaults | Exotic instruments may silently use wrong pip values |
| No slippage or spread cost in sizing | Execution assumes exact fill |
| No correlation-based position limits | Correlated positions (e.g., EUR pairs) counted separately |

## Further reading

- [Execution](execution.md) (forthcoming) — preflight and order submission
- [Paper vs Live](paper-vs-live.md) (forthcoming) — how limits differ by mode
- [Limitations](limitations.md) (forthcoming) — known gaps
