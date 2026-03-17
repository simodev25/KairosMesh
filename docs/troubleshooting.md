# Troubleshooting

## Triage rapide des logs

Signaux généralement normaux:
- `HTTP/1.1 200 OK` sur MetaApi, Qdrant, Ollama.
- `Task ... succeeded` côté worker Celery.
- `mingle: all alone` si un seul worker est lancé.

Signaux à traiter en priorité:
- `password authentication failed for user "forex"` (désalignement secrets DB).
- `database "... has a collation version mismatch"` (maintenance DB).
- `HTTP 401` sur Ollama/MetaApi (token/header/URL).
- `Waiting for backend health endpoint...` qui dure (backend/migrations non prêts).

## Script d'installation bloqué sur `Waiting for backend health endpoint...`

Diagnostic:

```bash
docker compose logs --tail 150 backend
docker compose exec backend alembic current
```

Correctif:

```bash
docker compose exec backend alembic upgrade head
docker compose restart backend worker beat
```

## PostgreSQL `password authentication failed for user "forex"`

Cause fréquente:
- volume Postgres existant avec ancien mot de passe, après modification des variables `.env`/`.env.prod`.

Correctif non destructif:
1. Vérifier que `DATABASE_URL` utilise le même secret que `POSTGRES_PASSWORD`.
2. Mettre à jour le mot de passe du rôle en base.

```bash
docker compose exec -T postgres psql -U forex -d postgres -c "ALTER ROLE forex WITH PASSWORD '<POSTGRES_PASSWORD>';"
docker compose restart backend worker beat
```

Correctif destructif (dev/test uniquement):

```bash
docker compose down -v
docker compose up -d --build
```

## PostgreSQL `collation version mismatch`

Symptôme:
- warning répété sur `forex_platform`/`template1`/`postgres`.

Correctif:

```bash
docker compose stop backend worker beat
docker compose exec -T postgres psql -U forex -d forex_platform -c "REINDEX DATABASE forex_platform;"
docker compose exec -T postgres psql -U forex -d postgres -c "ALTER DATABASE forex_platform REFRESH COLLATION VERSION;"
docker compose exec -T postgres psql -U forex -d postgres -c "ALTER DATABASE template1 REFRESH COLLATION VERSION;"
docker compose exec -T postgres psql -U forex -d postgres -c "ALTER DATABASE postgres REFRESH COLLATION VERSION;"
docker compose start backend worker beat
```

Vérification:

```bash
docker compose exec -T postgres psql -U forex -d postgres -c "SELECT datname, datcollversion FROM pg_database WHERE datname IN ('forex_platform','template1','postgres');"
```

## Login navigateur bloqué (CORS / origine)

Signes:
- requête `OPTIONS` ou `POST /api/v1/auth/login` bloquée dans le navigateur;
- présence de `strict-origin-when-cross-origin` dans les headers (ce header seul n'est pas une erreur).

Fix:
- autoriser explicitement les origines utilisées par le frontend:
  - local: `http://localhost:5173`
  - mode prod docker local: `http://localhost:4173`

Exemple:

```dotenv
CORS_ORIGINS=http://localhost:5173,http://localhost:4173
```

Puis:

```bash
docker compose restart backend
```

Test preflight:

```bash
curl -i -X OPTIONS http://localhost:8000/api/v1/auth/login \
  -H "Origin: http://localhost:5173" \
  -H "Access-Control-Request-Method: POST"
```

## `Temps running` affiche `+1h` dans l'UI

Symptôme:

- La durée affichée semble commencer avec une heure en plus (ex: `1h 00m 00s`).

Cause:

- Interprétation locale d'un timestamp backend sans timezone explicite.

Fix:

- Le front interprète désormais les timestamps backend sans timezone comme UTC.
- Rebuild frontend si nécessaire:
```bash
docker compose up -d --build frontend
```

## Celery ne démarre pas (`cors_origins` parse error)

Symptôme:

- `error parsing value for field "cors_origins" from source "EnvSettingsSource"`

Cause:

- `CORS_ORIGINS` mal formaté.

Fix:

- utiliser CSV simple:
  - `CORS_ORIGINS=http://localhost:5173`
- ou JSON valide:
  - `CORS_ORIGINS=["http://localhost:5173"]`

## Erreur SQL `type "vector" does not exist`

Symptôme:

- migration `embedding VECTOR(64)` échoue.

Cause:

- extension pgvector absente en base.

Fix:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

Puis relancer migrations.

## Redis connection refused côté worker

Symptôme:

- `Error 111 connecting to redis:6379. Connection refused`

Fix:

- vérifier service redis:
```bash
docker compose ps redis
docker compose logs redis
```
- redémarrer worker après redis:
```bash
docker compose up -d redis worker
```

## Celery `KeyError: app.tasks.run_analysis_task.execute`

Cause probable:

- worker sur une image ancienne (code task non aligné).

Fix:

```bash
docker compose up -d --build backend worker
```

## Qdrant collection not found

Symptôme:

- `Collection forex_long_term_memory doesn't exist`

Comportement attendu:

- la collection est auto-créée au premier write/search.

Fix si persiste:

- vérifier `QDRANT_COLLECTION` et connectivité.
- supprimer/réinitialiser volume Qdrant si besoin.

## Ollama `401 Unauthorized`

Symptôme:

- `HTTPStatusError: 401 Unauthorized ... /api/chat`

Checklist:

- `OLLAMA_API_KEY` valide (sans guillemets parasites).
- `OLLAMA_BASE_URL` correct (`https://api.ollama.com` ou `https://ollama.com`).
- test direct API (voir `docs/ollama-cloud.md`).

## MetaApi `invalid auth-token header`

Checklist:

- `METAAPI_TOKEN` correct.
- `METAAPI_AUTH_HEADER=auth-token`.
- `METAAPI_ACCOUNT_ID` valide pour ce token.
- endpoint/région conformes au compte.

## `Unknown trade return code`

Sens:

- MetaApi n'a pas confirmé explicitement l'ordre.

Comportement plateforme:

- en `paper`: repli simulation possible.
- en `live`: run en erreur d'exécution.

## `tradeMode=SYMBOL_TRADE_MODE_DISABLED`

Sens:

- le symbole est désactivé sur ce compte broker.

Fix:

- utiliser un symbole tradable sur le compte.
- si broker suffixe les paires, configurer le suffixe directement dans `DEFAULT_FOREX_PAIRS` (ex: `EURUSD.pro`).

## `Object of type datetime is not JSON serializable`

Symptôme:

- crash SQLAlchemy à l'écriture de `execution_orders.response_payload`.

Fix attendu:

- encoder la payload avec `jsonable_encoder` avant commit
  (`ExecutionService._json_safe`).

## NameError `llm_model` dans agent

Cause:

- variable non définie ou image worker non rebuild.

Fix:

- corriger le code agent et rebuild `worker`.
- vérifier que le conteneur actif contient la version patchée.
