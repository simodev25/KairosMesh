---
id: chg-GH-20-fix-risk-engine-notional-exposure
status: Proposed
created: 2026-04-25T13:39:22Z
last_updated: 2026-04-25T13:39:22Z
owners:
  - kairos-mesh-team
service: backend/risk-engine
labels:
  - bug
  - risk-engine
  - currency-exposure
  - leverage
links:
  change_spec: doc/changes/2026-04/2026-04-25--GH-20--fix-risk-engine-notional-exposure/chg-GH-20-spec.md
summary: >-
  Corriger GH-20 : `currency_notional_exposure_pct` est surévalué d’un facteur égal au levier
  du compte (ex. ×100 en 100:1) car `compute_currency_exposure()` calcule un notionnel brut.
  Le correctif introduit `account_leverage` (défaut sûr 100.0) et propage le levier réel à
  tous les callsites de production.
version_impact: patch
---

## Context and Goals

### Contexte

- **Bug** : `currency_notional_exposure_pct` est calculé sur un notionnel brut (lots → unités via `volume × contract_size`) sans tenir compte du levier, ce qui gonfle l’exposition d’un facteur égal au levier.
- **Root cause confirmée (@architect)** : `backend/app/services/risk/currency_exposure.py` (ligne ~140) — `base_units = pos.volume * contract_size * sign` doit être divisé par `account_leverage` (normalisé).
- **Impact** : faux positifs de blocage sur les règles de concentration notionnelle + incohérences d’observabilité (MCP / API / websocket).

### Objectifs (alignés spec)

- G-1 : intégrer le levier de compte dans `compute_currency_exposure()`.
- G-2 : reproduire run-101 (USDCHF, 9.81 lots, equity=47_914, leverage=100) → **~20.5 %**.
- G-3 : propager le levier réel à **tous** les callsites de production existants.
- G-4 : ne pas modifier `trading_params.risk_limits` ni les autres règles du risk engine.
- G-5 : conserver un défaut sûr `account_leverage=100.0` si info absente/invalide.
- G-6 : ajouter une couverture de test empêchant la régression.

### Open questions

- Aucune question ouverte identifiée dans la spec (les callsites cibles et la normalisation sont explicités).

## Scope

### In Scope

- Modifier la signature de `compute_currency_exposure()` pour accepter `account_leverage: float = 100.0`.
- Normaliser `account_leverage` en `effective_leverage = account_leverage if > 0 else 100.0`.
- Corriger la formule : `base_units = volume_lots × contract_size × sign / effective_leverage`.
- Propager `account_leverage` sur 4 callsites de production :
  1. `backend/app/services/risk/rules.py` (~660) — passer `portfolio.leverage`
  2. `backend/app/services/mcp/trading_server.py` (~1494) — passer `state.leverage`
  3. `backend/app/main.py` (~439) — passer le levier disponible (cf. `state.leverage` en spec)
  4. `backend/app/api/routes/portfolio.py` (~46) — passer le levier disponible (cf. `state.leverage` en spec)
- Mettre à jour/ajouter les tests unitaires :
  - Ajouter un test chiffré « run-101 » (9.81 lots, equity=47_914, leverage=100 → ~20.5 %)
  - Corriger les tests existants qui encodent l’ancien calcul brut (dont `backend/tests/unit/test_risk_engine_portfolio.py` ligne ~214 : seuil 500% masquant le bug).

### Out of Scope

- Modifier les seuils `trading_params.risk_limits`.
- Modifier toute autre règle du risk engine (drawdown, free margin, max positions, sizing, etc.).
- Activer le trading live ou changer `ALLOW_LIVE_TRADING`.

### Constraints

- Zone sensible : modifications sous `backend/app/services/risk/*` → revue `@architect` requise (référence : AGENTS.md).
- Compatibilité : aucun appel ne doit lever d’exception si le levier est absent/invalide (fallback 100.0).

### Risks

- Divergence décision/observabilité si un callsite n’est pas aligné (API/websocket/MCP vs risk engine).
- Tests existants : attentes implicites basées sur notionnel brut → nécessité d’ajustements ciblés.

### Success Metrics

- Le cas run-101 retourne **20.5 %** (arrondi à 0.1) au lieu de **2047.4 %**.
- `currency_open_risk_pct` reste inchangé avant/après sur les cas existants.
- Aucun diff sur `trading_params.risk_limits`.

