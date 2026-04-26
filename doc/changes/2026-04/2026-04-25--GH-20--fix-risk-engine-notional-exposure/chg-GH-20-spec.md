---
change:
  ref: GH-20
  type: fix
  status: Proposed
  slug: fix-risk-engine-notional-exposure
  title: "Correction du calcul d'exposition notionnelle par devise dans le risk engine"
  owners: [kairos-mesh-team]
  service: backend/risk-engine
  labels: [bug, risk-engine, currency-exposure, leverage]
  version_impact: patch
  audience: internal
  security_impact: none
  risk_level: high
  dependencies:
    internal: [risk-engine, portfolio-state, portfolio-api, trading-server]
    external: []
---

# CHANGE SPECIFICATION

> **PURPOSE** — Corriger le bug GH-20 : `currency_notional_exposure_pct` est surévalué d'un facteur égal au levier du compte, ce qui déclenche à tort les règles de concentration notionnelle du risk engine et affiche des métriques incohérentes dans les surfaces d'observabilité.

---

## 1. SOMMAIRE

Le calcul actuel de `compute_currency_exposure()` transforme les lots en unités nominales via
`volume × contract_size`, sans tenir compte du levier du compte. Pour un compte forex à levier
100:1, cela gonfle artificiellement `currency_notional_exposure_pct` d'un facteur 100.

Le correctif attendu consiste à introduire `account_leverage` dans `compute_currency_exposure()`
avec une valeur par défaut sûre de `100.0`, puis à propager la valeur réelle du portefeuille
depuis tous les callsites de production qui disposent déjà de `state.leverage` ou
`portfolio.leverage`.

---

## 2. CONTEXTE

### 2.1 Root cause confirmée

Le point de calcul concerné est `backend/app/services/risk/currency_exposure.py` :

- `compute_currency_exposure()` est défini vers la ligne **108**.
- La formule actuelle calcule `base_units = pos.volume * contract_size * sign` vers la ligne **140**.
- `quote_units` est ensuite dérivé depuis `base_units`, donc l'erreur se propage aux deux jambes de la paire.

### 2.2 Exemple concret — run-101

| Donnée | Valeur |
|--------|--------|
| Symbole | `USDCHF` |
| Volume | `9.81` lots |
| Equity | `47 914` USD |
| Levier | `100` |

**Calcul actuel (incorrect)**

`(9.81 × 100 000 / 47 914) × 100 = 2047.4 %`

**Calcul attendu (corrigé)**

`(9.81 × 100 000 / 100 / 47 914) × 100 = 20.5 %`

Conséquence métier : le trade est bloqué à tort alors que `20.5 %` reste inférieur à la limite
de blocage configurée à `22 %`.

### 2.3 Constat d'architecture / périmètre réel

Les callsites de production de `compute_currency_exposure()` ne se limitent pas au risk engine :

| Fichier | Ligne repère | Usage |
|--------|--------------|-------|
| `backend/app/services/risk/rules.py` | ~660 | Application des limites `currency_notional_exposure_pct` |
| `backend/app/services/mcp/trading_server.py` | ~1494 | Enrichissement du résumé portefeuille exposé au serveur MCP |
| `backend/app/main.py` | ~439 | Flux websocket portfolio |
| `backend/app/api/routes/portfolio.py` | ~46 | Endpoint `/portfolio/state` |

`PortfolioState.leverage` existe déjà dans `backend/app/services/risk/portfolio_state.py` :

- attribut du dataclass vers la ligne **35** avec défaut `100.0`
- alimentation depuis MetaAPI vers la ligne **137** via `info.get("leverage", 100)`

Le chemin correct du serveur MCP est **`backend/app/services/mcp/trading_server.py`**
(et non `services/agentscope/trading_server.py`).

---

## 3. ÉNONCÉ DU PROBLÈME

Le risk engine et les vues de portefeuille consomment une métrique de concentration notionnelle
calculée sur un notionnel brut au lieu d'un notionnel ramené au capital réellement mobilisé.
Cette erreur produit des faux positifs de blocage, des warnings artificiels et une observabilité
incohérente entre le risque réellement supporté et les pourcentages exposés.

---

## 4. OBJECTIFS

