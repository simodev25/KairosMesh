---
change:
  ref: GH-24
  type: feat
  status: Proposed
  slug: agent-benchmark-system-lot-a
  title: "Système de benchmarking des modèles LLM par agent de trading (Lot A)"
  owners: [engineering]
  service: benchmark
  labels: [type:feature, priority:high, change]
  version_impact: minor
  audience: internal
  security_impact: low
  risk_level: medium
  dependencies:
    internal:
      - pipeline-core (registry, agents, toolkit, model_factory)
      - llm_call_log (table, lecture seule)
      - analysis_run (table, lecture seule)
      - celery-worker
    external:
      - ollama
      - openai
      - mistral
---

# CHANGE SPECIFICATION

> **PURPOSE** : Doter Kairos Mesh d'un sous-système de benchmarking reproductible permettant de comparer objectivement les modèles LLM par agent de trading à l'aide de fixtures versionnées, d'un moteur d'exécution isolé et d'une API REST dédié — afin de remplacer la sélection de modèles basée sur l'intuition par des décisions fondées sur des données.

---

## 1. RÉSUMÉ

Kairos Mesh ne dispose d'aucun mécanisme objectif pour évaluer et comparer les performances des modèles LLM par agent de trading. Ce changement (Lot A) introduit un sous-système de benchmarking dédié composé de : fixtures versionnées gelant les entrées et configurations, un moteur d'exécution réutilisant le cœur partagé du pipeline (`ALL_AGENT_FACTORIES`, `build_toolkit()`, `build_model()`, `build_formatter()`), un moteur de scoring V1 purement objectif (validité de schéma, complétude, conformité aux politiques d'outils, cohérence des références, stabilité), et une API REST complète. Le Lot A couvre uniquement le backend ; le dashboard frontend (Lot B) et le scoring LLM-juge (Lot C) sont explicitement hors périmètre.

---

## 2. CONTEXTE

### 2.1 État Actuel

- **8 agents** opèrent à travers un pipeline en 4 phases : Phase 1 (analyse parallèle : `technical-analyst`, `news-analyst`, `market-context-analyst`), Phases 2–3 (débat : `bullish-researcher`, `bearish-researcher`, `trader-agent` comme modérateur), Phase 4 (séquentiel : décision `trader-agent`, `risk-manager`, `execution-manager`).
- Chaque agent dispose d'un schéma de sortie Pydantic strict (ex. `TechnicalAnalysisResult`, `NewsAnalysisResult`).
- Les agents utilisent des MCP tools avec `preset_kwargs` et `force_kwargs` pour la reproductibilité.
- `build_model()` supporte les fournisseurs ollama, openai et mistral.
- `_run_deterministic()` est disponible quand `llm_enabled=false`.
- La **règle de saut du débat** est documentée : si l'un quelconque des 3 agents du débat a `llm_enabled=false`, le débat entier est sauté.
- La limitation **"Single LLM provider per run"** est documentée dans `docs/limitations.md`.
- Tables existantes : `analysis_run`, `agent_step`, `llm_call_log`, `portfolio_snapshot`.
- Pattern API existant : REST sous `/api/v1/`, authentification JWT, contrôle d'accès basé sur les rôles (SUPER_ADMIN, ADMIN, TRADER_OPERATOR, ANALYST).
- Celery est utilisé pour l'exécution asynchrone des runs de trading et des backtests.

### 2.2 Points de Douleur / Lacunes

- **Sélection de modèles subjective** : le choix des modèles LLM par agent repose exclusivement sur l'intuition du développeur, sans données de comparaison.
- **Absence de reproductibilité** : aucun mécanisme ne garantit que deux évaluations d'un même modèle utilisent exactement les mêmes inputs, prompts et configurations d'outils.
- **Risque de dérive** : sans ancrage au cœur partagé du pipeline, un benchmark ad hoc divergerait du comportement réel des agents en production.
- **Coût LLM non maîtrisé** : les expérimentations informelles ne permettent pas de contrôler ni de tracer les coûts des appels LLM dédiés aux évaluations.
- **Opacité des performances** : il est impossible de justifier objectivement un changement de modèle ou de comparer deux modèles sur une tâche d'agent donnée.

---

## 3. ÉNONCÉ DU PROBLÈME

Parce qu'il n'existe aucun sous-système de benchmarking reproductible dans Kairos Mesh, les ingénieurs et analystes ne peuvent pas comparer objectivement les performances des modèles LLM par agent de trading, ce qui résulte en des décisions de sélection de modèles subjectives, une impossibilité de détecter des régressions lors d'un changement de modèle, et un risque accru d'erreurs de trading causées par un modèle sous-optimal.

---

## 4. OBJECTIFS

- **G-1** : Permettre le benchmarking reproductible de modèles LLM par agent via des fixtures versionnées gelant les inputs, prompts, skills et configuration d'outils avec un hash d'intégrité.
- **G-2** : Fournir un scoring objectif V1 couvrant : validité de schéma, complétude, conformité aux politiques d'outils, cohérence des références, et stabilité (répétabilité des sorties).
- **G-3** : Exposer les résultats de benchmark via une API REST suivant les patterns existants (`/api/v1/`), avec filtres par agent, modèle et fixture.
- **G-4** : Réutiliser le cœur partagé du pipeline de trading (`ALL_AGENT_FACTORIES`, `build_toolkit()`, `build_model()`, `build_formatter()`) pour garantir que les benchmarks reflètent le comportement réel en production.
- **G-5** : Supporter 3 types de scénarios : agent unique, bundle débat (bullish + bearish + trader), et pipeline complet.

### 4.1 Métriques de Succès / KPIs

| Métrique | Cible |
|----------|-------|
| Reproductibilité du scoring | Inputs identiques → scores identiques à 100 % |
| Couverture des métriques V1 | 5 métriques opérationnelles (validité schéma, complétude, conformité outils, cohérence références, stabilité) |
| Couverture de tests unitaires | Fixture, exécution agent unique, scoring, CRUD API — tous couverts |
| Régression sur tests existants | Zéro régression |
| Latence API résultats | Requête de résultats avec filtres < 500 ms (p95) sur 1 000 tentatives |
| Traçabilité migration | 4 tables créées par migration Alembic sans erreur |

### 4.2 Non-Objectifs

- **NG-1** : Aucun dashboard ou interface frontend — réservé au Lot B.
- **NG-2** : Aucun scoring subjectif basé sur un LLM juge — réservé au Lot C / V2.
- **NG-3** : Aucune intégration CI/CD automatisée pour les benchmarks.
- **NG-4** : Aucune modification du pipeline de trading en production.
- **NG-5** : Aucune gestion de quotas LLM ou limitation de coût automatique (seule la configuration manuelle `per-run limit` est prévue).
- **NG-6** : Aucune comparaison statistique avancée (tests de significativité, intervalles de confiance) — Lot C.

---

## 5. CAPACITÉS FONCTIONNELLES

| ID | Capacité | Justification |
|----|----------|---------------|
| F-1 | Gestion CRUD des fixtures de benchmark versionnées | Permet de geler et réutiliser de manière déterministe les conditions d'un test (inputs, prompts, skills, config outils, hash d'intégrité). |
| F-2 | Lancement de runs de benchmark avec spécification explicite du modèle (`BenchmarkModelSpec`) | Permet de comparer plusieurs modèles sur une même fixture de manière isolée et traçable. |
| F-3 | Moteur d'exécution réutilisant le cœur partagé du pipeline | Garantit que le comportement benchmarké correspond exactement au comportement en production ; prévient la dérive. |
| F-4 | Support de 3 types de scénarios : agent unique, bundle débat, pipeline complet | Couvre les différents contextes d'utilisation des agents et respecte les contraintes du pipeline (règle de saut du débat). |
| F-5 | Moteur de scoring V1 objectif et déterministe | Produit des scores comparables, reproductibles et sans dépendance à un LLM externe pour l'évaluation. |
| F-6 | API REST pour consulter et filtrer les résultats de benchmark | Permet aux ingénieurs de comparer les modèles par agent, fixture et run via des requêtes structurées. |
| F-7 | Exécution asynchrone des runs via Celery | Évite le blocage des workers HTTP pour des runs potentiellement longs ; s'aligne sur le pattern existant (backtests, analysis_run). |
| F-8 | Traçabilité vers `llm_call_log` | Permet de corréler chaque tentative de benchmark avec les appels LLM effectués, pour audit et contrôle de coût. |

