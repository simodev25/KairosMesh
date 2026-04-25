import re
import sys
import types

import pytest


if "agentscope" not in sys.modules:
    _agentscope = types.ModuleType("agentscope")
    _agentscope_message = types.ModuleType("agentscope.message")
    _agentscope_pipeline = types.ModuleType("agentscope.pipeline")
    _agentscope_agent = types.ModuleType("agentscope.agent")
    _agentscope_memory = types.ModuleType("agentscope.memory")
    _agentscope_formatter = types.ModuleType("agentscope.formatter")
    _agentscope_model = types.ModuleType("agentscope.model")
    _agentscope_tool = types.ModuleType("agentscope.tool")
    _agentscope_tool_toolkit = types.ModuleType("agentscope.tool._toolkit")

    class _DummyMsg:
        def __init__(self, name="", content="", role="assistant", metadata=None):
            self.name = name
            self.content = content
            self.role = role
            self.metadata = metadata or {}

        def get_text_content(self):
            return self.content

    async def _dummy_fanout_pipeline(*_args, **_kwargs):
        return []

    class _DummyMsgHub:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class _DummyReActAgent:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

    class _DummyInMemoryMemory:
        async def get_memory(self):
            return []

    class _DummyFormatter:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

    class _DummyModel:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

    class _DummyTextBlock:
        def __init__(self, type="text", text=""):
            self.type = type
            self.text = text

    class _DummyToolResponse:
        def __init__(self, content=None):
            self.content = content or []

    class _DummyToolkit:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs
            self.skills = {}

        def register_tool_function(self, *_args, **_kwargs):
            return None

        def register_agent_skill(self, *_args, **_kwargs):
            return None

    class _DummyAgentSkill:
        def __init__(self, name="", description="", dir=""):
            self.name = name
            self.description = description
            self.dir = dir

    _agentscope_message.Msg = _DummyMsg
    _agentscope_message.TextBlock = _DummyTextBlock
    _agentscope_pipeline.fanout_pipeline = _dummy_fanout_pipeline
    _agentscope_pipeline.MsgHub = _DummyMsgHub
    _agentscope_agent.ReActAgent = _DummyReActAgent
    _agentscope_memory.InMemoryMemory = _DummyInMemoryMemory
    _agentscope_formatter.OllamaChatFormatter = _DummyFormatter
    _agentscope_formatter.OllamaMultiAgentFormatter = _DummyFormatter
    _agentscope_formatter.OpenAIChatFormatter = _DummyFormatter
    _agentscope_formatter.OpenAIMultiAgentFormatter = _DummyFormatter
    _agentscope_model.OllamaChatModel = _DummyModel
    _agentscope_model.OpenAIChatModel = _DummyModel
    _agentscope_tool.Toolkit = _DummyToolkit
    _agentscope_tool.ToolResponse = _DummyToolResponse
    _agentscope_tool_toolkit.AgentSkill = _DummyAgentSkill

    sys.modules["agentscope"] = _agentscope
    sys.modules["agentscope.message"] = _agentscope_message
    sys.modules["agentscope.pipeline"] = _agentscope_pipeline
    sys.modules["agentscope.agent"] = _agentscope_agent
    sys.modules["agentscope.memory"] = _agentscope_memory
    sys.modules["agentscope.formatter"] = _agentscope_formatter
    sys.modules["agentscope.model"] = _agentscope_model
    sys.modules["agentscope.tool"] = _agentscope_tool
    sys.modules["agentscope.tool._toolkit"] = _agentscope_tool_toolkit

from app.services.agentscope.registry import (
    AgentScopeRegistry,
    _detect_missing_placeholders,
)
from app.services.prompts.registry import SafeDict


def assert_no_missing_placeholders(prompt: str) -> None:
    assert "<MISSING:" not in prompt, (
        "Placeholder(s) détecté(s) dans le prompt: "
        f"{re.findall(r'<MISSING:[^>]+>', prompt)}"
    )


