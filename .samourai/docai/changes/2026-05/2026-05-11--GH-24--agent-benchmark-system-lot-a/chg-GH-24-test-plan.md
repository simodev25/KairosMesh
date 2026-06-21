---
id: chg-GH-24-test-plan
status: Proposed
created: 2026-05-11T13:29:38Z
last_updated: 2026-05-11T13:29:38Z
owners: [engineering]
service: benchmark
labels: [type:feature, priority:high, change]
links:
  change_spec: ./chg-GH-24-spec.md
  implementation_plan: ./chg-GH-24-plan.md
  testing_strategy: ../../../../ai/rules/testing-strategy.md
version_impact: minor
summary: >
  Définir la stratégie de test et les scénarios traçables pour le Lot A du sous-système
  de benchmarking (fixtures versionnées, exécution via Celery, scoring V1 déterministe,
  API REST) conformément à la spec GH-24.
---

# Test Plan - Système de benchmarking des modèles LLM par agent de trading (Lot A)

## 1. Scope and Objectives

Objectif : vérifier, de façon traçable et reproductible, que le sous-système backend de benchmark (Lot A) satisfait la spec `chg-GH-24-spec.md`.

Périmètre couvert par ce plan :

- Fixtures benchmark versionnées : CRUD + immutabilité + hash d’intégrité (F-1).
- Runs benchmark : création, vérification de hash, annulation, statut, exécution asynchrone (F-2, F-7).
- Moteur d’exécution : scénarios `single-agent`, `debate-bundle`, `full-pipeline` + règle `SKIPPED_DEBATE` (F-3, F-4).
- Scoring V1 : métriques (validité schéma, complétude, conformité outils, cohérence références, stabilité), agrégation, déterminisme (F-5, NFR-2).
- API REST : endpoints `/api/v1/benchmark/*` (F-6) et gestion d’erreurs (hash mismatch, invalidations, annulation, échec run).
- Non-fonctionnel : performance lecture résultats (NFR-1), intégrité fixtures (NFR-6), traçabilité coûts (NFR-5), non-régression (AC-NFR-1).

Hors périmètre de ce plan (car hors spec / Lot A) : frontend (Lot B), scoring LLM-juge (Lot C), CI/CD benchmark automatique.

## 2. References

- Spec : `./chg-GH-24-spec.md`
- Plan : `./chg-GH-24-plan.md`
- Stratégie de test repo : `.samourai/ai/rules/testing-strategy.md`

## 3. Coverage Overview

### 3.1 Functional Coverage (F-#, AC-#)

| Capacité | Critères d’acceptation | Couverture (TC) | Statut |
|---|---|---|---|
| F-1 Gestion CRUD fixtures | AC-F1-1 | TC-BENCH-001, TC-BENCH-003 | Planifié |
|  | AC-F1-2 | TC-BENCH-002 | Planifié |
|  | AC-F1-3 | TC-BENCH-004 | Planifié |
| F-2 Lancement runs (BenchmarkModelSpec) | AC-F2-1 | TC-BENCH-006, TC-BENCH-018 | Planifié |
|  | AC-F2-2 | TC-BENCH-007 | Planifié |
|  | AC-F2-3 | TC-BENCH-010 | Planifié |
| F-3 Moteur d’exécution (cœur partagé) | AC-F4-2 | TC-BENCH-012 | Planifié |
| F-4 Scénarios (single/debate/full) | AC-F4-1 | TC-BENCH-011 | Planifié |
|  | AC-F4-3 | TC-BENCH-013 | Planifié |
|  | AC-F4-4 | TC-BENCH-014 | Planifié |
| F-5 Scoring V1 déterministe | AC-F5-1 | TC-BENCH-015 | Planifié |
|  | AC-F5-2 | TC-BENCH-015 | Planifié |
|  | AC-F5-3 | TC-BENCH-016 | Planifié |
|  | AC-F5-4 | TC-BENCH-017 | Planifié |
| F-6 Consultation résultats via API REST | AC-F6-1 | TC-BENCH-008 | Planifié |
|  | AC-F6-2 | TC-BENCH-009, TC-BENCH-022 | Planifié |
| NFR (non-régression) | AC-NFR-1 | TC-BENCH-024 | Planifié |

Remarque : la capacité F-8 (traçabilité vers `llm_call_log`) est couverte via NFR-5 + vérifications de persistance de `analysis_run_id` / `llm_calls_count` (TC-BENCH-021).

### 3.2 Interface Coverage (API-#, EVT-#, DM-#)

#### Endpoints REST (spec §8.1)

| Endpoint | Couverture (TC) |
|---|---|
| POST `/api/v1/benchmark/fixtures` | TC-BENCH-001 |
| GET `/api/v1/benchmark/fixtures` | TC-BENCH-004 |
| GET `/api/v1/benchmark/fixtures/{id}` | TC-BENCH-005 |
| PATCH `/api/v1/benchmark/fixtures/{id}` | TC-BENCH-003 |
| DELETE `/api/v1/benchmark/fixtures/{id}` | TC-BENCH-003 |
| POST `/api/v1/benchmark/runs` | TC-BENCH-006, TC-BENCH-007 |
| GET `/api/v1/benchmark/runs` | TC-BENCH-008 |
| GET `/api/v1/benchmark/runs/{id}` | TC-BENCH-009 |
| DELETE `/api/v1/benchmark/runs/{id}` | TC-BENCH-010 |

#### Événements (spec §8.2)

| ID | Couverture (TC) | Note |
|---|---|---|
| EVT-1 `benchmark.run.started` | TC-BENCH-019 | Vérifier l’orchestration Celery (environnement de test) |
| EVT-2 `benchmark.run.completed` | TC-BENCH-019 | Vérifier statut + logs |
| EVT-3 `benchmark.run.failed` | TC-BENCH-020 | Vérifier statut FAILED + error exposée |

