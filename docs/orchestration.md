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

## Enrichissements V1.1

- Les agents `news`, `bullish`, `bearish` utilisent des prompts versionnés en base (`prompt_templates`).
- Le contexte de débat inclut la mémoire long-terme vectorielle (`memory_entries` + Qdrant).
- Chaque run enrichit la mémoire avec un résumé décisionnel réutilisable.

## Traçabilité

- Chaque étape est persistée en base (`agent_steps`)
- Run global dans `analysis_runs`
- Ordres dans `execution_orders`
