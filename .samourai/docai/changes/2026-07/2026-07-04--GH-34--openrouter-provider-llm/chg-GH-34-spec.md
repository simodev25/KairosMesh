---
change:
  ref: GH-34
  type: feat
  slug: openrouter-provider-llm
  title: "Ajouter OpenRouter comme provider LLM (API OpenAI-compatible)"
  service: llm-providers
  labels: ["type:feature", "llm"]
  risk_level: low
  dependencies:
    internal: ["llm-client", "model-selector", "agentscope"]
    external: ["openrouter.ai"]
---

# Spécification — GH-34 : Provider LLM OpenRouter

## 1. Problème

Kairos Mesh supporte 3 providers LLM (Ollama, OpenAI, Mistral). OpenRouter permet d'accéder à 300+ modèles (Claude, Gemini, DeepSeek R1, etc.) via une API OpenAI-compatible unifiée — mais n'est pas intégré.

## 2. Objectif

Ajouter OpenRouter comme 4ème provider, en réutilisant le pattern existant `OpenAICompatibleClient` (OpenRouter est 100% compatible API OpenAI).

## 3. Scope

### In
- 6 variables d'env : `OPENROUTER_BASE_URL`, `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`, `OPENROUTER_TIMEOUT_SECONDS`, `OPENROUTER_INPUT_COST_PER_1M_TOKENS`, `OPENROUTER_OUTPUT_COST_PER_1M_TOKENS`
- `'openrouter'` dans `SUPPORTED_LLM_PROVIDERS`
- `OpenAICompatibleClient('openrouter')` instancié dans `LlmClient`
- Dispatch `openrouter` dans les 8 points de résolution provider
- AgentScope `model_factory` et `formatter_factory` (comme OpenAI/Mistral)
- Tests unitaires pour chaque couche modifiée
- Mise à jour `docs/configuration.md` et `.env.example`

### Out
- Pas de SDK dédié OpenRouter
- Pas de modification UI

## 4. Architecture cible

Même pattern que Mistral : 6 champs Settings + dispatch dans les 8 fichiers listés.

Modèle par défaut : `openrouter/auto` (auto-routing OpenRouter).

## 5. Critères d'acceptation

- [ ] **AC1** : `OPENROUTER_API_KEY` + `LLM_PROVIDER=openrouter` → health endpoint `llm: configured`
- [ ] **AC2** : `LLM_PROVIDER=openrouter` → requêtes routées vers `https://openrouter.ai/api/v1`
- [ ] **AC3** : `ConnectorConfig(provider='openrouter')` en DB → sélection dynamique fonctionnelle
- [ ] **AC4** : `build_model('openrouter', ...)` → `OpenAIChatModel` configuré pour OpenRouter
- [ ] **AC5** : Tous les tests existants passent sans régression
- [ ] **AC6** : Nouveaux tests unitaires couvrent `OpenAICompatibleClient('openrouter')`, `LlmClient`, `model_selector`, `model_factory`

## 6. Definition of Done

- [ ] Code implémenté dans les 14 fichiers listés
- [ ] Tests unitaires ajoutés et verts
- [ ] Tests existants sans régression
- [ ] `docs/configuration.md` mis à jour (section OpenRouter)
- [ ] `.env.example` mis à jour (6 variables)
- [ ] `SUPPORTED_LLM_PROVIDERS` inclut `'openrouter'`

## 7. Risques

| Risque | Probabilité | Impact | Mitigation |
|--------|------------|--------|------------|
| Changement API OpenRouter | Faible | Moyen | API OpenAI-compatible standard, rétrocompatibilité garantie par OpenRouter |
| Régression providers existants | Très faible | Élevé | Tests exhaustifs existants préservés |

## 8. Dépendances

- Aucune dépendance interne sur d'autres tickets
- Dépendance externe : API OpenRouter stable (`https://openrouter.ai/api/v1`)

## 9. Fichiers impactés

| Fichier | Changement |
|---------|-----------|
| `backend/app/core/config.py` | 6 champs `openrouter_*` |
| `backend/app/services/llm/model_selector.py` | `SUPPORTED_LLM_PROVIDERS` + `'openrouter'` |
| `backend/app/services/llm/provider_client.py` | `self.openrouter = OpenAICompatibleClient('openrouter')` + dispatch |
| `backend/app/services/llm/openai_compatible_client.py` | Branches `provider == 'openrouter'` (5 méthodes) |
| `backend/app/services/agentscope/model_factory.py` | `'openrouter'` dans la condition `if provider in (...)` |
| `backend/app/services/agentscope/formatter_factory.py` | `'openrouter'` dans la condition |
| `backend/app/services/benchmark/engine.py` | `_resolve_provider_config()` cas openrouter |
| `backend/app/services/market/news_provider.py` | Résolution URL/clé openrouter |
| `backend/app/api/routes/health.py` | `elif llm_provider == 'openrouter'` |
| `backend/app/services/strategy/optimizer_service.py` | `_resolve_llm_config()` cas openrouter |
| `docs/configuration.md` | Section OpenRouter |
| `.env.example` | 6 variables OpenRouter |
| `backend/tests/unit/test_openai_compatible_client.py` | Test `OpenAICompatibleClient('openrouter')` |
| `backend/tests/unit/test_llm_provider_client.py` | Test dispatch openrouter |
| `backend/tests/unit/test_agent_model_selector.py` | Test `resolve_provider` openrouter |
| `backend/tests/unit/test_agentscope_model_factory.py` | Test `build_model('openrouter', ...)` |