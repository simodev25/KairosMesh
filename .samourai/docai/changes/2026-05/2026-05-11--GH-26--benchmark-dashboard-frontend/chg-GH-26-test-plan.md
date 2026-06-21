---
id: chg-GH-26-test-plan
status: Proposed
created: 2026-05-11T00:00:00Z
last_updated: 2026-05-11T00:00:00Z
owners: ["mbensass"]
service: frontend
labels: ["type:feature", "in-progress", "change"]
version_impact: minor
summary: "Dashboard frontend (SPA React) pour piloter fixtures/runs et visualiser/comparer les scores V1 du système de benchmark d'agents."
links:
  change_spec: ./chg-GH-26-spec.md
  implementation_plan: null
  testing_strategy: .samourai/ai/rules/testing-strategy.md
---

# Test Plan - Agent Benchmark System — Lot B : Dashboard Frontend

## 1. Scope and Objectives

Ce plan de test couvre la livraison d'une nouvelle page `/benchmark` dans le SPA React existant : navigation, affichage des fixtures, lancement d'un run, visualisation des résultats (scores V1), comparaison multi-modèles et détail d'un run.

Le lot étant **frontend React/TypeScript** et sans setup de tests unitaires frontend dans le projet, la stratégie privilégie :
- vérifications de build TypeScript/Vite (0 erreur, pas de warning bloquant) ;
- checklist de tests manuels ciblés sur les AC ;
- vérifications de types et de conventions (contrats TS, accessibilité, design tokens).

### 1.1 In Scope

- F-1 à F-7, AC associés (navigation, page benchmark, liste fixtures, run, résultats, comparaison, détail, types).
- Contrats consommés (API-1 à API-6) via tests manuels (UI) et validation de typage (DM-1 à DM-7).
- NFR build, performance (observations), design system, maintenabilité (LOC), accessibilité.

### 1.2 Out of Scope & Known Gaps

- Tests E2E Playwright automatisés (explicitement hors périmètre du lot — spec §4.2/§7.2).
- Validation du backend (Lot A, GH-24) : supposé fonctionnel ; ce plan ne couvre pas de tests backend/pytest.

## 2. References

- Change spec : `./chg-GH-26-spec.md`
- Stratégie de test repo : `.samourai/ai/rules/testing-strategy.md`
- Dépendance fonctionnelle : GH-24 (Lot A — API REST `/api/v1/benchmark/`) (cf. spec §1/§13)

## 3. Coverage Overview

### 3.1 Functional Coverage (F-#, AC-#)

| AC ID | Description (résumé) | TC ID(s) | Status |
|---|---|---|---|
| AC-F1-1 | Entrée BENCHMARK → `/benchmark` se charge et affiche le titre | TC-BENCH-001 | Planned |
| AC-F2-1 | Liste fixtures : nom, agent_key, scenario_type, date | TC-BENCH-002 | Planned |
| AC-F2-2 | Aucune fixture → message "Aucune fixture disponible" | TC-BENCH-003 | Planned |
| AC-F3-1 | Form run valide → POST runs + spinner pendant soumission | TC-BENCH-004 | Planned |
| AC-F3-2 | Soumission OK → nouveau run apparaît dans la liste | TC-BENCH-005 | Planned |
| AC-F4-1 | Résultats run : 5 métriques V1 + overall par modèle | TC-BENCH-006 | Planned |
| AC-F4-2 | Coloration scores selon seuils (vert/orange/rouge) | TC-BENCH-007 | Planned |
| AC-F5-1 | Comparaison 2+ modèles : tableau + meilleur score mis en évidence | TC-BENCH-008 | Planned |
| AC-F6-1 | Détail run : cases + attempts (statut, latence, token count) | TC-BENCH-009 | Planned |
| AC-F7-1 | Types benchmark : pas d'erreur TS liée aux types benchmark au build | TC-BENCH-010 | Planned |
| AC-NFR3-1 | Build frontend : aucune nouvelle erreur TS introduite vs GH-24 | TC-BENCH-011 | Planned |
| AC-NFR5-1 | Composants benchmark utilisent uniquement tokens/classes de `theme.css` | TC-BENCH-012 | Planned |

