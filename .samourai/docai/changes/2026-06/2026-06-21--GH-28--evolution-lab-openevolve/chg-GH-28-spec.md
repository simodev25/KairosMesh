---
change:
  ref: GH-28
  type: feature
  status: Proposed
  title: "Evolution Lab — Intégration OpenEvolve pour évolution de prompts/skills par agent (Lots C+D)"
  owners: [engineering]
  labels: [change, type:feature, priority:high]
---

# SPEC — GH-28 Evolution Lab

## Summary

Intégrer OpenEvolve comme laboratoire offline d'évolution pour les 9 agents de trading, afin de générer des variantes de prompts/skills, les évaluer via le BenchmarkEngine existant, visualiser la progression, puis promouvoir manuellement les meilleurs candidats.

## Context

- Les prompts/skills sont aujourd'hui maintenus manuellement.
- GH-24 fournit déjà un BenchmarkEngine multi-métriques (5 dimensions) réutilisable pour scorer.
- GH-29 a introduit le versionnage des skills d'agents (pré-requis critique).
- Le projet impose une isolation stricte du pipeline de trading réel et aucune modification du moteur de risque.

## Problem Statement

Sans mécanisme d'exploration automatisée, l'amélioration des prompts/skills est lente, peu reproductible et non systématique, ce qui limite la capacité d'itération et l'apprentissage continu par agent.

## Goals

1. Permettre la création et l'exécution de campagnes d'évolution par agent en mode offline.
2. Générer des candidats (prompt système, template user, skills) avec OpenEvolve/LLM mutator.
3. Évaluer chaque candidat avec le BenchmarkEngine et calculer un fitness agrégé.
4. Exposer l'historique et la progression (fitness-series, leaderboard, détails).
5. Garantir une promotion strictement manuelle vers les artefacts versionnés existants.

## Scope

### In scope

- Lot C backend:
  - Nouveau module `backend/app/services/evolution/`:
    - `engine.py`, `service.py`, `evaluator.py`, `mutator.py`.
  - Migration Alembic `0015` + 4 tables dédiées évolution.
  - Tâche Celery `run_evolution_campaign` sur queue `evolution`.
  - Endpoints `/api/v1/evolution/*` listés dans ce document.
  - Schémas Pydantic requête/réponse.
- Lot D frontend:
  - Nouvelle page `/evolution-lab` (lazy loaded).
  - Navigation `EVOLUTION_LAB` dans `Layout.tsx`.
  - Tabs Campagnes / + Nouvelle / Leaderboard.
  - Composants UI dédiés (AgentChip, CampaignCard, etc.).

### Non-goals

- Auto-promotion/activation automatique en production.
- Impact sur `backend/app/risk/`.
- Activation live trading / exécution broker réelle.
- Refonte du BenchmarkEngine (uniquement adaptation).
- Correction des erreurs TypeScript préexistantes hors périmètre GH-28.

## Functional Capabilities

1. Créer, lancer, annuler et consulter des campagnes d'évolution par agent.
2. Générer des candidats successifs (générations) avec filiation parentale.
3. Évaluer baseline et candidats via BenchmarkEngine + agrégation fitness.
4. Afficher séries de fitness, leaderboard, progression et diff baseline/candidat.
5. Promouvoir un candidat manuellement vers prompt template et/ou agent skill versionnée.
6. Enforcer des garde-fous de coût: max itérations, max candidats, max appels LLM, budget USD.

## System Flows

### Flow A — Création + lancement campagne

1. UI envoie `POST /api/v1/evolution/campaigns`.
2. API valide bornes + baseline (`prompt_template_id`, `skill_id`).
3. `EvolutionService` crée la campagne en statut `pending`.
4. API enqueue `run_evolution_campaign` sur queue `evolution`, stocke `celery_task_id`.
5. Campagne passe à `running` côté worker.

### Flow B — Boucle d'évolution

1. Worker charge baseline.
2. `Mutator` génère N candidats.
3. `Evaluator` exécute BenchmarkEngine pour chaque candidat.
4. `Engine` persiste métriques, score agrégé, coût LLM, appels LLM.
5. Arrêt quand borne atteinte ou annulation.

### Flow C — Promotion manuelle

1. Utilisateur clique Promouvoir sur un candidat.
2. API `POST /api/v1/evolution/candidates/{id}/promote` vérifie état campagne/candidat.
3. Service crée nouvelles versions artefacts cibles (prompt template et/ou skills) + trace `evolution_promotions`.
4. Aucune promotion automatique n'est exécutée sans action explicite.

## Data Model

## Table: `evolution_campaigns`

