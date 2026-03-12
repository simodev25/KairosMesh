# Tests

## Backend

- Unit tests:
  - règles risque
  - décision trader
  - moteur backtest
  - prompt registry versioning
- Integration tests:
  - login
  - création/liste run via API

Commande:
```bash
cd backend
pytest -q
```

## Frontend

- Playwright smoke minimal sur écran login

Commande:
```bash
cd frontend
npm run test:e2e
```
