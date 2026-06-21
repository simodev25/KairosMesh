---
id: ADR-0001
decision_type: adr
created: 2026-06-21
decision_date: null
last_updated: 2026-06-21
status: Proposed
summary: "Créer un Evolution Lab découplé du pipeline live, piloté par OpenEvolve et réutilisant benchmark/backtest comme évaluateurs."
owners: ["simodev25"]
service: "benchmark/evolution-lab"
links:
  related_changes: ["GH-24"]
  supersedes: []
  superseded_by: []
  spec: []
  contracts: ["docs/api-contracts-backend.md"]
  diagrams: []
  decisions: []
---

# ADR-0001: Introduire un Evolution Lab découplé basé sur OpenEvolve

## Context

Kairos Mesh dispose déjà d'un backend benchmark asynchrone (`/api/v1/benchmark`, `BenchmarkEngine`, queue Celery dédiée), d'un Backtest Engine, de prompts versionnés en base (`prompt_templates`) et d'un frontend multi-pages sans page dédiée au benchmark ni à l'évolution. Le pipeline live reste gouverné par des frontières fortes : moteur de risque déterministe, exécution broker séparée, trading live désactivé par défaut et promotion manuelle des stratégies.

Le besoin actuel est d'ajouter un "Strategy Evolution Lab" permettant d'évaluer puis d'améliorer des prompts/modèles d'agents sans toucher au chemin live. L'intégration d'OpenEvolve ajoute un nouveau sous-système, de nouvelles tables, une nouvelle API publique FastAPI et une nouvelle page frontend. Le changement est donc cross-service, introduit une dépendance structurante et modifie le modèle de données.

## Problem Framing (Clarified)

La décision à prendre n'est pas "faut-il un écran de plus" mais "où loger un moteur d'évolution coûteux et potentiellement risqué sans contaminer le runtime live".

Le lab doit permettre :

- de sélectionner un agent et un couple provider/modèle,
- de lancer une campagne d'évolution/backtest sur des prompts candidats,
- d'observer la progression par génération et la comparaison au baseline,
- de promouvoir manuellement un candidat sans auto-activation implicite,
- de conserver traçabilité, budgets et garde-fous.

Le problème est donc un problème de frontières d'architecture, de gouvernance et d'opérabilité avant d'être un problème UI.

## Decision Drivers

1. **Isolation du live trading** — aucun impact sur `risk/`, `metaapi/` et le pipeline live.
2. **Réutilisation maximale de l'existant** — benchmark, backtest, prompts versionnés, logs LLM.
3. **Auditabilité** — provenance complète des campagnes, candidats, coûts, promotions.
4. **Contrôle des coûts** — budget campagne, plafond d'appels, arrêt anticipé.
5. **Évolutivité** — démarrer par l'évolution de prompts puis étendre aux templates/paramètres.
6. **Simplicité opératoire** — queue dédiée, annulation, lecture claire depuis le frontend.
7. **Réversibilité** — désactiver le lab sans effet sur les surfaces existantes.

## Mental Models & Techniques Used

- **First Principles** : séparer exploration offline et exécution live.
- **Systems Thinking** : considérer backend, DB, queue, API, frontend et gouvernance comme un tout.
- **Second-Order Thinking** : gérer les effets futurs sur coût, concurrence Celery et promotion de prompts.
- **KISS** : ne pas enfouir OpenEvolve dans le moteur benchmark existant.
- **Opportunity Cost** : éviter une intégration "rapide" mais coûteuse à maintenir dans le pipeline temps réel.

## Alternatives Considered

| Alternative | Description | Avantages | Inconvénients |
|---|---|---|---|
| ALT-0 | Statu quo | Zéro coût d'intégration | Aucun lab, aucune amélioration structurée |
| ALT-1 | Étendre directement le sous-système benchmark pour piloter l'évolution | Réutilisation apparente forte | Mélange orchestration d'évolution et moteur de benchmark, couplage excessif |
| ALT-2 | Nouveau sous-système `evolution` réutilisant benchmark/backtest comme évaluateurs | Isolation, lisibilité, extensibilité, gouvernance claire | Nouveau schéma DB et nouvelles routes à opérer |
| ALT-3 | Brancher OpenEvolve dans le pipeline live ou dans la gestion active des prompts | Boucle plus courte | Inacceptable sur le plan des frontières de confiance et du risque opérationnel |

## Decision

Adopter **ALT-2**.

Concrètement :

- créer un sous-système backend dédié `services/evolution/` avec ses routes `api/routes/evolution.py` et sa task Celery `tasks/evolution_task.py`,
- exécuter OpenEvolve dans une **queue Celery séparée** (`evolution`) avec limites de concurrence dédiées,
- utiliser le benchmark existant comme **évaluateur de prompts d'agents** via un adapter "shadow prompt" qui injecte un prompt candidat sans modifier `prompt_templates`,
- préparer un second adapter d'évaluation pour la **stratégie/backtest** utilisant `validation_scoring.py` et le Backtest Engine,
- stocker les campagnes/candidats/évaluations dans des tables dédiées ; les prompts actifs restent dans `prompt_templates`,
- imposer une **promotion manuelle en deux temps** : créer une nouvelle version de prompt depuis un candidat, puis activation explicite.