### 5.1 Détail des Capacités

**F-1 — Gestion CRUD des fixtures versionnées**
Une fixture capture de manière immuable : l'identifiant de l'agent cible, les inputs bruts (symbol, timeframe, market data snapshot), la configuration complète (prompt système, skills, preset_kwargs, force_kwargs), et un hash calculé sur l'ensemble de ces éléments. La version d'une fixture ne peut être modifiée ; toute évolution crée une nouvelle fixture. Les fixtures sont listables, consultables, activables/désactivables. La suppression est logique (soft delete).

**F-2 — Lancement de run avec `BenchmarkModelSpec`**
Un run de benchmark est initié via API avec : une référence à une fixture (ID + hash vérifié), un `BenchmarkModelSpec` explicite (fournisseur, nom du modèle, paramètres de génération), et un type de scénario. Le run est accepté de manière synchrone (201 Created + run ID) et exécuté de manière asynchrone via Celery. La limite de coût par run (`max_llm_calls`) est configurable à la création du run.

**F-3 — Moteur d'exécution réutilisant le cœur partagé**
Le moteur d'exécution invoque `ALL_AGENT_FACTORIES`, `build_toolkit()`, `build_model()` et `build_formatter()` pour construire l'agent cible, exactement comme le pipeline de trading. Il n'introduit aucune logique d'agent parallèle à la production. Les sorties brutes de l'agent sont capturées intégralement pour scoring.

**F-4 — 3 types de scénarios**
- *Agent unique* : exécute un seul agent identifié par la fixture.
- *Bundle débat* : exécute `bullish-researcher`, `bearish-researcher` et `trader-agent` en séquence, en respectant la règle de saut du débat si `llm_enabled=false` pour l'un d'eux.
- *Pipeline complet* : exécute les 8 agents dans l'ordre du pipeline de production, avec les 4 phases.

