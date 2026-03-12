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
