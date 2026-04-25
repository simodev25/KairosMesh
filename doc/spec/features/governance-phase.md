# Spécification — Phase Gouvernance

| Champ | Valeur |
|-------|--------|
| **workItemRef** | TODO (créer issue GitHub) |
| **Statut** | Draft |
| **Auteur** | @spec-writer |
| **Date** | 2026-04-25 |
| **Composants impactés** | `backend/app/services/risk_engine*`, `backend/app/services/execution*` |

---

## 1. Contexte

La phase Gouvernance est la 4ème et dernière étape du pipeline Kairos Mesh.
Elle intervient après que l'agent Trader a produit une décision (BUY / SELL / HOLD).

Son rôle est de garantir que **aucun ordre ne peut être soumis à un broker sans avoir
passé un ensemble de vérifications déterministes** — indépendamment du raisonnement LLM.

---

## 2. Objectif

Fournir un garde-fou déterministe entre la décision de l'agent Trader et l'exécution
réelle (paper ou live), en validant :

- les limites de risque du portefeuille
- la conformité de la décision avec les paramètres de stratégie
- les préconditions opérationnelles (connexion broker, mode autorisé)

---

## 3. Périmètre

### Inclus

- Validation du risque : taille de position, exposition maximale, stop-loss minimum
- Preflight checks : mode autorisé (`ALLOW_LIVE_TRADING`), compte broker disponible
- Rejet déterministe avec motif structuré (pas de LLM dans ce chemin)
- Journalisation de chaque décision de gouvernance (APPROVED / REJECTED + motif)
- Mode simulation : gouvernance s'exécute mais aucun ordre n'est soumis

### Exclus

- Modification de la décision de l'agent Trader (la gouvernance approuve ou rejette — elle ne modifie pas)
- Feedback loop vers les agents (pas de mémoire entre les runs)
- Backtesting de la gouvernance (couvert séparément)

---

## 4. Critères d'acceptation

| ID | Critère |
|----|---------|
| GOV-01 | Une décision SELL avec stop-loss > entrée est rejetée avec motif `INVALID_STOPLOSS` |
| GOV-02 | Une décision avec taille de position > limite configurée est rejetée avec motif `POSITION_SIZE_EXCEEDED` |
| GOV-03 | En mode `ALLOW_LIVE_TRADING=false`, toute décision BUY/SELL retourne `SIMULATION_ONLY` — aucun appel broker |
| GOV-04 | Chaque décision de gouvernance est persistée en DB avec timestamp, décision entrante, verdict et motif |
| GOV-05 | Le preflight check échoue proprement si le broker est inaccessible (timeout < 5s, motif `BROKER_UNAVAILABLE`) |
| GOV-06 | La gouvernance n'utilise aucun LLM — 100% code déterministe Python |

---

## 5. Architecture

```
DecisionOutput (Trader)
        │
        ▼
┌───────────────────┐
│  RiskEngine       │  ← Validation position size, SL/TP, exposition
│  (déterministe)   │
└────────┬──────────┘
         │ APPROVED / REJECTED
         ▼
┌───────────────────┐
│  ExecutionManager │  ← Preflight checks (mode, broker, compte)
│                   │
└────────┬──────────┘
         │
    ┌────┴──────────┐
    │               │
SIMULATION       PAPER/LIVE
(DB only)     (MetaAPI call)
```

---

## 6. Interfaces

### Entrée

```python
class DecisionOutput:
    symbol: str
    action: Literal["BUY", "SELL", "HOLD"]
    entry_price: float
    stop_loss: float
    take_profit: float
    position_size: float
    confidence: float
    reasoning: str
```

### Sortie

```python
class GovernanceResult:
    verdict: Literal["APPROVED", "REJECTED", "SIMULATION_ONLY"]
    reason: str | None
    order_id: str | None  # Rempli si APPROVED et broker appelé
    timestamp: datetime
```

---

## 7. Cas limites

| Cas | Comportement attendu |
|-----|---------------------|
| action = HOLD | Gouvernance retourne immédiatement `SIMULATION_ONLY` — aucun check de risque |
| stop_loss = 0 | Rejeté : `STOPLOSS_REQUIRED` |
| Broker timeout | Rejeté : `BROKER_UNAVAILABLE` — ordre non soumis |
| Mode live sans `TRADER_OPERATOR` role | Rejeté : `INSUFFICIENT_PERMISSIONS` |

---

## 8. Tests requis

- Unit : `RiskEngine` avec tableau de cas (paramétrique pytest)
- Unit : `ExecutionManager` preflight en mode simulation
- Intégration : pipeline complet → décision BUY → governance → DB entry
- Intégration : pipeline complet → décision BUY invalide → rejet → pas d'appel broker