Schéma logique minimal retenu :

- `evolution_campaigns` : campagne, baseline, modèle, budget, statut, configuration d'évaluation,
- `evolution_candidates` : candidats générés, contenu de prompt, génération, parent, scores agrégés, provenance,
- `evolution_candidate_evaluations` : scores détaillés par run/fenêtre/split, liens vers `benchmark_runs` ou `backtest_runs`,
- `evolution_promotions` : trace de promotion vers `prompt_templates`.

Extension recommandée pour la traçabilité de coût : ajouter à `llm_call_logs` des références facultatives `evolution_campaign_id`, `evolution_candidate_id` et `phase` (`mutation`/`evaluation`).

## Trade-offs & Consequences

### Positive Outcomes

- Frontière claire entre expérimentation et production.
- Réutilisation disciplinée du benchmark et du backtest au lieu de les dupliquer.
- Promotion humaine et auditée des prompts.
- Architecture extensible vers templates/paramètres sans rework majeur.
- Lecture produit simple : page dédiée, API dédiée, états dédiés.

### Negative Outcomes

- Nouveau domaine backend à maintenir.
- Besoin de migrations SQLAlchemy/Alembic supplémentaires.
- Surcoût de stockage si les artefacts/candidats sont conservés longtemps.
- Complexité d'observabilité plus élevée qu'un simple écran frontend.

### Unresolved Questions

- Quels agents sont autorisés dans le lot initial : les 9 agents, ou un sous-ensemble priorisé ?
- Faut-il autoriser la promotion directe avec activation, ou forcer "create version" puis activation séparée ?
- Quel budget par campagne est acceptable par défaut en solo-dev (`$`, appels LLM, durée) ?
- Quel jeu de fixtures benchmark doit devenir le baseline officiel pour l'évolution des prompts ?

## Implementation Plan

1. **Lot C — Fondations backend Evolution Lab** (5 à 7 j)
   - Tables `evolution_*`, schémas Pydantic, routes CRUD/list/detail/cancel.
   - Queue Celery `evolution`, service `OpenEvolveCampaignService`, adapter évaluateur benchmark.
   - Budgets durs : `budget_usd_limit`, `max_iterations`, `max_candidates`, `max_llm_calls`, timeout.
2. **Lot D — Frontend Evolution Lab MVP** (3 à 4 j)
   - Nouvelle route lazy-loadée `/evolution-lab`.
   - Formulaire lancement campagne, liste des campagnes, détail sélectionné, courbe fitness, leaderboard candidats.
3. **Lot E — Promotion & gouvernance** (2 à 3 j)
   - Endpoint de promotion depuis candidat vers nouvelle `prompt_template`.
   - Confirmation explicite d'activation, journalisation et garde-fous de rôle.
4. **Lot F — Évaluateur stratégie/backtest et optimisation multi-objectif avancée** (5 à 8 j)
   - Adapter Backtest Engine, scoring OOS, comparaison baseline stratégie.

## Verification Criteria

- Une campagne d'évolution n'écrit jamais dans `prompt_templates` tant qu'aucune promotion explicite n'est faite.
- Aucune route ni task d'évolution n'appelle `ExecutionService` ni MetaAPI.
- L'annulation d'une campagne stoppe la task Celery et marque la campagne `CANCELLED`.
- Le détail campagne expose baseline, meilleur candidat, coût cumulé et progression par génération.
- La promotion crée une nouvelle version de prompt traçable vers `campaign_id` et `candidate_id`.
- Les workers `benchmark` et `evolution` peuvent être configurés séparément en concurrence.

## Confidence Rating

**0.86 / 1.00** — forte confiance sur la séparation des responsabilités et la réutilisation de l'existant ; confiance moyenne sur le calibrage initial des budgets et du scoring fitness, qui devra être validé empiriquement.

## Lessons Learned (Retrospective)

- Le benchmark récemment livré réduit fortement le coût d'entrée pour un lab d'évolution, mais il ne doit pas devenir un "god service".
- La vraie difficulté n'est pas OpenEvolve ; c'est la gouvernance des promotions et la maîtrise du coût.
- La présence de prompts versionnés en base permet une promotion propre si l'on garde les candidats hors de `prompt_templates` jusqu'au dernier moment.

## Examples & Usage (Optional)

- **Flux recommandé** : créer campagne `technical-analyst` → exécuter générations offline → comparer au baseline benchmark → promouvoir un candidat en nouvelle version de prompt → activer explicitement après revue.
- **Flux interdit** : campagne d'évolution qui active automatiquement un prompt ou qui branche un candidat sur le pipeline live sans validation humaine.

## References

- `docs/architecture.md`
- `docs/decision-pipeline.md`
- `docs/api-contracts-backend.md`
- `backend/app/services/benchmark/engine.py`
- `backend/app/services/benchmark/runs_service.py`
- `backend/app/api/routes/benchmark.py`
- `backend/app/api/routes/prompts.py`
- `backend/app/db/models/prompt_template.py`
- `backend/app/services/strategy/validation_scoring.py`