#### Modèle de données (spec §8.3)

| ID | Couverture (TC) |
|---|---|
| DM-1 `benchmark_fixture` | TC-BENCH-001, TC-BENCH-003, TC-BENCH-004, TC-BENCH-005 |
| DM-2 `benchmark_run` | TC-BENCH-006, TC-BENCH-008, TC-BENCH-009, TC-BENCH-010 |
| DM-3 `benchmark_case` | TC-BENCH-011, TC-BENCH-013, TC-BENCH-019 |
| DM-4 `benchmark_attempt` | TC-BENCH-011, TC-BENCH-015, TC-BENCH-017, TC-BENCH-019, TC-BENCH-021 |

### 3.3 Non-Functional Coverage (NFR-#)

| NFR | Exigence | Couverture (TC) | Statut |
|---|---|---|---|
| NFR-1 | p95 < 500ms (GET /runs, GET /runs/{id}) sur 1 000 tentatives | TC-BENCH-022 | Planifié (perf) |
| NFR-2 | Déterminisme scoring (inputs identiques → scores identiques) | TC-BENCH-016, TC-BENCH-023 | Planifié |
| NFR-3 | Isolation (pas d’impact mesurable sur pipeline prod) | TC-BENCH-025 | TODO (validation ops) |
| NFR-4 | Tolérance aux pannes (run échoué n’affecte pas les autres) | TC-BENCH-020 | Planifié |
| NFR-5 | Traçabilité coûts (llm_calls_count non nul) | TC-BENCH-021 | Planifié |
| NFR-6 | Intégrité fixtures (hash mismatch → 409) | TC-BENCH-007 | Planifié |
| NFR-7 | Scalabilité (50 runs simultanés) | TC-BENCH-026 | TODO (load) |

## 4. Test Types and Layers

Conformément à `.samourai/ai/rules/testing-strategy.md` :

- **Unit (pytest)** : logique métier isolée sans dépendance DB/LLM/broker.
  - Localisation : `backend/tests/unit/`
  - LLM : toujours mocké
  - DB : SQLite in-memory autorisée si strictement locale au test unitaire
- **Integration (pytest + FastAPI TestClient/httpx)** : endpoints API et flux DB complets.
  - Localisation : `backend/tests/integration/`
  - DB : PostgreSQL de test
  - Broker/Celery : mock (par défaut) ; tests dédiés possibles selon environnement

Couche **Backend API E2E** (HTTP réel sur service lancé) : pertinente car la spec introduit des endpoints REST et un workflow multi-étapes (fixture → run async → résultats). Le dépôt ne documente pas explicitement une localisation/harness E2E backend ; ce plan inclut donc un scénario E2E **semi-automatisé** (TC-BENCH-018) et une question ouverte (section 8) pour industrialiser cette couche.

## 5. Test Scenarios

### 5.1 Scenario Index

| TC-ID | Titre court | Type(s) | Priorité | IDs couverts |
|---|---|---:|---:|---|
| TC-BENCH-001 | Créer une fixture versionnée (hash server-side) | Integration | High | F-1, AC-F1-1, DM-1 |
| TC-BENCH-002 | Rejeter modification d’une fixture (immutabilité) | Integration | High | F-1, AC-F1-2 |
| TC-BENCH-003 | Activer/désactiver + soft delete fixture | Integration | Medium | F-1, DM-1 |
| TC-BENCH-004 | Lister fixtures filtrées + pagination | Integration | Medium | F-1, AC-F1-3 |
| TC-BENCH-005 | Lire le détail d’une fixture | Integration | Medium | F-1 |
| TC-BENCH-006 | Créer un run (PENDING) + enqueue Celery | Integration | High | F-2, F-7, AC-F2-1, DM-2, EVT-1 |
| TC-BENCH-007 | Rejeter run si fixture_hash mismatch (409) | Integration | High | F-2, AC-F2-2, NFR-6 |
| TC-BENCH-008 | Lister runs avec filtres + pagination | Integration | High | F-6, AC-F6-1 |
| TC-BENCH-009 | Détail run : cases + tentatives + 5 scores | Integration | High | F-6, AC-F6-2 |
| TC-BENCH-010 | Annuler un run PENDING (CANCELLED + révocation) | Integration | High | F-2, AC-F2-3 |
| TC-BENCH-011 | Exécution single-agent : N tentatives + COMPLETED | Unit | High | F-3, F-4, AC-F4-1, DM-3, DM-4 |
| TC-BENCH-012 | Exécution : réutilisation stricte du cœur partagé | Unit | High | F-3, AC-F4-2 |
| TC-BENCH-013 | Exécution debate-bundle : 3 cases + passage de contexte | Unit | High | F-4, AC-F4-3 |
| TC-BENCH-014 | debate-bundle : SKIPPED_DEBATE si llm_enabled=false | Unit | High | F-4, AC-F4-4 |
| TC-BENCH-015 | Scoring : validité de schéma (1.0 / 0.0) | Unit | High | F-5, AC-F5-1, AC-F5-2 |
| TC-BENCH-016 | Scoring : déterminisme (hors stabilité) | Unit | High | F-5, AC-F5-3, NFR-2 |
| TC-BENCH-017 | Scoring : stabilité calculée pour repetitions>=2 | Unit | High | F-5, AC-F5-4 |
| TC-BENCH-018 | Parcours API E2E backend : fixture → run → résultats | E2E | Medium | F-1, F-2, F-6 |
| TC-BENCH-019 | Exécution asynchrone Celery : RUNNING→COMPLETED | Integration | Medium | F-7, EVT-1, EVT-2 |
| TC-BENCH-020 | Gestion d’erreur : échec LLM / exception engine → FAILED | Integration | High | F-7, NFR-4, EVT-3 |
| TC-BENCH-021 | Traçabilité : llm_calls_count + lien analysis_run_id | Unit | Medium | F-8, NFR-5 |
| TC-BENCH-022 | Performance lecture résultats (p95 < 500ms) | Performance | Low | NFR-1 |
| TC-BENCH-023 | Déterminisme bout-en-bout (mêmes inputs → mêmes scores) | Integration | Medium | NFR-2 |
| TC-BENCH-024 | Non-régression : suite backend existante | Unit | High | AC-NFR-1 |
| TC-BENCH-025 | Isolation : pas d’impact mesurable pipeline trading | Manual | Low | NFR-3 |
| TC-BENCH-026 | Scalabilité : 50 runs simultanés | Manual | Low | NFR-7 |
| TC-BENCH-027 | Erreur : création fixture invalide (validation) | Integration | Medium | F-1 |
| TC-BENCH-028 | Erreur : lancement run avec fixture inexistante | Integration | Medium | F-2 |
| TC-BENCH-029 | Scoring : complétude (ratio champs requis non nuls) | Unit | Medium | F-5 |
| TC-BENCH-030 | Scoring : conformité politiques d’outils | Unit | Medium | F-5 |
| TC-BENCH-031 | Scoring : cohérence des références (symbol/timeframe) | Unit | Medium | F-5 |
| TC-BENCH-032 | Exécution full-pipeline : 8 agents, 4 phases | Unit | Low | F-4 |
| TC-BENCH-033 | RBAC API : ADMIN write, ANALYST read, forbidden sinon | Integration | High | F-6 |

