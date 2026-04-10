# Governance Monitoring System — Design Spec

**Date:** 2026-04-10  
**Status:** Approved  
**Approach:** GovernanceService + run_type extension (Approach C)

---

## Goal

Add a Governance page that monitors open MetaAPI positions, runs them through the existing agent pipeline, and automatically adjusts SL/TP or closes positions based on agent decisions validated by the risk engine. The system operates in two modes: fully automatic or confirmation-required, switchable via a UI toggle.

---

## Architecture

```
┌─── Celery Beat (every N min) ──────────────────────────────────┐
│    + POST /governance/reevaluate (manual UI trigger)           │
└──────────────────────┬─────────────────────────────────────────┘
                       ▼
          GovernanceService.analyze_open_positions()
                       │
          For each open MetaAPI position:
                       │
                       ▼
       AnalysisRun(run_type="governance",
                   governance_position_id=pos_id,
                   analysis_depth="light"|"full")
                       │
                       ▼
         AgentScopeRegistry (governance branch)
           → injects position context into agent prompts
             (entry price, current price, current SL/TP, PNL, unrealized %)
           → LIGHT: Phase 1 only (technical-analyst, news-analyst, market-context)
           → FULL: complete 4-phase pipeline (all 8 agents)
           → GovernanceOutputSchema:
               { action: HOLD|ADJUST_SL|ADJUST_TP|ADJUST_BOTH|CLOSE,
                 new_sl, new_tp, reasoning, risk_score, confidence }
                       │
                       ▼
              Risk Engine validates
                       │
              ┌─────────────────┐
          mode=auto         mode=confirmation
              │                  │
         ExecutionService    Governance action stored as PENDING
         modify/close()      → UI shows [APPROVE] / [REJECT] buttons
              │                  │
         MetaAPI ◄───────────────┘ (on approval)
                       │
              Decision logged to AgentStep + AuditLog
              → GovernanceDecisionStream via WebSocket
```

### Why this approach

- Reuses `AnalysisRun`, `AgentStep`, `AuditLog`, WebSocket, Celery infrastructure unchanged
- A single `run_type` field distinguishes governance runs from analysis runs
- All existing tooling (RunDetailPage, observability, audit trail) works automatically
- No duplication of the agent pipeline

---

## Data Model

### DB Changes (1 migration)

```python
# AnalysisRun — 2 new fields
run_type: Enum("analysis", "governance")  # default="analysis", not null
governance_position_id: String(50, nullable=True)  # MetaAPI position ID

# GovernanceSettings — new table (singleton per system)
id: Integer PK
execution_mode: Enum("auto", "confirmation")  # default="confirmation"
analysis_depth: Enum("light", "full")          # default="light"
interval_minutes: Integer                      # default=15, min=5
enabled: Boolean                               # default=False
updated_at: DateTime
updated_by: String (actor email)
```

### GovernanceOutputSchema (new Pydantic schema)

```python
class GovernanceDecision(BaseModel):
    action: Literal["HOLD", "ADJUST_SL", "ADJUST_TP", "ADJUST_BOTH", "CLOSE"]
    new_sl: float | None = None      # required if ADJUST_SL or ADJUST_BOTH
    new_tp: float | None = None      # required if ADJUST_TP or ADJUST_BOTH
    reasoning: str                   # human-readable explanation
    risk_score: float                # 0.0–1.0 (higher = riskier to act)
    confidence: float                # 0.0–1.0 (agent confidence in decision)
```

### Execution States

A governance run produces one of these outcomes stored in `AgentStep.output_payload`:

| State | Meaning |
|-------|---------|
| `HOLD` | No action taken — position healthy |
| `APPROVED` | Action executed (auto mode or user-confirmed) |
| `BLOCKED` | Risk engine rejected the action |
| `PENDING` | Awaiting user confirmation (confirmation mode) |
| `REJECTED` | User rejected the proposed action |

---

## Backend Components

### 1. GovernanceService (`services/governance/service.py`)

```python
class GovernanceService:
    async def analyze_open_positions(depth: str) -> list[str]
        # Fetches open MetaAPI positions
        # Skips positions with an in-progress governance run
        # Creates AnalysisRun(run_type=governance) per position
        # Enqueues Celery tasks
        # Returns list of created run_ids

    async def approve_action(run_id: str, actor: str) -> None
        # Retrieves governance decision from AgentStep
        # Calls ExecutionService.modify_position() or close_position()
        # Updates run status, logs to AuditLog

    async def reject_action(run_id: str, actor: str) -> None
        # Marks run as REJECTED
        # Logs to AuditLog
```

### 2. AgentScopeRegistry — governance branch

Add governance path in `execute()`:

```python
if run.run_type == "governance":
    position_context = self._build_position_context(run)
    # Inject into system prompts: entry_price, current_price, 
    #   current_sl, current_tp, unrealized_pnl, unrealized_pct, side
    
    if run.analysis_depth == "light":
        # Run Phase 1 only: technical-analyst, news-analyst, market-context
        # Then: governance-decision agent (new, uses GovernanceOutputSchema)
    else:
        # Run full 4-phase pipeline
        # Trader agent receives position context + outputs GovernanceDecision
    
    return self._handle_governance_decision(decision)
```

### 3. ExecutionService — new methods

```python
async def modify_position(position_id: str, new_sl: float | None, 
                           new_tp: float | None) -> dict
    # MetaAPI: modifyPosition(positionId, stopLoss, takeProfit)

async def close_position(position_id: str) -> dict
    # MetaAPI: closePosition(positionId)
```

