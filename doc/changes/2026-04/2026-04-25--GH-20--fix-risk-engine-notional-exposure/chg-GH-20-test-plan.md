---
id: chg-GH-20-fix-risk-engine-notional-exposure-test-plan
change_ref: GH-20
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
  implementation_plan: doc/changes/2026-04/2026-04-25--GH-20--fix-risk-engine-notional-exposure/chg-GH-20-plan.md
summary: >-
  Plan de test pour GH-20 : valider la correction du calcul de `currency_notional_exposure_pct`
  via `account_leverage` (fallback sûr 100.0) et la propagation du levier sur les 4 callsites
  de production (risk rules, MCP trading server, websocket, API portfolio), sans modifier les
  seuils `trading_params.risk_limits` ni les autres règles.
---

## Objectifs de test

- Valider la nouvelle signature et le calcul corrigé de `compute_currency_exposure()`.
- Couvrir les cas de normalisation du levier : 100, 1, 0 (fallback).
- Garantir la propagation du levier réel sur les 4 callsites listés dans la spec.
- Assurer la non-régression des tests existants du risk engine.

## Périmètre

### Dans le périmètre

- `backend/app/services/risk/currency_exposure.py` — `compute_currency_exposure(account_leverage=...)`
- Callsites :
  - `backend/app/services/risk/rules.py` (~660)
  - `backend/app/services/mcp/trading_server.py` (~1494)
  - `backend/app/main.py` (~439)
  - `backend/app/api/routes/portfolio.py` (~46)
- Tests existants :
  - `backend/tests/unit/test_risk_engine_portfolio.py`
  - `backend/tests/unit/test_risk_engine.py`

### Hors périmètre

- Modification de `trading_params.risk_limits`
- Toute autre règle du risk engine (drawdowns, free margin, max positions, sizing, etc.)
- Trading live (`ALLOW_LIVE_TRADING`)

## Pré-requis / Données

- Cas chiffré de référence (spec run-101) :
  - symbole : `USDCHF`
  - volume : `9.81` lots
  - contract_size : `100_000`
  - equity : `47_914`
  - leverage : `100`
  - attendu : `(9.81 × 100_000 / 100 / 47_914) × 100 ≈ 20.5 %` (arrondi à 0.1)
- Convention fallback : `effective_leverage = account_leverage if > 0 else 100.0`

## Stratégie

- Tests unitaires centrés sur `compute_currency_exposure()` pour couvrir le calcul et la normalisation.
- Test d’intégration léger (sans broker) pour prouver que les callsites passent le paramètre de levier.
- Non-régression : exécuter les suites unitaires existantes liées.

## Cas de test

### TC-01 — `compute_currency_exposure()` (leverage=100) reproduit run-101

**But**: Vérifier que l’exposition notionnelle est divisée par 100 sur un compte 100:1.

**Étapes**:

1. Construire une position `USDCHF` avec `volume=9.81` lots et un `contract_size=100_000`.
2. Appeler `compute_currency_exposure(..., equity=47_914, account_leverage=100)` (selon signature réelle).
3. Lire `currency_notional_exposure_pct` (ou la métrique équivalente retournée).

**Attendus**:

- `currency_notional_exposure_pct` ≈ **20.5** (arrondi à 0.1).
- `currency_open_risk_pct` inchangé vs avant correctif sur ce scénario (si couvert par fixtures existantes).

**Automatisation**: Oui — test unitaire (`backend/tests/unit/test_currency_exposure.py`).

### TC-02 — leverage=1 (pas de levier) = comportement historique

**But**: Vérifier que `account_leverage=1` reproduit le calcul brut (pas de division).

**Étapes**:

1. Reprendre un scénario simple (mêmes inputs que TC-01 ou un cas minimal).
2. Calculer l’exposition avec `account_leverage=1`.

**Attendus**:

- `currency_notional_exposure_pct` est identique (à l’arrondi près) à l’ancien calcul brut :
  `(volume × contract_size / equity) × 100`.

**Automatisation**: Oui — test unitaire.

### TC-03 — leverage=0 (invalide) → fallback 100.0

**But**: Garantir un comportement déterministe et sûr sans exception.

**Étapes**:

1. Exécuter `compute_currency_exposure(..., account_leverage=0)` sur le même scénario que TC-01.

**Attendus**:

- Le calcul n’échoue pas.
- Le résultat est équivalent à `account_leverage=100` (fallback) → `~20.5 %` sur run-101.

**Automatisation**: Oui — test unitaire.

### TC-04 — Propagation du levier : 4 callsites passent bien `account_leverage`

**But**: Prévenir toute divergence entre décision et observabilité.

**Approche (intégration légère)**:

- Mettre en place un test qui **instrumente** `compute_currency_exposure()` (patch/spies) et déclenche les 4 chemins (ou leurs fonctions englobantes) avec un `state.leverage` / `portfolio.leverage` non défaut.

**Étapes**:

1. Fixer un levier distinct (ex. 50) dans `PortfolioState.leverage` et/ou `portfolio.leverage`.
2. Déclencher :
   - l’évaluation des règles (chemin `rules.py`)
   - l’enrichissement MCP (chemin `trading_server.py`)
   - le flux websocket (chemin `main.py`)
   - l’endpoint `/portfolio/state` (chemin `portfolio.py`)
3. Vérifier que `compute_currency_exposure()` a été appelée avec `account_leverage=50` (ou la valeur fixée) sur chacun des chemins.

**Attendus**:

- Les 4 callsites passent explicitement le levier (`portfolio.leverage` ou `state.leverage`).
- Aucune divergence visible : les métriques exposées sont cohérentes entre surfaces (au moins sur un même input de test).

**Automatisation**: Oui — test(s) unitaires/integ légère (selon conventions du repo).

### TC-05 — Non-régression : tests risk engine existants

**But**: Garantir que seules les métriques notionnelles attendues changent.

**Étapes**:

1. Exécuter les tests existants liés :
   - `backend/tests/unit/test_risk_engine_portfolio.py`
   - `backend/tests/unit/test_risk_engine.py`
2. Mettre à jour les assertions qui reposaient sur l’ancien calcul brut (notamment autour de la ligne ~214 dans `test_risk_engine_portfolio.py`).

**Attendus**:

- Tous les tests passent.
- Les assertions modifiées deviennent **discriminantes** (pas de seuil trop permissif type 500% qui masquerait une régression).

**Automatisation**: Oui.

## Exécution

Commandes recommandées :

```bash
cd backend && pytest tests/unit/test_currency_exposure.py
cd backend && pytest tests/unit/test_risk_engine_portfolio.py
cd backend && pytest tests/unit/test_risk_engine.py
```

Option non-régression élargie :

```bash
cd backend && pytest
```

## Critères de sortie

- TC-01..TC-05 validés.
- AC de la spec (AC-1..AC-7) démontrables via tests + inspection diff.
- Aucun changement sur `trading_params.risk_limits`.
- Aucun changement sur `ALLOW_LIVE_TRADING`.
