---
change:
  ref: GH-28
  type: test-plan
  status: Proposed
---

# TEST PLAN — GH-28 Evolution Lab

## 1. Stratégie de test

## Objectif

Valider que l'Evolution Lab fonctionne offline, respecte les bornes de coût, n'impacte pas le pipeline trading, et permet une promotion manuelle fiable des candidats prompts/skills.

## Niveaux de test

1. **Unitaires backend**
   - `EvolutionService` (CRUD, transitions d'état, bornes)
   - `Evaluator` (adaptation BenchmarkEngine)
   - `Mutator` (format candidats + validation)
   - `Engine` (orchestration stop/cancel/budget)
2. **Tests API backend**
   - Endpoints `POST/GET/cancel/candidates/fitness-series/promote`
3. **Tests async Celery (intégration ciblée)**
   - `run_evolution_campaign` queue `evolution`
4. **Tests frontend**
   - Services API evolution
   - Composants page `/evolution-lab`
   - Build Vite
5. **Non-régression**
   - BenchmarkEngine GH-24
   - Pipeline existant (sans impact risk/live)

## Commandes de validation

```bash
cd backend && pytest -q
cd frontend && npm run build
```

E2E frontend si composants visuels critiques impactés:

```bash
cd frontend && npx playwright test
```

---

## 2. Matrice AC → Tests

| AC | Description | Tests associés |
|---|---|---|
| AC-1 | Création + lancement campagne | T-API-01, T-SVC-01, T-CEL-01 |
| AC-2 | Annulation campagne | T-API-04, T-ENG-04 |
| AC-3 | Évaluation benchmark persistée | T-EVAL-01, T-EVAL-02, T-API-05 |
| AC-4 | Arrêt sur bornes coût/calls | T-ENG-02, T-ENG-03 |
| AC-5 | Endpoint fitness-series | T-API-07 |
| AC-6 | Promotion manuelle tracée | T-API-08, T-SVC-06 |
| AC-7 | Pas d'auto-promotion | T-ENG-05 |
| AC-8 | Route + tabs frontend | T-FE-01, T-FE-02 |
| AC-9 | Détail campagne (graph + leaderboard + log) | T-FE-05, T-FE-06 |
| AC-10 | Accessibilité de base | T-FE-08 |

---

## 3. Cas de test détaillés

## 3.1 Unitaires service/orchestrateur (T-SVC / T-ENG)

### T-SVC-01 — create_campaign valide payload et persiste
- Given un payload valide
- When `EvolutionService.create_campaign()` est appelé
- Then une campagne `pending` est créée avec bornes enregistrées.

### T-SVC-02 — create_campaign rejette bornes invalides
- Given `max_iterations=0` ou `budget_usd_limit<0`
- When création
- Then erreur de validation.

### T-SVC-03 — list_campaigns filtre par agent/status
- Given plusieurs campagnes
- When filtre agent/status
- Then seules les campagnes correspondantes sont retournées.

### T-SVC-04 — get_candidates renvoie ordre attendu
- Given candidats multi-générations
- When listing
- Then tri stable (generation asc ou fitness desc selon paramètre).

### T-SVC-05 — fitness-series agrège correctement
- Given évaluations persistées
- When série demandée
- Then points par génération cohérents (best/avg).

### T-SVC-06 — promote_candidate crée trace promotion
- Given candidat évalué et promote flags valides
- When promote
- Then `evolution_promotions` inséré avec IDs promus.

### T-ENG-01 — orchestration baseline + génération 1
- Given campagne prête
- When engine run
- Then baseline + candidats sont créés et évalués.

### T-ENG-02 — stop sur `max_llm_calls`
- Given max_llm_calls faible
- When run atteint limite
- Then statut terminal explicite, plus de génération.

### T-ENG-03 — stop sur budget USD
- Given budget faible
- When coût cumulé atteint limite
- Then campagne arrêtée automatiquement.

### T-ENG-04 — cancel request interrompe génération suivante
- Given campagne en cours
- When cancel flag activé
- Then aucune nouvelle évaluation ne démarre.

### T-ENG-05 — absence auto-promotion
- Given campagne complétée avec meilleur candidat
- When aucun promote explicite
- Then aucun changement de versions actives prompt/skills.

## 3.2 Unitaires evaluator/mutator

### T-EVAL-01 — evaluator appelle BenchmarkEngine
- Given un candidat
- When `Evaluator.evaluate_candidate()`
- Then BenchmarkEngine est invoqué et renvoie métriques 5 dimensions.

### T-EVAL-02 — evaluator persiste aggregate_score + metrics
- Given métriques benchmark
- When persistance
- Then ligne `evolution_candidate_evaluations` créée correctement.

### T-MUT-01 — mutator produit candidat valide
- Given baseline prompt/skills
- When mutation
- Then `system_prompt`, `user_prompt_template`, `skills` non vides et typés.

### T-MUT-02 — mutator rejette sortie invalide
- Given sortie LLM mal formée
- When validation mutator
- Then candidat marqué `rejected` avec raison.

### T-MUT-03 — mutator respecte borne appels
- Given limite appels faible
- When boucle de mutation
- Then compteur n'excède pas `max_llm_calls`.

## 3.3 API backend

### T-API-01 — POST campaigns (201)
- Given utilisateur autorisé
- When POST payload valide
- Then `201`, campagne créée + `celery_task_id` présent.

### T-API-02 — POST campaigns (400 validation)
- Given payload invalide
- When POST
- Then `400` message explicite.

### T-API-03 — GET campaigns
- Given données existantes
- When GET list
- Then `200` + pagination/filtrage corrects.

### T-API-04 — POST cancel
- Given campagne running
- When POST cancel
- Then `202` + statut `cancel_requested`.

### T-API-05 — GET campaign detail
- Given campagne active
- When GET detail
- Then `200` inclut progression, best_candidate, budget consommé.

### T-API-06 — GET candidates
- Given campagne avec candidats
- When GET candidates
- Then `200` + items attendus.

### T-API-07 — GET fitness-series
- Given évaluations disponibles
- When GET fitness-series
- Then `200` + série ordonnée exploitable Recharts.

### T-API-08 — POST promote
- Given candidat évalué
- When promote
- Then `201`, promotion tracée + IDs versions promues.

### T-API-09 — sécurité RBAC
- Given utilisateur non autorisé
- When POST campaign/cancel/promote
- Then `403`.

## 3.4 Celery intégration

### T-CEL-01 — task routée queue evolution
- Given lancement campagne
- When task publiée
- Then routing key/queue = `evolution`.

### T-CEL-02 — task statut terminal cohérent
- Given exception engine
- When task fail
- Then campagne `failed` + `error` renseigné.

## 3.5 Frontend

### T-FE-01 — route lazy `/evolution-lab`
- Given application lancée
- When navigation route
- Then page charge sans casser autres routes.

### T-FE-02 — tabs visibles
- Given page Evolution Lab
- When rendu initial
- Then tabs Campagnes / + Nouvelle / Leaderboard visibles.

### T-FE-03 — CampaignForm valeurs par défaut
- Given tab + Nouvelle
- When ouverture formulaire
- Then iterations=100, candidates=50 préremplies.

### T-FE-04 — AgentChip 9 agents
- Given formulaire
- When sélection agent
- Then 9 chips disponibles et sélection unique.

### T-FE-05 — CampaignCard sparkline + progress
- Given campagnes avec données
- When affichage liste
- Then sparkline et barre progression rendues.

### T-FE-06 — CampaignDetail graph + leaderboard + log
- Given campagne sélectionnée
- When ouverture détail
- Then courbe fitness, leaderboard et generation log présents.

### T-FE-07 — PromptDiffViewer baseline vs candidat
- Given baseline et candidat
- When ouverture diff
- Then diff side-by-side lisible avec insertions/suppressions.

### T-FE-08 — PromoteButton confirmation
- Given candidat sélectionné
- When clic promote
- Then dialog confirmation avant appel API.

### T-FE-09 — états loading/empty/error
- Given latence/erreur API/absence données
- When affichage
- Then états visuels explicites par composant.

### T-FE-10 — build frontend
- When `cd frontend && npm run build`
- Then build passe ou les erreurs préexistantes hors GH-28 sont documentées.

## 3.6 Non-régression

### T-REG-01 — BenchmarkEngine inchangé
- Given suite GH-24
- When tests benchmark exécutés
- Then comportements/contrats inchangés.

### T-REG-02 — pipeline trading existant
- Given tests backend complets
- When `cd backend && pytest -q`
- Then pas de régression sur modules non concernés.

### T-REG-03 — aucune interaction risk/live
- Given exécution campagne evolution
- When logs/side effects inspectés
- Then aucun appel risk engine modifié ni ALLOW_LIVE_TRADING activé.

---

## 4. Jeux de données

- Baseline prompt template réel d'un agent (ex `technical-analyst`).
- Baseline skill versionnée GH-29.
- Set benchmark de référence (profil standard + holdout).
- Cas mutator invalide (JSON cassé, prompt vide, skills mal typées).

---

## 5. Critères de sortie

Le test plan est validé si:
1. 100% des AC de la spec sont couverts par au moins un test.
2. Les tests backend ciblés passent.
3. Le build frontend est exécuté et résultat documenté.
4. Les non-régressions critiques (benchmark/pipeline) sont vérifiées.
