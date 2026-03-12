# Données Forex et news

## Source

- `yfinance` pour:
  - historique prix Yahoo Finance (`EURUSD=X`, etc.)
  - news Yahoo Finance

## Normalisation

- Snapshot marché: prix, RSI, EMA20/EMA50, MACD diff, ATR, tendance
- News: titre, publisher, lien, date publication

## Mode dégradé

- Si yfinance indisponible: payload `degraded=true` et run continue
