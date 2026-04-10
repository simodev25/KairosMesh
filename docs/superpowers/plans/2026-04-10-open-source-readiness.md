# Open Source Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prepare the MultiAgentTrading repo for public open source release under the MIT licence.

**Architecture:** Five sequential changes — gitignore update, git untracking, LICENSE creation, README update, CONTRIBUTING creation — then one clean commit.

**Tech Stack:** git, Markdown

---

### Task 1: Update `.gitignore`

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Add missing entries to `.gitignore`**

Open `.gitignore` (root) and append the following block at the end:

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

- [ ] **Step 2: Verify the gitignore is valid**

Run:
```bash
git check-ignore -v .claude/projects/-Users-mbensass-projetPreso-MultiAgentTrading/memory/MEMORY.md
```
Expected output: `.gitignore:<line>:.claude/	.claude/projects/...`

---

### Task 2: Untrack private files from git

**Files:** (removed from tracking only — files stay on disk)

- [ ] **Step 1: Remove `.claude/` from git tracking**

```bash
git rm -r --cached .claude/
```
Expected: multiple lines like `rm '.claude/projects/...'`

- [ ] **Step 2: Remove `skills-lock.json` from git tracking**

```bash
git rm --cached skills-lock.json
```
Expected: `rm 'skills-lock.json'`

- [ ] **Step 3: Remove `MIGRATION_REPORT_EN.md` from git tracking**

```bash
git rm --cached MIGRATION_REPORT_EN.md
```
Expected: `rm 'MIGRATION_REPORT_EN.md'`

- [ ] **Step 4: Remove TypeScript build artifacts from git tracking**

```bash
git rm --cached frontend/tsconfig.app.tsbuildinfo frontend/tsconfig.node.tsbuildinfo
```
Expected: two `rm` lines

- [ ] **Step 5: Remove test results from git tracking**

```bash
git rm -r --cached frontend/test-results/
```
Expected: `rm 'frontend/test-results/.last-run.json'`

- [ ] **Step 6: Verify nothing sensitive remains tracked**

```bash
git ls-files | grep -E "\.claude|skills-lock|tsbuildinfo|test-results|MIGRATION"
```
Expected: **no output**

---

### Task 3: Create `LICENSE`

**Files:**
- Create: `LICENSE`

- [ ] **Step 1: Create the MIT licence file**

Create file `LICENSE` at the repo root with this exact content:

```
MIT License

Copyright (c) 2026 simodev25

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

- [ ] **Step 2: Verify file exists**

```bash
head -3 LICENSE
```
Expected:
```
MIT License

Copyright (c) 2026 simodev25
```

---

### Task 4: Update `README.md`

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add MIT licence badge at the top of the README**

The README currently starts with `# Multi-Agent Trading Platform`. Replace that first line with:

```markdown
# Multi-Agent Trading Platform

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
```

- [ ] **Step 2: Replace the License section**

Find this block at the bottom of `README.md`:
```markdown
## License

Private — All rights reserved.
```

Replace it with:
```markdown
## ⚠️ Disclaimer

This software is for educational and research purposes only. It does not constitute financial advice. Past performance is not indicative of future results. Use at your own risk. Never trade with money you cannot afford to lose. The authors accept no responsibility for any financial losses incurred through the use of this software.

## License

This project is licensed under the [MIT License](LICENSE).
```

- [ ] **Step 3: Verify the changes**

```bash
grep -n "MIT\|Disclaimer\|Private" README.md
```
Expected: lines showing the badge, Disclaimer section, and MIT mention. No line with "Private".

---

### Task 5: Create `CONTRIBUTING.md`

**Files:**
- Create: `CONTRIBUTING.md`

- [ ] **Step 1: Create `CONTRIBUTING.md` at the repo root**

```markdown
# Contributing to Multi-Agent Trading Platform

Thank you for your interest in contributing!

## Prerequisites

- Python 3.12+
- Node.js 22+
- Docker & Docker Compose

## Local Setup

### 1. Clone and configure

```bash
git clone https://github.com/simodev25/MultiAgentTrading.git
cd MultiAgentTrading

# Configure backend environment
cp backend/.env.example backend/.env
# Edit backend/.env — add your LLM provider key (Ollama, OpenAI, or Mistral)
```

### 2. Start infrastructure

```bash
docker compose up postgres redis rabbitmq -d
```

### 3. Run the backend

```bash
make backend-install
make backend-run
# API available at http://localhost:8000
# Docs at http://localhost:8000/docs
```

### 4. Run the frontend

```bash
make frontend-install
make frontend-run
# UI available at http://localhost:5173
```

### 5. Run the full stack (Docker)

```bash
docker compose up --build
```

## Running Tests

```bash
make backend-test
```

## Configuration Reference

See [`backend/.env.example`](backend/.env.example) for the full list of environment variables.

Key variables to get started:

| Variable | Description |
|----------|-------------|
| `LLM_PROVIDER` | `ollama`, `openai`, or `mistral` |
| `OLLAMA_MODEL` | Model name (e.g. `deepseek-r1:7b`) |
| `ALLOW_LIVE_TRADING` | Keep `false` during development |

## Pull Request Workflow

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make your changes with clear, focused commits
4. Ensure tests pass: `make backend-test`
5. Open a PR against the `main` branch
6. Describe what your PR does and why

## Code Style

- **Python:** follow existing patterns, no new dependencies without discussion
- **TypeScript:** follow existing component patterns in `frontend/src/`

## Questions?

Open a GitHub Issue for bugs, feature requests, or questions.
```

- [ ] **Step 2: Verify file exists**

```bash
head -5 CONTRIBUTING.md
```
Expected:
```
# Contributing to Multi-Agent Trading Platform

Thank you for your interest in contributing!
```

---

### Task 6: Final commit

- [ ] **Step 1: Stage all changes**

```bash
git add .gitignore LICENSE README.md CONTRIBUTING.md docs/superpowers/specs/2026-04-10-open-source-readiness-design.md docs/superpowers/plans/2026-04-10-open-source-readiness.md
```

- [ ] **Step 2: Verify staging is correct**

```bash
git status
```
Expected:
- `modified: .gitignore`
- `modified: README.md`
- `new file: LICENSE`
- `new file: CONTRIBUTING.md`
- `deleted: MIGRATION_REPORT_EN.md` (removed from tracking)
- `deleted: skills-lock.json` (removed from tracking)
- `deleted: .claude/...` (multiple files removed from tracking)
- `deleted: frontend/tsconfig.app.tsbuildinfo`
- `deleted: frontend/tsconfig.node.tsbuildinfo`
- `deleted: frontend/test-results/.last-run.json`

No `.env` files should appear.

- [ ] **Step 3: Commit**

```bash
git commit -m "chore: prepare project for open source release

- Add MIT licence (LICENSE)
- Add CONTRIBUTING.md with setup and PR workflow
- Update README: MIT badge, trading disclaimer, licence section
- Remove internal files from git tracking: .claude/, skills-lock.json,
  MIGRATION_REPORT_EN.md, *.tsbuildinfo, frontend/test-results/
- Update .gitignore to cover all removed entries

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

- [ ] **Step 4: Verify the commit**

```bash
git show --stat HEAD
```
Expected: shows all the files above changed in one clean commit.
