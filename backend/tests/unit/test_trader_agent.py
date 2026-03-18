from app.services.orchestrator.agents import AgentContext, TraderAgent


def test_trader_agent_outputs_buy_when_score_positive() -> None:
    agent = TraderAgent()
    ctx = AgentContext(
        pair='EURUSD',
        timeframe='H1',
        mode='simulation',
        risk_percent=1.0,
        market_snapshot={'last_price': 1.1234, 'atr': 0.001, 'trend': 'bullish'},
        news_context={'news': []},
        memory_context=[],
    )
    outputs = {
        'technical': {'score': 0.3},
        'news': {'score': 0.2},
        'macro': {'score': 0.1},
    }
    bullish = {'arguments': ['x']}
    bearish = {'arguments': ['y']}

    result = agent.run(ctx, outputs, bullish, bearish)
    assert result['decision'] == 'BUY'
    assert result['stop_loss'] is not None
    assert result['take_profit'] is not None


def test_trader_agent_debate_score_can_unlock_trade() -> None:
    agent = TraderAgent()
    ctx = AgentContext(
        pair='EURUSD',
        timeframe='H1',
        mode='simulation',
        risk_percent=1.0,
        market_snapshot={'last_price': 1.1234, 'atr': 0.001, 'trend': 'bullish'},
        news_context={'news': []},
        memory_context=[],
    )
    outputs = {
        'technical': {'score': 0.12},
        'news': {'score': 0.0},
        'macro': {'score': 0.0},
    }
    bullish = {'arguments': ['x'], 'confidence': 1.0}
    bearish = {'arguments': ['y'], 'confidence': 0.0}

    result = agent.run(ctx, outputs, bullish, bearish)
    assert result['net_score'] == 0.12
    assert result['combined_score'] == 0.42
    assert result['decision'] == 'BUY'


def test_trader_agent_holds_when_debate_conflict_is_high() -> None:
    agent = TraderAgent()
    ctx = AgentContext(
        pair='EURUSD',
        timeframe='H1',
        mode='simulation',
        risk_percent=1.0,
        market_snapshot={'last_price': 1.1234, 'atr': 0.001, 'trend': 'bullish'},
        news_context={'news': []},
        memory_context=[],
    )
    outputs = {
        'technical': {'score': 0.1},
    }
    bullish = {'arguments': ['x'], 'confidence': 0.5}
    bearish = {'arguments': ['y'], 'confidence': 0.5}

    result = agent.run(ctx, outputs, bullish, bearish)
    assert result['signal_conflict'] is True
    assert result['decision'] == 'HOLD'


def test_trader_agent_execution_note_falls_back_to_structured_levels(monkeypatch) -> None:
    agent = TraderAgent()
    monkeypatch.setattr(agent.model_selector, 'is_enabled', lambda *_args, **_kwargs: True)
    monkeypatch.setattr(agent.model_selector, 'resolve', lambda *_args, **_kwargs: 'llama3.1')
    monkeypatch.setattr(
        agent.llm,
        'chat',
        lambda *_args, **_kwargs: {
            'text': (
                "**Decision : HOLD**\n"
                "**Stop-loss : 1.0825**\n"
                "**Take-profit : 1.0775**"
            ),
            'degraded': False,
        },
    )

    ctx = AgentContext(
        pair='EURUSD.PRO',
        timeframe='M15',
        mode='live',
        risk_percent=1.0,
        market_snapshot={'last_price': 1.1460, 'atr': 0.0008, 'trend': 'bullish'},
        news_context={'news': []},
        memory_context=[],
    )
    outputs = {
        'technical': {'score': 0.3},
        'macro': {'score': 0.15},
        'sentiment': {'score': 0.05},
    }
    bullish = {'arguments': ['x'], 'confidence': 0.6}
    bearish = {'arguments': ['y'], 'confidence': 0.0}

    result = agent.run(ctx, outputs, bullish, bearish)

    assert result['decision'] == 'BUY'
    assert '**Decision : BUY**' in result['execution_note']
    assert '1.0825' not in result['execution_note']
    assert '1.0775' not in result['execution_note']
    assert '1.1448' in result['execution_note']
    assert '1.148' in result['execution_note']