### 5.2 Scenario Details

#### TC-BENCH-001 - Créer une fixture versionnée (hash server-side)

**Scenario Type**: Happy Path
**Impact Level**: Critical
**Priority**: High
**Related IDs**: F-1, AC-F1-1, DM-1
**Test Type(s)**: Integration
**Automation Level**: Automated
**Target Layer / Location**: `backend/tests/integration/test_benchmark_fixtures_integration.py`
**Tags**: @backend @api

**Preconditions**:

- Un utilisateur authentifié avec rôle ADMIN.

**Steps**:

1. Appeler POST `/api/v1/benchmark/fixtures` avec `agent_name`, `inputs`, `config` valides.
2. Vérifier la réponse HTTP 201 et la présence de `fixture_id` et `hash`.
3. Relire la fixture (GET `/api/v1/benchmark/fixtures/{id}`) et vérifier : `version=1`, `is_active=true`, `hash` présent et stable.

**Expected Outcome**:

- Fixture persistée avec hash SHA-256 calculé côté serveur.
- Réponse conforme au critère AC-F1-1.

#### TC-BENCH-002 - Rejeter modification d’une fixture (immutabilité)

**Scenario Type**: Negative
**Impact Level**: Critical
**Priority**: High
**Related IDs**: F-1, AC-F1-2
**Test Type(s)**: Integration
**Automation Level**: Automated
**Target Layer / Location**: `backend/tests/integration/test_benchmark_fixtures_integration.py`
**Tags**: @backend @api

**Preconditions**:

- Fixture existante.
- Utilisateur ADMIN.

**Steps**:

1. Tenter de modifier `inputs` ou `config` d’une fixture existante (ex. PATCH) de manière à simuler une modification de contenu.
2. Observer la réponse.

**Expected Outcome**:

- La requête est rejetée avec HTTP 422 et un message expliquant l’immutabilité (AC-F1-2).

#### TC-BENCH-003 - Activer/désactiver + soft delete fixture

**Scenario Type**: Edge Case
**Impact Level**: Important
**Priority**: Medium
**Related IDs**: F-1, DM-1
**Test Type(s)**: Integration
**Automation Level**: Automated
**Target Layer / Location**: `backend/tests/integration/test_benchmark_fixtures_integration.py`
**Tags**: @backend @api

**Preconditions**:

- Fixture existante.
- Utilisateur ADMIN.

**Steps**:

1. PATCH `/api/v1/benchmark/fixtures/{id}` pour désactiver la fixture.
2. Vérifier via GET list que la fixture apparaît comme inactive (selon contrat de réponse).
3. DELETE `/api/v1/benchmark/fixtures/{id}`.
4. Vérifier que la suppression est logique (la fixture n’est plus utilisable pour lancer un run ou n’apparaît plus selon les filtres attendus).

**Expected Outcome**:

- Activation/désactivation fonctionne.
- Suppression logique effectuée (soft delete) sans suppression physique.

#### TC-BENCH-004 - Lister fixtures filtrées + pagination

**Scenario Type**: Happy Path
**Impact Level**: Important
**Priority**: Medium
**Related IDs**: F-1, AC-F1-3
**Test Type(s)**: Integration
**Automation Level**: Automated
**Target Layer / Location**: `backend/tests/integration/test_benchmark_fixtures_integration.py`
**Tags**: @backend @api

**Preconditions**:

- Plusieurs fixtures existent pour plusieurs agents.
- Utilisateur ANALYST.

**Steps**:

1. Appeler GET `/api/v1/benchmark/fixtures?agent_name=technical-analyst`.
2. Vérifier que seules les fixtures de cet agent sont retournées.
3. Vérifier la pagination (format projet) si applicable.

**Expected Outcome**:

- Filtrage et pagination conformes (AC-F1-3).

#### TC-BENCH-005 - Lire le détail d’une fixture

**Scenario Type**: Regression
**Impact Level**: Minor
**Priority**: Medium
**Related IDs**: F-1
**Test Type(s)**: Integration
**Automation Level**: Automated
**Target Layer / Location**: `backend/tests/integration/test_benchmark_fixtures_integration.py`
**Tags**: @backend @api

