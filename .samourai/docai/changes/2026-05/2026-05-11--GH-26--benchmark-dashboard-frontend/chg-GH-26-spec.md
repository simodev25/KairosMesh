---
change:
  ref: GH-26
  type: feat
  status: Proposed
  slug: benchmark-dashboard-frontend
  title: "Agent Benchmark System — Lot B : Dashboard Frontend"
  owners: ["mbensass"]
  service: frontend
  labels: ["type:feature", "in-progress", "change"]
  version_impact: minor
  audience: internal
  security_impact: none
  risk_level: low
  dependencies:
    internal: ["GH-24 (Lot A — API REST /api/v1/benchmark/)", "frontend design system (theme.css)", "frontend SPA React (App.tsx, Layout.tsx)"]
    external: []
---

# CHANGE SPECIFICATION

> **PURPOSE** : Définir le périmètre, les exigences fonctionnelles, les critères d'acceptation et les décisions de conception du dashboard frontend du système de benchmark d'agents LLM (Lot B). Ce document est la référence canonique pour la phase de test planning et de delivery planning.

---

## 1. SOMMAIRE

Le Lot A (GH-24) a livré le moteur backend de benchmark avec son API REST sous `/api/v1/benchmark/`. Les résultats ne sont aujourd'hui consultables que via appels API bruts. Ce changement (Lot B) livre l'interface visuelle intégrée au SPA React existant, permettant aux opérateurs de gérer des fixtures de benchmark, de lancer des runs, et de visualiser et comparer les scores V1 par modèle LLM et par agent.

---

## 2. CONTEXTE

### 2.1 État actuel

- Le SPA React (terminal-style, Tailwind v4, JetBrains Mono) expose six sections dans la navigation latérale : Portfolio, Terminal, Ordres, Strategy Engine, Backtest Engine, System Config.
- Le Lot A (GH-24) a livré les endpoints REST `POST/GET /fixtures`, `POST/GET /runs`, `GET /runs/{id}`, `GET /runs/{id}/results`.
- Les données de benchmark (fixtures, runs, scores V1) ne sont accessibles qu'en JSON brut via l'API ; aucune page dédiée n'existe dans le frontend.
- Le pattern de page de référence est `BacktestsPage.tsx` : formulaire de lancement, liste de résultats avec panneau d'expansion, stat cards, hooks `useAuth`, appels `api.*`.

### 2.2 Points de douleur / Lacunes

- Aucune visibilité sur les performances comparatives des modèles LLM par agent.
- Les opérateurs doivent utiliser des clients HTTP bruts pour consulter les résultats de scoring.
- L'absence de vue de comparaison rend le choix de modèle subjectif et non traçable.

---

## 3. ÉNONCÉ DU PROBLÈME

Les opérateurs du système Kairos Mesh ne disposent d'aucune interface pour piloter le cycle benchmark : créer ou sélectionner des fixtures, lancer des runs multi-modèles, et comparer les scores V1 de manière visuelle. Cela rend la sélection de modèle LLM par agent opaque et non outillée.

---

## 4. OBJECTIFS

- Rendre le dashboard benchmark accessible depuis la navigation principale sans friction.
- Permettre de lancer un run de benchmark (choix fixture + modèles) en moins de 3 clics.
- Afficher les 5 métriques V1 et le score global par modèle de façon lisible.
- Permettre la comparaison côte à côte de 2 modèles ou plus sur la même fixture.
- Respecter intégralement le design system existant (tokens, typographie, composants terminal-style).

### 4.1 Métriques de succès / KPIs

| Métrique | Cible |
|---|---|
| Build frontend sans nouvelle erreur TypeScript | 0 erreur introduite |
| Couverture des types TypeScript des objets API benchmark | 100 % des champs documentés typés |
| Accessibilité de la route `/benchmark` | Réponse HTTP 200 après build |
| Délai de chargement de la liste des fixtures (réseau local) | < 2 s |

### 4.2 Non-objectifs

- Modification du backend (Lot A livré, non modifiable dans ce lot).
- Graphiques avancés de type radar chart ou heatmap (itération future).
- Scoring V2 / juge LLM (Lot C).
- Tests E2E Playwright (hors périmètre de ce lot).
- Authentification ou contrôle d'accès spécifique au benchmark (hérite du système existant).

