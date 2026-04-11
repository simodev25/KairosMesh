# Limitations

This document catalogues known limitations, incomplete features, and operational constraints. It is maintained to prevent overestimation of the system's current capabilities.

**Reading this before deploying for any purpose involving real capital is mandatory.**

---

## Agent pipeline

| Limitation | Impact | Status |
|-----------|--------|--------|
| No cross-run memory | Each run starts with fresh context. Past decisions, outcomes, and patterns do not influence future runs. | By design (stateless runs) |
| Debate is conditional | Debate phase only runs when all 3 debate agents have LLM enabled in DB config. With default Ollama or partial config, debate is frequently skipped. | Known behavior |
| Agent skills are soft guidelines | LLMs may deviate from `agent-skills.json` behavioral rules at any time. | Inherent to LLM-based agents |
| Structured output degradation | Schema validation uses clamping/normalization that can mask low-quality LLM outputs. NaN/Inf fields are rejected, but near-threshold values may pass. | Graceful with guards |
| Single LLM provider per run | All agents in a run use the same provider (Ollama/OpenAI/Mistral). Per-agent model selection is not supported. | Not implemented |
| Deterministic fallback is not an error recovery | `_run_deterministic()` activates only when `llm_enabled=false`. LLM failures retry and then propagate as errors — they do not silently fall back. | By design |
| `ORCHESTRATOR_AUTONOMY_ENABLED` flag exists but autonomy path is untested | The multi-cycle orchestrator flag is `true` by default but the code path is not exercised in the main analysis flow. | Experimental |

---

## Risk and execution

| Limitation | Impact | Status |
|-----------|--------|--------|
| No portfolio-level risk aggregation | Multiple concurrent runs can each pass per-run risk checks while combined exposure exceeds portfolio tolerance. | Not implemented |
| No real-time broker margin check | Volume sizing uses locally-fetched portfolio state, not live broker margin API. | Not implemented |
| Contract specs are hardcoded defaults | Pip sizes, contract sizes, volume limits are static in `risk/rules.py`. Not fetched from broker. Exotic or non-standard instruments may use incorrect specs. | Known gap |
| No slippage modeling | All modes assume exact fill at the requested price. | Not implemented |
| No partial fill handling | Orders are assumed to fill completely or fail. | Not implemented |
| No order modification | Positions cannot be modified after placement (no trailing stop, no SL/TP adjustment). | Not implemented |
| No spread modeling in backtest | Backtest P&L ignores bid-ask spread. | Not implemented |
| No commission modeling | Backtest, paper, and live P&L calculations ignore broker commissions. | Not implemented |
| No emergency stop mechanism | There is no automated kill switch to close all positions or halt future runs. | Not implemented |

---

## Memory and learning

| Limitation | Impact | Status |
|-----------|--------|--------|
| No automated feedback loop | Trade outcomes (win/loss, P&L) are stored in DB but do not flow back to agent behavior, prompts, or decision thresholds. | By design (current version) |
| No RAG or vector retrieval | No retrieval from past decisions or analyses during runs. | Not implemented |

---

## Strategy engine

| Limitation | Impact | Status |
|-----------|--------|--------|
| 4 templates only | Strategy generation is limited to EMA crossover, RSI mean reversion, Bollinger breakout, MACD divergence. | By design |
| No walk-forward testing | Backtests use in-sample data only. No out-of-sample validation. | Not implemented |
| No Monte Carlo simulation | No confidence intervals on backtest results. | Not implemented |
| Promotion is manual | VALIDATED → PAPER → LIVE strategy promotion requires manual action. | By design |

---

## Market data

| Limitation | Impact | Status |
|-----------|--------|--------|
| MetaAPI primary, YFinance fallback | Different providers may return different candle granularity or timing. Results may differ depending on which provider serves the request. | Known inconsistency |
| News API dependency | News tools depend on external API availability and rate limits. | External dependency |
| No real-time tick data | Analysis uses candle snapshots, not tick-by-tick data. | By design |
| No order book data | No depth-of-market or level 2 data integration. | Not implemented |
| Instrument classification is heuristic | `InstrumentClassifier` uses pattern matching. May misclassify exotic symbols, leading to wrong contract specs. | Known gap |

---

## Observability

| Limitation | Impact | Status |
|-----------|--------|--------|
| No alerting rules | Prometheus metrics exist but no default alert rules are configured. | Not implemented |
| Debug traces written to local disk | Not available across replicas or after container restart without volume mount. | Known gap |
| No structured JSON log format | Logs are plain text stdout. | Known gap |
| No LLM prompt logging to DB | Full prompts only in debug JSON trace files (privacy consideration). | Intentional |
| Cross-Celery trace correlation incomplete | Correlation IDs propagated but span-level tracing across workers not fully connected. | Partial |

---

## Security

| Limitation | Impact | Status |
|-----------|--------|--------|
| JWT stored in localStorage | Standard SPA pattern; vulnerable to XSS attacks. | Known trade-off |
| No API key rotation mechanism | MetaAPI and LLM API keys stored in DB, no automated rotation. | Not implemented |
| No rate limiting on endpoints | Login, LLM, and backtest endpoints are unprotected against brute force or DoS. | Not implemented |
| Connector config changes not audited | UI changes to LLM/news provider settings are not tracked in the audit log. | Not implemented |

---

## Frontend

| Limitation | Impact | Status |
|-----------|--------|--------|
| Polling-based updates for most data | Most data fetches use polling (3–5s), not pure push. WebSocket is used for run progress only. | Known trade-off |
| No mobile layout | Dashboard is designed for desktop monitors. | Not implemented |
| `ENABLE_METAAPI_REAL_TRADES_DASHBOARD` is `false` by default | Real trades dashboard feature is incomplete. | Experimental |

---

## What this system is not

- **Not a high-frequency trading system** — analysis runs take seconds to minutes due to LLM latency
- **Not a portfolio management system** — single-position, single-instrument per run
- **Not a regulated trading platform** — no compliance tooling, no regulatory audit trail
- **Not a backtesting framework** — backtesting is a validation utility, not a primary feature
- **Not autonomous** — requires human oversight for strategy promotion and live trading enablement
- **Not production-hardened** — the codebase has not undergone security or load-testing at scale

---

## Legacy items

| Item | Location | Notes |
|------|----------|-------|
| French signal parsing tokens | `agents.py` (via agentscope schemas) | Parses legacy LLM outputs that may contain French text |
| `_normalize_legacy_market_wording` | `registry.py` | Normalizes French text from user-stored prompt templates |