**Preconditions**:

- Fixture existante.
- Utilisateur ANALYST.

**Steps**:

1. Appeler GET `/api/v1/benchmark/fixtures/{id}`.

**Expected Outcome**:

- La réponse inclut l’identifiant, le hash, et les informations attendues (spec §8.1).

#### TC-BENCH-006 - Créer un run (PENDING) + enqueue Celery

**Scenario Type**: Happy Path
**Impact Level**: Critical
**Priority**: High
**Related IDs**: F-2, F-7, AC-F2-1, DM-2, EVT-1
**Test Type(s)**: Integration
**Automation Level**: Automated
**Target Layer / Location**: `backend/tests/integration/test_benchmark_runs_integration.py`
**Tags**: @backend @api

**Preconditions**:

- Fixture active existante.
- Utilisateur ADMIN.
- Enqueue Celery mockée (ou mode eager en environnement d’intégration, selon conventions du repo).

**Steps**:

1. POST `/api/v1/benchmark/runs` avec `fixture_id`, `fixture_hash`, `model_spec`, `scenario_type`, `repetitions`.
2. Vérifier HTTP 201 et présence de `run_id`.
3. Vérifier que le run est créé en statut `PENDING`.
4. Vérifier qu’une tâche Celery est enqueueée avec ce `run_id`.

**Expected Outcome**:

- Run `PENDING` créé et tâche Celery déclenchée (AC-F2-1).

#### TC-BENCH-007 - Rejeter run si fixture_hash mismatch (409)

**Scenario Type**: Negative
**Impact Level**: Critical
**Priority**: High
**Related IDs**: F-2, AC-F2-2, NFR-6
**Test Type(s)**: Integration
**Automation Level**: Automated
**Target Layer / Location**: `backend/tests/integration/test_benchmark_runs_integration.py`
**Tags**: @backend @api

**Preconditions**:

- Fixture existante.
- Utilisateur ADMIN.

**Steps**:

1. POST `/api/v1/benchmark/runs` avec un `fixture_hash` volontairement incorrect.

**Expected Outcome**:

- Réponse HTTP 409 avec message explicite (AC-F2-2).

#### TC-BENCH-008 - Lister runs avec filtres + pagination

**Scenario Type**: Happy Path
**Impact Level**: Critical
**Priority**: High
**Related IDs**: F-6, AC-F6-1
**Test Type(s)**: Integration
**Automation Level**: Automated
**Target Layer / Location**: `backend/tests/integration/test_benchmark_runs_integration.py`
**Tags**: @backend @api

**Preconditions**:

- Plusieurs runs (différents agents/modèles/fixtures) existent.
- Utilisateur ANALYST.

**Steps**:

1. Appeler GET `/api/v1/benchmark/runs?fixture_id=X&agent_name=technical-analyst`.
2. Vérifier que seuls les runs correspondant aux filtres sont retournés.
3. Vérifier la pagination et la présence des scores agrégés attendus.

**Expected Outcome**:

- Filtrage et pagination conformes (AC-F6-1).

#### TC-BENCH-009 - Détail run : cases + tentatives + 5 scores

**Scenario Type**: Happy Path
**Impact Level**: Critical
**Priority**: High
**Related IDs**: F-6, AC-F6-2
**Test Type(s)**: Integration
**Automation Level**: Automated
**Target Layer / Location**: `backend/tests/integration/test_benchmark_runs_integration.py`
**Tags**: @backend @api

**Preconditions**:

- Un run `COMPLETED` existe (données seedées ou exécution via task en mode test).
- Utilisateur ANALYST.

**Steps**:

1. Appeler GET `/api/v1/benchmark/runs/{id}`.
2. Vérifier que la réponse inclut : cases, tentatives, 5 métriques, `aggregate_score` par tentative et par case.

**Expected Outcome**:

- Contrat de réponse conforme (spec §8.1) et AC-F6-2.

#### TC-BENCH-010 - Annuler un run PENDING (CANCELLED + révocation)

**Scenario Type**: Happy Path
**Impact Level**: Critical
**Priority**: High
**Related IDs**: F-2, AC-F2-3
**Test Type(s)**: Integration
**Automation Level**: Automated
**Target Layer / Location**: `backend/tests/integration/test_benchmark_runs_integration.py`
**Tags**: @backend @api

**Preconditions**:

- Un run en statut `PENDING` existe.
- Utilisateur ADMIN.
- Révocation Celery observable (mock).

**Steps**:

1. Appeler DELETE `/api/v1/benchmark/runs/{id}`.
2. Vérifier que le run passe au statut `CANCELLED`.
3. Vérifier que la tâche Celery associée est révoquée.

**Expected Outcome**:

- Annulation conforme (AC-F2-3) et aucune tentative n’est créée.

#### TC-BENCH-011 - Exécution single-agent : N tentatives + COMPLETED

**Scenario Type**: Happy Path
**Impact Level**: Critical
**Priority**: High
**Related IDs**: F-3, F-4, AC-F4-1, DM-3, DM-4
**Test Type(s)**: Unit
**Automation Level**: Automated
**Target Layer / Location**: `backend/tests/unit/test_benchmark_engine_unit.py`
**Tags**: @backend

**Preconditions**:

- Le moteur d’exécution benchmark peut être exécuté en mode test (LLM mocké ou déterministe).
- `repetitions=3`.

**Steps**:

1. Exécuter le scénario `single-agent` sur une fixture de test.
2. Observer le résultat persistant ou l’objet de résultat (selon design).

**Expected Outcome**:

- Exactement 3 tentatives sont créées pour le case de l’agent.
- Le run passe à `COMPLETED` (AC-F4-1).

