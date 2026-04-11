# Agents

Kairos Mesh runs 8 agents across a 4-phase pipeline. This document is a technical reference covering each agent's role, inputs, output schema, and MCP tool calls. For a pipeline overview, read [Runtime Flow](runtime-flow.md) first.

Note: this document covers only the 8 decision-pipeline agents. Additional agents exist in the system for strategy management and scheduling (e.g., `schedule-planner-agent`, `order-guardian`, `strategy-designer`) and are configured in `backend/config/agent-skills.json`, but are not part of the per-candle decision pipeline described here.

## Agent inventory

| # | Name | Phase | LLM by default | Authority |
|---|------|-------|----------------|-----------|
| 1 | technical-analyst | 1 (parallel) | Configurable per-agent | Advisory |
| 2 | news-analyst | 1 (parallel) | Configurable per-agent | Advisory |
| 3 | market-context-analyst | 1 (parallel) | Configurable per-agent | Advisory |
| 4 | bullish-researcher | 2 (debate) | Configurable; debate skipped if any disabled | Advisory |
| 5 | bearish-researcher | 2 (debate) | Configurable; debate skipped if any disabled | Advisory |
| 6 | trader-agent | 4 (moderates Phase 2+3 debate, decides in Phase 4) | Configurable per-agent | Decision-bearing |
| 7 | risk-manager | 4 | Hybrid (tool result is authoritative) | Binding |
| 8 | execution-manager | 4 | Optional (`EXECUTION_MANAGER_LLM_ENABLED`, default: false) | Binding |

Per-agent LLM enable/disable is configured in the UI (Connectors → AI Models) and stored in the DB. The `AGENT_SKILLS_BOOTSTRAP_FILE` env var is the mechanism for configuring per-agent `llm_enabled` initial values — the bootstrap file sets the starting state, which the UI/DB can subsequently override. There is no built-in default path; operators must set `AGENT_SKILLS_BOOTSTRAP_FILE` explicitly (e.g., to `backend/config/agent-skills.json`). When `llm_enabled=false`, the agent runs in deterministic mode: tools are called directly, no LLM inference.

---

## 1. technical-analyst

**Role**: Describes what the price data shows as objective facts — no trading recommendation.

**Phase**: 1 (parallel with news-analyst and market-context-analyst)

**Inputs** (context injected at run start):
- Instrument pair, asset class, timeframe
- Market snapshot (trend, RSI, MACD diff, ATR, last price, change pct)
- OHLC arrays pre-loaded into tool calls (up to last 200 bars)

**MCP tools** (max_iters: 5, parallel_tool_calls: true):
| Tool | Purpose |
|------|---------|
| `indicator_bundle` | Trend, RSI, MACD, EMA, ATR from OHLC data |
| `divergence_detector` | RSI-price divergence detection |
| `pattern_detector` | Candlestick pattern recognition |
| `support_resistance_detector` | Key support and resistance levels |
| `multi_timeframe_context` | Higher timeframe alignment check |
| `technical_scoring` | Deterministic scoring of technical signals |

**Output schema** (`TechnicalAnalysisResult`):
- `structural_bias`: `"bullish"` | `"bearish"` | `"neutral"`
- `local_momentum`: `"bullish"` | `"bearish"` | `"neutral"` | `"mixed"`
- `setup_quality`: `"high"` | `"medium"` | `"low"` | `"none"`
- `key_levels`: list of price level strings
- `patterns_found`: list of detected pattern strings
- `contradictions`: list of conflicting signal strings
- `summary`: factual paragraph (required, min length 1)
- `tradability`: `"high"` | `"medium"` | `"low"`
- `degraded`: bool (true when data is incomplete)

**Constraints / Notes**: Must call tools first, then describe findings. Must not invent levels or patterns not returned by tools. Does not make a trading recommendation.

---

## 2. news-analyst

**Role**: Describes news sentiment and key drivers for the instrument as objective facts.

**Phase**: 1 (parallel with technical-analyst and market-context-analyst)