### 3.2 Interface Coverage (API-#, EVT-#, DM-#)

| ID | Interface / Contrat | Couverture (TC) | Notes |
|---|---|---|---|
| API-1 | GET `/api/v1/benchmark/fixtures` | TC-BENCH-002, TC-BENCH-003 | Chargement initial / état vide |
| API-2 | GET `/api/v1/benchmark/fixtures/{id}` | TODO | La spec mentionne l'endpoint ; le flux UI détaillé n'exige pas explicitement son usage (à confirmer) |
| API-3 | POST `/api/v1/benchmark/runs` | TC-BENCH-004, TC-BENCH-005 | Soumission + rafraîchissement |
| API-4 | GET `/api/v1/benchmark/runs` | TC-BENCH-005, TC-BENCH-008 | Liste runs / sélection pour comparaison |
| API-5 | GET `/api/v1/benchmark/runs/{id}` | TC-BENCH-009 | Détail run |
| API-6 | GET `/api/v1/benchmark/runs/{id}/results` | TC-BENCH-006, TC-BENCH-007, TC-BENCH-008 | Résultats + comparaison |
| DM-1..DM-7 | Types TS (ModelSpec, Fixture, Run, Case, Attempt, ScoresV1, RunResults) | TC-BENCH-010, TC-BENCH-011 | Vérifiés via build TS/Vite |
| EVT-* | Événements | N/A | Aucun événement requis (spec §8.2) |

> Remarque : le contrat exact de `API-6` est une question ouverte OQ-1 dans la spec.

### 3.3 Non-Functional Coverage (NFR-#)

| NFR ID | Exigence | TC ID(s) | Status |
|---|---|---|---|
| NFR-1 | Chargement fixtures < 2s (réseau local, < 50) | TC-BENCH-013 | Planned |
| NFR-2 | Rendu tableau résultats < 500ms après réponse API | TC-BENCH-014 | Planned |
| NFR-3 | Build `npm run build` : 0 erreur TS introduite | TC-BENCH-011 | Planned |
| NFR-4 | Build `npm run build` : 0 warning Vite bloquant | TC-BENCH-011 | Planned |
| NFR-5 | Design tokens/typo via `theme.css` uniquement | TC-BENCH-012 | Planned |
| NFR-6 | Aucun composant > 400 lignes | TC-BENCH-015 | Planned |
| NFR-7 | Accessibilité : éléments interactifs ont label/aria-label | TC-BENCH-016 | Planned |

## 4. Test Types and Layers

Alignement stratégie repo (`.samourai/ai/rules/testing-strategy.md`) :

- **Unit (backend)** / **Integration (backend)** : non applicables pour ce lot (pas de code backend).
- **E2E (frontend)** : la stratégie repo propose Playwright (`frontend/tests/`), mais la spec (Lot B) indique explicitement que les tests E2E Playwright sont hors périmètre. Les vérifications de ce lot sont donc :
  - **Build/Type checks** (semi-automatisés) : `cd frontend && npm run build` (et, si disponible, `npx tsc --noEmit`).
  - **Tests manuels UI** : parcours ciblés sur `/benchmark` + régressions navigation.
  - **Checks de conformité** (semi-automatisés) : recherche de couleurs hardcodées, taille des composants.

## 5. Test Scenarios

### 5.1 Scenario Index