| ID | Objectif |
|----|----------|
| G-1 | Corriger `currency_notional_exposure_pct` pour intégrer le levier du compte |
| G-2 | Reproduire le cas run-101 avec un résultat cible de `20.5 %` |
| G-3 | Propager le levier réel à tous les callsites de production existants |
| G-4 | Ne modifier ni les seuils `trading_params.risk_limits` ni les autres règles du risk engine |
| G-5 | Conserver un défaut sûr `account_leverage=100.0` si l'information n'est pas fournie |
| G-6 | Ajouter une couverture de test empêchant le retour du bug |

### 4.1 Non-objectifs

- [OUT] Modifier les seuils `max_currency_notional_exposure_pct_warn` ou `max_currency_notional_exposure_pct_block`
- [OUT] Refondre le modèle de marge ou introduire un levier par instrument
- [OUT] Changer la logique de `currency_open_risk_pct`
- [OUT] Changer les autres règles du risk engine (drawdown, free margin, max positions, sizing)

---

## 5. COMPORTEMENT ACTUEL VS ATTENDU

### 5.1 Formule actuelle

Pour chaque position, l'algorithme calcule aujourd'hui :

- `base_units = volume_lots × contract_size × sign`
- `quote_units = -(base_units × price)`

Puis :

- `net_value = abs(net_units) × rate_to_account`
- `currency_notional_exposure_pct = (net_value / equity) × 100`

### 5.2 Formule attendue

L'algorithme doit calculer un notionnel ramené au capital mobilisé :

- `effective_leverage = account_leverage si > 0, sinon 100.0`
- `base_units = volume_lots × contract_size × sign / effective_leverage`
- `quote_units = -(base_units × price)`

### 5.3 Effet attendu sur le système

| Zone | Effet attendu |
|------|---------------|
| `currency_notional_exposure_pct` | Baisse proportionnelle au levier (ex. ÷100 pour un compte 100:1) |
| `currency_open_risk_pct` | Inchangé |
| `free_margin_pct`, `daily_drawdown_pct`, `weekly_drawdown_pct`, `max_positions` | Inchangés |
| Seuils `trading_params.risk_limits` | Inchangés |
| Payloads API / websocket / MCP | Valeurs alignées avec le risk engine |

---

## 6. PÉRIMÈTRE & FRONTIÈRES

### 6.1 Dans le périmètre

#### A. Moteur de calcul

1. `backend/app/services/risk/currency_exposure.py`
   - `compute_currency_exposure()` ligne repère **108**
   - Ajouter le paramètre `account_leverage: float = 100.0`
   - Corriger la formule ligne repère **140** pour diviser par le levier effectif

#### B. Callsites de production à aligner

2. `backend/app/services/risk/rules.py`
   - appel ligne repère **660**
   - passer `portfolio.leverage`

3. `backend/app/services/mcp/trading_server.py`
   - appel ligne repère **1494**
   - passer `state.leverage`

4. `backend/app/main.py`
   - appel ligne repère **439**
   - passer `state.leverage`

5. `backend/app/api/routes/portfolio.py`
   - appel ligne repère **46**
   - passer `state.leverage`

#### C. Couverture de tests

6. `backend/tests/unit/test_currency_exposure.py`
   - ajouter/adapter les tests de calcul pour refléter le défaut `100.0`
   - ajouter un cas reproduisant run-101 ou son équivalent unitaire
   - garantir qu'aucun autre indicateur du rapport n'est impacté hors notionnel attendu

### 6.2 Hors périmètre

- [OUT] `PortfolioStateService.get_current_state()` : le levier existe déjà et est correctement alimenté
- [OUT] Toute modification des limites métier dans `trading_params.risk_limits`
- [OUT] Toute modification de `RiskEngine.evaluate()` hors propagation du paramètre vers `compute_currency_exposure()`

---

## 7. SPÉCIFICATION DÉTAILLÉE

### F-1 — Signature de `compute_currency_exposure()`

- La fonction accepte un nouveau paramètre optionnel `account_leverage: float = 100.0`.
- Si l'appelant ne fournit pas cette valeur, le comportement par défaut reste déterministe et sûr.

### F-2 — Normalisation du levier

- Le calcul utilise `effective_leverage`.
- Si `account_leverage` n'est pas un nombre strictement positif, la valeur de repli est `100.0`.
- Aucun appel ne doit lever d'exception pour un levier absent ou invalide.

### F-3 — Nouveau calcul notionnel

- `base_units` doit être divisé par `effective_leverage`.
- `quote_units` doit être dérivé à partir de ce `base_units` déjà corrigé.
- `net_exposure_lots` ne doit pas être modifié par ce correctif.
- `currency_open_risk_pct` ne doit pas être modifié par ce correctif.

