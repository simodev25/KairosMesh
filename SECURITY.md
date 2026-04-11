# Security

## Reporting vulnerabilities

If you discover a security vulnerability, please do not open a public GitHub issue.

Report it privately via GitHub's [Security Advisories](../../security/advisories/new) feature or by emailing the maintainers directly.

Include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Any suggested mitigation

We will acknowledge receipt within 48 hours and aim to release a fix within 14 days for critical issues.

## Security model

Kairos Mesh is designed for research and evaluation use. It has not been audited or hardened for production deployment with real capital.

### Trust boundaries

| Boundary | Enforcement | Notes |
|----------|-------------|-------|
| LLM cannot submit orders directly | Orders go through `ExecutionService` after deterministic preflight | Enforced in code |
| Risk tool overrides LLM | `portfolio_risk_evaluation` result is authoritative | Enforced in code |
| Live trading off by default | `ALLOW_LIVE_TRADING=false` | Environment variable |
| Live trading requires role | `TRADER_OPERATOR` role checked at API | Enforced in code |

### Known security limitations

| Issue | Severity | Notes |
|-------|----------|-------|
| JWT in localStorage | Medium | Vulnerable to XSS; standard SPA trade-off |
| No rate limiting on API endpoints | Medium | Login, LLM, backtest endpoints unprotected |
| No API key rotation | Medium | LLM and broker keys stored in DB |
| Connector config changes not audited | Low | UI changes to LLM/news config not logged |
| `SECRET_KEY` default in `.env.example` | **High** | Must be changed before any non-local deployment |
| Default PostgreSQL credentials | **High** | `trading`/`trading` — must be changed in production |

## Deployment security notes

Before deploying to any environment accessible beyond localhost:

1. **Change `SECRET_KEY`** — the default value in `.env.example` is public
2. **Change PostgreSQL credentials** — default `trading`/`trading` is not acceptable
3. **Restrict CORS** — update `CORS_ORIGINS` to your specific frontend origin
4. **Keep `ALLOW_LIVE_TRADING=false`** unless you have completed the checklist in [Paper vs Live](docs/paper-vs-live.md)
5. **Do not expose MetaAPI tokens** in environment files committed to version control

## Supported versions

This project does not yet have a formal versioning or LTS policy. Security fixes are applied to the main branch.
