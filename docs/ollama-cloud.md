# Guide Ollama Cloud

## Variables d'environnement

- `OLLAMA_BASE_URL` (ex: `https://api.ollama.com`)
- `OLLAMA_API_KEY`
- `OLLAMA_MODEL`
- `OLLAMA_TIMEOUT_SECONDS`

## Comportement

- Client: `backend/app/services/llm/ollama_client.py`
- Endpoint utilisé: `/api/chat`
- Retry exponentiel x3
- Log minimal des appels
- Fallback déterministe si clé manquante ou indisponibilité