**Inputs** (context injected at run start):
- Instrument pair, asset class, timeframe
- News items list (pre-loaded into `news_search` and `sentiment_parser` tools)
- Macro events list (pre-loaded into `macro_event_feed` tool)

**MCP tools** (max_iters: 4, parallel_tool_calls: true):
| Tool | Purpose |
|------|---------|
| `news_search` | Filter and retrieve relevant news items |
| `macro_event_feed` | Upcoming macro events (NFP, FOMC, ECB, etc.) |
| `sentiment_parser` | Parse headline-level sentiment direction |
| `symbol_relevance_filter` | Filter news and macro items by instrument relevance |
| `news_evidence_scoring` | Scores the strength and quality of news evidence |
| `news_validation` | Validates news signal coherence and coverage |

**Output schema** (`NewsAnalysisResult`):
- `sentiment`: `"bullish"` | `"bearish"` | `"neutral"` (for the instrument, not a currency)
- `coverage`: `"none"` | `"low"` | `"medium"` | `"high"`
- `key_drivers`: list of factor strings
- `risk_events`: list of upcoming event strings with timing
- `summary`: factual paragraph (required, min length 1)
- `degraded`: bool

**Constraints / Notes**: Only uses news items actually provided — never invents news. When `coverage=none`, `sentiment` is forced to `"neutral"`. Direction convention is instrument-relative (bullish USD = bearish EUR/USD).

---

## 3. market-context-analyst

**Role**: Assesses current market regime, session timing, volatility, and execution conditions.

**Phase**: 1 (parallel with technical-analyst and news-analyst)

**Inputs** (context injected at run start):
- Instrument pair, asset class, timeframe
- Market snapshot (OHLC-derived indicators pre-loaded into tools)

**MCP tools** (max_iters: 5, parallel_tool_calls: true):
| Tool | Purpose |
|------|---------|
| `market_regime_detector` | Classify regime: trending_up, trending_down, ranging, volatile, calm |
| `session_context` | Active trading sessions and session overlaps |
| `volatility_analyzer` | ATR-based volatility and spread conditions |
| `correlation_analyzer` | Cross-asset correlation context |

**Output schema** (`MarketContextResult`):
- `regime`: free-form string (e.g. `"trending_up"`, `"ranging"`)
- `session_quality`: `"high"` | `"medium"` | `"low"`
- `execution_risk`: `"high"` | `"medium"` | `"low"`
- `summary`: factual paragraph (required, min length 1)
- `degraded`: bool

**Constraints / Notes**: Reports conditions only — does not recommend trades. If data is insufficient, says so explicitly.

---

## 4. bullish-researcher

**Role**: Constructs the strongest possible bull case from Phase 1 analysis evidence.

**Phase**: 2 (debate phase; runs sequentially with bearish-researcher under trader-agent moderation)

**Inputs** (context injected at run start):
- Instrument pair and timeframe
- Full Phase 1 analysis results (technical, news, market context summaries)

**MCP tools** (max_iters: 4):
| Tool | Purpose |
|------|---------|
| `evidence_query` | Retrieves and aggregates all upstream analysis outputs |
| `thesis_support_extractor` | Structures supporting vs. opposing arguments |

**Output schema** (`DebateThesis`):
- `thesis`: one-sentence bull case
- `arguments`: list of supporting evidence strings
- `confidence`: float 0.0–1.0
- `invalidation_conditions`: list of future events that would break the thesis
- `degraded`: bool

**Constraints / Notes**: Must call `evidence_query()` first, then `thesis_support_extractor()`. Invalidation conditions must describe future events — not conditions already present. If any debate agent (bullish-researcher, bearish-researcher, trader-agent) has `llm_enabled=false`, the debate is skipped entirely and both researchers run in parallel deterministic mode, with `debate_result` set to `DebateResult(winner="no_edge", conviction="weak")`.

---

## 5. bearish-researcher

**Role**: Constructs the strongest possible bear case from Phase 1 analysis evidence.

**Phase**: 2 (debate phase; runs sequentially with bullish-researcher under trader-agent moderation)

**Inputs** (context injected at run start):
- Instrument pair and timeframe
- Full Phase 1 analysis results (technical, news, market context summaries)

