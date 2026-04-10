# Open Source Readiness — Design Spec
**Date:** 2026-04-10  
**Status:** Approved

## Goal

Prepare the MultiAgentTrading project for public open source release on GitHub under the MIT licence.

## Scope

**In scope:**
- Remove private/internal files from git tracking
- Update `.gitignore`
- Add `LICENSE` (MIT)
- Update `README.md` (licence section, badge, trading disclaimer)
- Add `CONTRIBUTING.md`

**Out of scope:** CODE_OF_CONDUCT, issue templates, PR templates, CHANGELOG (can be added later as community grows).

---

## Section 1 — Git Cleanup

Files to remove from git tracking (`git rm --cached`) and add to `.gitignore`:

| File / Dir | Reason |
|---|---|
| `.claude/` | Personal Claude Code session notes — not relevant to contributors |
| `skills-lock.json` | Claude Code internal file |
| `MIGRATION_REPORT_EN.md` | Internal migration report |
| `frontend/tsconfig.app.tsbuildinfo` | TypeScript build artifact |
| `frontend/tsconfig.node.tsbuildinfo` | TypeScript build artifact |
| `frontend/test-results/` | Local test run artifacts |

**No action needed:** `.env` files with real credentials (`backend/.env`, `.env.prod`) are already covered by existing `.gitignore` entries (`.env` and `.env.*`).

---

## Section 2 — Files to Create / Modify

### `LICENSE`
Standard MIT licence, year 2026, author `simodev25`.

### `README.md` changes
1. Replace the `## License` section footer: remove `Private — All rights reserved`, add MIT badge link + reference to LICENSE file.
2. Add licence badge at the top of the README.
3. Add `## ⚠️ Disclaimer` section before `## License`:
   > This software is for educational and research purposes only. It does not constitute financial advice. Use at your own risk. Never trade with money you cannot afford to lose.

### `CONTRIBUTING.md` (new file, root level)
Sections:
- Prerequisites (Python 3.12+, Node.js 22+, Docker & Docker Compose)
- Local setup (based on existing Makefile targets)
- Running tests
- PR workflow (fork → feature branch → PR against `main`)
- Configuration reference (link to `backend/.env.example`)

---

## Section 3 — `.gitignore` additions

```gitignore
# Claude Code internal
.claude/
skills-lock.json

# TypeScript build artifacts
*.tsbuildinfo

# Test results
frontend/test-results/

# Internal docs
MIGRATION_REPORT_EN.md
```

Existing entries are correct and remain unchanged.

---

## Implementation Order

1. Update `.gitignore`
2. `git rm --cached` for all files listed in Section 1
3. Create `LICENSE`
4. Update `README.md`
5. Create `CONTRIBUTING.md`
6. Commit everything in one clean commit
