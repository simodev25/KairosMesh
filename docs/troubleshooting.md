# Troubleshooting

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