def test_gh19_cause_a_defaults_present_without_tool_results() -> None:
    registry = AgentScopeRegistry()
    variables = registry._build_prompt_variables(
        pair="EURUSD",
        timeframe="H1",
        snapshot={},
        news={},
    )

    assert "tool_results_block" in variables
    assert "interpretation_rules_block" in variables
    assert isinstance(variables["tool_results_block"], str)
    assert isinstance(variables["interpretation_rules_block"], str)

    rendered = (
        "Tool results:\n{tool_results_block}\n\n"
        "Interpretation rules:\n{interpretation_rules_block}"
    ).format_map(SafeDict(**variables))
    assert_no_missing_placeholders(rendered)


def test_gh19_cause_a_builds_tool_results_block_from_snapshot() -> None:
    registry = AgentScopeRegistry()
    snapshot = {
        "trend": "bullish",
        "rsi": 58.4,
        "macd_diff": 0.0012,
        "atr": 0.0021,
        "ema_fast": 1.101,
        "ema_slow": 1.098,
        "change_pct": 0.24,
    }
    variables = registry._build_prompt_variables(
        pair="EURUSD",
        timeframe="H1",
        snapshot=snapshot,
        news={},
    )

    assert "indicator_bundle" in variables["tool_results_block"]
    rendered = "{tool_results_block}\n{interpretation_rules_block}".format_map(SafeDict(**variables))
    assert_no_missing_placeholders(rendered)


def test_gh19_cause_b_defaults_when_risk_out_missing() -> None:
    registry = AgentScopeRegistry()
    variables = registry._build_prompt_variables(
        pair="EURUSD",
        timeframe="H1",
        snapshot={},
        news={},
        risk_out=None,
    )

    assert variables["risk_approved"] == "False"
    assert variables["risk_volume"] == "0.0"

    rendered = "approved={risk_approved} volume={risk_volume}".format_map(SafeDict(**variables))
    assert_no_missing_placeholders(rendered)


def test_gh19_cause_b_propagates_risk_fields_when_available() -> None:
    registry = AgentScopeRegistry()
    variables = registry._build_prompt_variables(
        pair="EURUSD",
        timeframe="H1",
        snapshot={},
        news={},
        risk_out={
            "text": "Risk approved",
            "metadata": {"approved": True, "adjusted_volume": 1.23},
        },
    )

    assert variables["risk_approved"] == "True"
    assert variables["risk_volume"] == "1.23"
    rendered = "approved={risk_approved} volume={risk_volume}".format_map(SafeDict(**variables))
    assert_no_missing_placeholders(rendered)


def test_gh19_guardrail_detect_function_lists_missing_placeholders() -> None:
    missing = _detect_missing_placeholders("hello <MISSING:foo> and <MISSING:bar>")
    assert missing == ["<MISSING:foo>", "<MISSING:bar>"]


def test_gh19_guardrail_raises_in_test_runtime() -> None:
    class _PromptService:
        def render(self, *_args, **_kwargs):
            return {
                "prompt_id": 1,
                "version": 1,
                "system_prompt": "sys <MISSING:bad>",
                "user_prompt": "user",
                "skills": [],
                "missing_variables": [],
            }

    registry = AgentScopeRegistry(prompt_service=_PromptService())
    with pytest.raises(ValueError, match="Unresolved placeholders"):
        registry._render_prompt(db=None, agent_name="technical-analyst", variables={})


def test_gh19_guardrail_warning_only_when_non_test_runtime(monkeypatch, caplog) -> None:
    class _PromptService:
        def render(self, *_args, **_kwargs):
            return {
                "prompt_id": 1,
                "version": 1,
                "system_prompt": "sys <MISSING:bad>",
                "user_prompt": "user",
                "skills": [],
                "missing_variables": [],
            }

    from app.services.agentscope import registry as registry_module

    monkeypatch.setattr(registry_module, "_is_test_runtime", lambda: False)
    registry = AgentScopeRegistry(prompt_service=_PromptService())

    rendered = registry._render_prompt(db=None, agent_name="technical-analyst", variables={})
    assert rendered["prompt_id"] == 1
    assert any("Unresolved placeholders detected" in record.message for record in caplog.records)
