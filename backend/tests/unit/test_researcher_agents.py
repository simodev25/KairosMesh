from app.services.orchestrator.agents import AgentContext, BearishResearcherAgent, BullishResearcherAgent
from app.services.prompts.registry import PromptTemplateService


def _context() -> AgentContext:
    return AgentContext(
        pair='EURUSD',
        timeframe='H1',
        mode='simulation',
        risk_percent=1.0,
        market_snapshot={'last_price': 1.1, 'atr': 0.001, 'trend': 'bullish'},
        news_context={'news': []},
        memory_context=[],
    )


def test_bullish_researcher_exposes_structured_support_and_invalidation() -> None:
    agent = BullishResearcherAgent(PromptTemplateService())
    outputs = {
        'technical-analyst': {'signal': 'bullish', 'score': 0.32, 'reason': 'Trend + momentum aligned'},
        'news-analyst': {'signal': 'bullish', 'score': 0.14, 'reason': 'Catalyseurs macro favorables'},
        'market-context-analyst': {'signal': 'bearish', 'score': -0.11, 'reason': 'Unfavorable volatility'},
    }

    result = agent.run(_context(), outputs, db=None)

    assert result['arguments']
    assert result['supporting_signal_count'] >= 2
    assert result['opposing_signal_count'] >= 1
    assert isinstance(result['counter_arguments'], list)
    assert isinstance(result['invalidation_conditions'], list)
    assert len(result['invalidation_conditions']) >= 1


def test_bearish_researcher_exposes_structured_support_and_invalidation() -> None:
    agent = BearishResearcherAgent(PromptTemplateService())
    outputs = {
        'technical-analyst': {'signal': 'bearish', 'score': -0.35, 'reason': 'Breakdown sous support'},
        'news-analyst': {'signal': 'bearish', 'score': -0.12, 'reason': 'Unfavorable macro catalysts'},
        'market-context-analyst': {'signal': 'bullish', 'score': 0.09, 'reason': 'Regime still readable bullish'},
    }

    result = agent.run(_context(), outputs, db=None)

    assert result['arguments']
    assert result['supporting_signal_count'] >= 2
    assert result['opposing_signal_count'] >= 1
    assert isinstance(result['counter_arguments'], list)
    assert isinstance(result['invalidation_conditions'], list)
    assert len(result['invalidation_conditions']) >= 1


def test_bullish_researcher_calls_llm_without_db_and_surfaces_thesis(monkeypatch) -> None:
    agent = BullishResearcherAgent(PromptTemplateService())
    monkeypatch.setattr(agent.model_selector, 'is_enabled', lambda *_args, **_kwargs: True)
    monkeypatch.setattr(agent.model_selector, 'resolve', lambda *_args, **_kwargs: 'dummy-model')
    monkeypatch.setattr(agent.model_selector, 'resolve_decision_mode', lambda *_args, **_kwargs: 'balanced')
    monkeypatch.setattr(
        agent.llm,
        'chat',
        lambda *_args, **_kwargs: {
            'text': 'Bullish thesis: macro and technical alignment remains constructive.',
            'degraded': False,
        },
    )
    outputs = {
        'technical-analyst': {'signal': 'bullish', 'score': 0.32, 'reason': 'Trend + momentum aligned'},
        'news-analyst': {'signal': 'bullish', 'score': 0.14, 'reason': 'Catalyseurs macro favorables'},
    }

    result = agent.run(_context(), outputs, db=None)

    assert result['llm_called'] is True
    assert 'constructive' in result['llm_debate'].lower()
    assert any('constructive' in argument.lower() for argument in result['arguments'])


def test_bullish_researcher_flags_missing_independent_confirmation_when_only_context_supports() -> None:
    agent = BullishResearcherAgent(PromptTemplateService())
    outputs = {
        'technical-analyst': {'signal': 'neutral', 'score': 0.0, 'reason': 'No actionable setup'},
        'news-analyst': {'signal': 'neutral', 'score': 0.0, 'reason': 'No retained catalyst'},
        'market-context-analyst': {'signal': 'bullish', 'score': 0.18, 'reason': 'Readable regime'},
    }

    result = agent.run(_context(), outputs, db=None)

    assert any('no independent source' in condition.lower() for condition in result['invalidation_conditions'])


def test_bullish_researcher_reduces_confidence_when_opposition_is_material() -> None:
    agent = BullishResearcherAgent(PromptTemplateService())
    outputs = {
        'technical-analyst': {'signal': 'bullish', 'score': 0.35, 'reason': 'Trend + momentum aligned'},
        'news-analyst': {'signal': 'bullish', 'score': 0.14, 'reason': 'Catalyseurs macro favorables'},
        'market-context-analyst': {'signal': 'bearish', 'score': -0.30, 'reason': 'Volatility is adverse'},
    }

    result = agent.run(_context(), outputs, db=None)

    assert result['opposing_signal_count'] == 1
    assert result['confidence'] < 0.35