**F-5 — Scoring V1 objectif et déterministe**
Le moteur de scoring évalue chaque tentative sur 5 dimensions :
1. *Validité de schéma* : la sortie de l'agent valide-t-elle le schéma Pydantic attendu ? (binaire)
2. *Complétude* : proportion de champs requis non nuls dans la sortie.
3. *Conformité aux politiques d'outils* : les appels d'outils respectent-ils `preset_kwargs` et `force_kwargs` ? (ratio d'appels conformes)
4. *Cohérence des références* : les identifiants (symbol, timeframe) dans la sortie correspondent-ils aux inputs de la fixture ?
5. *Stabilité* : sur N répétitions identiques, quel est le coefficient de variation des scores ? (mesure sur au moins 2 tentatives par run)

Le score final par tentative est un agrégat pondérable des 5 dimensions (poids configurables au niveau du run, valeurs par défaut égales).

**F-6 — API REST résultats**
Les endpoints permettent de : lister les runs avec filtres (agent, modèle, fixture, statut), consulter le détail d'un run (cases + tentatives + scores), comparer des runs sur une même fixture. Les réponses respectent le format de pagination existant du projet.

**F-7 — Exécution asynchrone via Celery**
À la création d'un run, une tâche Celery est enqueueée. Le statut du run (`PENDING`, `RUNNING`, `COMPLETED`, `FAILED`) est mis à jour de manière atomique en base. Les erreurs d'exécution sont journalisées et exposées via l'API.

**F-8 — Traçabilité `llm_call_log`**
Chaque tentative (`benchmark_attempt`) référence les entrées de `llm_call_log` générées lors de son exécution via l'`analysis_run_id` du run de benchmark. Cela permet une corrélation complète pour audit et contrôle de coût sans écriture dans `llm_call_log`.

---

## 6. FLUX UTILISATEUR & SYSTÈME

### Flux 1 — Création et exécution d'un benchmark agent unique

```
Ingénieur → POST /api/v1/benchmark/fixtures  (définit inputs + config + agent)
  → Système : valide, calcule hash, persiste fixture (benchmark_fixture)
  → Système : 201 Created { fixture_id, version, hash }

Ingénieur → POST /api/v1/benchmark/runs  (fixture_id + BenchmarkModelSpec + scénario=single-agent)
  → Système : vérifie hash fixture, crée run PENDING (benchmark_run)
  → Système : enqueue tâche Celery
  → Système : 201 Created { run_id, status: PENDING }

Celery Worker:
  → Charge fixture (inputs + config gelés)
  → Construit agent via ALL_AGENT_FACTORIES + build_toolkit() + build_model()
  → Exécute agent N fois (N configurable, min 2 pour stabilité)
  → Pour chaque exécution : capture sortie brute → calcule scores V1
  → Persiste benchmark_case + benchmark_attempt(s) avec scores
  → Met à jour run status = COMPLETED

Ingénieur → GET /api/v1/benchmark/runs/{run_id}
  → Système : retourne run + cases + tentatives + scores agrégés
```

### Flux 2 — Comparaison de deux modèles sur la même fixture

```
Ingénieur → POST /api/v1/benchmark/runs  (fixture_id=X, model=gpt-4o)
  → run_id=R1

Ingénieur → POST /api/v1/benchmark/runs  (fixture_id=X, model=mistral-large)
  → run_id=R2

(après complétion des deux runs)

Ingénieur → GET /api/v1/benchmark/runs?fixture_id=X
  → Système : retourne [R1, R2] avec scores agrégés côte à côte (filtrable par agent/modèle)
```

### Flux 3 — Benchmark bundle débat

```
Ingénieur → POST /api/v1/benchmark/runs  (fixture_id + model + scénario=debate-bundle)
Celery Worker:
  → Exécute bullish-researcher avec fixture inputs
  → Passe sortie bullish comme contexte à bearish-researcher
  → Passe sorties bullish+bearish comme contexte à trader-agent
  → Score chaque agent individuellement
  → Score cohérence inter-agents (F-5 cohérence des références)
  → Si l'un des 3 agents a llm_enabled=false → run marqué SKIPPED_DEBATE + log
```

---

## 7. PÉRIMÈTRE & FRONTIÈRES

### 7.1 Dans le Périmètre

- 4 tables de base de données : `benchmark_fixture`, `benchmark_run`, `benchmark_case`, `benchmark_attempt`
- Migration Alembic pour les 4 tables
- Moteur de scoring V1 (5 métriques objectives)
- Moteur d'exécution benchmark réutilisant le cœur partagé du pipeline
- 3 types de scénarios : agent unique, bundle débat, pipeline complet
- API REST CRUD fixtures (`/api/v1/benchmark/fixtures`)
- API REST lancement de runs (`/api/v1/benchmark/runs`)
- API REST consultation et filtrage des résultats (`/api/v1/benchmark/runs`, `/api/v1/benchmark/runs/{id}`)
- Exécution asynchrone via Celery
- Traçabilité vers `llm_call_log`
- Tests unitaires : création de fixture, exécution agent unique, scoring, CRUD API

### 7.2 Hors Périmètre

- [OUT] Dashboard ou interface frontend (Lot B)
- [OUT] Scoring subjectif par LLM juge (Lot C / V2)
- [OUT] Intégration CI/CD pour l'exécution automatique des benchmarks
- [OUT] Modification du pipeline de trading en production
- [OUT] Gestion automatique de quotas LLM ou alertes de coût
- [OUT] Comparaison statistique avancée (tests de significativité, intervalles de confiance)
- [OUT] Import/export de fixtures au format CSV ou Excel
- [OUT] API d'administration des workers Celery dédiés au benchmark
- [OUT] Support multi-tenant pour les fixtures et résultats

### 7.3 Différé / Peut-être Plus Tard

- Scoring LLM juge pour métriques subjectives (pertinence, qualité de raisonnement) — Lot C
- Dashboard de visualisation des résultats avec graphiques comparatifs — Lot B
- Intégration CI : exécution de benchmarks de régression à chaque PR
- Statistiques comparatives avancées (p-values, intervalles de confiance sur les scores)
- Alertes automatiques si un modèle dégrade un score sous un seuil configuré
- Support de benchmarks multi-symboles / multi-timeframes en un seul run
- Export des résultats en JSON/CSV pour analyse externe

---

## 8. INTERFACES & CONTRATS D'INTÉGRATION

### 8.1 Endpoints REST / HTTP

Tous les endpoints respectent le pattern existant : préfixe `/api/v1/`, authentification JWT Bearer, contrôle d'accès par rôle, format de pagination uniforme, codes HTTP standard.

**Fixtures**

| Méthode | Endpoint | Rôle minimum | Description |
|---------|----------|--------------|-------------|
| POST | `/api/v1/benchmark/fixtures` | ADMIN | Créer une fixture versionnée |
| GET | `/api/v1/benchmark/fixtures` | ANALYST | Lister les fixtures (filtres : agent, actif/inactif) |
| GET | `/api/v1/benchmark/fixtures/{id}` | ANALYST | Détail d'une fixture (avec hash) |
| PATCH | `/api/v1/benchmark/fixtures/{id}` | ADMIN | Activer / désactiver une fixture |
| DELETE | `/api/v1/benchmark/fixtures/{id}` | ADMIN | Suppression logique (soft delete) |

**Runs de benchmark**

| Méthode | Endpoint | Rôle minimum | Description |
|---------|----------|--------------|-------------|
| POST | `/api/v1/benchmark/runs` | ADMIN | Lancer un run (accepté, tâche Celery enqueued) |
| GET | `/api/v1/benchmark/runs` | ANALYST | Lister les runs (filtres : agent, modèle, fixture, statut, date) |
| GET | `/api/v1/benchmark/runs/{id}` | ANALYST | Détail d'un run : cases + tentatives + scores |
| DELETE | `/api/v1/benchmark/runs/{id}` | ADMIN | Annuler un run PENDING |

**Contrat de création d'un run (corps de requête POST)**

```
{
  fixture_id: UUID,
  fixture_hash: string,          // vérifié côté serveur
  model_spec: {
    provider: "ollama" | "openai" | "mistral",
    model_name: string,
    parameters: { temperature?, top_p?, max_tokens?, ... }
  },
  scenario_type: "single-agent" | "debate-bundle" | "full-pipeline",
  repetitions: integer (min: 2, défaut: 3),
  max_llm_calls: integer (optionnel, limite de coût)
}
```

**Contrat de réponse résultats (GET /runs/{id})**

```
{
  run_id: UUID,
  status: "PENDING" | "RUNNING" | "COMPLETED" | "FAILED" | "SKIPPED_DEBATE",
  fixture_id: UUID,
  model_spec: { ... },
  scenario_type: string,
  started_at: datetime,
  completed_at: datetime,
  cases: [
    {
      case_id: UUID,
      agent_name: string,
      attempts: [
        {
          attempt_id: UUID,
          attempt_number: integer,
          raw_output: object,
          scores: {
            schema_validity: float,      // 0.0 ou 1.0
            completeness: float,         // 0.0 – 1.0
            tool_policy_compliance: float,
            reference_consistency: float,
            stability: float             // coefficient de variation normalisé
          },
          aggregate_score: float,
          llm_calls_count: integer
        }
      ],
      aggregate_score: float
    }
  ],
  run_aggregate_score: float
}
```

### 8.2 Événements / Messages

| ID | Événement | Producteur | Consommateur | Description |
|----|-----------|------------|--------------|-------------|
| EVT-1 | `benchmark.run.started` | API (Celery enqueue) | Celery Worker | Déclenche l'exécution du run benchmark |
| EVT-2 | `benchmark.run.completed` | Celery Worker | — (log) | Signale la fin d'un run (succès ou échec) |
| EVT-3 | `benchmark.run.failed` | Celery Worker | — (log) | Signale un échec d'exécution avec cause |

Les événements sont transmis via la file Celery existante (Redis/RabbitMQ). Aucun nouveau broker n'est introduit.

### 8.3 Impact sur le Modèle de Données

| ID | Élément | Description |
|----|---------|-------------|
| DM-1 | `benchmark_fixture` | Nouvelle table. Stocke les fixtures versionnées : `id` (UUID PK), `agent_name`, `version` (integer), `hash` (SHA-256 de la config), `inputs` (JSONB), `config` (JSONB : prompt, skills, preset_kwargs, force_kwargs), `is_active` (boolean), `created_at`, `created_by` (FK user). Index sur `(agent_name, is_active)`. |
| DM-2 | `benchmark_run` | Nouvelle table. Représente un run : `id` (UUID PK), `fixture_id` (FK DM-1), `fixture_hash` (string, snapshot au lancement), `model_spec` (JSONB : provider, model_name, parameters), `scenario_type` (enum), `status` (enum), `repetitions`, `max_llm_calls`, `started_at`, `completed_at`, `error` (text nullable), `created_by` (FK user). Index sur `(fixture_id, status)`, `(created_by, created_at)`. |
| DM-3 | `benchmark_case` | Nouvelle table. Un case = un agent dans un run : `id` (UUID PK), `run_id` (FK DM-2), `agent_name`, `aggregate_score` (float nullable), `case_order` (integer, pour scénarios séquentiels). Index sur `(run_id, agent_name)`. |
| DM-4 | `benchmark_attempt` | Nouvelle table. Une tentative d'exécution = une répétition d'un case : `id` (UUID PK), `case_id` (FK DM-3), `attempt_number`, `raw_output` (JSONB), `schema_validity_score` (float), `completeness_score` (float), `tool_policy_compliance_score` (float), `reference_consistency_score` (float), `stability_score` (float nullable, calculé après N tentatives), `aggregate_score` (float), `llm_calls_count` (integer), `analysis_run_id` (UUID nullable, FK lecture seule vers `analysis_run` si créé), `executed_at`. Index sur `(case_id, attempt_number)`. |

### 8.4 Intégrations Externes

| Intégration | Nature | Impact |
|-------------|--------|--------|
| Fournisseurs LLM (ollama, openai, mistral) | Lecture (appels d'inférence via `build_model()`) | Les benchmarks génèrent des appels LLM réels facturés ; le champ `max_llm_calls` permet de limiter le coût par run. |
| Celery / Redis / RabbitMQ | File de tâches existante | Réutilisation du broker existant, aucune modification de configuration requise. |

### 8.5 Compatibilité Ascendante

- Aucune modification des tables existantes (`analysis_run`, `agent_step`, `llm_call_log`, `portfolio_snapshot`).
- Le cœur du pipeline (`registry.py`, `agents.py`, `toolkit.py`, `model_factory.py`) est utilisé en lecture seule ; aucune modification de ses signatures.
- Les endpoints existants sous `/api/v1/` ne sont pas modifiés.
- La migration Alembic est additive uniquement (nouvelles tables, aucun `ALTER TABLE` sur les tables existantes).

---

## 9. EXIGENCES NON FONCTIONNELLES (NFR)

| ID | Exigence | Seuil |
|----|----------|-------|
| NFR-1 | **Performance API** : latence des requêtes de consultation de résultats (GET /runs, GET /runs/{id}) | p95 < 500 ms pour 1 000 tentatives indexées |
| NFR-2 | **Déterminisme du scoring** : reproductibilité des scores sur des inputs identiques | 100 % — même inputs → même scores, sans exception |
| NFR-3 | **Isolation** : les runs de benchmark n'impactent pas les performances du pipeline de trading en production | Aucune dégradation mesurable des temps de réponse du pipeline (< 5 % d'augmentation de latence p99) |
| NFR-4 | **Tolérance aux pannes** : un run échoué n'affecte pas les autres runs ni le pipeline de trading | Isolation par tâche Celery ; statut `FAILED` mis à jour sans impact sur l'état global |
| NFR-5 | **Traçabilité des coûts** : chaque tentative enregistre le nombre d'appels LLM effectués | `llm_calls_count` non nul pour toute tentative COMPLETED |
| NFR-6 | **Intégrité des fixtures** : toute tentative d'exécution d'un run avec un hash de fixture ne correspondant pas à la fixture en base est rejetée | Rejet HTTP 409 avec message d'erreur explicite |
| NFR-7 | **Scalabilité** : le sous-système doit supporter jusqu'à 50 runs simultanés sans dégradation | Limité par la capacité de la file Celery existante (configurable) |

---

## 10. TÉLÉMÉTRIE & OBSERVABILITÉ

| Type | Élément | Description |
|------|---------|-------------|
| **Log** | `benchmark.run.started` | Log INFO à la création d'un run (run_id, fixture_id, model_spec, scenario_type) |
| **Log** | `benchmark.run.completed` | Log INFO à la complétion d'un run (run_id, duration, aggregate_score, llm_calls_total) |
| **Log** | `benchmark.run.failed` | Log ERROR à l'échec d'un run (run_id, error_type, stack_trace) |
| **Log** | `benchmark.attempt.scored` | Log DEBUG par tentative (attempt_id, scores individuels, aggregate) |
| **Métrique** | `benchmark_runs_total` | Compteur Prometheus : nombre de runs par statut (COMPLETED, FAILED, SKIPPED_DEBATE) |
| **Métrique** | `benchmark_run_duration_seconds` | Histogramme Prometheus : durée des runs par scénario_type |
| **Métrique** | `benchmark_llm_calls_total` | Compteur Prometheus : appels LLM consommés par le sous-système de benchmark |
| **Métrique** | `benchmark_aggregate_score` | Gauge Prometheus : dernier score agrégé par (agent_name, model_name) |
| **Trace** | Span Celery pour chaque run | Trace OpenTelemetry de la durée totale d'exécution du run, incluant les sous-spans par agent |

---

## 11. RISQUES & MITIGATIONS

| ID | Risque | Impact | Probabilité | Mitigation | Risque Résiduel |
|----|--------|--------|-------------|------------|-----------------|
| RSK-1 | Dérive entre le moteur d'exécution benchmark et le pipeline de trading si le cœur partagé évolue | H | M | Réutilisation stricte de `ALL_AGENT_FACTORIES`, `build_toolkit()`, `build_model()`, `build_formatter()` sans fork ; tests d'intégration vérifiant la cohérence à chaque PR | Faible — couplage fort intentionnel |
| RSK-2 | Coût LLM incontrôlé lors de benchmarks intensifs | M | M | Champ `max_llm_calls` configurable par run ; logs de coût traçables via `llm_calls_count` | Faible — limitation manuelle disponible |
| RSK-3 | Scores de stabilité non calculables si N < 2 répétitions | M | L | Contrainte `repetitions >= 2` enforced à la validation de l'API ; score de stabilité marqué null si N = 1 | Très faible |
| RSK-4 | Violation de la règle de saut du débat dans le scénario debate-bundle | H | L | Logique de saut explicite dans le moteur d'exécution ; run marqué `SKIPPED_DEBATE` + log warn si applicable | Très faible |
| RSK-5 | Surcharge du broker Celery si trop de runs simultanés | M | L | File dédiée optionnelle pour les tâches benchmark (configurable) ; documentation de la limite de 50 runs simultanés | Faible |
| RSK-6 | Hash de fixture manipulé / contournement de l'intégrité | M | L | Rejet HTTP 409 si `fixture_hash` ne correspond pas ; hash calculé côté serveur à la création, non modifiable | Faible |

---

## 12. HYPOTHÈSES

- Le cœur partagé du pipeline (`ALL_AGENT_FACTORIES`, `build_toolkit()`, `build_model()`, `build_formatter()`) est stable et son interface publique n'est pas modifiée pendant le développement du Lot A.
- La table `llm_call_log` est accessible en lecture et sa structure ne change pas.
- Celery, Redis et/ou RabbitMQ sont opérationnels et correctement configurés dans l'environnement de déploiement.
- Les fournisseurs LLM (ollama, openai, mistral) sont accessibles depuis les workers Celery lors de l'exécution des benchmarks.
- Le mécanisme JWT et le système de rôles RBAC existants sont suffisants pour protéger les nouveaux endpoints sans modification.
- Les schémas Pydantic de sortie de chaque agent (`TechnicalAnalysisResult`, `NewsAnalysisResult`, etc.) sont stables et documentés.
- `_run_deterministic()` est disponible pour les tests unitaires ne nécessitant pas d'appels LLM réels.

---

## 13. DÉPENDANCES

| Direction | Élément | Notes |
|-----------|---------|-------|
| Dépend de | Cœur partagé du pipeline : `registry.py`, `agents.py`, `toolkit.py`, `model_factory.py` | Utilisé en lecture seule ; aucune modification permise dans ce changement |
| Dépend de | Table `llm_call_log` | Lecture seule pour corrélation et comptage d'appels |
| Dépend de | Celery worker infrastructure (Redis/RabbitMQ) | Réutilisation de la configuration existante |
| Dépend de | Système d'authentification JWT + RBAC | Réutilisation sans modification |
| Dépend de | Fournisseurs LLM (ollama, openai, mistral) | Accès réseau requis depuis les workers |
| Bloque | GH-25 (Lot B — dashboard frontend benchmark) | Le frontend ne peut être développé sans l'API REST de ce Lot A |
| Bloque | GH-26 (Lot C — scoring LLM juge) | Le scoring subjectif s'appuie sur les structures de données et l'API du Lot A |

---

## 14. QUESTIONS OUVERTES

| ID | Question | Contexte | Statut |
|----|----------|---------|--------|
| OQ-1 | La file Celery de benchmark doit-elle être isolée de la file de trading pour éviter la contention ? | RSK-5 — en cas de 50+ runs simultanés, un pic de benchmark pourrait retarder les analysis_run de trading | Décision attendue du développeur avant la phase delivery |
| OQ-2 | Les poids de l'agrégation des 5 métriques de scoring doivent-ils être configurables par fixture ou uniquement par run ? | Permettre des poids par fixture offre plus de flexibilité mais complexifie le modèle de données | Décision attendue du développeur |
| OQ-3 | Le scénario "pipeline complet" doit-il inclure l'`execution-manager` (avec risque d'ordre réel) ou s'arrêter au `risk-manager` ? | Sécurité : inclure `execution-manager` en mode simulation uniquement ; clarifier la configuration par défaut | Décision attendue — consulter `@architect` si nécessaire |

