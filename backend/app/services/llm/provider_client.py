from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.services.llm.model_selector import AgentModelSelector, normalize_llm_provider
from app.services.llm.ollama_client import OllamaCloudClient
from app.services.llm.openai_compatible_client import OpenAICompatibleClient


class LlmClient:
    def __init__(self) -> None:
        self.model_selector = AgentModelSelector()
        self.ollama = OllamaCloudClient()
        self.openai = OpenAICompatibleClient('openai')
        self.mistral = OpenAICompatibleClient('mistral')

    def _resolve_provider(self, db: Session | None) -> str:
        return normalize_llm_provider(self.model_selector.resolve_provider(db), fallback='ollama')

    def _provider_client(self, provider: str) -> Any:
        if provider == 'openai':
            return self.openai
        if provider == 'mistral':
            return self.mistral
        return self.ollama

    def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        db: Session | None = None,
    ) -> dict[str, Any]:
        provider = self._resolve_provider(db)
        client = self._provider_client(provider)
        if provider == 'ollama':
            return client.chat(system_prompt, user_prompt, model=model)
        return client.chat(system_prompt, user_prompt, model=model)

    def list_models(self, db: Session | None = None) -> dict[str, Any]:
        provider = self._resolve_provider(db)
        client = self._provider_client(provider)
        payload = client.list_models()
        if not isinstance(payload, dict):
            return {'provider': provider, 'models': [], 'source': None, 'error': 'Invalid provider response'}
        if 'provider' not in payload:
            payload = {**payload, 'provider': provider}
        return payload