## Phases

### Phase 1: Correction du calcul d’exposition par devise

**Goal**: Introduire `account_leverage` et corriger le calcul du notionnel ramené au capital mobilisé.

**Tasks**:

- [ ] Modifier la signature de `compute_currency_exposure()` : ajouter `account_leverage: float = 100.0`.
- [ ] Implémenter la normalisation : `effective_leverage = account_leverage if account_leverage > 0 else 100.0`.
- [ ] Corriger la formule : diviser `base_units` par `effective_leverage` (et laisser `quote_units` dériver de ce `base_units` corrigé).
- [ ] Vérifier explicitement que `net_exposure_lots` et `currency_open_risk_pct` ne changent pas (pas de modification d’algorithme hors notionnel).

**Acceptance Criteria**:

- Must: la signature accepte `account_leverage` avec défaut 100.0.
- Must: `base_units` est divisé par le levier effectif (fallback 100.0 si levier invalide).
- Must: `currency_open_risk_pct` inchangé (via tests).

**Files and modules**:

- `backend/app/services/risk/currency_exposure.py`

**Tests**:

- Unit: `backend/tests/unit/test_currency_exposure.py`

**Completion signal**: commit incluant le nouveau paramètre + formule corrigée + tests unitaires associés.

### Phase 2: Propagation du levier sur les callsites de production

**Goal**: Éviter toute divergence entre décision risk engine et surfaces d’observabilité.

**Tasks**:

- [ ] `backend/app/services/risk/rules.py` (~660) : passer `portfolio.leverage` à `compute_currency_exposure()`.
- [ ] `backend/app/services/mcp/trading_server.py` (~1494) : passer `state.leverage` à `compute_currency_exposure()`.
- [ ] `backend/app/main.py` (~439) : passer le levier disponible (attendu : `state.leverage` selon la spec).
- [ ] `backend/app/api/routes/portfolio.py` (~46) : passer le levier disponible (attendu : `state.leverage` selon la spec).

**Acceptance Criteria**:

- Must: les 4 callsites listés passent un levier explicite.
- Must: aucun changement des seuils `trading_params.risk_limits`.
- Should: alignement des métriques `currency_notional_exposure_pct` entre risk engine, API, websocket et MCP.

**Files and modules**:

- `backend/app/services/risk/rules.py`
- `backend/app/services/mcp/trading_server.py`
- `backend/app/main.py`
- `backend/app/api/routes/portfolio.py`

**Tests**:

- Unit / integration légère (voir Phase 3) : validation que le levier est bien propagé.

**Completion signal**: diff montrant l’ajout de `account_leverage=...` (ou param positionnel) sur les 4 callsites.

### Phase 3: Tests unitaires et non-régression

**Goal**: Capturer le bug GH-20 et empêcher le retour (incluant le cas run-101).

**Tasks**:

- [ ] Ajouter un test « run-101 » : `volume=9.81`, `equity=47_914`, `account_leverage=100` → `currency_notional_exposure_pct ≈ 20.5 %` (arrondi à 0.1).
- [ ] Ajouter des tests de normalisation :
  - [ ] `account_leverage=1` (pas de levier) → même résultat que l’ancien calcul brut.
  - [ ] `account_leverage=0` (invalide) → fallback 100.0.
- [ ] Mettre à jour les tests existants impactés :
  - [ ] `backend/tests/unit/test_risk_engine_portfolio.py` (~214) : corriger l’attente (le seuil 500% masque le bug ; rendre l’assertion discriminante).
  - [ ] `backend/tests/unit/test_risk_engine.py` : ajuster toute attente dépendant du notionnel brut (si applicable).
- [ ] Ajouter/adapter un test d’intégration léger garantissant que les 4 callsites utilisent le levier (approche via appel de haut niveau ou patch/spies selon conventions tests du repo).

**Acceptance Criteria**:

- Must: le cas run-101 échoue avant correctif et passe après (exposition ~20.5%).
- Must: non-régression : `currency_open_risk_pct` inchangé sur les scénarios existants.
- Must: les tests existants passent sans relâcher les garanties (pas de seuil trop permissif).

**Files and modules**:

- `backend/tests/unit/test_currency_exposure.py`
- `backend/tests/unit/test_risk_engine_portfolio.py`
- `backend/tests/unit/test_risk_engine.py`

