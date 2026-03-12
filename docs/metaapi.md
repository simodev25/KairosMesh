# Guide MetaApi

## Variables

- `METAAPI_TOKEN`
- `METAAPI_ACCOUNT_ID`
- `METAAPI_REGION`

## Modes

- Simulation: jamais de call broker
- Paper: tentative MetaApi puis fallback simulé
- Live: désactivé par défaut (`ALLOW_LIVE_TRADING=false`)

## Sécurité

- RBAC pour endpoints trading
- Contrôles risque obligatoires avant exécution
