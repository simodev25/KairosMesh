# Installation Production avec Docker

## Objectif

Déployer la plateforme en mode production avec:
- `docker-compose.yml` + `docker-compose.prod.yml`
- un seul script d'installation/deploiement
- configuration workers adaptee a Mac M4 Pro

## Fichiers utilises

- `docker-compose.yml`
- `docker-compose.prod.yml`
- `.env.prod` (a creer depuis `.env.prod.example`)
- `scripts/install-prod-docker.sh`

## Pre-requis

- Docker + Docker Compose v2
- 16 GB RAM recommande
- Sur Mac M4 Pro: profil workers preconfigure

## 1) Creer le fichier d'environnement production

```bash
cp .env.prod.example .env.prod
```

Puis modifier au minimum:
- `SECRET_KEY`
- `POSTGRES_PASSWORD`
- `DATABASE_URL`
- `OLLAMA_API_KEY` (si LLM actif)
- `METAAPI_TOKEN` / `METAAPI_ACCOUNT_ID` (si trading MetaApi)
- `GF_SECURITY_ADMIN_PASSWORD` (si monitoring)

Paramètres skills recommandés:
- `AGENT_SKILLS_BOOTSTRAP_FILE=/app/config/agent-skills.json`
- `AGENT_SKILLS_BOOTSTRAP_MODE=merge`
- `AGENT_SKILLS_BOOTSTRAP_APPLY_ONCE=true`

Validation conseillee avant installation:
- `POSTGRES_PASSWORD` et `DATABASE_URL` doivent contenir le meme mot de passe.
- aucun placeholder ne doit rester (`change-me`, `replace_me`, etc.).

```bash
grep -E '^(POSTGRES_USER|POSTGRES_PASSWORD|POSTGRES_DB|DATABASE_URL|CORS_ORIGINS|ENABLE_PGVECTOR)=' .env.prod
```

Contrôle optionnel des variables skills:

```bash
grep -E '^(AGENT_SKILLS_BOOTSTRAP_FILE|AGENT_SKILLS_BOOTSTRAP_MODE|AGENT_SKILLS_BOOTSTRAP_APPLY_ONCE)=' .env.prod
```

## 2) Lancer l'installation / deploiement

Sans monitoring:

```bash
./scripts/install-prod-docker.sh
```

Avec monitoring (Prometheus + Grafana):

```bash
./scripts/install-prod-docker.sh --with-monitoring
```

Options utiles:

```bash
./scripts/install-prod-docker.sh --help
```

## 3) Configuration workers (Mac M4 Pro)

Valeurs recommandees:

- M4 Pro 12 coeurs logiques:
  - `BACKEND_UVICORN_WORKERS=4`
  - `CELERY_WORKER_CONCURRENCY=4`
  - `ORCHESTRATOR_PARALLEL_WORKERS=6`
- M4 Pro 14 coeurs logiques:
  - `BACKEND_UVICORN_WORKERS=5`
  - `CELERY_WORKER_CONCURRENCY=5`
  - `ORCHESTRATOR_PARALLEL_WORKERS=7`
- Parametres Celery associes:
  - `CELERY_WORKER_PREFETCH_MULTIPLIER=1`
  - `CELERY_WORKER_MAX_TASKS_PER_CHILD=200`

Le script applique automatiquement ce profil si:
- `.env.prod` vient d'etre cree, et
- la machine est un Mac Apple Silicon.

Forcer le profil M4 Pro:

```bash
./scripts/install-prod-docker.sh --tune-m4-pro
```

## 4) Verifications post-deploiement

- Frontend: `http://localhost:4173`
- API docs: `http://localhost:8000/docs`
- Health API: `http://localhost:8000/api/v1/health`
- Grafana (si active): `http://localhost:3000`

Etat des conteneurs:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.prod ps
```

Checks rapides recommandes:

```bash
curl -sS http://localhost:8000/api/v1/health
curl -sS -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@local.dev","password":"admin1234"}'
docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.prod logs --tail 80 backend worker
```

Vérifier l'injection des skills:

```bash
TOKEN="$(curl -sS -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@local.dev","password":"admin1234"}' \
  | python3 -c 'import json,sys; print(json.load(sys.stdin).get("access_token",""))')"

curl -sS http://localhost:8000/api/v1/connectors \
  -H "Authorization: Bearer ${TOKEN}"
```

Puis vérifier:
- `ollama.settings.agent_skills`
- `ollama.settings.agent_skills_bootstrap_meta`

## 5) Commandes d'exploitation

Voir les logs:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.prod logs -f backend worker beat
```

Arreter:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.prod down
```

Redemarrer avec rebuild:

```bash
./scripts/install-prod-docker.sh
```

## Notes

- En mode prod, les ports des services internes (Postgres/Redis/RabbitMQ/Qdrant) ne sont pas exposes sur l'hote.
- Le service Postgres prod utilise `pgvector/pgvector:pg16`, donc `ENABLE_PGVECTOR=true` est supporte.
- Le frontend est servi via `vite preview` sur le port `4173`.
- Pour un environnement internet public, ajouter un reverse proxy TLS (Nginx/Traefik/Caddy).
- Le fichier skills par défaut est embarqué dans l'image backend (`/app/config/agent-skills.json`).

## Troubleshooting

### `install-prod-docker.sh` bloque sur `Waiting for backend health endpoint...`

Cause la plus frequente:
- migration non appliquee ou erreur runtime backend au demarrage.

Diagnostic:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.prod logs --tail 120 backend
docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.prod run --rm backend alembic current
```

Correctif:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.prod run --rm backend alembic upgrade head
docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.prod restart backend worker beat
```

### PostgreSQL `password authentication failed for user "forex"`

Cause frequente:
- volume Postgres existant avec ancien mot de passe, puis changement de `.env.prod`.

Correctif non destructif:
1. Aligner `DATABASE_URL` et `POSTGRES_PASSWORD` dans `.env.prod`.
2. Mettre a jour le role DB si necessaire:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.prod \
  exec -T postgres psql -U forex -d postgres -c "ALTER ROLE forex WITH PASSWORD '<POSTGRES_PASSWORD>';"
docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.prod restart backend worker beat
```

Reset destructif (dev/test uniquement):

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.prod down -v
./scripts/install-prod-docker.sh
```

### CORS bloque entre UI et API (ports `5173` / `4173`)

Contexte:
- en test local, l'UI peut tourner sur `5173`;
- en mode prod docker local, l'UI tourne sur `4173`.

Regler `CORS_ORIGINS` pour couvrir les deux si besoin:

```dotenv
CORS_ORIGINS=http://localhost:5173,http://localhost:4173
```

Puis:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.prod restart backend
```

Verification preflight:

```bash
curl -i -X OPTIONS http://localhost:8000/api/v1/auth/login \
  -H "Origin: http://localhost:4173" \
  -H "Access-Control-Request-Method: POST"
```

### Warning PostgreSQL `collation version mismatch`

Si les logs affichent en boucle:
- `database "..." has a collation version mismatch`

Executer:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.prod exec -T postgres psql -U forex -d forex_platform -c "REINDEX DATABASE forex_platform;"
docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.prod exec -T postgres psql -U forex -d postgres -c "ALTER DATABASE forex_platform REFRESH COLLATION VERSION;"
docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.prod exec -T postgres psql -U forex -d postgres -c "ALTER DATABASE template1 REFRESH COLLATION VERSION;"
docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.prod exec -T postgres psql -U forex -d postgres -c "ALTER DATABASE postgres REFRESH COLLATION VERSION;"
```

Puis redemarrer les services applicatifs:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.prod restart backend worker beat
```