| Colonne | Type | Null | Contraintes / Notes |
|---|---|---:|---|
| id | BIGSERIAL | Non | PK |
| name | VARCHAR(160) | Non | nom campagne |
| agent_name | VARCHAR(64) | Non | 9 agents trading uniquement |
| provider | VARCHAR(32) | Non | ex: openai/ollama |
| model_name | VARCHAR(128) | Non | modèle mutator |
| model_parameters | JSONB | Non | température, top_p, etc |
| baseline_prompt_template_id | BIGINT | Non | FK prompt_templates.id |
| baseline_skill_id | BIGINT | Oui | FK agent_skills.id |
| status | VARCHAR(24) | Non | pending/running/completed/cancelled/failed |
| max_iterations | INT | Non | >0 |
| max_candidates | INT | Non | >0 |
| max_llm_calls | INT | Non | >0 |
| budget_usd_limit | NUMERIC(12,4) | Non | >=0 |
| evaluation_config | JSONB | Non | config benchmark + pondérations |
| best_candidate_id | BIGINT | Oui | FK evolution_candidates.id |
| celery_task_id | VARCHAR(128) | Oui | task async |
| created_by_id | BIGINT | Oui | FK users.id |
| created_at | TIMESTAMPTZ | Non | default now() |
| started_at | TIMESTAMPTZ | Oui | |
| completed_at | TIMESTAMPTZ | Oui | |
| error | TEXT | Oui | message si failed |

Index recommandés: `(agent_name,status)`, `(created_at DESC)`.

## Table: `evolution_candidates`

| Colonne | Type | Null | Contraintes / Notes |
|---|---|---:|---|
| id | BIGSERIAL | Non | PK |
| campaign_id | BIGINT | Non | FK evolution_campaigns.id |
| generation | INT | Non | >=0 |
| parent_candidate_id | BIGINT | Oui | FK self |
| system_prompt | TEXT | Non | snapshot candidat |
| user_prompt_template | TEXT | Non | snapshot candidat |
| skills | JSONB | Non | snapshot skills candidat |
| fitness_score | FLOAT | Oui | score agrégé |
| metrics_summary | JSONB | Oui | résumé 5 dimensions |
| llm_cost_usd | NUMERIC(12,6) | Non | default 0 |
| llm_calls_count | INT | Non | default 0 |
| is_baseline | BOOLEAN | Non | baseline true/false |
| status | VARCHAR(24) | Non | generated/evaluating/evaluated/rejected |
| created_at | TIMESTAMPTZ | Non | default now() |

Contraintes recommandées: `UNIQUE(campaign_id, id)`, index `(campaign_id,generation)`, `(campaign_id,fitness_score DESC)`.

## Table: `evolution_candidate_evaluations`

| Colonne | Type | Null | Contraintes / Notes |
|---|---|---:|---|
| id | BIGSERIAL | Non | PK |
| candidate_id | BIGINT | Non | FK evolution_candidates.id |
| evaluation_type | VARCHAR(32) | Non | baseline/benchmark/recheck |
| benchmark_run_id | BIGINT | Oui | FK benchmark_runs.id (nullable) |
| metrics | JSONB | Non | détails scoring |
| aggregate_score | FLOAT | Non | score final |
| created_at | TIMESTAMPTZ | Non | default now() |

Index: `(candidate_id, created_at DESC)`.

## Table: `evolution_promotions`

| Colonne | Type | Null | Contraintes / Notes |
|---|---|---:|---|
| id | BIGSERIAL | Non | PK |
| campaign_id | BIGINT | Non | FK evolution_campaigns.id |
| candidate_id | BIGINT | Non | FK evolution_candidates.id |
| prompt_template_id | BIGINT | Oui | FK prompt_templates.id version promue |
| agent_skill_id | BIGINT | Oui | FK agent_skills.id version promue |
| promoted_by_id | BIGINT | Non | FK users.id |
| created_at | TIMESTAMPTZ | Non | default now() |

Règle: au moins un des deux champs `prompt_template_id` ou `agent_skill_id` doit être non nul.

## API Endpoints

## 1) POST `/api/v1/evolution/campaigns`

Crée et lance une campagne.

Request (extrait):

```json
{
  "name": "TA Prompt Evolution v1",
  "agent_name": "technical-analyst",
  "provider": "openai",
  "model_name": "gpt-4.1-mini",
  "model_parameters": {"temperature": 0.7},
  "baseline_prompt_template_id": 42,
  "baseline_skill_id": 10,
  "max_iterations": 100,
  "max_candidates": 50,
  "max_llm_calls": 1000,
  "budget_usd_limit": 10.0,
  "evaluation_config": {"benchmark_profile": "standard"}
}
```

Response `201` (extrait):

```json
{
  "id": 1,
  "status": "pending",
  "celery_task_id": "<task-id>",
  "created_at": "2026-06-21T18:00:00Z"
}
```

## 2) GET `/api/v1/evolution/campaigns`

Liste paginée des campagnes (filtres status/agent possibles).

Response `200`: `{ "items": [...], "total": 24 }`

## 3) GET `/api/v1/evolution/campaigns/{id}`

Détail campagne + stats courantes (progression, best score, coût).

Response `200` inclut `status`, `best_candidate_id`, `consumed_budget_usd`, `llm_calls_used`.