---

## 5. CAPACITÉS FONCTIONNELLES

| ID | Capacité | Rationale |
|---|---|---|
| F-1 | Navigation vers la page Benchmark depuis le sidebar | Point d'entrée nécessaire pour toute la fonctionnalité |
| F-2 | Liste des fixtures de benchmark | Vue d'ensemble des jeux de test disponibles |
| F-3 | Lancement d'un run de benchmark | Déclenchement du processus d'évaluation multi-modèles |
| F-4 | Affichage des résultats d'un run (scores V1 par métrique) | Lisibilité des résultats d'évaluation |
| F-5 | Vue de comparaison de modèles sur une même fixture | Aide à la décision pour le choix de modèle |
| F-6 | Vue détail d'un run (cases et attempts) | Diagnostic fin des résultats |
| F-7 | Types TypeScript complets pour les objets benchmark | Contrat de type entre frontend et API |

### 5.1 Détail des capacités

**F-1 — Entrée de navigation**
Un item "BENCHMARK" est ajouté au tableau `navItems` de `Layout.tsx`, avec icône Lucide et numéro de nœud, dans le style des items existants. La route `/benchmark` est enregistrée dans `App.tsx` avec lazy loading.

**F-2 — Liste des fixtures**
La page affiche la liste des fixtures disponibles (appel `GET /benchmark/fixtures`). Chaque ligne expose : nom, `agent_key`, `scenario_type`, date de création. L'utilisateur peut sélectionner une fixture pour afficher ses runs associés ou lancer un nouveau run.

**F-3 — Formulaire de lancement de run**
Un formulaire permet de configurer et soumettre un run : sélection de fixture, saisie de `model_specs` (au moins un `{provider, model_name, temperature}`), saisie de `repeat_count` optionnel, saisie de `tags` optionnels. Le lancement appelle `POST /benchmark/runs`. L'état de soumission est matérialisé par un spinner (`ButtonSpinner`).

**F-4 — Tableau de résultats d'un run**
Après sélection d'un run, les résultats agrégés sont affichés (appel `GET /benchmark/runs/{id}/results`). Pour chaque modèle : les 5 métriques V1 (`schema_validity`, `completeness`, `tool_policy`, `reference_consistency`, `stability`) et le score global (`overall`) sont affichés sous forme de colonnes. Les valeurs sont colorées selon un seuil (vert ≥ 0,7 ; orange 0,4–0,69 ; rouge < 0,4).

**F-5 — Vue de comparaison**
L'utilisateur peut sélectionner 2 modèles ou plus depuis les runs d'une même fixture et les voir côte à côte : un tableau comparatif par métrique, avec mise en évidence du meilleur score pour chaque ligne.

**F-6 — Vue détail d'un run**
Affichage des `BenchmarkCase` et `BenchmarkAttempt` d'un run : statut de chaque case, latence, token count, erreurs éventuelles. Utilisé pour le diagnostic.

**F-7 — Types TypeScript**
Un ensemble de types/interfaces est ajouté dans `frontend/src/types/index.ts` ou dans un fichier dédié `frontend/src/types/benchmark.ts`, couvrant : `BenchmarkFixture`, `BenchmarkRun`, `BenchmarkCase`, `BenchmarkAttempt`, `BenchmarkScoresV1`, `BenchmarkRunResults`, `ModelSpec`.

---

## 6. FLUX UTILISATEUR & SYSTÈME

### Flux principal — Lancer un benchmark et consulter les résultats

```
Utilisateur → Clique "BENCHMARK" dans le sidebar
    → BenchmarkPage se charge (liste des fixtures via GET /benchmark/fixtures)
    → Sélectionne une fixture
    → Remplit le formulaire (modèles, repeat_count)
    → Clique "Lancer"
    → POST /benchmark/runs → run créé (status: pending/running)
    → La liste des runs de la fixture se rafraîchit
    → Sélectionne le run terminé
    → GET /benchmark/runs/{id}/results
    → Tableau de scores V1 affiché par modèle
```