| TC ID | Title | Type | Level | Priority | AC Coverage |
|---|---|---|---|---|---|
| TC-BENCH-001 | Accès navigation → page `/benchmark` | Happy Path | Important | High | AC-F1-1 |
| TC-BENCH-002 | Fixtures : liste non vide et colonnes attendues | Happy Path | Important | High | AC-F2-1 |
| TC-BENCH-003 | Fixtures : état vide | Edge Case | Minor | Medium | AC-F2-2 |
| TC-BENCH-004 | Lancer un run : validation minimale + spinner + POST | Happy Path | Critical | High | AC-F3-1 |
| TC-BENCH-005 | Run créé : rafraîchissement et apparition dans liste | Happy Path | Critical | High | AC-F3-2 |
| TC-BENCH-006 | Résultats : métriques V1 + overall par modèle | Happy Path | Critical | High | AC-F4-1 |
| TC-BENCH-007 | Résultats : coloration par seuils | Edge Case | Important | High | AC-F4-2 |
| TC-BENCH-008 | Comparaison 2+ modèles : tableau + meilleur score | Happy Path | Important | Medium | AC-F5-1 |
| TC-BENCH-009 | Détail run : cases/attempts (statut/latence/tokens) | Happy Path | Important | Medium | AC-F6-1 |
| TC-BENCH-010 | Types benchmark : compilation TS sans erreur liée aux types | Regression | Critical | High | AC-F7-1 |
| TC-BENCH-011 | Build frontend : 0 erreur TS et 0 warning bloquant | Regression | Critical | High | AC-NFR3-1 |
| TC-BENCH-012 | Design system : pas de valeurs hardcodées (hex/police) | Regression | Important | Medium | AC-NFR5-1 |
| TC-BENCH-013 | Perf : chargement fixtures < 2s (observation) | Performance | Important | Medium | NFR-1 |
| TC-BENCH-014 | Perf : rendu tableau résultats < 500ms (observation) | Performance | Important | Low | NFR-2 |
| TC-BENCH-015 | Maintenabilité : composants ≤ 400 LOC | Regression | Minor | Medium | NFR-6 |
| TC-BENCH-016 | Accessibilité : labels/aria-label sur éléments interactifs | Regression | Important | Medium | NFR-7 |

### 5.2 Scenario Details

#### TC-BENCH-001 - Accès navigation → page `/benchmark`

**Scenario Type**: Happy Path
**Impact Level**: Important
**Priority**: High
**Related IDs**: F-1, AC-F1-1
**Test Type(s)**: Manual
**Automation Level**: Manual
**Target Layer / Location**: Frontend SPA (navigation)
**Tags**: @ui

**Preconditions**:

- Utilisateur authentifié (token via mécanisme existant `useAuth`).
- Frontend lancé en local.

**Steps**:

1. Ouvrir l'application.
2. Dans le sidebar, cliquer sur l'entrée "BENCHMARK".
3. Vérifier l'URL et l'affichage.

**Expected Outcome**:

- La route `/benchmark` se charge sans erreur visible.
- Le titre de section Benchmark est affiché.


#### TC-BENCH-002 - Fixtures : liste non vide et colonnes attendues

**Scenario Type**: Happy Path
**Impact Level**: Important
**Priority**: High
**Related IDs**: F-2, AC-F2-1, API-1, DM-2
**Test Type(s)**: Manual
**Automation Level**: Manual
**Target Layer / Location**: BenchmarkPage (liste fixtures)
**Tags**: @ui @api

**Preconditions**:

- Au moins 1 fixture existe côté backend (créée via API/script).
- Backend GH-24 accessible depuis le frontend (base URL/config existante).

**Steps**:

1. Aller sur `/benchmark`.
2. Attendre la fin du chargement initial.
3. Observer la liste des fixtures.

**Expected Outcome**:

- Chaque ligne affiche : nom, `agent_key`, `scenario_type`, date de création.


#### TC-BENCH-003 - Fixtures : état vide

**Scenario Type**: Edge Case
**Impact Level**: Minor
**Priority**: Medium
**Related IDs**: F-2, AC-F2-2, API-1
**Test Type(s)**: Manual
**Automation Level**: Manual
**Target Layer / Location**: BenchmarkPage (liste fixtures)
**Tags**: @ui