---

## 15. JOURNAL DES DÉCISIONS

| ID | Décision | Justification | Date |
|----|----------|---------------|------|
| DEC-1 | Sous-système dédié (ALT-2) plutôt qu'extension du pipeline existant | Isolation complète du code de benchmarking ; pas de risque de régression sur le pipeline de trading ; couplage via interfaces partagées uniquement | 2026-05-11 |
| DEC-2 | Fixtures versionnées avec hash d'intégrité | Reproductibilité garantie ; détection de toute modification accidentelle des conditions d'un test | 2026-05-11 |
| DEC-3 | `BenchmarkModelSpec` explicite plutôt qu'`AgentModelSelector` | Contrôle total du modèle utilisé pour chaque run ; évite l'ambiguïté de sélection automatique | 2026-05-11 |
| DEC-4 | Scoring V1 objectif uniquement (pas de LLM juge) | Déterminisme garanti ; coût nul d'évaluation ; LLM juge différé au Lot C pour éviter la complexité prématurée | 2026-05-11 |
| DEC-5 | 4 tables distinctes : `benchmark_fixture`, `benchmark_run`, `benchmark_case`, `benchmark_attempt` | Modélisation claire de la hiérarchie fixture → run → case → tentative ; queryabilité optimale avec index ciblés | 2026-05-11 |
| DEC-6 | 3 types de scénarios : agent unique, bundle débat, pipeline complet | Couvre tous les contextes d'utilisation des agents ; respecte la règle de saut du débat documentée | 2026-05-11 |
| DEC-7 | Exécution asynchrone via Celery | Cohérence avec les patterns existants (backtests, analysis_run) ; évite le blocage des workers HTTP | 2026-05-11 |

