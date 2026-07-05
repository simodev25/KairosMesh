from app.services.llm.openai_compatible_client import OpenAICompatibleClient


def test_openai_client_prefers_runtime_connector_api_key(monkeypatch) -> None:
    client = OpenAICompatibleClient('openai')
    client.settings.openai_api_key = 'env-openai'

    monkeypatch.setattr(
        'app.services.llm.openai_compatible_client.RuntimeConnectorSettings.get_string',
        lambda _connector_name, keys, **_kwargs: 'runtime-openai' if 'OPENAI_API_KEY' in keys else '',
    )

    assert client._normalized_api_key() == 'runtime-openai'


def test_mistral_client_prefers_runtime_connector_api_key(monkeypatch) -> None:
    client = OpenAICompatibleClient('mistral')
    client.settings.mistral_api_key = 'env-mistral'

    monkeypatch.setattr(
        'app.services.llm.openai_compatible_client.RuntimeConnectorSettings.get_string',
        lambda _connector_name, keys, **_kwargs: 'runtime-mistral' if 'MISTRAL_API_KEY' in keys else '',
    )

    assert client._normalized_api_key() == 'runtime-mistral'


def test_openrouter_client_base_url() -> None:
    client = OpenAICompatibleClient('openrouter')
    client.settings.openrouter_base_url = 'https://openrouter.ai/api/v1'
    assert client._normalized_base_url() == 'https://openrouter.ai/api/v1'


def test_openrouter_client_default_model() -> None:
    client = OpenAICompatibleClient('openrouter')
    assert client._default_model() == 'openrouter/auto'


def test_openrouter_client_not_configured_without_key() -> None:
    client = OpenAICompatibleClient('openrouter')
    client.settings.openrouter_api_key = ''
    assert client.is_configured() is False
