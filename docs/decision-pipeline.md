# Decision Pipeline

This document describes how market data is processed through the agent pipeline and combined into a trade intent.

## Pipeline stages

```
Market data + News
    ↓
Phase 1: Parallel analysis (technical, news, market-context)
    ↓
Confidence aggregation (simple average) + aligned-source count
    ↓
Phase 2+3: Debate (if llm_enabled=true for all 3 debate agents)
            └─ if skipped: DebateResult(winner="no_edge", conviction="weak")
    ↓
Phase 4: Trader decision → risk validation → preflight → execution
```

## Phase 1: Score and confidence aggregation

Each Phase 1 agent produces a `score` (typically -1.0 to +1.0) and `confidence` (0.0 to 1.0).

**Confidence aggregation** (live decision loop):

```python
# backend/app/services/agentscope/registry.py:995
_avg_conf = sum(_confs) / len(_confs) if _confs else 0.0
```

Confidence is a **simple unweighted average** of the three Phase 1 agent confidence values. No per-agent weighting is applied in the live path.

**Score synthesis**: In LLM mode, the trader agent receives all three Phase 1 analyses as context and synthesizes its own directional assessment. There is no deterministic weighted formula applied to scores in the live decision loop.

> **Note**: `decision_helpers.py` defines `SCORE_WEIGHTS = {"technical-analyst": 0.50, "news-analyst": 0.25, "market-context-analyst": 0.25}` and a `compute_deterministic_score()` function. These are **trace/debug only** — labeled "TRACE ONLY — not used in the decision loop" in the source. They are not invoked during a live run.

**Aligned sources count**: number of Phase 1 agents whose direction (bullish/bearish/neutral) matches the aggregate direction. Used in gating threshold checks.

## Technical scoring weights

Individual technical signals are weighted before producing the technical analyst's final score. These weights are defined in `constants.py` and must sum to 1.0:

| Signal | Weight |
|--------|--------|
| Trend | 0.22 |
| EMA | 0.10 |
| RSI | 0.13 |
| MACD | 0.16 |
| Price change | 0.06 |
| Pattern | 0.06 |
| Divergence | 0.07 |
| Multi-timeframe | 0.14 |
| Support/resistance level | 0.06 |

## Debate phase (Phase 2+3)

The debate phase runs only when **all three debate agents** (`bullish-researcher`, `bearish-researcher`, and `trader-agent` as moderator) have `llm_enabled=true`. If any one has `llm_enabled=false`, the entire debate phase is skipped.

**When skipped**: the pipeline returns `DebateResult(winner="no_edge", conviction="weak")` and the trader agent proceeds to Phase 4 using only Phase 1 analysis. The bullish and bearish researchers still run their `_run_deterministic()` path to produce theses, but the debate MsgHub exchange is not executed.

**When debate runs**: the bullish and bearish researchers exchange arguments via `MsgHub`; the trader-agent moderates and produces a `DebateResult` with `winner` (bullish/bearish/no_edge) and `conviction` (strong/moderate/weak). The conviction level is used by the trader in Phase 4.

## Decision gating policy

After Phase 1 aggregation, the `decision_gating` MCP tool evaluates whether the combined signal is strong enough to proceed with a directional trade.

Thresholds are defined by `DECISION_MODE` (set via env var or UI). All three modes block on major contradictions (`block_major_contradiction=True`).

### Mode thresholds

| Parameter | Conservative | Balanced (default) | Permissive |
|-----------|-------------|-------------------|------------|
| `min_combined_score` | 0.32 | 0.22 | 0.13 |
| `min_confidence` | 0.38 | 0.28 | 0.25 |
| `min_aligned_sources` | 2 | 1 | 1 |
| `allow_technical_single_source_override` | false | true | true |
| `block_major_contradiction` | true | true | true |

### Contradiction penalties

When Phase 1 agents disagree, the effective confidence is reduced:

| Level | Conservative | Balanced | Permissive |
|-------|-------------|---------|------------|
| Weak | -0.0 | -0.0 | -0.01 |
| Moderate | conf × 0.80 (then -0.08) | conf × 0.85 (then -0.06) | conf × 0.90 (then -0.04) |
| Major | conf × 0.60 (then -0.14) | conf × 0.70 (then -0.11) | conf × 0.75 (then -0.08) |

Exact values from `constants.py`:

| Field | Conservative | Balanced | Permissive |
|-------|-------------|---------|------------|
| `contradiction_penalty_weak` | 0.0 | 0.0 | 0.01 |
| `contradiction_penalty_moderate` | 0.08 | 0.06 | 0.04 |
| `contradiction_penalty_major` | 0.14 | 0.11 | 0.08 |
| `confidence_multiplier_moderate` | 0.80 | 0.85 | 0.90 |
| `confidence_multiplier_major` | 0.60 | 0.70 | 0.75 |

## Trade sizing

If trader-agent produces a BUY/SELL decision but is missing entry, stop-loss, or take-profit levels, the `trade_sizing` tool computes them using ATR:

- Stop loss: `entry ± ATR × 1.5` (`SL_ATR_MULTIPLIER = 1.5`)
- Take profit: `entry ± ATR × 2.5` (`TP_ATR_MULTIPLIER = 2.5`)
- Fallback (no ATR available): SL = 0.3% from entry (`SL_PERCENT_FALLBACK = 0.003`), TP = 0.6% from entry (`TP_PERCENT_FALLBACK = 0.006`)

## What happens with a HOLD decision

If the trader decides HOLD:
- Risk manager is skipped entirely
- Execution manager is skipped
- Run completes as `completed` with no order created
- The HOLD reasoning is stored in the run trace

## Structured output validation

All agent outputs are validated against Pydantic schemas. Invalid values:
- `NaN` or `Inf` in float fields: rejected, step marked failed
- Out-of-range floats: clamped to schema bounds (e.g., confidence clamped to [0.0, 1.0])
- Missing required fields: step marked failed; run may continue with partial data

## Signal thresholds (strategy monitor)

When the strategy monitor evaluates signals for auto-triggering runs, it uses separate thresholds from `constants.py`:

| Constant | Value | Description |
|----------|-------|-------------|
| `SIGNAL_THRESHOLD` | 0.05 | Minimum combined signal strength to consider a trigger |
| `TECHNICAL_SIGNAL_THRESHOLD` | 0.15 | Technical analyst signal strength required |
| `NEWS_SIGNAL_THRESHOLD` | 0.10 | News analyst signal strength required |
| `CONTEXT_SIGNAL_THRESHOLD` | 0.12 | Market context analyst signal strength required |

## Further reading

- [Agents](agents.md) — per-agent output schemas
- [Risk & Governance](risk-and-governance.md) — what happens after trade intent is formed
- [Runtime Flow](runtime-flow.md) — phase timing
