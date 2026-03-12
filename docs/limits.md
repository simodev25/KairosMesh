# Limites connues V1

- Connecteur MetaApi dépend de la disponibilité du SDK et compte MetaTrader
- Analyse macro simplifiée (proxy volatilité/tendance)
- Pas de gestion avancée portefeuille multi-position en exécution réelle
- Coût LLM estimé (pas de facturation contractuelle exacte)
- Keycloak non branché en V1 (JWT local)

## Améliorations proposées

- Ajout mémoire long-terme vectorielle (Qdrant/pgvector)
- Débat agents enrichi par prompts versionnés en base
- Backtesting et analytics de performance plus avancés
- Support multi-comptes MetaApi
- Dashboards Grafana enrichis par latence/couts LLM
