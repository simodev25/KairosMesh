# Guide de Développement — Kairos Mesh

## Prérequis

| Outil | Version Minimale |
|---|---|
| Docker + Docker Compose | Dernière version stable |
| Python | 3.12+ |
| Node.js | 22+ |
| Git | Dernière version stable |

---

## Installation

### Démarrage avec Docker Compose (recommandé)

```bash
# Cloner le dépôt
git clone <repo-url>
cd MultiAgentTrading

# Démarrer toute la stack
docker compose up -d
```

### Installation locale

```bash
# Backend
cd backend
pip install -r requirements.txt

# Frontend
cd frontend
npm install
```

---

## Commandes Make

| Commande | Description |
|---|---|
| `make backend-install` | Installer les dépendances backend |
| `make backend-run` | Lancer le backend (FastAPI + Uvicorn) |
| `make backend-test` | Lancer les tests pytest |
| `make frontend-install` | Installer les dépendances frontend |
| `make frontend-run` | Lancer le frontend (Next.js dev server) |
| `make docker-up` | Démarrer la stack Docker complète |
| `make docker-down` | Arrêter la stack Docker |

---

## Variables d'Environnement Clés

| Variable | Description | Exemple |
|---|---|---|
| `DATABASE_URL` | URL de connexion PostgreSQL | `postgresql://user:pass@localhost:5432/kairos` |
| `REDIS_URL` | URL Redis | `redis://localhost:6379/0` |
| `CELERY_BROKER_URL` | URL du broker RabbitMQ | `amqp://guest:guest@localhost:5672//` |
| `LLM_PROVIDER` | Fournisseur LLM actif | `ollama`, `openai`, `mistral` |
| `OLLAMA_BASE_URL` | URL du serveur Ollama | `http://localhost:11434` |
| `OPENAI_API_KEY` | Clé API OpenAI | `sk-...` |
| `METAAPI_TOKEN` | Token d'accès MetaAPI | — |
| `CORS_ORIGINS` | Origines CORS autorisées | `http://localhost:3000` |
| `JWT_SECRET_KEY` | Clé secrète pour la signature JWT | — |

> **Attention** : ne jamais commiter les fichiers `.env` contenant des secrets. Utiliser `.env.example` comme modèle.

---

## Structure des Tests

### Backend

- **Framework** : `pytest` + `pytest-asyncio`
- **Emplacement** : `backend/tests/`
- **Lancement** :

```bash
cd backend
pytest -q
```

### Frontend

- **Framework** : Playwright (tests end-to-end)
- **Emplacement** : `frontend/tests/`
- **Lancement** :

```bash
cd frontend
npx playwright test
```

---

## Conventions

## Benchmark subsystem (GH-24 Lot A)

Le backend expose un sous-système de benchmark sous `/api/v1/benchmark` :

- `POST /api/v1/benchmark/fixtures` (ADMIN)
- `GET /api/v1/benchmark/fixtures` (ANALYST+)
- `GET /api/v1/benchmark/fixtures/{id}` (ANALYST+)
- `PATCH /api/v1/benchmark/fixtures/{id}` (ADMIN)
- `DELETE /api/v1/benchmark/fixtures/{id}` (ADMIN, soft delete)
- `POST /api/v1/benchmark/runs` (ADMIN)
- `GET /api/v1/benchmark/runs` (ANALYST+)
- `GET /api/v1/benchmark/runs/{id}` (ANALYST+)
- `DELETE /api/v1/benchmark/runs/{id}` (ADMIN, annulation run PENDING)

Notes opérationnelles:

- Exécution asynchrone via Celery queue dédiée `benchmark` (`CELERY_BENCHMARK_QUEUE`).
- Le moteur benchmark réutilise le cœur partagé AgentScope (`ALL_AGENT_FACTORIES`, `build_toolkit`, `build_model`, `build_formatter`) sans copie.
- Le scénario `full-pipeline` benchmark s’arrête à `risk-manager` (pas d’appel `execution-manager`) pour éviter tout effet d’exécution.
- La corrélation de coûts LLM utilise `analysis_run_id` propagé jusqu’à `llm_call_logs`.

### Stratégie de Branches

| Préfixe | Usage | Exemple |
|---|---|---|
| `feature/*` | Nouvelles fonctionnalités | `feature/risk-engine-v2` |
| `fix/GH-{n}/{slug}` | Corrections de bugs | `fix/GH-42/websocket-reconnect` |

### Commits Conventionnels

Format : `type(portée): description`

| Type | Usage |
|---|---|
| `fix()` | Correction de bug |
| `feat()` | Nouvelle fonctionnalité |
| `test()` | Ajout ou modification de tests |
| `docs()` | Documentation |
| `chore()` | Maintenance, dépendances, configuration |
| `refactor()` | Refactoring sans changement fonctionnel |

### Nommage

Se référer au fichier `governance/conventions/naming.md` pour les conventions de nommage détaillées (variables, fichiers, classes, routes API).

### Revue de Code

Les politiques de revue sont définies dans `governance/policies/review-policy.yaml`. Toute pull request nécessite au minimum une approbation avant fusion.

---

## CI/CD

### GitHub Actions (`ci.yml`)

Deux jobs parallèles s'exécutent à chaque push et pull request :

#### Job 1 — Backend

```yaml
- Python 3.12
- pip install -r requirements.txt
- pytest -q
```

#### Job 2 — Frontend

```yaml
- Node.js 22
- npm install
- npm run build
```

---

## Déploiement

### Développement

```bash
docker compose up -d
```

Démarre **8 services** : backend, frontend, PostgreSQL, Redis, RabbitMQ, Celery worker, Ollama, Prometheus.

Tous les ports d'infrastructure sont exposés pour le débogage local.

### Production

```bash
docker compose -f docker-compose.prod.yml up -d
```

Configuration durcie :
- **Aucun port d'infrastructure exposé** (PostgreSQL, Redis, RabbitMQ accessibles uniquement via le réseau Docker interne)
- **Multi-workers** Uvicorn pour la montée en charge
- **Credentials paramétrés** via variables d'environnement (pas de valeurs par défaut)

### Kubernetes

Des Helm charts squelettes sont disponibles dans `infra/helm/` :
- Déploiements backend et frontend uniquement
- L'infrastructure (base de données, broker, cache) est supposée gérée séparément (services managés ou opérateurs K8s)

```bash
helm install kairos-mesh infra/helm/kairos-mesh \
  --namespace trading \
  --values infra/helm/kairos-mesh/values-prod.yaml
```
