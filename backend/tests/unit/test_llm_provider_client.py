from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models.connector_config import ConnectorConfig
from app.services.llm.model_selector import AgentModelSelector
from app.services.llm.provider_client import LlmClient


def test_llm_client_uses_db_selected_provider_for_chat() -> None:
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(bind=engine)

    with Session(engine) as db:
        AgentModelSelector.clear_cache()
        db.add(
            ConnectorConfig(
                connector_name='ollama',
                enabled=True,
                settings={'provider': 'mistral'},
            )
        )
        db.commit()

        client = LlmClient()
        client.mistral.chat = lambda *_args, **_kwargs: {'provider': 'mistral', 'text': 'ok', 'degraded': False}  # type: ignore[method-assign]

        result = client.chat('sys', 'usr', model='mistral-small-latest', db=db)
        assert result['provider'] == 'mistral'
        assert result['degraded'] is False


def test_llm_client_lists_models_for_selected_provider() -> None:
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(bind=engine)

    with Session(engine) as db:
        AgentModelSelector.clear_cache()
        db.add(
            ConnectorConfig(
                connector_name='ollama',
                enabled=True,
                settings={'provider': 'openai'},
            )
        )
        db.commit()

        client = LlmClient()
        client.openai.list_models = lambda: {'provider': 'openai', 'models': ['gpt-4o-mini'], 'source': 'mock'}  # type: ignore[method-assign]

        result = client.list_models(db)
        assert result['provider'] == 'openai'
        assert result['models'] == ['gpt-4o-mini']