#### TC-BENCH-012 - Exécution : réutilisation stricte du cœur partagé

**Scenario Type**: Regression
**Impact Level**: Critical
**Priority**: High
**Related IDs**: F-3, AC-F4-2
**Test Type(s)**: Unit
**Automation Level**: Automated
**Target Layer / Location**: `backend/tests/unit/test_benchmark_engine_unit.py`
**Tags**: @backend

**Preconditions**:

- Possibilité de patcher/spy `ALL_AGENT_FACTORIES`, `build_toolkit()`, `build_model()`, `build_formatter()`.

**Steps**:

1. Exécuter un run (scénario minimal) en instrumentant les appels.
2. Vérifier que les fonctions du cœur partagé sont appelées.
3. Vérifier que les paramètres proviennent de la fixture (config gelée) et du `BenchmarkModelSpec`.

**Expected Outcome**:

- Les 4 points d’extension partagés sont utilisés, sans fork de logique (AC-F4-2).

#### TC-BENCH-013 - Exécution debate-bundle : 3 cases + passage de contexte

**Scenario Type**: Happy Path
**Impact Level**: Critical
**Priority**: High
**Related IDs**: F-4, AC-F4-3
**Test Type(s)**: Unit
**Automation Level**: Automated
**Target Layer / Location**: `backend/tests/unit/test_benchmark_scenarios_unit.py`
**Tags**: @backend

**Preconditions**:

- Agents du débat exécutables avec sorties mockées.

**Steps**:

1. Exécuter le scénario `debate-bundle`.
2. Vérifier la création de 3 cases (bullish, bearish, trader).
3. Vérifier que la sortie bullish est utilisée en contexte de bearish, et bullish+bearish pour trader.

**Expected Outcome**:

- Passage de contexte et persistance conformes (AC-F4-3).

#### TC-BENCH-014 - debate-bundle : SKIPPED_DEBATE si llm_enabled=false

**Scenario Type**: Edge Case
**Impact Level**: Critical
**Priority**: High
**Related IDs**: F-4, AC-F4-4, NFR-4
**Test Type(s)**: Unit
**Automation Level**: Automated
**Target Layer / Location**: `backend/tests/unit/test_benchmark_scenarios_unit.py`
**Tags**: @backend

**Preconditions**:

- Un des 3 agents du débat est configuré `llm_enabled=false`.

**Steps**:

1. Lancer un run `debate-bundle`.

**Expected Outcome**:

- Statut `SKIPPED_DEBATE`.
- Aucune tentative n’est créée.
- Un log WARN explicite est émis (AC-F4-4).

#### TC-BENCH-015 - Scoring : validité de schéma (1.0 / 0.0)

**Scenario Type**: Happy Path
**Impact Level**: Critical
**Priority**: High
**Related IDs**: F-5, AC-F5-1, AC-F5-2
**Test Type(s)**: Unit
**Automation Level**: Automated
**Target Layer / Location**: `backend/tests/unit/test_benchmark_scoring_v1_unit.py`
**Tags**: @backend

**Preconditions**:

- Un schéma Pydantic attendu est connu pour un agent.

**Steps**:

1. Scorer une `raw_output` valide.
2. Scorer une `raw_output` invalide.

**Expected Outcome**:

- `schema_validity_score=1.0` pour la sortie valide (AC-F5-1).
- `schema_validity_score=0.0` pour la sortie invalide (AC-F5-2).

#### TC-BENCH-016 - Scoring : déterminisme (hors stabilité)

**Scenario Type**: Regression
**Impact Level**: Critical
**Priority**: High
**Related IDs**: F-5, AC-F5-3, NFR-2
**Test Type(s)**: Unit
**Automation Level**: Automated
**Target Layer / Location**: `backend/tests/unit/test_benchmark_scoring_v1_unit.py`
**Tags**: @backend

**Preconditions**:

- Même fixture, même modèle, même scénario, mêmes outputs bruts (ou outputs déterministes via mocks).

**Steps**:

1. Calculer les scores V1 (hors stabilité) deux fois sur les mêmes inputs.

**Expected Outcome**:

- `schema_validity`, `completeness`, `tool_policy_compliance`, `reference_consistency` identiques à 100% entre les deux exécutions (AC-F5-3).

#### TC-BENCH-017 - Scoring : stabilité calculée pour repetitions>=2

**Scenario Type**: Happy Path
**Impact Level**: Critical
**Priority**: High
**Related IDs**: F-5, AC-F5-4
**Test Type(s)**: Unit
**Automation Level**: Automated
**Target Layer / Location**: `backend/tests/unit/test_benchmark_scoring_v1_unit.py`
**Tags**: @backend

**Preconditions**:

- `repetitions >= 2`.

**Steps**:

1. Produire au moins 2 tentatives avec scores agrégés.
2. Déclencher le calcul de stabilité.

**Expected Outcome**:

- `stability_score` calculé et non nul (AC-F5-4).

#### TC-BENCH-018 - Parcours API E2E backend : fixture → run → résultats

**Scenario Type**: Happy Path
**Impact Level**: Important
**Priority**: Medium
**Related IDs**: F-1, F-2, F-6
**Test Type(s)**: E2E
**Automation Level**: Semi-automated
**Target Layer / Location**: TODO (harness E2E backend à définir)
**Tags**: @backend @api @e2e

**Preconditions**:

- Backend lancé (HTTP réel) sur un environnement de test.
- Broker Celery et worker disponibles (ou mode exécution test équivalent).
- Comptes de test ADMIN/ANALYST.

**Steps**:

