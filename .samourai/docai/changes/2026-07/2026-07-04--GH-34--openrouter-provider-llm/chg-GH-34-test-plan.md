# Test Plan — GH-34 : Provider LLM OpenRouter

## Stratégie de test

Tests unitaires ciblés sur chaque couche modifiée + test de non-régression global. Aucun test d'intégration/E2E nécessaire (pas de nouveau comportement, pas d'impact frontend).

## Mapping AC → Tests

| AC | Tests |
|----|-------|
| AC1 : Health `llm: configured` | `test_openrouter_health_configured` |
| AC2 : Routage `openrouter.ai` | `test_openrouter_client_base_url`, `test_openrouter_client_default_model` |
| AC3 : `ConnectorConfig(provider='openrouter')` | `test_agent_model_selector_openrouter_provider` |
| AC4 : `build_model('openrouter', ...)` | `test_build_openrouter_model` |
| AC5 : Non-régression | `cd backend && pytest -q` (tous les tests) |
| AC6 : Couverture par couche | Voir tableau ci-dessous |

---

## Cas de test

### 1. Settings (`test_openrouter_settings.py` — nouveau)

| ID | Test | Vérification |
|----|------|-------------|
| T1.1 | `Settings` charge `OPENROUTER_BASE_URL` | `settings.openrouter_base_url == "https://openrouter.ai/api/v1"` |
| T1.2 | `Settings` charge `OPENROUTER_MODEL` | `settings.openrouter_model == "openrouter/auto"` |
| T1.3 | `Settings` valeurs par défaut | Tous les champs ont leur défaut (api_key='', timeout=30, coûts=0.0) |

### 2. Model Selector (`test_agent_model_selector.py` — ajout)

| ID | Test | Vérification |
|----|------|-------------|
| T2.1 | `normalize_llm_provider('openrouter')` | Retourne `'openrouter'` |
| T2.2 | `normalize_llm_provider('OPENROUTER')` | Normalisé → `'openrouter'` |
| T2.3 | `resolve_provider(db)` avec `provider='openrouter'` en DB | Retourne `'openrouter'` |

### 3. LlmClient (`test_llm_provider_client.py` — ajout)

| ID | Test | Vérification |
|----|------|-------------|
| T3.1 | `_provider_client('openrouter')` | Retourne instance `OpenAICompatibleClient` avec `provider='openrouter'` |
| T3.2 | `chat()` avec provider openrouter en DB | `result['provider'] == 'openrouter'` |

### 4. OpenAICompatibleClient (`test_openai_compatible_client.py` — ajout)

| ID | Test | Vérification |
|----|------|-------------|
| T4.1 | `_normalized_base_url()` | `"https://openrouter.ai/api/v1"` |
| T4.2 | `_normalized_api_key()` | Lit `OPENROUTER_API_KEY` |
| T4.3 | `_default_model()` | `"openrouter/auto"` |
| T4.4 | `_timeout_seconds()` | `settings.openrouter_timeout_seconds` |
| T4.5 | `is_configured()` avec clé valide | `True` |
| T4.6 | `is_configured()` sans clé | `False` |

### 5. AgentScope model_factory (`test_agentscope_model_factory.py` — ajout)

| ID | Test | Vérification |
|----|------|-------------|
| T5.1 | `build_model('openrouter', 'openrouter/auto', 'https://openrouter.ai/api/v1', 'key')` | Retourne `OpenAIChatModel` |
| T5.2 | `build_model('openrouter', ...)` a les bons kwargs | `api_key='key'`, `client_kwargs['base_url']` correct |

### 6. AgentScope formatter_factory (`test_agentscope_model_factory.py` — ajout)

| ID | Test | Vérification |
|----|------|-------------|
| T6.1 | `build_formatter('openrouter')` | Retourne `OpenAIChatFormatter` |
| T6.2 | `build_formatter('openrouter', multi_agent=True)` | Retourne `OpenAIMultiAgentFormatter` |

---

## Données de test

- **API key factice** : `"sk-or-v1-test-key"` (format OpenRouter standard : `sk-or-v1-*`)
- **Base URL** : `"https://openrouter.ai/api/v1"`
- **Modèle par défaut** : `"openrouter/auto"`
- **DB ConnectorConfig** : `ConnectorConfig(connector_name='ollama', enabled=True, settings={'provider': 'openrouter'})`

---

## Exécution

```bash
# Tests unitaires ciblés
cd backend && python -m pytest tests/unit/test_openai_compatible_client.py \
  tests/unit/test_llm_provider_client.py \
  tests/unit/test_agent_model_selector.py \
  tests/unit/test_agentscope_model_factory.py -v

# Non-régression
cd backend && pytest -q
```