## 4) POST `/api/v1/evolution/campaigns/{id}/cancel`

Demande d'annulation.

Response `202`: `{ "id": 1, "status": "cancel_requested" }`

## 5) GET `/api/v1/evolution/campaigns/{id}/candidates`

Liste des candidats de la campagne (tri fitness/génération).

Response `200`: `{ "items": [{"id":7,"generation":3,"fitness_score":0.81,...}] }`

## 6) GET `/api/v1/evolution/campaigns/{id}/fitness-series`

Série temporelle/générationnelle pour graphe.

Response `200`:

```json
{
  "points": [
    {"generation": 0, "best": 0.61, "avg": 0.61},
    {"generation": 1, "best": 0.69, "avg": 0.64}
  ]
}
```

## 7) POST `/api/v1/evolution/candidates/{id}/promote`

Promotion manuelle du candidat.

Request:

```json
{ "promote_prompt": true, "promote_skills": true }
```

Response `201`:

```json
{
  "promotion_id": 9,
  "prompt_template_id": 77,
  "agent_skill_id": 31,
  "created_at": "2026-06-21T19:00:00Z"
}
```

## NFRs

1. **Isolation**: 0 appel broker/live trading déclenché par le module évolution.
2. **Borne coût**: arrêt auto à 100% de `max_llm_calls` ou `budget_usd_limit`.
3. **Perf API**: p95 < 2s pour création campagne (async enqueue inclus).
4. **Traçabilité**: 100% promotions journalisées.
5. **Résilience**: annulation campagne convergente (<30s pour arrêt de nouveaux candidats).
6. **Sécurité**: endpoints mutation/promote accessibles aux rôles autorisés uniquement.
7. **Observabilité**: logs structurés campagne/candidat/itération + statut terminal.
8. **UI accessibilité**: contraste AA, navigation clavier sur tabs, dialogs et tableaux.

## Risks

- Overfitting benchmark → utiliser holdout/config benchmark robuste.
- Dépassement coût LLM → hard caps + visibilité coût.
- Intégration OpenEvolve complexe → adapter derrière `engine` isolé.
- Contention workers Celery → queue `evolution` dédiée.
- Candidats invalides (format prompt/skills) → validation stricte avant évaluation.
- Régression perfs backend → pagination + indexes DB + async.
- Mauvaise promotion humaine → dialog confirmation + diff explicite.
- Erreurs TS existantes hors scope → isoler build/checks lot D sans corriger hors périmètre.

## Decisions

1. Evolution Lab est strictement offline (pas de live trading).
2. Promotion manuelle obligatoire; jamais auto.
3. Queue Celery dédiée `evolution`.
4. Evaluator réutilise BenchmarkEngine (pas de moteur parallèle).
5. Références immuables vers baseline prompt/skills versionnées.

## Acceptance Criteria (Given/When/Then)

1. **Création campagne**
   - Given un utilisateur autorisé
   - When il appelle `POST /api/v1/evolution/campaigns` avec payload valide
   - Then la campagne est créée en base et une tâche queue `evolution` est planifiée.

2. **Annulation campagne**
   - Given une campagne `running`
   - When `POST /api/v1/evolution/campaigns/{id}/cancel` est appelé
   - Then la campagne passe en état d'annulation et aucun nouveau candidat n'est généré.

3. **Évaluation benchmark**
   - Given un candidat généré
   - When l'évaluation est lancée
   - Then une entrée `evolution_candidate_evaluations` est créée avec métriques et `aggregate_score`.

4. **Bornes coût**
   - Given une campagne avec budget/calls bornés
   - When la borne est atteinte
   - Then la campagne s'arrête automatiquement avec statut terminal explicite.

5. **Fitness series**
   - Given une campagne avec plusieurs générations
   - When `GET /fitness-series` est appelé
   - Then la réponse retourne une série ordonnée compatible avec le graphe frontend.

6. **Promotion manuelle**
   - Given un candidat évalué
   - When un utilisateur autorisé déclenche `POST /candidates/{id}/promote`
   - Then une ligne `evolution_promotions` est créée et les versions promues sont tracées.

7. **Aucune auto-promotion**
   - Given une campagne complétée
   - When aucun appel promote n'est effectué
   - Then aucun prompt/skill actif n'est modifié.

8. **UI tabs et routing**
   - Given l'application frontend
   - When l'utilisateur navigue vers `/evolution-lab`
   - Then la page lazy-loaded affiche les 3 tabs (Campagnes, + Nouvelle, Leaderboard).

9. **Visualisation progression**
   - Given une campagne avec données
   - When l'utilisateur ouvre le détail
   - Then la courbe fitness, le leaderboard et le log de générations sont visibles.

10. **Accessibilité minimale**
    - Given le thème hacker/terminal
    - When l'utilisateur navigue au clavier
    - Then les éléments interactifs clés sont focusables et lisibles avec contraste AA.