**Preconditions**:

- Aucune fixture disponible côté backend (environnement de test dédié / base vide).

**Steps**:

1. Aller sur `/benchmark`.
2. Attendre le chargement.

**Expected Outcome**:

- Le message "Aucune fixture disponible" est affiché.


#### TC-BENCH-004 - Lancer un run : validation minimale + spinner + POST

**Scenario Type**: Happy Path
**Impact Level**: Critical
**Priority**: High
**Related IDs**: F-3, AC-F3-1, API-3, DM-1
**Test Type(s)**: Manual
**Automation Level**: Manual
**Target Layer / Location**: BenchmarkPage (formulaire run)
**Tags**: @ui @api

**Preconditions**:

- Une fixture est sélectionnable dans la liste.

**Steps**:

1. Sélectionner une fixture.
2. Renseigner `model_specs` avec au moins un modèle (provider + model_name ; temperature optionnelle).
3. Cliquer sur "Lancer".

**Expected Outcome**:

- Un appel `POST /api/v1/benchmark/runs` est émis.
- Un spinner (`ButtonSpinner`) est visible pendant la soumission.


#### TC-BENCH-005 - Run créé : rafraîchissement et apparition dans liste

**Scenario Type**: Happy Path
**Impact Level**: Critical
**Priority**: High
**Related IDs**: F-3, AC-F3-2, API-3, API-4, DM-3
**Test Type(s)**: Manual
**Automation Level**: Manual
**Target Layer / Location**: BenchmarkPage (liste runs)
**Tags**: @ui @api

**Preconditions**:

- Le run créé dans TC-BENCH-004 aboutit à une réponse API 2xx.

**Steps**:

1. Après la soumission, observer la liste des runs associée à la fixture.
2. Si nécessaire, déclencher l'action de rafraîchissement prévue (selon implémentation : refresh automatique après succès).

**Expected Outcome**:

- Le nouveau run apparaît dans la liste des runs de la fixture.


#### TC-BENCH-006 - Résultats : métriques V1 + overall par modèle

**Scenario Type**: Happy Path
**Impact Level**: Critical
**Priority**: High
**Related IDs**: F-4, AC-F4-1, API-6, DM-6, DM-7
**Test Type(s)**: Manual
**Automation Level**: Manual
**Target Layer / Location**: BenchmarkPage (tableau résultats)
**Tags**: @ui @api

**Preconditions**:

- Un run terminé est disponible (status terminé côté backend).

**Steps**:

1. Sélectionner un run terminé.
2. Attendre le chargement des résultats.
3. Vérifier les colonnes/valeurs affichées par modèle.

**Expected Outcome**:

- Pour chaque modèle, les métriques `schema_validity`, `completeness`, `tool_policy`, `reference_consistency`, `stability` et `overall` sont affichées.


#### TC-BENCH-007 - Résultats : coloration par seuils

**Scenario Type**: Edge Case
**Impact Level**: Important
**Priority**: High
**Related IDs**: F-4, AC-F4-2, NFR-5
**Test Type(s)**: Manual
**Automation Level**: Manual
**Target Layer / Location**: BenchmarkPage (tableau résultats)
**Tags**: @ui

**Preconditions**:

- Disposer d'un run dont les scores incluent des valeurs dans les 3 zones (<0,4 ; 0,4–0,69 ; ≥0,7).

**Steps**:

1. Ouvrir les résultats du run.
2. Pour quelques cellules de score, vérifier la couleur selon la valeur.

**Expected Outcome**:

- Score ≥ 0,7 : vert.
- Score 0,4–0,69 : orange.
- Score < 0,4 : rouge.


#### TC-BENCH-008 - Comparaison 2+ modèles : tableau + meilleur score