---

## 16. COMPOSANTS AFFECTÉS (NIVEAU MACRO)

| Composant | Impact |
|-----------|--------|
| Backend — module `benchmark` | Nouveau — moteur d'exécution, moteur de scoring, service de gestion des fixtures et runs |
| Backend — API REST (`/api/v1/benchmark/`) | Nouveau — 9 endpoints (fixtures CRUD + runs launch/query/cancel) |
| Backend — workers Celery | Mis à jour — enregistrement des tâches de benchmark |
| Base de données PostgreSQL | Mis à jour — 4 nouvelles tables via migration Alembic |
| Cœur partagé du pipeline (`registry`, `agents`, `toolkit`, `model_factory`) | Utilisé en lecture — aucune modification |
| Table `llm_call_log` | Utilisée en lecture — aucune modification |
| Prometheus / OpenTelemetry | Mis à jour — nouvelles métriques et spans benchmark |

---

## 17. CRITÈRES D'ACCEPTATION

### Gestion des fixtures (F-1)

| ID | Critère | Lié à |
|----|---------|-------|
| AC-F1-1 | **Étant donné** un payload de création de fixture valide (agent_name, inputs, config), **quand** un ADMIN poste sur `/api/v1/benchmark/fixtures`, **alors** la fixture est persistée avec un hash SHA-256 calculé côté serveur, `version=1`, `is_active=true`, et la réponse est HTTP 201 avec `fixture_id` et `hash`. | F-1 |
| AC-F1-2 | **Étant donné** une fixture existante, **quand** un ADMIN tente de modifier ses `inputs` ou `config`, **alors** la requête est rejetée avec HTTP 422 et un message expliquant qu'une fixture est immuable. | F-1 |
| AC-F1-3 | **Étant donné** une liste de fixtures, **quand** un ANALYST consulte `/api/v1/benchmark/fixtures?agent_name=technical-analyst`, **alors** seules les fixtures de cet agent sont retournées, avec pagination. | F-1 |

