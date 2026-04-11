# Paper vs Live

Kairos Mesh supports three execution modes: **simulation** (default), **paper**, and **live**. This document explains precisely what differs between them, what each mode does and does not model, and what an operator must verify before enabling live trading.

Source files cited throughout:
- `backend/app/services/execution/executor.py`
- `backend/app/services/execution/preflight.py`
- `backend/app/services/risk/limits.py`
- `backend/.env.example`
- `backend/app/core/config.py`

---

## 1. Mode Comparison

| Aspect | Simulation | Paper | Live |
|---|---|---|---|
| Broker connection | None | Yes — MetaAPI demo account | Yes — MetaAPI real account |
| Real capital at risk | No | No | Yes |
| Order fills | Assumed exact (no broker) | Demo account via MetaAPI | Real market via MetaAPI |
| Default | Yes | No | No |
| Enabling config | None required | `ENABLE_PAPER_EXECUTION=true` + MetaAPI credentials | `ALLOW_LIVE_TRADING=true` + `trader-operator` role |
| Max risk per trade | 5% | 3% | 2% |
| Max daily loss | 10% | 6% | 3% |
| Max open risk | 15% | 10% | 6% |
| Max simultaneous positions | 10 | 5 | 3 |
| Max positions per symbol | 3 | 2 | 1 |
| Min free margin | 20% | 30% | 50% |
| Max gross exposure | 100% | 60% | 40% |
| Max weekly loss | 15% | 10% | 5% |
| Max VaR 95% | 15% | 10% | 5% |
| Spread threshold | 0.05% | 0.02% | 0.01% |
| Stress test scenarios | risk_off | risk_off, flash_crash | risk_off, flash_crash, usd_crash |

Risk limits are defined in `backend/app/services/risk/limits.py` (`RISK_LIMITS` dict). Spread thresholds are defined in `backend/app/services/execution/preflight.py` (`MAX_SPREAD_PCT` dict).

Config defaults are in `backend/app/core/config.py`:
- `allow_live_trading: bool = Field(default=False, ...)`
- `enable_paper_execution: bool = Field(default=True, ...)`

---

## 2. What Simulation Does Not Model

Simulation mode records that an order would have been placed and marks it with status `simulated`, but it does not contact any broker. This has several implications:

- **No slippage.** The fill is assumed to occur at exactly the requested entry price. In real markets, especially at high volume or during news events, actual fill prices deviate.
- **No partial fills.** The entire requested volume is assumed filled in one step. In practice, liquidity constraints can result in partial fills at different prices.
- **No spread cost in P&L.** Spread is checked against the `0.05%` threshold during preflight (Check 6 in `preflight.py`), but spread is not deducted from the simulated P&L.
- **Market hours apply, but are simplified.** The `_is_market_open` check in `preflight.py` uses static UTC hour windows as a proxy for exchange sessions. These windows do not account for daylight saving adjustments, exchange-specific holidays, or early close days.
- **No margin call or liquidation modelling.** Position sizing by the risk engine assumes available margin. Simulation does not model what happens if a position moves adversely past the free margin threshold.

Simulation is useful for testing agent logic, pipeline wiring, and risk rule behaviour. It is not a substitute for paper trading when you need to verify broker connectivity or execution realism.

---

## 3. What Paper Trading Gives You — and Its Limits

### What it provides

- **Real broker connectivity.** Orders are routed to MetaAPI and submitted to a demo (paper) account on the connected MT4/MT5 broker. If MetaAPI credentials are invalid, connectivity is broken, or the account is misconfigured, paper mode will fail — revealing those issues before they matter in live.
- **A degraded fallback.** If MetaAPI is unreachable during a paper run, the executor falls back to a simulated fill and sets `paper_fallback: true` on the response (see `executor.py`, lines 302–317). The run continues rather than halting entirely.
- **Stricter risk limits than simulation.** Paper mode enforces tighter position, exposure, and drawdown limits than simulation, providing a more conservative rehearsal environment.
- **No real capital at risk.** A demo account has no financial consequences for losses.

### Its limits

