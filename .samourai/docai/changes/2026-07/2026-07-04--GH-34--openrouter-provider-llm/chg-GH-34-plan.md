# Plan d'implémentation — GH-34 : Provider LLM OpenRouter

## Vue d'ensemble

Ajout d'OpenRouter comme 4ème provider LLM. Extension purement additive : aucun changement de comportement pour Ollama/OpenAI/Mistral.

---

## Phase 1 : Settings

### 1.1 `backend/app/core/config.py`
- [ ] Ajouter 6 champs à la classe `Settings` :
```python
openrouter_base_url: str = Field(default='https://openrouter.ai/api/v1', alias='OPENROUTER_BASE_URL')
openrouter_api_key: str = Field(default='', alias='OPENROUTER_API_KEY')
openrouter_model: str = Field(default='openrouter/auto', alias='OPENROUTER_MODEL')
openrouter_timeout_seconds: int = Field(default=30, alias='OPENROUTER_TIMEOUT_SECONDS')
openrouter_input_cost_per_1m_tokens: float = Field(default=0.0, alias='OPENROUTER_INPUT_COST_PER_1M_TOKENS')
openrouter_output_cost_per_1m_tokens: float = Field(default=0.0, alias='OPENROUTER_OUTPUT_COST_PER_1M_TOKENS')
```

---

## Phase 2 : Model Selector

### 2.1 `backend/app/services/llm/model_selector.py`
- [ ] Ligne 28 : `SUPPORTED_LLM_PROVIDERS = {'ollama', 'openai', 'mistral', 'openrouter'}`

---

## Phase 3 : Provider Client

### 3.1 `backend/app/services/llm/provider_client.py`
- [ ] `__init__` : `self.openrouter = OpenAICompatibleClient('openrouter')`
- [ ] `_provider_client()` : `if provider == 'openrouter': return self.openrouter`

### 3.2 `backend/app/services/llm/openai_compatible_client.py`
- [ ] `_normalized_api_key()` : branche `self.provider == 'openrouter'`
- [ ] `_normalized_base_url()` : branche `self.provider == 'openrouter'`
- [ ] `_default_model()` : branche `self.provider == 'openrouter'`
- [ ] `_timeout_seconds()` : branche `self.provider == 'openrouter'`
- [ ] `_estimate_cost_usd()` : branche `self.provider == 'openrouter'`

---

## Phase 4 : AgentScope

### 4.1 `backend/app/services/agentscope/model_factory.py`
- [ ] `build_model()` : `if provider in ("openai", "mistral", "openrouter"):`

### 4.2 `backend/app/services/agentscope/formatter_factory.py`
- [ ] `build_formatter()` : ajouter `openrouter` au dispatch (utilise `OpenAI*Formatter` comme OpenAI/Mistral)

---

## Phase 5 : Points d'intégration

### 5.1 `backend/app/services/benchmark/engine.py`
- [ ] `_resolve_provider_config()` : `if provider == 'openrouter': return provider, model_name, settings.openrouter_base_url, settings.openrouter_api_key`

### 5.2 `backend/app/services/market/news_provider.py`
- [ ] Résolution provider : ajouter cas `openrouter` pour base_url et api_key

### 5.3 `backend/app/api/routes/health.py`
- [ ] `health()` : `elif llm_provider == 'openrouter': llm_configured = bool((settings.openrouter_api_key or '').strip())`

### 5.4 `backend/app/services/strategy/optimizer_service.py`
- [ ] `_resolve_llm_config()` : `elif provider == 'openrouter': base_url = settings.openrouter_base_url; api_key = settings.openrouter_api_key`

---

## Phase 6 : Documentation

### 6.1 `docs/configuration.md`
- [ ] Ajouter section `### OpenRouter` après Mistral (ligne ~141)

### 6.2 `.env.example`
- [ ] Ajouter les 6 variables OpenRouter avec commentaires

---

## Phase 7 : Tests

### 7.1 `backend/tests/unit/test_openai_compatible_client.py`
- [ ] `test_openrouter_client_base_url()`
- [ ] `test_openrouter_client_default_model()`
- [ ] `test_openrouter_client_is_configured()`
- [ ] `test_openrouter_client_not_configured_without_key()`

### 7.2 `backend/tests/unit/test_llm_provider_client.py`
- [ ] `test_llm_client_uses_openrouter_provider()`

### 7.3 `backend/tests/unit/test_agent_model_selector.py`
- [ ] `test_agent_model_selector_supports_openrouter_provider()`
- [ ] `test_normalize_llm_provider_accepts_openrouter()`

### 7.4 `backend/tests/unit/test_agentscope_model_factory.py`
- [ ] `test_build_openrouter_model()`

---

## Phase 8 : Validation

- [ ] `cd backend && pytest -q` — pas de régression
- [ ] `cd frontend && npm run build` — pas d'impact frontend