### Flux secondaire — Comparaison de modèles

```
Utilisateur → Sur la liste des runs d'une fixture
    → Coche 2+ runs (modèles différents)
    → Clique "Comparer"
    → Vue comparaison : tableau métriques × modèles, meilleur score mis en évidence
```

### Flux secondaire — Détail d'un run

```
Utilisateur → Depuis la liste des runs
    → Clique sur un run
    → Expansion panel ou page dédiée
    → GET /benchmark/runs/{id} → affichage cases + attempts
```

---

## 7. PÉRIMÈTRE & FRONTIÈRES

### 7.1 Dans le périmètre

- Nouvelle page `BenchmarkPage` accessible via la route `/benchmark`.
- Entrée "BENCHMARK" dans la navigation latérale (`Layout.tsx`).
- Méthodes API benchmark dans `frontend/src/api/client.ts` (listFixtures, getFixture, listBenchmarkRuns, createBenchmarkRun, getBenchmarkRun, getBenchmarkRunResults).
- Types TypeScript pour : `BenchmarkFixture`, `BenchmarkRun`, `BenchmarkCase`, `BenchmarkAttempt`, `BenchmarkScoresV1`, `ModelSpec`, `BenchmarkRunResults`.
- Composants internes à la page : liste fixtures, formulaire de lancement, tableau de résultats, vue comparaison, panneau détail run.
- Lazy loading de la page dans `App.tsx`.
- Coloration conditionnelle des scores V1 (vert/orange/rouge).

### 7.2 Hors périmètre

- [OUT] Toute modification du backend ou de ses modèles de données.
- [OUT] Charts avancés (radar, heatmap, graphique temporel des scores).
- [OUT] Scoring V2 ou juge LLM (Lot C).
- [OUT] Tests E2E Playwright.
- [OUT] Création de fixtures via l'UI (le formulaire de création de fixture est une future itération).
- [OUT] Export CSV/PDF des résultats.
- [OUT] Gestion des permissions spécifiques au benchmark.

### 7.3 Différé / Peut-être plus tard

- Graphique radar des métriques V1 par modèle.
- Création de fixture via formulaire UI.
- Export des résultats (CSV, JSON).
- Polling automatique du statut d'un run en cours.
- Filtres et tri avancés sur la liste des runs.

---

## 8. INTERFACES & CONTRATS D'INTÉGRATION

### 8.1 Endpoints REST / HTTP consommés

| ID | Méthode | Chemin | Usage |
|---|---|---|---|
| API-1 | GET | `/api/v1/benchmark/fixtures` | Lister les fixtures |
| API-2 | GET | `/api/v1/benchmark/fixtures/{id}` | Détail d'une fixture |
| API-3 | POST | `/api/v1/benchmark/runs` | Créer un run (body: fixture_id, model_specs, repeat_count, tags) |
| API-4 | GET | `/api/v1/benchmark/runs` | Lister les runs |
| API-5 | GET | `/api/v1/benchmark/runs/{id}` | Détail d'un run (cases + attempts) |
| API-6 | GET | `/api/v1/benchmark/runs/{id}/results` | Résultats agrégés avec scores V1 |

Tous les appels suivent le pattern `request<T>()` de `frontend/src/api/client.ts` avec token d'authentification.

### 8.2 Événements / Messages

Aucun événement WebSocket n'est requis pour ce lot. Le rafraîchissement des données est déclenché manuellement (rechargement de la liste après soumission).

### 8.3 Impact sur le modèle de données

Ajout de types TypeScript uniquement (aucun changement de schéma base de données — côté backend uniquement, Lot A).

**Nouveaux types à définir** :

| ID | Type | Description |
|---|---|---|
| DM-1 | `ModelSpec` | `{ provider: string; model_name: string; temperature?: number }` |
| DM-2 | `BenchmarkFixture` | Représentation d'une fixture avec ses champs gelés |
| DM-3 | `BenchmarkRun` | Run avec statut, model_specs (array ModelSpec), timestamps |
| DM-4 | `BenchmarkCase` | Case d'un run par agent et modèle |
| DM-5 | `BenchmarkAttempt` | Tentative avec scores V1, latence, token count |
| DM-6 | `BenchmarkScoresV1` | `{ schema_validity: number; completeness: number; tool_policy: number; reference_consistency: number; stability: number; overall: number }` |
| DM-7 | `BenchmarkRunResults` | Résultats agrégés d'un run par modèle |