### F-4 — Propagation du levier réel

- `rules.py` doit utiliser `portfolio.leverage` pour la décision risk engine.
- Les surfaces d'observabilité (`trading_server.py`, `main.py`, `portfolio.py`) doivent aussi utiliser
  le levier réel afin d'éviter une divergence entre décision et affichage.

### F-5 — Compatibilité fonctionnelle

- Les seuils de configuration existants restent inchangés.
- Le correctif doit uniquement modifier la métrique de notionnel exposé.
- Toute évolution future vers un levier par instrument est explicitement hors scope de GH-20.

---

## 8. CRITÈRES D'ACCEPTATION VÉRIFIABLES

| ID | Critère | Vérification attendue |
|----|---------|-----------------------|
| AC-1 | `compute_currency_exposure()` accepte `account_leverage` avec défaut `100.0` | Signature inspectable + tests unitaires |
| AC-2 | Le cas run-101 produit `currency_notional_exposure_pct = 20.5` (arrondi à 0.1) | Test unitaire dédié ou reproduction contrôlée |
| AC-3 | `rules.py` passe `portfolio.leverage` à `compute_currency_exposure()` | Revue de code ciblée |
| AC-4 | `trading_server.py`, `main.py` et `portfolio.py` passent `state.leverage` à `compute_currency_exposure()` | Revue de code ciblée |
| AC-5 | `currency_open_risk_pct` reste identique avant/après correctif sur les cas de test existants | Suite unitaire |
| AC-6 | Aucun seuil de `trading_params.risk_limits` n'est modifié | Diff ciblé |
| AC-7 | Les règles hors notionnel (`free_margin_pct`, drawdowns, max positions, sizing) ne changent pas de comportement | Revue ciblée + non-régression tests |

### 8.1 Cas d'acceptation chiffré minimal

Pour une position `USDCHF` de `9.81` lots, `equity=47_914`, `account_leverage=100` :

- exposition actuelle observée : `2047.4 %`
- exposition corrigée attendue : `20.5 %`

Le trade ne doit plus être bloqué pour le seul motif `currency_notional_exposure_pct` si la
limite de blocage reste `22 %`.

---

## 9. RISQUES, EFFETS DE BORD ET GARDE-FOUS

### 9.1 Risques identifiés

- **R-1** — Ne corriger que `rules.py` et `trading_server.py` laisserait des valeurs aberrantes dans l'API portfolio et le websocket.
- **R-2** — Les tests unitaires actuels sur le notionnel implicite forex/crypto/métal peuvent devenir invalides si leurs attentes reposent sur l'ancien calcul brut.
- **R-3** — Le levier est aujourd'hui un levier de compte, pas un levier par instrument ; le correctif améliore fortement la cohérence sans modéliser tous les cas broker.

### 9.2 Garde-fous

- Aligner tous les callsites de production recensés.
- Ajouter des assertions explicites sur les cas unitaires forex à levier 100.
- Limiter le changement au calcul de `currency_notional_exposure_pct` et à sa propagation.

---

## 10. STRATÉGIE DE TEST

- Tests unitaires sur `compute_currency_exposure()` pour :
  - défaut `account_leverage=100.0`
  - levier explicite `100`
  - levier invalide ou absent → fallback `100.0`
  - non-régression sur `currency_open_risk_pct`
- Vérification ciblée des callsites pour confirmer la propagation du levier réel.

---

## 11. CONTRAINTES DE MISE EN ŒUVRE

- Zone sensible : changement dans `backend/app/services/risk/*` soumis à revue architect.
- Aucun changement de seuils de configuration dans `trading_params.risk_limits`.
- Valeur par défaut obligatoire : `account_leverage=100.0` si non fournie.
- Aucun impact intentionnel sur les autres règles du risk engine.

---

## 12. RÉFÉRENCES

- `backend/app/services/risk/currency_exposure.py`
- `backend/app/services/risk/rules.py`
- `backend/app/services/risk/portfolio_state.py`
- `backend/app/services/mcp/trading_server.py`
- `backend/app/main.py`
- `backend/app/api/routes/portfolio.py`
- `backend/tests/unit/test_currency_exposure.py`
- `doc/changes/2026-04/2026-04-25--GH-20--fix-risk-engine-notional-exposure/chg-GH-20-pm-notes.yaml`