- **Demo fills are not live fills.** Demo accounts at most brokers fill orders immediately at the last-known price without modelling real market depth, queuing, or latency. Win rates observed in paper mode may not hold in live.
- **Requires valid MetaAPI credentials.** `METAAPI_TOKEN` and `METAAPI_ACCOUNT_ID` must be set and must correspond to a working demo account. Without them, every paper order falls back to simulated.
- **Same market-hours logic as simulation.** Preflight applies the same simplified UTC-window check regardless of mode.

---

## 4. Pre-Live Checklist

Complete every item on this list before setting `ALLOW_LIVE_TRADING=true`. There is no automated enforcement of this checklist — it is the operator's responsibility.

- [ ] **`ALLOW_LIVE_TRADING=true` set explicitly.** The default is `false` (see `backend/app/core/config.py`). If this flag is absent or set to `false`, live orders are blocked with the error `"Live trading is disabled by default."` (see `executor.py`, lines 267–274). Set it only in your `.env` file after completing this checklist.

- [ ] **User account has the `trader-operator` role.** The API enforces role-based access to live execution endpoints. To grant the role, run the following against your PostgreSQL database:

  ```sql
  UPDATE users
  SET role = 'trader-operator'
  WHERE email = 'your-operator@example.com';
  ```

  Verify the change before enabling live trading.

- [ ] **Valid MetaAPI live account credentials.** Set `METAAPI_TOKEN` and `METAAPI_ACCOUNT_ID` to values for a real (not demo) MetaAPI account. Confirm connectivity by running a paper trade successfully before switching to live.

- [ ] **`SECRET_KEY` changed from the default.** The `.env.example` ships with `SECRET_KEY=change-me`. In `config.py`, if `SECRET_KEY` is empty or equals `change-me`, the application generates an ephemeral random key on startup and logs a critical warning in production environments. An ephemeral key invalidates all JWT tokens on every restart. Set a stable, random value of at least 48 characters before deploying.

- [ ] **Risk limits reviewed and understood.** The live limits in `backend/app/services/risk/limits.py` are more restrictive than paper or simulation (2% max risk per trade, 3% max daily loss, 3 max positions). Review them against your intended strategy. See [risk-and-governance.md](risk-and-governance.md) for the full risk engine documentation.

- [ ] **Paper trading tested and working on the same instrument.** Run at least one full paper cycle on the instrument you intend to trade live. Confirm that orders reach MetaAPI, fills are returned, and no `paper_fallback` flag appears in responses.

- [ ] **`docs/limitations.md` read and understood.** That document covers known modelling gaps, unimplemented safeguards, and experimental flags. Read it before enabling live trading.

- [ ] **`SECURITY.md` reviewed.** Covers authentication, credential handling, and recommended deployment hardening. If absent from your copy, check the repository for the latest version or raise the issue with the project maintainer before proceeding.

---

## 5. How to Switch Modes

The execution mode is set per run, not globally, via the `mode` field in the run creation request:

```http
POST /api/v1/runs
Content-Type: application/json

{
  "pair": "EURUSD",
  "mode": "paper",
  ...
}
```

Valid values for `mode` are `simulation`, `paper`, and `live`.

- If `mode` is omitted, the application defaults to `simulation`.
- If `mode` is `paper` and `ENABLE_PAPER_EXECUTION=false`, the order is blocked before reaching MetaAPI.
- If `mode` is `live` and `ALLOW_LIVE_TRADING=false`, the order is blocked before reaching MetaAPI.

These guards are in `backend/app/services/execution/executor.py` (lines 258–274).

---

## 6. Safety Reminder

Kairos Mesh is research software. It has not been independently audited, stress-tested under real market conditions, or hardened for production deployment with live capital.

Enabling live trading is the operator's sole responsibility. The authors and contributors accept no liability for financial losses resulting from use of this software in live trading, misconfiguration, software defects, broker connectivity failures, or any other cause.

Before enabling live trading:
- Read `SECURITY.md` (authentication, secrets management).
- Read `docs/limitations.md` (known modelling gaps and missing features).
- Understand that demo-account performance does not guarantee live-account performance.
- Keep position sizes small while validating live execution for the first time.
- Monitor the system actively; do not leave it running unattended without alerting and circuit-breaker configuration in place.