**MCP tools** (max_iters: 4):
| Tool | Purpose |
|------|---------|
| `evidence_query` | Retrieves and aggregates all upstream analysis outputs |
| `thesis_support_extractor` | Structures supporting vs. opposing arguments |

**Output schema** (`DebateThesis`):
- `thesis`: one-sentence bear case
- `arguments`: list of supporting evidence strings
- `confidence`: float 0.0–1.0
- `invalidation_conditions`: list of future events that would break the thesis
- `degraded`: bool

**Constraints / Notes**: Identical tool set and schema to bullish-researcher — opposite mandate. Subject to same debate-skip rule (see bullish-researcher notes).

---

## 6. trader-agent

**Role**: Makes the final trade decision (BUY, SELL, or HOLD) by weighing all prior analysis and the debate verdict.

**Phase**: 4 (moderates Phase 2+3 debate, decides in Phase 4)

**Inputs** (context injected at run start):
- Instrument pair, asset class, timeframe
- Market snapshot
- Debate result: winner, conviction, key argument, weakness
- Full Phase 1 analysis summary (technical + news + market context)
- Decision mode: `conservative` | `balanced` | `permissive` (configured globally)

**MCP tools** (max_iters: 5):
| Tool | Purpose |
|------|---------|
| `scenario_validation` | Validates proposed trade scenario against analysis; `decision_mode` and `execution_mode` are pre-injected via preset_kwargs |
| `decision_gating` | Checks whether conditions meet threshold for a BUY/SELL; `mode` and `execution_mode` are pre-injected via preset_kwargs |
| `contradiction_detector` | Detects conflicts between decision and market signals; `macd_diff` and `atr` are pre-injected from the market snapshot so the LLM cannot invent incorrect values |
| `trade_sizing` | Computes entry, SL, and TP levels; `price`, `atr`, `decision_mode`, and `execution_mode` are pre-injected via preset_kwargs |

**Output schema** (`TraderDecisionDraft`):
- `decision`: `"BUY"` | `"SELL"` | `"HOLD"`
- `conviction`: float 0.0–1.0
- `reasoning`: explanation string (required, min length 1)
- `key_level`: float or null (the price level defining the trade)
- `invalidation`: string or null (what would prove the decision wrong)
- `degraded`: bool

**Constraints / Notes**: Tools are advisory — trader decides freely. `decision_gating` and `contradiction_detector` provide perspective, not veto. `trade_sizing` is called when BUY/SELL to compute exact entry/SL/TP. MACD diff, ATR, and price are pre-injected into relevant tools from the market snapshot so the LLM cannot invent incorrect values. Source for preset/force_kwargs injection: `backend/app/services/agentscope/toolkit.py`.

---

## 7. risk-manager

**Role**: Capital preservation gatekeeper — can only make the trade more conservative, never more aggressive.

**Phase**: 4 (sequential after trader-agent)

**Inputs** (context injected at run start):
- Instrument pair, timeframe, execution mode
- Full trader decision: decision, conviction, reasoning, key level, entry, SL, TP, risk %
- Live portfolio state (balance, equity, free margin, open positions, daily PnL) — fetched before Phase 4 begins

**MCP tools** (max_iters: 4):
| Tool | Purpose |
|------|---------|
| `position_size_calculator` | Computes allowed position size from risk parameters |
| `portfolio_risk_evaluation` | Authoritative risk gate — evaluates the full portfolio risk for the proposed trade; `trader_decision` and `injected_portfolio_state` are force-injected via `force_kwargs` (LLM cannot override or omit them) |
| `portfolio_stress_test` | Simulates portfolio stress scenarios against the proposed trade |

**Output schema** (`RiskAssessmentResult`):
- `approved`: bool
- `adjusted_volume`: float ≥ 0.0 (lots; never exceeds trade_sizing volume)
- `reasoning`: explanation string (optional, default empty string, min_length 0)
- `risk_flags`: list of risk concern strings
- `degraded`: bool