### Lancement de run (F-2, F-7)

| ID | Critère | Lié à |
|----|---------|-------|
| AC-F2-1 | **Étant donné** une fixture active et un `BenchmarkModelSpec` valide, **quand** un ADMIN poste sur `/api/v1/benchmark/runs`, **alors** un run est créé en statut PENDING, une tâche Celery est enqueueée, et la réponse est HTTP 201 avec `run_id`. | F-2, F-7 |
| AC-F2-2 | **Étant donné** un payload de création de run avec un `fixture_hash` ne correspondant pas au hash stocké, **quand** l'API reçoit la requête, **alors** la requête est rejetée avec HTTP 409 et un message d'erreur explicite. | F-2, NFR-6 |
| AC-F2-3 | **Étant donné** un run en statut PENDING, **quand** un ADMIN appelle DELETE `/api/v1/benchmark/runs/{id}`, **alors** le run est annulé (statut CANCELLED) et la tâche Celery est révoquée. | F-2 |

### Exécution agent unique (F-3, F-4)

| ID | Critère | Lié à |
|----|---------|-------|
| AC-F4-1 | **Étant donné** un run de scénario `single-agent` avec `repetitions=3`, **quand** le Celery worker exécute le run, **alors** exactement 3 `benchmark_attempt` sont créées sous le `benchmark_case` correspondant à l'agent unique, et le statut du run passe à COMPLETED. | F-3, F-4 |
| AC-F4-2 | **Étant donné** un run en cours d'exécution, **quand** on inspecte les appels aux fonctions du cœur partagé, **alors** `ALL_AGENT_FACTORIES`, `build_toolkit()`, `build_model()`, `build_formatter()` sont appelés avec les paramètres de la fixture, sans fork de ces fonctions. | F-3 |

