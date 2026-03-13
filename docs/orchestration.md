# Orchestration multi-agent

## Chaîne V1

1. Technical analyst
2. News analyst
3. Macro analyst
4. Sentiment analyst
5. Bullish researcher
6. Bearish researcher
7. Trader agent
8. Risk manager
9. Execution manager

## Niveaux de developpement

- `N3 (avance)` : implemente, branche au workflow principal, resilence/fallback presents, trace exploitable.
- `N2 (intermediaire)` : implemente et stable, logique claire, mais heuristiques encore simples.
- `N1 (basique)` : MVP fonctionnel, regles minimales, precision a renforcer.

## Roles et niveau par agent

| Agent | Nom technique | Role dans le workflow | Implementation actuelle | Niveau |
|---|---|---|---|---|
| Technical analyst | `technical-analyst` | Calcule un signal technique (trend/RSI/MACD) et un score initial. | Classe dediee (`TechnicalAnalystAgent`) avec logique deterministe. | `N2` |
| News analyst | `news-analyst` | Analyse les news Yahoo Finance, produit sentiment + resume. | Classe dediee (`NewsAnalystAgent`) avec appel LLM, prompts versionnes en base, mode degrade. | `N3` |
| Macro analyst | `macro-analyst` | Ajoute un biais macro proxy (volatilite + tendance) pour filtrer le contexte. | Classe dediee (`MacroAnalystAgent`) a heuristiques simples. | `N1` |
| Sentiment analyst | `sentiment-agent` | Donne un signal momentum court terme depuis variation prix. | Classe dediee (`SentimentAgent`) a heuristiques simples. | `N1` |
| Bullish researcher | `bullish-researcher` | Construit la these haussiere et les invalidations. | Classe dediee avec agregation des signaux + debat LLM + prompts versionnes + memoire long-terme. | `N3` |
| Bearish researcher | `bearish-researcher` | Construit la these baissiere et les invalidations. | Classe dediee avec agregation des signaux + debat LLM + prompts versionnes + memoire long-terme. | `N3` |
| Trader agent | `trader-agent` | Agrege les sorties et decide `BUY/SELL/HOLD` + SL/TP + rationale. | Classe dediee (`TraderAgent`) reglee par net score. | `N2` |
| Risk manager | `risk-manager` | Valide/refuse l'ordre, controle risque selon mode, propose volume. | Service `RiskEngine` (pas une classe agent nommee) avec regles explicites. | `N2` |
| Execution manager | `execution-manager` | Execute simulation/paper/live, applique garde-fous et fallback paper. | Service `ExecutionService` + `MetaApiClient` (pas une classe agent nommee). | `N3` |

## Differences run vs backtest

- Run normal (`/runs`) : workflow complet jusqu'a `execution-manager`.
- Backtest `agents_v1` : workflow analyse jusqu'a `risk-manager`; execution broker desactivee par design.

## Mapping code (source of truth)

- Orchestrateur et ordre des etapes : `backend/app/services/orchestrator/engine.py`
- Agents metier : `backend/app/services/orchestrator/agents.py`
- Gestion du risque : `backend/app/services/risk/rules.py`
- Execution : `backend/app/services/execution/executor.py`

## Enrichissements V1.1

- Les agents `news`, `bullish`, `bearish` utilisent des prompts versionnés en base (`prompt_templates`).
- Le contexte de débat inclut la mémoire long-terme vectorielle (`memory_entries` + Qdrant).
- Chaque run enrichit la mémoire avec un résumé décisionnel réutilisable.

## Traçabilité

- Chaque étape est persistée en base (`agent_steps`)
- Run global dans `analysis_runs`
- Ordres dans `execution_orders`