1. HTTP POST `/api/v1/benchmark/fixtures` (ADMIN) et récupérer `{fixture_id, hash}`.
2. HTTP POST `/api/v1/benchmark/runs` (ADMIN) avec `{fixture_id, fixture_hash, model_spec, scenario_type, repetitions}`.
3. Poller HTTP GET `/api/v1/benchmark/runs/{id}` (ANALYST) jusqu’au statut `COMPLETED` (ou timeout).
4. Vérifier la présence des cases, tentatives et 5 métriques.

**Expected Outcome**:

- Workflow complet fonctionnel via HTTP réel, résultats cohérents.

**Notes / Clarifications**:

- Si aucun harness E2E backend n’existe, conserver ce scénario comme référence de validation manuelle/outillage à créer.

#### TC-BENCH-019 - Exécution asynchrone Celery : RUNNING→COMPLETED

**Scenario Type**: Happy Path
**Impact Level**: Important
**Priority**: Medium
**Related IDs**: F-7, EVT-1, EVT-2
**Test Type(s)**: Integration
**Automation Level**: Semi-automated
**Target Layer / Location**: `backend/tests/integration/test_benchmark_celery_integration.py`
**Tags**: @backend

**Preconditions**:

- Environnement d’intégration permettant l’exécution de tâches Celery (mode eager ou worker de test).

**Steps**:

1. Créer un run `PENDING`.
2. Exécuter la tâche `execute_benchmark_run(run_id)` dans le mode de test.
3. Vérifier les transitions de statut et la création des tentatives.

**Expected Outcome**:

- Statut final `COMPLETED` et événements/logs cohérents.

#### TC-BENCH-020 - Gestion d’erreur : échec LLM / exception engine → FAILED

**Scenario Type**: Negative
**Impact Level**: Critical
**Priority**: High
**Related IDs**: F-7, NFR-4, EVT-3
**Test Type(s)**: Integration
**Automation Level**: Automated
**Target Layer / Location**: `backend/tests/integration/test_benchmark_celery_integration.py`
**Tags**: @backend

**Preconditions**:

- Possibilité de forcer une exception (ex. mock de `build_model()`/appel LLM) lors de l’exécution.

**Steps**:

1. Créer un run.
2. Forcer une erreur pendant l’exécution.
3. Exécuter la tâche.
4. Lire le run via API (ou service) pour inspecter `status` et `error`.

**Expected Outcome**:

- Statut `FAILED`.
- Champ `error` renseigné.
- Les autres runs ne sont pas impactés (NFR-4).

#### TC-BENCH-021 - Traçabilité : llm_calls_count + lien analysis_run_id

**Scenario Type**: Regression
**Impact Level**: Important
**Priority**: Medium
**Related IDs**: F-8, NFR-5, DM-4
**Test Type(s)**: Unit
**Automation Level**: Automated
**Target Layer / Location**: `backend/tests/unit/test_benchmark_traceability_unit.py`
**Tags**: @backend

**Preconditions**:

- Une tentative créée avec un contexte qui expose (ou simule) les appels LLM et l’`analysis_run_id`.

**Steps**:

1. Finaliser une tentative « COMPLETED » en test.
2. Vérifier `llm_calls_count` et la présence (ou absence justifiée) de `analysis_run_id`.

**Expected Outcome**:

- `llm_calls_count` non nul pour une tentative complétée (NFR-5).

#### TC-BENCH-022 - Performance lecture résultats (p95 < 500ms)

**Scenario Type**: Regression
**Impact Level**: Minor
**Priority**: Low
**Related IDs**: NFR-1
**Test Type(s)**: Performance
**Automation Level**: Semi-automated
**Target Layer / Location**: Guide d’exécution (section 6)
**Tags**: @backend @perf

**Preconditions**:

- Base de test pré-remplie avec ~1 000 tentatives indexées (ou génération contrôlée).

**Steps**:

1. Exécuter 1 000 requêtes GET `/api/v1/benchmark/runs/{id}` (ou GET `/runs` selon besoin) en conditions identiques.
2. Mesurer la latence et calculer le p95.

**Expected Outcome**:

- p95 < 500 ms (NFR-1).

#### TC-BENCH-023 - Déterminisme bout-en-bout (mêmes inputs → mêmes scores)

**Scenario Type**: Regression
**Impact Level**: Important
**Priority**: Medium
**Related IDs**: NFR-2
**Test Type(s)**: Integration
**Automation Level**: Automated
**Target Layer / Location**: `backend/tests/integration/test_benchmark_determinism_integration.py`
**Tags**: @backend

**Preconditions**:

- Possibilité d’exécuter deux runs identiques en mode test (LLM mocké/déterministe).

**Steps**:

1. Lancer deux runs strictement identiques.
2. Comparer les scores par métrique et `aggregate_score`.

**Expected Outcome**:

- Scores identiques à 100% (NFR-2).

#### TC-BENCH-024 - Non-régression : suite backend existante

**Scenario Type**: Regression
**Impact Level**: Critical
**Priority**: High
**Related IDs**: AC-NFR-1
**Test Type(s)**: Unit
**Automation Level**: Automated
**Target Layer / Location**: CI / local
**Tags**: @backend

**Preconditions**:

- Aucune.

**Steps**:

1. Exécuter `cd backend && pytest -q`.

**Expected Outcome**:

- Zéro régression (AC-NFR-1).

#### TC-BENCH-025 - Isolation : pas d’impact mesurable pipeline trading

**Scenario Type**: Manual
**Impact Level**: Minor
**Priority**: Low
**Related IDs**: NFR-3
**Test Type(s)**: Manual
**Automation Level**: Manual
**Target Layer / Location**: Observabilité (Prometheus / traces)
**Tags**: @backend

**Preconditions**:

- Environnement proche prod (ou staging) avec pipeline trading et benchmark activés.

**Steps**:

