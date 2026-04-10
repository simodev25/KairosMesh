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
