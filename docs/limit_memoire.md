# Limites memoire (Qdrant / PGVector / memory_context)

## Objectif

Ce document explique pourquoi la couche memoire peut sembler "ne pas impacter" la decision finale des agents, et quelles corrections prioriser.

## 1) Fonctionnement actuel (factuel)

- La memoire est chargee au debut du run uniquement si `memory_context_enabled=true` dans `connector_configs.settings` (connector `ollama`).
- La recherche utilise la query:
  - `"{pair} {timeframe} trend {trend}"`
  - avec `limit=5`.
- Le service memoire:
  - priorise Qdrant (`search` vectoriel + filtre `pair/timeframe`),
  - fallback en SQL + cosine locale (top 100 recents).
- `add_run_memory()` est appele **apres** le run (decision deja prise), pour alimenter les runs suivants.
- Les embeddings sont un hash SHA256 deterministe (64 dimensions), pas un embedding semantique LLM.
- `memory_context` est surtout injecte dans:
  - `news-analyst`
  - `bullish-researcher`
  - `bearish-researcher`
- Le `trader-agent` ne met pas la memoire dans ses gates deterministes; il conserve surtout `memory_refs` dans la rationale/debug.

## 2) Frontiere PGVector vs Qdrant

- PGVector est ici surtout un **type de colonne** optionnel (`Vector(64)` en PostgreSQL).
- La recherche active n'exploite pas de pipeline SQL vectoriel avance dans ce code.
- En pratique:
  - Qdrant = moteur principal de retrieval,
  - fallback SQL = cosine locale en Python.

## 3) Ce que montrent les debug-traces (echantillon present)

- 41 runs inspectes.
- 32 runs avec `memory_context` non vide.
- Taille `memory_context`: majoritairement 3-4 items.
- `source_type` memoire observe: `run_outcome` (quasi uniquement).
- `news_count` observe: 0 sur l'echantillon (donc peu de signal news exploitable).
- Beaucoup de decisions restent `HOLD` meme avec memoire.

## 4) Pourquoi l'impact peut paraitre faible

- Les gates critiques de decision trader (score/confidence/source/qualite) sont deterministes et priment.
- Si les agents qui lisent la memoire ne produisent pas un signal fort utilisable, la memoire reste narrative.
- Le retrieval base sur hash peut ramener des items peu pertinents semantiquement.
- Le contenu memoire est souvent homogene (`run_outcome`), ce qui limite la diversite informationnelle.

## 5) Limites majeures

1. Embedding non semantique (hash) -> pertinence retrieval limitee.
2. Query retrieval trop simple (`pair/timeframe/trend`) -> peu de contexte trading.
3. Peu de types memoire (`run_outcome` dominant).
4. Pas de seuil strict de similarite pour filtrer le bruit.
5. Faible lien direct entre memoire et score trader deterministe.
6. Schema debug-trace pas toujours uniforme selon versions de run.

## 6) Correctifs prioritaires

1. Remplacer l'embedding hash par un vrai embedding semantique.
2. Ajouter un filtre de score minimal + recence (time decay).
3. Enrichir le payload memoire (features utiles au trader):
   - regime, volatilite, contradiction level, issue trade, etc.
4. Introduire une feature memoire **deterministe** dans le scoring trader:
   - ex: performance recente sur contexte similaire.
5. Mesurer l'impact reel:
   - run A/B avec memoire ON/OFF sur memes inputs.
6. Uniformiser le schema des debug-traces.

## 7) Checklist de verification rapide

- Verifier le flag memoire:
  - `GET /api/v1/connectors` -> `ollama.settings.memory_context_enabled`.
- Verifier retrieval:
  - `POST /api/v1/memory/search`.
- Verifier qu'il y a des entrees:
  - `GET /api/v1/memory?limit=...`.
- Verifier l'injection:
  - dans debug-trace: `context.memory_context`.
- Verifier impact:
  - comparer decision/gates avec et sans memoire sur meme paire/timeframe.

## References code

- `backend/app/services/memory/vector_memory.py`
- `backend/app/db/models/memory_entry.py`
- `backend/app/services/orchestrator/engine.py`
- `backend/app/services/orchestrator/agents.py`
- `backend/app/services/llm/model_selector.py`
- `backend/app/api/routes/connectors.py`
- `backend/app/api/routes/memory.py`

