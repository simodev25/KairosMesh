---
name: Kairos Mesh Documentation Refactor
description: Design spec for the full documentation rewrite — flat docs/ layout, grounded in implementation reality
type: project
---

# Documentation Refactor — Design Spec

**Date**: 2026-04-10  
**Project**: Kairos Mesh (Multi-Agent Trading System)  
**Goal**: Rewrite all documentation to be technically precise, honest, and grounded in codebase reality.

---

## Context

The repository currently has 13 markdown files in `docs/architecture/`. They are partially accurate but contain:
- Overstated claims (debate always runs, persistent memory, autonomous learning)
- Missing explanations (deterministic fallback, tool-overrides-LLM risk logic, transient vs persistent memory)
- No operator-facing configuration reference
- No honest limitations page
- No paper-vs-live safety clarifications

The `docs/agentscope/` subdirectory contains AgentScope framework docs, not Kairos-specific content — it will be left untouched.

---

## Decision

**Option A chosen**: Flat `docs/` layout — all new files at top level of `docs/`, existing `docs/architecture/` subdirectory retired (content absorbed and improved).

---

## File Responsibility Map

### Root files

| File | Responsibility |
|------|---------------|
| `README.md` | First contact: what it is, architecture overview, quickstart summary, limitations callout, docs map |
| `CONTRIBUTING.md` | Dev setup, PR process, coding conventions, how to add agents/tools |
| `SECURITY.md` | Vulnerability reporting process, security model, known boundaries |

### docs/ files

| File | Responsibility |
|------|---------------|
| `docs/getting-started.md` | Prerequisites, stack setup (Docker Compose), first run walkthrough |
| `docs/quickstart.md` | Minimal path to a working paper-trading run in < 5 minutes |
| `docs/architecture.md` | System layers, component map, technology stack, runtime overview diagram |
| `docs/runtime-flow.md` | Step-by-step: how a run starts → 4 phases → WebSocket → DB commit |
| `docs/agents.md` | All 8 agents: role, inputs, outputs, tools, advisory vs binding, wiring status |
| `docs/decision-pipeline.md` | Market ingestion → analysis → debate → trade intent → gating logic |
| `docs/risk-and-governance.md` | Deterministic risk engine, per-mode limits, gates, tool-overrides-LLM logic |
| `docs/execution.md` | Execution manager, simulation/paper/live modes, order flow, idempotency, safeguards |
| `docs/memory.md` | Transient InMemoryMemory, persistent DB logs, no RAG, write-back gaps |
| `docs/configuration.md` | All env vars in tables: required / optional / dangerous / feature flags |
| `docs/observability.md` | Prometheus metrics, structured run records, audit trail, trace files, Grafana |
| `docs/paper-vs-live.md` | What differs between modes, safety checklist before live, default=paper |
| `docs/limitations.md` | Incomplete features, runtime gaps, partial implementations, honest constraints |

---

## Key Architectural Truths to Preserve

These facts were confirmed by codebase audit and must be clearly stated in the documentation:

1. **Run entry point**: `POST /api/v1/runs` → Celery task queue → `AgentScopeRegistry.execute()`
2. **Orchestrator**: `AgentScopeRegistry` (single class, ~1800 lines) owns all 4 phases
3. **4-phase pipeline**:
   - Phase 1 (parallel): technical-analyst, news-analyst, market-context-analyst
   - Phase 2+3 (sequential): bullish/bearish debate via MsgHub, trader-agent as moderator
   - Phase 4 (sequential): trader decision → risk validation → preflight → execution
4. **Debate is conditional**: Only runs if all 3 debate agents have `llm_enabled=true`; otherwise returns `DebateResult(winner="no_edge", conviction="weak")`
5. **Deterministic fallback**: Each agent has `_run_deterministic()` path — activates when `llm_enabled=false`, not on error
6. **Risk engine is separate**: Deterministic Python code, not an LLM. Tool result (`portfolio_risk_evaluation`) overrides LLM if conflict.
7. **Execution default**: `ALLOW_LIVE_TRADING=false`; simulation and paper are safe defaults
8. **Memory is transient per run**: `InMemoryMemory` cleared after each run. No RAG. No outcome-based learning.
9. **Persistent storage**: PostgreSQL stores all runs, agent steps, execution orders, LLM call logs — audit trail only, not a learning loop
10. **All 8 agents are fully implemented**: No stubs found

---

## Claims to Remove or Downgrade

| Claim | Action |
|-------|--------|
| "Debate is mandatory / always runs" | Replace with: debate is conditional on `llm_enabled` for all 3 agents |
| "Persistent memory across runs" | Replace with: transient per-run memory; DB is audit log, not learning store |
| "Autonomous alpha engine" | Remove entirely |
| "Production-ready" | Remove; system is paper-trading by default, live trading requires explicit flags |
| "LLM controls risk decisions" | Correct to: tool result overrides LLM; risk engine is deterministic |
| "Memory influences future runs" | Correct to: no automated feedback loop; DB logs are queryable but not used in LLM inference |

---

## Missing Content to Add

| Topic | File |
|-------|------|
| Deterministic fallback path (`_run_deterministic`) | `docs/runtime-flow.md`, `docs/agents.md` |
| Tool-overrides-LLM in risk-manager | `docs/risk-and-governance.md` |
| Order idempotency key logic | `docs/execution.md` |
| Debate timeout/skip behavior | `docs/decision-pipeline.md` |
| Transient vs persistent memory distinction | `docs/memory.md` |
| Per-mode risk limits (simulation/paper/live values) | `docs/risk-and-governance.md` |
| Decision mode threshold values | `docs/decision-pipeline.md` |
| WebSocket event protocol | `docs/observability.md` |
| Agent skills bootstrap (`agent-skills.json`) | `docs/agents.md` |
| `ALLOW_LIVE_TRADING` flag and operator roles | `docs/paper-vs-live.md`, `docs/configuration.md` |

---

## Style Rules

- No hype, no marketing language
- Use tables for configuration, agent inventory, safeguards
- Explicit "Partial / Experimental / Not wired" labels where applicable
- Cite file paths where claims are code-backed
- Limitations page is mandatory and must be written last, after all other files

---

## Files to Retire

- `docs/architecture/ARCHITECTURE.md` → absorbed into `docs/architecture.md`
- `docs/architecture/AGENTS.md` → absorbed into `docs/agents.md`
- `docs/architecture/RUNTIME_FLOW.md` → absorbed into `docs/runtime-flow.md`
- `docs/architecture/RISK_AND_EXECUTION.md` → absorbed into `docs/risk-and-governance.md` + `docs/execution.md`
- `docs/architecture/STRATEGY_ENGINE.md` → partially absorbed into `docs/architecture.md`
- `docs/architecture/TOOLS.md` → referenced from `docs/agents.md`
- `docs/architecture/MODULES.md` → absorbed into `docs/architecture.md`
- `docs/architecture/decision-modes.md` → absorbed into `docs/decision-pipeline.md`
- `docs/architecture/OBSERVABILITY.md` → absorbed into `docs/observability.md`
- `docs/architecture/LIMITATIONS.md` → replaced by `docs/limitations.md`
- All other files in `docs/architecture/` → reviewed and absorbed or discarded