### 8.4 Intégrations externes

Aucune intégration externe nouvelle. Le frontend consomme uniquement l'API backend interne (Lot A).

### 8.5 Compatibilité ascendante

- Aucune route existante n'est modifiée.
- Aucun type existant dans `types/index.ts` n'est modifié (ajout uniquement).
- `Layout.tsx` : ajout d'un item dans le tableau `navItems` — les items existants ne sont pas modifiés.
- `App.tsx` : ajout d'une route et d'un import lazy — le routage existant est inchangé.
- `client.ts` : ajout de méthodes dans l'objet `api` — les méthodes existantes sont inchangées.

---

## 9. EXIGENCES NON FONCTIONNELLES (NFR)

| ID | Catégorie | Exigence | Seuil |
|---|---|---|---|
| NFR-1 | Performance | Temps de chargement initial de la liste des fixtures (réseau local, < 50 fixtures) | < 2 s |
| NFR-2 | Performance | Temps de rendu du tableau de résultats après réception de la réponse API | < 500 ms |
| NFR-3 | Build | Le build `npm run build` ne doit introduire aucune nouvelle erreur TypeScript | 0 erreur TS introduite |
| NFR-4 | Build | Le build `npm run build` ne doit introduire aucun avertissement Vite bloquant | 0 warning bloquant |
| NFR-5 | Design | Respect intégral des tokens couleur, typographie (JetBrains Mono) et classes utilitaires Tailwind définies dans `theme.css` | 100 % des nouveaux composants utilisent les tokens existants |
| NFR-6 | Maintenabilité | Aucun composant ne dépasse 400 lignes ; extraction en sous-composants si nécessaire | Limite stricte 400 LOC/composant |
| NFR-7 | Accessibilité | Les éléments interactifs (boutons, inputs) ont un attribut `aria-label` ou un label visible | 100 % des éléments interactifs |

---

## 10. TÉLÉMÉTRIE & OBSERVABILITÉ

- Les erreurs API (réponse non-ok) sont capturées via le mécanisme `throw new Error()` existant dans `client.ts` et propagées à l'`ErrorBoundary` existant.
- Les états de chargement (loading spinner) sont matérialisés visuellement à l'utilisateur pour chaque appel API.
- Aucune nouvelle instrumentation d'analytics n'est requise dans ce lot.

---

## 11. RISQUES & MITIGATIONS

| ID | Risque | Impact | Probabilité | Mitigation | Risque résiduel |
|---|---|---|---|---|---|
| RSK-1 | Erreurs TypeScript pré-existantes dans le frontend bloquant le build | H | M | Isoler les nouveaux types dans un fichier dédié `types/benchmark.ts` ; ne pas modifier les types existants | L |
| RSK-2 | API backend (Lot A) non mergée dans `main` — divergence de branche | M | H | Branche GH-26 basée sur `feat/GH-24/agent-benchmark-system-lot-a` (DEC-1) ; rebase si Lot A évolue | M |
| RSK-3 | Contrat API Lot A pas encore stabilisé (champs, structure de réponse) | M | L | Typer les champs inconnus en `unknown` avec commentaire `// TODO: stabiliser avec Lot A` | L |
| RSK-4 | Régression sur les routes existantes | M | L | Le routage est additif ; tests manuels des routes existantes après intégration | L |

---

## 12. HYPOTHÈSES

- Le Lot A (GH-24) est fonctionnel sur sa branche et expose les endpoints listés en section 8.1.
- Le design system (`theme.css`) est stable et ne sera pas refondu pendant ce lot.
- L'authentification JWT existante (`useAuth`, token Bearer) est suffisante pour accéder aux endpoints benchmark.
- Les fixtures sont créées via l'API directement (backend ou script) — la création de fixture via l'UI n'est pas requise dans ce lot.
- Le composant `ExpansionPanel` existant peut être réutilisé pour le panneau détail d'un run.