### Bundle débat (F-4)

| ID | Critère | Lié à |
|----|---------|-------|
| AC-F4-3 | **Étant donné** un run de scénario `debate-bundle`, **quand** le Celery worker exécute le run, **alors** 3 `benchmark_case` sont créés (bullish-researcher, bearish-researcher, trader-agent), chacun avec ses tentatives, et les sorties de bullish-researcher sont passées en contexte à bearish-researcher, puis les deux sorties au trader-agent. | F-4 |
| AC-F4-4 | **Étant donné** un run de scénario `debate-bundle` où `llm_enabled=false` pour l'un des 3 agents, **quand** le worker tente d'exécuter, **alors** le run passe en statut `SKIPPED_DEBATE` avec un log WARN explicite, et aucune tentative n'est créée. | F-4, NFR-4 |

### Scoring V1 (F-5)

| ID | Critère | Lié à |
|----|---------|-------|
| AC-F5-1 | **Étant donné** une tentative dont la sortie brute valide le schéma Pydantic de l'agent, **quand** le moteur de scoring calcule `schema_validity_score`, **alors** le score est exactement 1.0. | F-5 |
| AC-F5-2 | **Étant donné** une tentative dont la sortie brute ne valide pas le schéma Pydantic de l'agent, **quand** le moteur de scoring calcule `schema_validity_score`, **alors** le score est exactement 0.0. | F-5 |
| AC-F5-3 | **Étant donné** des inputs identiques exécutés deux fois (mêmes fixture, modèle, scénario), **quand** les scores V1 sont calculés pour chaque tentative, **alors** les scores `schema_validity`, `completeness`, `tool_policy_compliance` et `reference_consistency` sont identiques à 100 %. | F-5, NFR-2 |
| AC-F5-4 | **Étant donné** un run avec `repetitions >= 2`, **quand** toutes les tentatives sont scorées, **alors** le `stability_score` est calculé et non nul pour le case. | F-5 |

### Consultation des résultats (F-6)

| ID | Critère | Lié à |
|----|---------|-------|
| AC-F6-1 | **Étant donné** des runs complétés, **quand** un ANALYST consulte `/api/v1/benchmark/runs?fixture_id=X&agent_name=technical-analyst`, **alors** seuls les runs correspondant aux deux filtres sont retournés, avec pagination et scores agrégés. | F-6 |
| AC-F6-2 | **Étant donné** un run COMPLETED, **quand** un ANALYST consulte `/api/v1/benchmark/runs/{id}`, **alors** la réponse inclut les cases, tentatives, scores individuels des 5 métriques, `aggregate_score` par tentative, et `aggregate_score` par case, en moins de 500 ms (p95). | F-6, NFR-1 |

### Non-régression (NFR)

| ID | Critère | Lié à |
|----|---------|-------|
| AC-NFR-1 | **Étant donné** la suite de tests existante du projet, **quand** le Lot A est intégré, **alors** zéro test préexistant ne régresse (passage de la CI sans erreur). | NFR-3, NFR-4 |

---

## 18. DÉPLOIEMENT & GESTION DU CHANGEMENT (NIVEAU MACRO)

- **Ordre de livraison** : migration Alembic en premier (backward compatible, tables nouvelles uniquement) → moteur de scoring et d'exécution → API REST → tâches Celery → tests.
- **Stratégie de merge** : PR unique par lot de composants cohérents ; aucun merge sans CI verte.
- **Rollback** : la migration est rollbackable via `alembic downgrade` sans impact sur les tables existantes.
- **Communication** : aucune communication externe requise (sous-système internal, Lot A).
- **Activation** : le sous-système est actif dès le déploiement ; aucun feature flag requis pour le Lot A.

---

## 19. MIGRATION / SEEDING DES DONNÉES (SI APPLICABLE)

- **Migration Alembic** : création additive des 4 tables (`benchmark_fixture`, `benchmark_run`, `benchmark_case`, `benchmark_attempt`) avec leurs index et contraintes de clés étrangères.
- **Seeding initial** : aucun seeding de données de production requis. Des fixtures d'exemple peuvent être créées via les scripts de développement existants.
- **Rollback** : `alembic downgrade` supprime les 4 nouvelles tables sans altérer les tables existantes.

---

## 20. REVUE CONFIDENTIALITÉ / CONFORMITÉ

- Les fixtures peuvent contenir des données de marché (market data snapshots) : ces données restent internes et ne sont pas exposées à des tiers.
- Les sorties brutes des agents (`raw_output` en JSONB) peuvent contenir des analyses de marché sensibles : accès restreint aux rôles ANALYST et supérieurs.
- Aucune donnée personnelle identifiable (PII) n'est traitée dans ce sous-système.
- Pas de transfert de données vers des services externes au-delà des appels LLM existants (déjà couverts par la politique de confidentialité en vigueur).

---

## 21. POINTS DE SÉCURITÉ

- **Authentification** : tous les endpoints benchmark sont protégés par JWT Bearer token (pattern existant, aucune dérogation).
- **Autorisation** : les opérations d'écriture (création de fixture, lancement de run, annulation) sont réservées au rôle ADMIN minimum ; la lecture est accessible à ANALYST.
- **Intégrité des fixtures** : hash SHA-256 vérifié côté serveur à chaque lancement de run (DEC-2). Toute manipulation du hash côté client entraîne un rejet HTTP 409.
- **Injection** : les `inputs` et `config` des fixtures sont stockés en JSONB et jamais interpolés dans des requêtes SQL brutes ; utilisation de l'ORM SQLAlchemy.
- **Limite de coût LLM** : le champ `max_llm_calls` limite l'exposition aux coûts d'appels LLM non maîtrisés (RSK-2).
- **Zone critique** : le moteur de benchmark accède au cœur du pipeline en lecture seule ; aucune modification de `backend/app/risk/` n'est incluse dans ce changement.

---

## 22. IMPACT SUR LA MAINTENANCE & LES OPÉRATIONS

