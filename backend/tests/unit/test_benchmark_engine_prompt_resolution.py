import asyncio
from types import SimpleNamespace

from app.services.benchmark.engine import BenchmarkEngine
from app.services.prompts.registry import DEFAULT_PROMPTS, PromptTemplateService


def _patch_agent_build_dependencies(monkeypatch):
    captured: dict[str, str] = {}

    monkeypatch.setattr(
        'app.services.benchmark.engine.build_model',
        lambda *args, **kwargs: object(),
    )
    monkeypatch.setattr(
        'app.services.benchmark.engine.build_formatter',
        lambda *args, **kwargs: object(),
    )

    async def _fake_build_toolkit(*args, **kwargs):
        return object()

    monkeypatch.setattr('app.services.benchmark.engine.build_toolkit', _fake_build_toolkit)

    def _fake_factory(*, model, formatter, toolkit, sys_prompt):
        captured['sys_prompt'] = sys_prompt
        return {'sys_prompt': sys_prompt}

    monkeypatch.setattr(
        'app.services.benchmark.engine.ALL_AGENT_FACTORIES',
        {'technical-analyst': _fake_factory},
    )
    return captured


def test_build_agent_loads_prompt_from_db_with_fixture_variables(monkeypatch) -> None:
    captured = _patch_agent_build_dependencies(monkeypatch)
    render_calls: dict[str, object] = {}

    def _fake_render(self, db, agent_name, fallback_system, fallback_user, variables):
        render_calls['agent_name'] = agent_name
        render_calls['fallback_system'] = fallback_system
        render_calls['fallback_user'] = fallback_user
        render_calls['variables'] = variables
        return {'system_prompt': 'PROMPT FROM DB'}

    monkeypatch.setattr(PromptTemplateService, 'render', _fake_render)

    fixture = SimpleNamespace(
        inputs={'symbol': 'EURUSD.PRO', 'timeframe': 'M15'},
        config={'llm_enabled': True},
    )
    engine = BenchmarkEngine()

    asyncio.run(
        engine._build_agent(
            run_id=1,
            db=object(),
            agent_name='technical-analyst',
            fixture=fixture,
            model_spec={'provider': 'ollama', 'model_name': 'deepseek-v3.2', 'parameters': {}},
        )
    )

    assert captured['sys_prompt'] == 'PROMPT FROM DB'
    assert render_calls['agent_name'] == 'technical-analyst'
    assert render_calls['variables'] == {'pair': 'EURUSD.PRO', 'timeframe': 'M15'}
    assert render_calls['fallback_system'] == DEFAULT_PROMPTS['technical-analyst']['system']
    assert render_calls['fallback_user'] == DEFAULT_PROMPTS['technical-analyst']['user']


def test_build_agent_prefers_fixture_system_prompt_override(monkeypatch) -> None:
    captured = _patch_agent_build_dependencies(monkeypatch)

    def _fail_if_called(*args, **kwargs):
        raise AssertionError('PromptTemplateService.render should not be called when override exists')

    monkeypatch.setattr(PromptTemplateService, 'render', _fail_if_called)

    fixture = SimpleNamespace(
        inputs={'pair': 'XAUUSD', 'timeframe': 'H4'},
        config={'system_prompt': 'OVERRIDE SYSTEM PROMPT'},
    )
    engine = BenchmarkEngine()

    asyncio.run(
        engine._build_agent(
            run_id=2,
            db=object(),
            agent_name='technical-analyst',
            fixture=fixture,
            model_spec={'provider': 'ollama', 'model_name': 'deepseek-v3.2', 'parameters': {}},
        )
    )

    assert captured['sys_prompt'] == 'OVERRIDE SYSTEM PROMPT'