---

## 13. DÉPENDANCES

| Dépendance | Type | Criticité | Statut |
|---|---|---|---|
| GH-24 (Lot A — API REST benchmark) | Interne | Bloquante | Livré sur branche `feat/GH-24/agent-benchmark-system-lot-a` |
| `frontend/src/styles/theme.css` | Interne | Forte | Stable |
| `frontend/src/components/Layout.tsx` | Interne | Forte | Stable — modification additive uniquement |
| `frontend/src/App.tsx` | Interne | Forte | Stable — modification additive uniquement |
| `frontend/src/api/client.ts` | Interne | Forte | Stable — extension additive |
| `frontend/src/components/ExpansionPanel.tsx` | Interne | Modérée | Réutilisation sans modification |
| Lucide React (icônes) | Externe | Faible | Déjà installé |

---

## 14. QUESTIONS OUVERTES

| ID | Question | Priorité | Propriétaire |
|---|---|---|---|
| OQ-1 | L'endpoint `GET /benchmark/runs/{id}/results` retourne-t-il des scores agrégés par modèle ou par case/attempt ? Format exact de la réponse ? | H | GH-24 / backend |
| OQ-2 | Le numéro de nœud de l'item navigation "BENCHMARK" dans le sidebar doit-il suivre la séquence (actuellement "06" pour SYSTEM_CONFIG) ? Libellé exact ? | M | mbensass |
| OQ-3 | Le formulaire de création de fixture doit-il être inclus dans ce lot ou est-ce confirmé hors périmètre ? | M | mbensass |
| OQ-4 | Un run en cours (status: running) doit-il être rafraîchi automatiquement (polling) ou uniquement via action manuelle ? | L | mbensass |
| OQ-5 | Les seuils de coloration des scores V1 (vert ≥ 0,7 ; orange 0,4–0,69 ; rouge < 0,4) sont-ils les bons ? | L | mbensass |

---

## 15. JOURNAL DES DÉCISIONS