**Constraints / Notes**: Hard limits (daily loss, weekly loss, position count, free margin, max currency exposure) are non-negotiable. Soft factors (Friday, correlation, drawdown) are judgment calls. For HOLD decisions, immediately returns `approved=false, adjusted_volume=0` without calling tools. The `portfolio_risk_evaluation` tool result is authoritative — if it conflicts with the LLM's reasoning, the tool result wins. The risk engine is deterministic Python code, not an LLM judgment. The `portfolio_risk_evaluation` function receives `trader_decision` automatically via `force_kwargs` — the LLM cannot override or omit it. Source for force_kwargs injection: `backend/app/services/agentscope/toolkit.py`.

---

## 8. execution-manager

**Role**: Chooses the optimal order type and timing for the approved trade.

**Phase**: 4 (sequential after risk-manager)

**Inputs** (context injected at run start):
- Instrument pair, timeframe, execution mode
- Trader decision and risk-manager result (approved, volume, entry, SL, TP)
- Market context summary (session quality, spread, volatility)

**MCP tools** (max_iters: 4):
| Tool | Purpose |
|------|---------|
| `market_snapshot` | Live market conditions (spread, liquidity, volatility) |

**Output schema** (`ExecutionPlanResult`):
- `order_type`: `"market"` | `"limit"` | `"stop_limit"`
- `timing`: `"immediate"` | `"wait_pullback"` | `"wait_session"`
- `reasoning`: explanation string (required, min length 1)
- `expected_slippage`: `"low"` | `"medium"` | `"high"`
- `degraded`: bool

**Constraints / Notes**: Must never change the decision, side, or volume. LLM is disabled by default (`EXECUTION_MANAGER_LLM_ENABLED=false`); in that case the agent runs in deterministic mode, choosing order type and timing from snapshot conditions without LLM inference.

---

## Deterministic mode

When `llm_enabled=false` for an agent, `_run_deterministic()` activates. In this mode:
- MCP tools are called directly with pre-injected inputs
- No LLM call is made
- A structured output is assembled from tool results

This is a configurable mode, not an error recovery path. On 5xx LLM provider errors (`"500"`, `"502"`, `"503"`, `"Internal Server Error"`), the registry retries up to 3 times and then propagates. Other exceptions (timeout, ValidationError, 429, network errors) propagate immediately without retry — it does NOT silently switch to deterministic mode.

Source: `backend/app/services/agentscope/registry.py`.

**Debate skip rule**: The debate (Phase 2/3) requires all three participating agents (`bullish-researcher`, `bearish-researcher`, `trader-agent`) to have `llm_enabled=true`. If any one of them is disabled, the debate is skipped entirely. Both researchers run in parallel deterministic mode and `debate_result` is set to `DebateResult(winner="no_edge", conviction="weak")`. Source: `backend/app/services/agentscope/registry.py`.

---

## Agent skills bootstrap

At startup, an optional `agent-skills.json` file is loaded from the path specified by `AGENT_SKILLS_BOOTSTRAP_FILE`. This env var has no built-in default — operators must set it explicitly (e.g., `AGENT_SKILLS_BOOTSTRAP_FILE=backend/config/agent-skills.json`). If unset, no bootstrap file is loaded. This file is the primary mechanism for configuring per-agent `llm_enabled` initial values — it sets the starting enabled/disabled state for each agent before the UI or DB can override it. In addition to `llm_enabled`, behavioral guidelines from this file are injected into agent system prompts as soft guidelines — LLMs may deviate from them.

Mode controlled by `AGENT_SKILLS_BOOTSTRAP_MODE` (`merge` or `replace`) and `AGENT_SKILLS_BOOTSTRAP_APPLY_ONCE` (default: `true`).

Per-agent skills can also be stored in the DB (configured via UI) and take priority over the bootstrap file. The fallback is a `SKILL.md` file under `config/skills/<agent-name>/`.

---

## Further reading

- [Decision Pipeline](decision-pipeline.md) — how agent outputs combine into a trade decision
- [Runtime Flow](runtime-flow.md) — phase timing and conditions
- [Risk & Governance](risk-and-governance.md) — risk-manager detail
- [Execution](execution.md) — execution-manager detail