**Tests**:

- `pytest backend/tests/unit/test_currency_exposure.py`
- `pytest backend/tests/unit/test_risk_engine_portfolio.py`
- `pytest backend/tests/unit/test_risk_engine.py`

**Completion signal**: suite unitaire verte avec nouvelles assertions chiffrées.

### Phase 4: Documentation & Spec Synchronization

**Goal**: Garantir l’alignement doc/spec avec l’implémentation finale.

**Tasks**:

- [ ] Vérifier que l’implémentation respecte strictement la spec (signature, fallback, callsites).
- [ ] Si un détail diverge, proposer une mise à jour minimale de la spec (sans élargir le scope) — sinon aucune modification.

**Acceptance Criteria**:

- Must: pas de divergence entre spec et code final.

**Files and modules**:

- `doc/changes/2026-04/2026-04-25--GH-20--fix-risk-engine-notional-exposure/chg-GH-20-spec.md`

**Tests**:

- N/A (contrôle documentaire)

**Completion signal**: checklist « spec alignée » validée.

### Phase 5: Code Review (Analysis)

**Goal**: Obtenir la revue requise sur la zone sensible risk engine.

**Tasks**:

- [ ] Demander une revue `@architect` sur les changements sous `backend/app/services/risk/*`.
- [ ] Vérifier en review : aucun changement des règles hors notionnel, aucun changement des seuils de config.

**Acceptance Criteria**:

- Must: revue `@architect` approuvée sur la correction du calcul et la propagation.

**Files and modules**:

- (selon diff)

**Tests**:

- Relecture des résultats de tests unitaires.

**Completion signal**: commentaire d’approbation / LGTM `@architect`.

### Phase 6: Post-Code Review Fixes (conditional)

**Goal**: Intégrer les retours de review si nécessaires.

**Tasks**:

- [ ] Appliquer les ajustements demandés.
- [ ] Rejouer les tests ciblés.

**Acceptance Criteria**:

- Must: aucune régression, tests verts.

**Files and modules**:

- (selon retours)

**Tests**:

- `pytest backend/tests/unit`

**Completion signal**: commit(s) correctifs post-review si requis.

### Phase 7: Finalize and Release

**Goal**: Finaliser le change patch en respectant les conventions repo.

**Tasks**:

- [ ] Bump de version **patch** selon conventions du dépôt (conformément à `version_impact: patch`).
- [ ] Reconciliation spec : confirmer que tous les critères AC-1..AC-7 sont couverts et traçables.
- [ ] Vérifier que `ALLOW_LIVE_TRADING` reste `false` (aucune modification).

**Acceptance Criteria**:

- Must: version bump patch effectué.
- Must: AC-1..AC-7 satisfaits.

**Files and modules**:

- (selon conventions versioning du repo)

**Tests**:

- `cd backend && pytest`
- `cd frontend && npm run build`

**Completion signal**: PR prête avec build/tests verts + version bump patch.

## Test Scenarios

- S-01 : `compute_currency_exposure()` avec `account_leverage=100` sur cas run-101 → `~20.5 %`.
- S-02 : `account_leverage=1` → comportement équivalent au calcul historique (notionnel brut).
- S-03 : `account_leverage=0` → fallback 100.0.
- S-04 : Les 4 callsites passent le levier explicite et alignent les surfaces (MCP/API/websocket/rules).
- S-05 : Non-régression sur `currency_open_risk_pct` et règles non-notionnelles.

## Artifacts and Links

- Spec : `doc/changes/2026-04/2026-04-25--GH-20--fix-risk-engine-notional-exposure/chg-GH-20-spec.md`
- Code (cibles) :
  - `backend/app/services/risk/currency_exposure.py`
  - `backend/app/services/risk/rules.py`
  - `backend/app/services/mcp/trading_server.py`
  - `backend/app/main.py`
  - `backend/app/api/routes/portfolio.py`
- Tests :
  - `backend/tests/unit/test_currency_exposure.py`
  - `backend/tests/unit/test_risk_engine_portfolio.py`
  - `backend/tests/unit/test_risk_engine.py`

## Plan Revision Log

- 2026-04-25T13:39:22Z — Création initiale du plan pour GH-20 (propagation leverage + tests run-101).

## Execution Log

- (à remplir pendant l’implémentation)