1. Mesurer une baseline de latence p99 du pipeline trading.
2. Lancer des runs de benchmark (charge modérée).
3. Re-mesurer la latence p99 du pipeline trading.

**Expected Outcome**:

- Variation < 5% (NFR-3) ou analyser/agir si dépassement.

#### TC-BENCH-026 - Scalabilité : 50 runs simultanés

**Scenario Type**: Manual
**Impact Level**: Minor
**Priority**: Low
**Related IDs**: NFR-7
**Test Type(s)**: Manual
**Automation Level**: Manual
**Target Layer / Location**: Environnement intégration / staging
**Tags**: @backend

**Preconditions**:

- Capacité de lancer 50 runs (scripts/outil interne).

**Steps**:

1. Soumettre 50 runs simultanés (différents modèles ou mêmes modèles).
2. Observer la stabilité du système et l’achèvement des runs.

**Expected Outcome**:

- Le système supporte la charge sans dégradation critique (NFR-7), sinon documenter la limite et la mitigation (queue dédiée, throttling).

#### TC-BENCH-027 - Erreur : création fixture invalide (validation)

**Scenario Type**: Negative
**Impact Level**: Important
**Priority**: Medium
**Related IDs**: F-1
**Test Type(s)**: Integration
**Automation Level**: Automated
**Target Layer / Location**: `backend/tests/integration/test_benchmark_fixtures_integration.py`
**Tags**: @backend @api

**Preconditions**:

- Utilisateur ADMIN.

**Steps**:

1. Appeler POST `/api/v1/benchmark/fixtures` avec un payload invalide (champ requis manquant ou type incorrect).

**Expected Outcome**:

- La requête est rejetée par validation (code d’erreur de validation standard du projet, typiquement 422) et aucun enregistrement n’est persisté.

#### TC-BENCH-028 - Erreur : lancement run avec fixture inexistante

**Scenario Type**: Negative
**Impact Level**: Important
**Priority**: Medium
**Related IDs**: F-2
**Test Type(s)**: Integration
**Automation Level**: Automated
**Target Layer / Location**: `backend/tests/integration/test_benchmark_runs_integration.py`
**Tags**: @backend @api

**Preconditions**:

- Utilisateur ADMIN.

**Steps**:

1. Appeler POST `/api/v1/benchmark/runs` avec un `fixture_id` inexistant (UUID aléatoire) et un `fixture_hash` quelconque.

**Expected Outcome**:

- La requête est rejetée (code d’erreur standard du projet pour ressource introuvable, typiquement 404) et aucun run n’est créé.

#### TC-BENCH-029 - Scoring : complétude (ratio champs requis non nuls)

**Scenario Type**: Edge Case
**Impact Level**: Important
**Priority**: Medium
**Related IDs**: F-5
**Test Type(s)**: Unit
**Automation Level**: Automated
**Target Layer / Location**: `backend/tests/unit/test_benchmark_scoring_v1_unit.py`
**Tags**: @backend

**Preconditions**:

- Un schéma Pydantic attendu est connu pour un agent.

**Steps**:

1. Construire une `raw_output` valide mais avec certains champs requis à `null`/manquants.
2. Calculer `completeness_score`.

**Expected Outcome**:

- `completeness_score` est strictement entre 0.0 et 1.0 selon le ratio défini par la spec (Annexe B).

#### TC-BENCH-030 - Scoring : conformité politiques d’outils

**Scenario Type**: Negative
**Impact Level**: Important
**Priority**: Medium
**Related IDs**: F-5
**Test Type(s)**: Unit
**Automation Level**: Automated
**Target Layer / Location**: `backend/tests/unit/test_benchmark_scoring_v1_unit.py`
**Tags**: @backend

**Preconditions**:

- Des logs d’appels outils (ou structure équivalente) sont disponibles/mimables.
- `preset_kwargs` et `force_kwargs` existent dans la fixture.

**Steps**:

1. Simuler un ensemble d’appels outils conformes puis non conformes à `preset_kwargs`/`force_kwargs`.
2. Calculer `tool_policy_compliance_score`.

**Expected Outcome**:

- Le score reflète le ratio d’appels conformes (Annexe B) et diminue en présence d’appels non conformes.

#### TC-BENCH-031 - Scoring : cohérence des références (symbol/timeframe)

**Scenario Type**: Negative
**Impact Level**: Important
**Priority**: Medium
**Related IDs**: F-5
**Test Type(s)**: Unit
**Automation Level**: Automated
**Target Layer / Location**: `backend/tests/unit/test_benchmark_scoring_v1_unit.py`
**Tags**: @backend

**Preconditions**:

- Fixture avec `symbol` et `timeframe` (ou identifiants équivalents) dans ses inputs.

**Steps**:

1. Produire une `raw_output` qui référence un `symbol`/`timeframe` différent de la fixture.
2. Calculer `reference_consistency_score`.

**Expected Outcome**:

- Le score reflète l’incohérence et est inférieur à 1.0 (Annexe B).

#### TC-BENCH-032 - Exécution full-pipeline : 8 agents, 4 phases

**Scenario Type**: Regression
**Impact Level**: Minor
**Priority**: Low
**Related IDs**: F-4
**Test Type(s)**: Unit
**Automation Level**: Semi-automated
**Target Layer / Location**: `backend/tests/unit/test_benchmark_scenarios_unit.py`
**Tags**: @backend

**Preconditions**:

- Décision clarifiée sur l’inclusion de `execution-manager` (spec OQ-3).

**Steps**:

1. Exécuter le scénario `full-pipeline`.
2. Vérifier que les agents attendus sont exécutés dans l’ordre de phases défini et que les cases correspondantes sont créées.

**Expected Outcome**:

- Le scénario `full-pipeline` reflète le comportement décidé et persiste les cases/tentatives attendues.

**Notes / Clarifications**:

- TODO : figer les attentes exactes (liste d’agents, terminaison au `risk-manager` ou inclure `execution-manager`) une fois OQ-3 résolue.

#### TC-BENCH-033 - RBAC API : ADMIN write, ANALYST read, forbidden sinon

**Scenario Type**: Negative
**Impact Level**: Critical
**Priority**: High
**Related IDs**: F-6
**Test Type(s)**: Integration
**Automation Level**: Automated
**Target Layer / Location**: `backend/tests/integration/test_benchmark_rbac_integration.py`
**Tags**: @backend @api

**Preconditions**:

- Comptes/identités de test pour rôles : ADMIN, ANALYST et un rôle insuffisant.

**Steps**:

1. Vérifier qu’un rôle insuffisant ne peut pas appeler POST `/fixtures` et POST `/runs` (forbidden).
2. Vérifier qu’ANALYST peut appeler GET `/fixtures`, GET `/runs`, GET `/runs/{id}`.
3. Vérifier qu’ANALYST ne peut pas appeler les endpoints write (PATCH/DELETE fixtures, POST/DELETE runs) si la politique l’interdit.

**Expected Outcome**:

- Les règles de rôles minimaux de la spec (§8.1) sont respectées sur tous les endpoints.

## 6. Environments and Test Data

- **Unit** : pytest, sans dépendances externes.
  - DB (si nécessaire) : SQLite in-memory.
  - LLM : mock systématique.

- **Integration** : pytest + FastAPI TestClient.
  - DB : PostgreSQL de test.
  - Celery : mode test (mock enqueue) par défaut ; mode eager/worker test pour TC-BENCH-019/020 si disponible.

Données de test :

- Fixtures minimales par agent (au moins `technical-analyst`, et un set pour débat : `bullish-researcher`, `bearish-researcher`, `trader-agent`).
- Outputs bruts synthétiques (valides / invalides) pour scorer le schéma et la complétude.

## 7. Automation Plan and Implementation Mapping

Mapping attendu (guidage pour l’implémentation des tests) :

| TC-ID | Test Type(s) | Localisation cible |
|---|---|---|
| TC-BENCH-001..005 | Integration | `backend/tests/integration/test_benchmark_fixtures_integration.py` |
| TC-BENCH-006..010 | Integration | `backend/tests/integration/test_benchmark_runs_integration.py` |
| TC-BENCH-011..014 | Unit | `backend/tests/unit/test_benchmark_engine_unit.py`, `backend/tests/unit/test_benchmark_scenarios_unit.py` |
| TC-BENCH-015..017 | Unit | `backend/tests/unit/test_benchmark_scoring_v1_unit.py` |
| TC-BENCH-018 | E2E | TODO (outillage E2E backend à définir) |
| TC-BENCH-019..020 | Integration | `backend/tests/integration/test_benchmark_celery_integration.py` |
| TC-BENCH-021 | Unit | `backend/tests/unit/test_benchmark_traceability_unit.py` |
| TC-BENCH-022 | Performance | Script/outillage local (section 6) |
| TC-BENCH-023 | Integration | `backend/tests/integration/test_benchmark_determinism_integration.py` |
| TC-BENCH-024 | Unit | `cd backend && pytest -q` |
| TC-BENCH-025..026 | Manual | Runbook interne (section 5) |
| TC-BENCH-027 | Integration | `backend/tests/integration/test_benchmark_fixtures_integration.py` |
| TC-BENCH-028 | Integration | `backend/tests/integration/test_benchmark_runs_integration.py` |
| TC-BENCH-029..031 | Unit | `backend/tests/unit/test_benchmark_scoring_v1_unit.py` |
| TC-BENCH-032 | Unit | `backend/tests/unit/test_benchmark_scenarios_unit.py` |
| TC-BENCH-033 | Integration | `backend/tests/integration/test_benchmark_rbac_integration.py` |

## 8. Risks, Assumptions, and Open Questions

Hypothèses (héritées de la spec) :

- Le cœur partagé (`ALL_AGENT_FACTORIES`, `build_toolkit()`, `build_model()`, `build_formatter()`) reste stable.
- Les tests ne doivent pas appeler de vrais fournisseurs LLM : mocks obligatoires (stratégie de test).

Risques de test :

- La couverture E2E backend (HTTP réel + Celery) n’est pas standardisée dans la stratégie actuelle → risque de gap entre TestClient et runtime.

Questions ouvertes (à résoudre pour compléter l’automatisation) :

- **OQ-T1** : Où doivent vivre les tests **API E2E backend** (répertoire, harness, commandes d’exécution) ? (lié TC-BENCH-018)
- **OQ-T2** : Quel mode Celery est standard en tests d’intégration (mock strict, eager, worker dédié) pour valider les transitions RUNNING→COMPLETED/FAILED ? (lié TC-BENCH-019/020)
- **OQ-T3** : Pour le scénario `full-pipeline`, la décision OQ-3 de la spec impacte les cas attendus ; ajouter un TC dédié une fois la décision prise.
- **OQ-T4** : Quelle est la source de vérité exacte des « tool call logs » pour calculer la conformité aux politiques d’outils (mécanisme, structure, et endroit où les capturer en benchmark) afin de rendre TC-BENCH-030 robuste ?

## 9. Plan Revision Log

| Version | Date (UTC) | Auteur | Changements |
|---|---|---|---|
| 1.0 | 2026-05-11 | test-plan-writer | Création initiale du plan de test GH-24 (Lot A backend) |

## 10. Test Execution Log

| Date (UTC) | Environnement | TC exécutés | Résultat | Lien preuve | Notes |
|---|---|---|---|---|---|