- **Monitoring additionnel** : 4 nouvelles métriques Prometheus et nouveaux spans OpenTelemetry à intégrer dans les dashboards existants.
- **Stockage** : les tables `benchmark_attempt` avec `raw_output` JSONB peuvent croître significativement à haute fréquence de benchmarking — prévoir une politique de rétention (recommandé : 90 jours, configurable).
- **Workers Celery** : aucun worker dédié requis initialement ; les tâches benchmark s'exécutent sur les workers existants. Si contention détectée, une file dédiée peut être configurée (OQ-1).
- **Documentation opérationnelle** : les commandes de gestion des fixtures et runs doivent être documentées dans `docs/development-guide.md` lors de la phase system_spec_update.

---

## 23. GLOSSAIRE

| Terme | Définition |
|-------|------------|
| Fixture | Ensemble immuable et versionné d'inputs, de configuration et de hash d'intégrité définissant les conditions reproductibles d'un benchmark pour un agent donné. |
| Run de benchmark | Exécution d'un scénario de benchmark pour une fixture et un modèle donnés, produisant des cases et tentatives scorées. |
| Case | Unité d'exécution d'un run pour un agent spécifique (un run multi-agents produit plusieurs cases). |
| Tentative (Attempt) | Une exécution unique d'un case (une répétition) ; un case a `repetitions` tentatives. |
| BenchmarkModelSpec | Spécification explicite du modèle LLM utilisé pour un run (fournisseur, nom, paramètres de génération). |
| Scoring V1 | Ensemble des 5 métriques objectives de scoring du Lot A : validité schéma, complétude, conformité outils, cohérence références, stabilité. |
| Bundle débat | Scénario regroupant l'exécution séquentielle des 3 agents du débat : bullish-researcher, bearish-researcher, trader-agent. |
| Pipeline complet | Scénario exécutant les 8 agents dans l'ordre du pipeline de production (4 phases). |
| Cœur partagé | Ensemble des fonctions partagées du pipeline de trading : `ALL_AGENT_FACTORIES`, `build_toolkit()`, `build_model()`, `build_formatter()`. |
| Dérive | Divergence entre le comportement d'un agent en benchmark et en production, causée par des implémentations parallèles non synchronisées. |
| Soft delete | Suppression logique d'un enregistrement (marquage `is_active=false`) sans suppression physique de la base. |

---

## 24. ANNEXES

### Annexe A — Structure de la hiérarchie de données benchmark

```
benchmark_fixture (DM-1)
  └── benchmark_run (DM-2)  [1 fixture → N runs]
        └── benchmark_case (DM-3)  [1 run → 1 à 8 cases selon scénario]
              └── benchmark_attempt (DM-4)  [1 case → repetitions tentatives]
```

### Annexe B — Métriques de scoring V1 — Définitions formelles

| Métrique | Type | Définition |
|----------|------|------------|
| `schema_validity_score` | Binaire [0.0, 1.0] | 1.0 si la sortie brute de l'agent valide le schéma Pydantic de l'agent cible sans erreur ; 0.0 sinon |
| `completeness_score` | Continue [0.0, 1.0] | Nombre de champs requis non nuls / Nombre total de champs requis dans le schéma |
| `tool_policy_compliance_score` | Continue [0.0, 1.0] | Nombre d'appels d'outils conformes à `preset_kwargs` ET `force_kwargs` / Nombre total d'appels d'outils |
| `reference_consistency_score` | Continue [0.0, 1.0] | Nombre d'identifiants référencés (symbol, timeframe, etc.) dans la sortie correspondant aux inputs de la fixture / Nombre total d'identifiants attendus |
| `stability_score` | Continue [0.0, 1.0] | 1 - CV(aggregate_scores) où CV = écart-type / moyenne des scores agrégés sur les N répétitions d'un case ; 1.0 = parfaitement stable |

### Annexe C — Règle de saut du débat appliquée au scénario debate-bundle

Conformément à la documentation du pipeline (`docs/decision-pipeline.md`) : si l'un quelconque des agents `bullish-researcher`, `bearish-researcher` ou `trader-agent` a `llm_enabled=false` au moment de l'exécution, **le scénario debate-bundle entier** est marqué `SKIPPED_DEBATE` et aucune tentative n'est créée. Cette règle est identique à celle appliquée dans le pipeline de trading en production.

---

## 25. HISTORIQUE DU DOCUMENT

| Version | Date | Auteur | Changements |
|---------|------|--------|-------------|
| 1.0 | 2026-05-11 | @spec-writer | Spécification initiale — Lot A du système de benchmarking LLM |

---

## DIRECTIVES D'AUTHORING

Cette spécification a été rédigée à partir des éléments suivants :
- Résumé de la session de planification fourni dans le contexte de la conversation (GH-24)
- Documentation système existante : `docs/architecture.md`, `docs/agents.md`, `docs/decision-pipeline.md`, `docs/limitations.md`
- Décisions architecturales validées par `@architect` (DEC-1 à DEC-7)
- Conventions du projet : `.samourai/core/governance/conventions/unified-change-convention-tracker-agnostic-specification.md`

Les informations manquantes ou ambiguës ont été capturées dans la section 14 (QUESTIONS OUVERTES) plutôt qu'inventées.

## CHECKLIST DE VALIDATION

- [x] `change.ref` correspond au `workItemRef` fourni (GH-24)
- [x] `owners` contient au moins une entrée (engineering)
- [x] `status` est "Proposed"
- [x] Toutes les sections présentes dans l'ordre (1 à 25 + directives + checklist)
- [x] Préfixes d'ID cohérents et uniques (F-, AC-, NFR-, RSK-, DEC-, DM-, OQ-, EVT-)
- [x] Les critères d'acceptation référencent au moins un ID F-/NFR- et utilisent le format Étant donné/Quand/Alors
- [x] Les NFR incluent des valeurs mesurables
- [x] Les risques incluent Impact & Probabilité (H/M/L)
- [x] Aucun détail d'implémentation (pas de chemins de fichiers de code, pas de tâches étape par étape)
- [x] Aucun contenu dupliqué depuis les docs liés
- [x] Le front matter valide selon les règles front_matter_rules