### 4. Governance Celery Task (`tasks/governance_monitor_task.py`)

```python
@celery_app.task
def governance_monitor_task():
    settings = get_governance_settings()
    if not settings.enabled:
        return
    service = GovernanceService()
    run_ids = await service.analyze_open_positions(settings.analysis_depth)
    # Each run_id is already enqueued as a standard analysis_task
```

Registered in Celery Beat schedule with `interval_minutes` from `GovernanceSettings`.

### 5. API Routes (`api/routes/governance.py`, prefix `/api/v1/governance`)

| Method | Path | Description | Role |
|--------|------|-------------|------|
| `GET` | `/settings` | Current governance settings | VIEWER |
| `PUT` | `/settings` | Update settings | TRADER_OPERATOR |
| `GET` | `/positions` | Open positions + latest governance run per position | VIEWER |
| `GET` | `/stream` | Last 50 governance decisions | VIEWER |
| `POST` | `/reevaluate` | Trigger analysis for all open positions | TRADER |
| `POST` | `/reevaluate/{position_id}` | Trigger analysis for one position | TRADER |
| `POST` | `/approve/{run_id}` | Approve pending action | TRADER_OPERATOR |
| `POST` | `/reject/{run_id}` | Reject pending action | TRADER_OPERATOR |

---

## Frontend Components

### New page: `GovernancePage.tsx`

Route: `/governance` — added to `Layout.tsx` nav between ORDERS and STRATEGIES with a Shield icon.

**Layout:**

```
Row 1 — KPI cards (4):
  ACTIVE_POSITIONS | TOTAL_FLOATING_PNL | GUARDIAN_RISK_SCORE | MARGIN_USAGE

Row 2 — Full-width:
  ACTIVE_MARKET_EXPOSURE table
    Columns: ID · ASSET · TYPE · ENTRY/CURRENT · PNL · SL/TP · ACTIONS
    Header actions: [REEVALUATE_ALL button] [AUTO_GUARDIAN toggle]
    Row actions: [⚙ settings] [⚡ reevaluate single]

Row 3 — Two columns:
  Left: GUARDIAN_RISK_VALIDATION      Right: GUARDIAN_DECISION_STREAM
        + ANALYSIS_DEPTH selector            (scrollable feed)
        + EXECUTION_MODE switch
```

### New components

| Component | Responsibility |
|-----------|---------------|
| `ActiveMarketExposure.tsx` | Positions table with entry/current, floating PNL, SL/TP, per-row reevaluate |
| `GuardianRiskValidation.tsx` | Risk rules status rows (drawdown, volatility, margin, news buffer) with colored dots |
| `GovernanceDecisionStream.tsx` | Scrollable decision feed — APPROVED (blue) / BLOCKED (red) / PENDING (yellow) / INFO badges, approve/reject buttons for PENDING |
| `GovernanceSettings.tsx` | Analysis depth radio (LIGHT/FULL), execution mode toggle (CONFIRMATION ←→ AUTO), interval input, enabled switch |
| `GovernanceKPIs.tsx` | 4 summary cards — active positions, floating PNL, risk score, margin usage |

### Data fetching

- `useGovernancePositions()` — polls `GET /governance/positions` every 10s
- `useGovernanceStream()` — polls `GET /governance/stream` every 5s, or subscribes via existing WebSocket when a governance run is active
- `useGovernanceSettings()` — fetches once on mount, refetches after PUT

### Execution mode UI behavior

| Mode | Behavior |
|------|---------|
| CONFIRMATION | PENDING decisions appear in stream with [APPROVE] / [REJECT] buttons; actions not auto-executed |
| AUTO | Decisions execute immediately; stream shows APPROVED/BLOCKED only (no PENDING state) |

The switch is a single UI toggle that calls `PUT /governance/settings` with `execution_mode`.

---

## Agent Prompt Injection (governance context)

For governance runs, inject this block into the system prompt of all Phase 1 agents:

```
GOVERNANCE_CONTEXT:
  Position ID: {position_id}
  Symbol: {symbol}
  Side: {side}  # LONG or SHORT
  Entry price: {entry_price}
  Current price: {current_price}
  Current SL: {current_sl}
  Current TP: {current_tp}
  Unrealized PNL: {unrealized_pnl} ({unrealized_pct}%)
  Open duration: {open_duration_hours}h

Task: Evaluate whether this existing position should be:
  - HELD as-is
  - SL/TP adjusted (provide new values)
  - CLOSED immediately
Based on current market conditions.
```

---

## Risk Engine Integration

The governance decision passes through the existing `evaluate_portfolio()` before execution. For SL adjustments, the validation checks that:
- New SL does not increase risk beyond `max_risk_per_trade_pct`
- New TP maintains minimum R:R ratio (configurable, default 1.5)

For CLOSE, validation is skipped (closing always reduces risk).

---

## Deduplication

`GovernanceService` checks for in-progress runs before creating a new one:

```python
existing = db.query(AnalysisRun).filter(
    AnalysisRun.run_type == "governance",
    AnalysisRun.governance_position_id == position_id,
    AnalysisRun.status.in_(["pending", "running"])
).first()
if existing:
    skip  # don't double-analyze the same position
```

---

## Out of Scope

- Per-position governance scheduling (all positions use the same interval)
- Partial position close (close full position only)
- Multi-position correlation analysis (each position analyzed independently)
- Push notifications (alerts, email) for governance decisions
- Governance history beyond last 50 decisions in stream (RunDetailPage shows full history)