| ID | Décision | Contexte | Alternatives écartées | Date |
|---|---|---|---|---|
| DEC-1 | Branche GH-26 basée sur `feat/GH-24/agent-benchmark-system-lot-a` | Le backend benchmark n'est pas encore mergé dans `main` | Attendre le merge de GH-24 (bloquant) | 2026-05-11 |
| DEC-2 | `BacktestsPage.tsx` comme pattern de référence pour la nouvelle page | Cohérence UX et technique ; page la plus proche fonctionnellement (lancement + liste de résultats) | Repartir de zéro (risque d'incohérence) | 2026-05-11 |
| DEC-3 | Types TypeScript benchmark dans un fichier séparé `types/benchmark.ts` | Isolation des risques liés aux erreurs TS pré-existantes ; évite de modifier `types/index.ts` | Ajouter dans `types/index.ts` (risque de conflits) | 2026-05-11 |

---

## 16. COMPOSANTS AFFECTÉS (HAUT NIVEAU)

| Composant | Nature de l'impact |
|---|---|
| `frontend/src/components/Layout.tsx` | Ajout d'un item dans `navItems` (modification additive) |
| `frontend/src/App.tsx` | Ajout d'une route `/benchmark` et d'un import lazy |
| `frontend/src/api/client.ts` | Ajout des méthodes API benchmark dans l'objet `api` |
| `frontend/src/types/benchmark.ts` | Création — nouveaux types TypeScript benchmark |
| `frontend/src/pages/BenchmarkPage.tsx` | Création — page principale du dashboard benchmark |
| Composants internes à `BenchmarkPage` | Création — liste fixtures, formulaire run, tableau résultats, vue comparaison, détail run |

---

## 17. CRITÈRES D'ACCEPTATION

| ID | Critère | Lié à |
|---|---|---|
| AC-F1-1 | **Étant donné** un utilisateur authentifié, **quand** il clique sur l'entrée "BENCHMARK" dans le sidebar, **alors** la page `/benchmark` se charge sans erreur et affiche le titre de la section. | F-1 |
| AC-F2-1 | **Étant donné** que des fixtures existent en base, **quand** la page `/benchmark` est chargée, **alors** la liste des fixtures affiche nom, `agent_key`, `scenario_type` et date de création pour chaque fixture. | F-2 |
| AC-F2-2 | **Étant donné** qu'aucune fixture n'existe, **quand** la page `/benchmark` est chargée, **alors** un message "Aucune fixture disponible" est affiché. | F-2 |
| AC-F3-1 | **Étant donné** une fixture sélectionnée, **quand** l'utilisateur remplit le formulaire (au moins un modèle avec provider et model_name) et clique "Lancer", **alors** un appel `POST /benchmark/runs` est émis et un spinner s'affiche pendant la soumission. | F-3 |
| AC-F3-2 | **Étant donné** une soumission réussie, **quand** la réponse API est reçue, **alors** le nouveau run apparaît dans la liste des runs de la fixture. | F-3 |
| AC-F4-1 | **Étant donné** un run terminé sélectionné, **quand** les résultats sont chargés, **alors** les 5 métriques V1 (`schema_validity`, `completeness`, `tool_policy`, `reference_consistency`, `stability`) et le score `overall` sont affichés pour chaque modèle. | F-4, DM-6 |
| AC-F4-2 | **Étant donné** des scores affichés, **quand** un score est ≥ 0,7, **alors** il est coloré en vert ; entre 0,4 et 0,69 en orange ; en dessous de 0,4 en rouge. | F-4, NFR-5 |
| AC-F5-1 | **Étant donné** plusieurs runs sur une même fixture, **quand** l'utilisateur sélectionne 2 modèles ou plus et déclenche la vue comparaison, **alors** un tableau métriques × modèles s'affiche avec le meilleur score de chaque ligne mis en évidence. | F-5 |
| AC-F6-1 | **Étant donné** un run sélectionné, **quand** l'utilisateur ouvre le détail, **alors** les `BenchmarkCase` et `BenchmarkAttempt` sont listés avec statut, latence et token count. | F-6 |
| AC-F7-1 | **Étant donné** le fichier `types/benchmark.ts`, **quand** le build `npm run build` est exécuté, **alors** aucune erreur TypeScript relative aux types benchmark n'est générée. | F-7, NFR-3 |
| AC-NFR3-1 | **Étant donné** l'ensemble du frontend, **quand** le build `npm run build` est exécuté après les modifications de ce lot, **alors** aucune nouvelle erreur TypeScript n'est introduite par rapport à la branche GH-24. | NFR-3 |
| AC-NFR5-1 | **Étant donné** les nouveaux composants benchmark, **quand** ils sont rendus, **alors** ils utilisent exclusivement les tokens couleur et classes typographiques définis dans `theme.css` (pas de valeurs hexadécimales ou de familles de polices codées en dur). | NFR-5 |

---

## 18. DÉPLOIEMENT & GESTION DU CHANGEMENT (HAUT NIVEAU)

- Livraison via Pull Request sur `feat/GH-26/benchmark-dashboard-frontend` → `feat/GH-24/agent-benchmark-system-lot-a`.
- Une fois GH-24 mergé dans `main`, GH-26 sera rebasé sur `main` et une PR finale sera ouverte.
- Aucune migration de données requise.
- Aucun changement de configuration d'infrastructure.
- Rollback : retrait de la route et de l'item de navigation suffit à désactiver la feature sans impact.

---

## 19. MIGRATION DE DONNÉES / SEEDING (SI APPLICABLE)

Non applicable. Ce lot ne touche pas aux données persistées. Les fixtures benchmark sont créées indépendamment (via API ou scripts du Lot A).

---

## 20. REVUE VIE PRIVÉE / CONFORMITÉ

Aucun traitement de données personnelles introduit par ce lot. Les données de benchmark sont des artefacts techniques internes (prompts gelés, outputs LLM, scores). Aucune revue RGPD spécifique requise.

---

## 21. POINTS SAILLANTS DE LA REVUE DE SÉCURITÉ

- Les appels API utilisent le token JWT Bearer existant (`useAuth`) — aucun nouveau mécanisme d'auth.
- Aucune donnée sensible (credentials, clés API) n'est manipulée par le dashboard benchmark.
- Les outputs LLM (champ `raw_output` des `BenchmarkAttempt`) sont affichés en lecture seule — aucun rendu de HTML non sanitisé.

---

## 22. IMPACT MAINTENANCE & OPÉRATIONS

- La page benchmark est une feature additive ; sa suppression est réversible sans impact sur les autres pages.
- Les méthodes API ajoutées dans `client.ts` suivent le pattern existant — maintenance alignée.
- Aucune nouvelle dépendance npm n'est introduite.

---

## 23. GLOSSAIRE

| Terme | Définition |
|---|---|
| Fixture | Jeu de test benchmark figé : inputs, prompts, skills et configuration d'outils pour un agent donné |
| Run | Exécution d'une fixture sur un ou plusieurs modèles LLM avec un nombre de répétitions donné |
| Case | Unité d'exécution d'un run pour un agent et un modèle spécifique |
| Attempt | Tentative individuelle d'un case (selon `repeat_count`) avec ses scores, latence et token count |
| Score V1 | Ensemble de 5 métriques automatiques (0,0–1,0) évaluant la qualité de la sortie d'un agent |
| Lot A | GH-24 — moteur backend de benchmark (fixtures, engine, scoring, API REST) |
| Lot B | GH-26 — dashboard frontend (ce changement) |
| Lot C | Futur — scoring V2 avec juge LLM |
| ModelSpec | Spécification d'un modèle LLM à benchmarker : provider, model_name, temperature |

---

## 24. ANNEXES

### Scores V1 — Définitions des métriques

| Métrique | Description |
|---|---|
| `schema_validity` | La sortie de l'agent respecte le schéma JSON attendu |
| `completeness` | Les champs obligatoires sont présents et renseignés |
| `tool_policy` | L'utilisation des outils respecte la politique définie |
| `reference_consistency` | La cohérence avec les données de référence figées dans la fixture |
| `stability` | La reproductibilité de la sortie sur plusieurs tentatives |
| `overall` | Moyenne pondérée des 5 métriques ci-dessus |

### Pattern de page de référence — BacktestsPage.tsx

Points clés du pattern à reproduire :
- Import `useAuth` pour le token
- `useState` pour les états locaux (liste, sélection, loading, error)
- `useEffect` pour le chargement initial
- Composant `ButtonSpinner` pour les états de chargement
- Composant `ExpansionPanel` pour les détails dépliables
- Classes CSS : `hw-surface-alt`, `text-text`, `text-text-dim`, `text-text-muted`, `border-border`, `bg-surface`
- Icônes Lucide React

---

## 25. HISTORIQUE DU DOCUMENT

| Version | Date | Auteur | Description |
|---|---|---|---|
| 1.0 | 2026-05-11 | mbensass (@spec-writer) | Création initiale |

---

## DIRECTIVES DE RÉDACTION

Ce document suit les conventions définies dans `.samourai/core/governance/conventions/unified-change-convention-tracker-agnostic-specification.md`.

- IDs stables : `F-`, `API-`, `DM-`, `NFR-`, `AC-`, `DEC-`, `RSK-`, `OQ-`
- Critères d'acceptation au format Given/When/Then
- NFRs quantifiées (seuils mesurables)
- Risques avec Impact & Probabilité (H/M/L)
- Aucune instruction d'implémentation (pas de chemins de fichiers de code, pas de tâches)

## CHECKLIST DE VALIDATION

- [x] Répertoire et nom de fichier suivent les règles de découverte
- [x] Front matter validé (ref, type, status=Proposed, owners ≥ 1)
- [x] Ordre des sections exact (1–25 + directives + checklist)
- [x] Préfixes d'ID cohérents et uniques par catégorie
- [x] Critères d'acceptation référencent au moins un ID et utilisent Given/When/Then
- [x] NFRs incluent des valeurs mesurables
- [x] Risques incluent Impact & Probabilité
- [x] Aucun détail d'implémentation (pas de chemins de fichiers source, pas de tâches)
- [x] Seul le fichier spec est créé dans ce commit