**Scenario Type**: Happy Path
**Impact Level**: Important
**Priority**: Medium
**Related IDs**: F-5, AC-F5-1, API-4, API-6
**Test Type(s)**: Manual
**Automation Level**: Manual
**Target Layer / Location**: BenchmarkPage (vue comparaison)
**Tags**: @ui

**Preconditions**:

- Plusieurs runs (ou résultats) existent pour une même fixture avec des modèles différents.

**Steps**:

1. Dans la liste des runs d'une fixture, sélectionner 2 modèles ou plus.
2. Déclencher l'action "Comparer".
3. Observer le tableau de comparaison.

**Expected Outcome**:

- Un tableau métriques × modèles est affiché.
- Pour chaque métrique, le meilleur score est mis en évidence.


#### TC-BENCH-009 - Détail run : cases/attempts (statut/latence/tokens)

**Scenario Type**: Happy Path
**Impact Level**: Important
**Priority**: Medium
**Related IDs**: F-6, AC-F6-1, API-5, DM-4, DM-5
**Test Type(s)**: Manual
**Automation Level**: Manual
**Target Layer / Location**: BenchmarkPage (panneau détail run / expansion)
**Tags**: @ui @api

**Preconditions**:

- Un run avec des cases/attempts est disponible.

**Steps**:

1. Sélectionner un run.
2. Ouvrir le détail (panneau d'expansion ou vue dédiée).
3. Parcourir la liste des cases et attempts.

**Expected Outcome**:

- Les `BenchmarkCase` et `BenchmarkAttempt` sont listés.
- Chaque entrée expose au minimum : statut, latence, token count.


#### TC-BENCH-010 - Types benchmark : compilation TS sans erreur liée aux types

**Scenario Type**: Regression
**Impact Level**: Critical
**Priority**: High
**Related IDs**: F-7, AC-F7-1, DM-1, DM-2, DM-3, DM-4, DM-5, DM-6, DM-7
**Test Type(s)**: Manual
**Automation Level**: Semi-automated
**Target Layer / Location**: Frontend build/typecheck
**Tags**: @ui

**Preconditions**:

- Dépendances frontend installées.

**Steps**:

1. Exécuter le build frontend (cf. TC-BENCH-011).
2. Vérifier l'absence d'erreurs TypeScript liées aux types benchmark.

**Expected Outcome**:

- Aucune erreur TypeScript relative aux types benchmark n'apparaît.


#### TC-BENCH-011 - Build frontend : 0 erreur TS et 0 warning bloquant

**Scenario Type**: Regression
**Impact Level**: Critical
**Priority**: High
**Related IDs**: NFR-3, NFR-4, AC-NFR3-1
**Test Type(s)**: Manual
**Automation Level**: Semi-automated
**Target Layer / Location**: Frontend build
**Tags**: @ui

**Preconditions**:

- Node/npm installés.
- `npm ci`/`npm install` déjà exécuté dans `frontend/`.

**Steps**:

1. Lancer : `cd frontend && npm run build`.
2. Inspecter la sortie.

**Expected Outcome**:

- Le build termine avec code 0.
- Aucune nouvelle erreur TypeScript n'est introduite par rapport à la branche de base GH-24.
- Aucun warning Vite bloquant n'est émis.


#### TC-BENCH-012 - Design system : pas de valeurs hardcodées (hex/police)

**Scenario Type**: Regression
**Impact Level**: Important
**Priority**: Medium
**Related IDs**: NFR-5, AC-NFR5-1
**Test Type(s)**: Manual
**Automation Level**: Semi-automated
**Target Layer / Location**: Frontend source review
**Tags**: @ui

**Preconditions**:

- Les fichiers de composants benchmark existent (page + sous-composants).

**Steps**:

1. Vérifier manuellement que les classes utilisées correspondent aux tokens/classes existants (`theme.css`) et aux patterns (cf. spec annexe pattern BacktestsPage).
2. (Option semi-automatisée) Rechercher dans les nouveaux fichiers benchmark des couleurs hexadécimales et des polices codées en dur.

**Expected Outcome**:

- Aucun usage de valeurs hexadécimales ou de font-family hardcodée dans les composants benchmark.


#### TC-BENCH-013 - Perf : chargement fixtures < 2s (observation)

**Scenario Type**: Performance
**Impact Level**: Important
**Priority**: Medium
**Related IDs**: NFR-1
**Test Type(s)**: Manual
**Automation Level**: Manual
**Target Layer / Location**: Frontend UI (Network)
**Tags**: @ui @perf

**Preconditions**:

- Environnement local (réseau local) avec < 50 fixtures.

**Steps**:

1. Ouvrir les DevTools navigateur → onglet Network.
2. Recharger `/benchmark`.
3. Mesurer la durée de la requête fixtures (API-1) et/ou le temps jusqu'à affichage de la liste.

**Expected Outcome**:

- Chargement perçu et/ou requête fixtures < 2 s dans les conditions de la spec.


#### TC-BENCH-014 - Perf : rendu tableau résultats < 500ms (observation)

**Scenario Type**: Performance
**Impact Level**: Important
**Priority**: Low
**Related IDs**: NFR-2
**Test Type(s)**: Manual
**Automation Level**: Manual
**Target Layer / Location**: Frontend UI
**Tags**: @ui @perf

**Preconditions**:

- Run terminé disponible ; résultats retournés rapidement par l'API.

**Steps**:

1. Sélectionner un run terminé.
2. Observer le délai entre la fin de réponse réseau et l'affichage complet du tableau.

**Expected Outcome**:

- Le tableau est rendu de manière quasi immédiate ; objectif < 500 ms (observation).


#### TC-BENCH-015 - Maintenabilité : composants ≤ 400 LOC

**Scenario Type**: Regression
**Impact Level**: Minor
**Priority**: Medium
**Related IDs**: NFR-6
**Test Type(s)**: Manual
**Automation Level**: Semi-automated
**Target Layer / Location**: Frontend source
**Tags**: @ui

**Preconditions**:

- Les fichiers de composants benchmark sont présents.

**Steps**:

1. Vérifier la taille (nombre de lignes) des composants benchmark.

**Expected Outcome**:

- Aucun composant ne dépasse 400 lignes ; sinon extraction en sous-composants.


#### TC-BENCH-016 - Accessibilité : labels/aria-label sur éléments interactifs

**Scenario Type**: Regression
**Impact Level**: Important
**Priority**: Medium
**Related IDs**: NFR-7
**Test Type(s)**: Manual
**Automation Level**: Manual
**Target Layer / Location**: Frontend UI
**Tags**: @ui

**Preconditions**:

- Page Benchmark rendue avec les principaux contrôles : boutons, inputs, cases à cocher, etc.

**Steps**:

1. Inspecter les éléments interactifs de la page (formulaire run, sélection, boutons d'action, comparaison).
2. Vérifier la présence d'un label visible ou d'un `aria-label`.

**Expected Outcome**:

- Tous les éléments interactifs ont un label accessible.

## 6. Environments and Test Data

### Environnements

- **Local dev** : frontend + backend accessible (Lot A GH-24) ; authentification active.
- Aucun besoin explicite de Docker/Compose pour ce lot (non requis par la spec).

### Données de test

- Jeu minimal :
  - 0 fixture (pour TC-BENCH-003) ;
  - ≥ 1 fixture (pour TC-BENCH-002) ;
  - ≥ 1 run terminé avec résultats incluant scores dans les 3 zones de seuil (pour TC-BENCH-006/007) ;
  - ≥ 2 modèles/runs comparables sur la même fixture (pour TC-BENCH-008).

> Note : la création de fixtures se fait hors UI (spec §7.2) ; via API/scripts backend.

## 7. Automation Plan and Implementation Mapping

Ce lot ne prévoit pas l'ajout de tests Playwright/Jest/Vitest ; l'automatisation attendue est principalement la **validation build** et quelques **checks semi-automatisés**.

| TC ID | Implementation status | Suggested command / location |
|---|---|---|
| TC-BENCH-001 | Manual Only | Lancer frontend local, naviguer `/benchmark` |
| TC-BENCH-002 | Manual Only | UI + observation des champs fixture |
| TC-BENCH-003 | Manual Only | UI avec environnement sans fixtures |
| TC-BENCH-004 | Manual Only | UI + DevTools Network pour vérifier POST |
| TC-BENCH-005 | Manual Only | UI après succès POST |
| TC-BENCH-006 | Manual Only | UI + sélection run terminé |
| TC-BENCH-007 | Manual Only | UI + valeurs de scores couvrant seuils |
| TC-BENCH-008 | Manual Only | UI + comparaison multi-modèles |
| TC-BENCH-009 | Manual Only | UI + détail run |
| TC-BENCH-010 | To Implement (semi-automated check) | Couvert par `cd frontend && npm run build` |
| TC-BENCH-011 | To Implement (semi-automated check) | `cd frontend && npm run build` (ou `make frontend-build`) |
| TC-BENCH-012 | Manual + Semi-automated | Revue code + recherche patterns (hex/font hardcodées) |
| TC-BENCH-013 | Manual Only | DevTools Network : mesure chargement fixtures |
| TC-BENCH-014 | Manual Only | Observation rendu post-réponse |
| TC-BENCH-015 | Semi-automated | `wc -l`/inspection taille fichiers composants benchmark |
| TC-BENCH-016 | Manual Only | Inspection DOM / labels accessibles |

## 8. Risks, Assumptions, and Open Questions

### 8.1 Risks

- **Contrat API-6 non stabilisé (OQ-1)** : risque de non-compatibilité UI vs backend ; mitigation : tests manuels avec backend GH-24 à jour et adaptation des types (commentaires TODO si nécessaire).
- **Erreurs TypeScript pré-existantes** (RSK-1) : risque de build cassé indépendamment ; mitigation : comparer avec la branche de base (GH-24) et isoler les nouveaux types (spec DEC-3).
- **Régression navigation/routing** (RSK-4) : mitigation : test manuel de navigation de base (inclure un mini smoke des pages existantes après ajout de la route).

### 8.2 Assumptions

- GH-24 fournit les endpoints listés (spec §8.1) et ils sont accessibles depuis le frontend.
- L'auth existante suffit (spec §12).
- Les fixtures/runs de test peuvent être seedés via API/scripts (spec §7.2/§19).

### 8.3 Open Questions

| ID | Question | Impact test | Owner |
|---|---|---|---|
| OQ-1 | Format exact de `GET /benchmark/runs/{id}/results` (agrégation par modèle vs par case/attempt) ? | Peut bloquer TC-BENCH-006/007/008 si le format diffère | GH-24 / backend |
| OQ-2 | Numéro de nœud et libellé exacts pour l'item "BENCHMARK" dans le sidebar ? | Affecte TC-BENCH-001 (assertion UI) | mbensass |
| OQ-3 | Confirmation que la création de fixture via UI est bien hors périmètre | Affecte couverture API-2 et scénarios futurs | mbensass |
| OQ-4 | Besoin de polling automatique pour runs en cours ? | Affecte scénarios/perf UX ; pas couvert si hors scope | mbensass |
| OQ-5 | Validation des seuils de coloration (0,7 / 0,4) | Affecte TC-BENCH-007 | mbensass |

## 9. Plan Revision Log

| Version | Date | Author | Changes |
|---|---|---|---|
| 1.0 | 2026-05-11 | mbensass (@test-plan-writer) | Création initiale du test plan (build + checklist manuelle, traçabilité AC) |

## 10. Test Execution Log

| TC ID | Run Date | Result | Notes |
|---|---|---|---|
