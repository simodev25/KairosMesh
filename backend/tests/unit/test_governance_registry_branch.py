from app.services.agentscope.registry import AgentScopeRegistry


def test_build_governance_context_msg_includes_position_fields():
    registry = AgentScopeRegistry()
    position = {
        'id': 'pos-123',
        'symbol': 'BTCUSD',
        'type': 'POSITION_TYPE_BUY',
        'openPrice': 64200.0,
        'currentPrice': 65115.0,
        'stopLoss': 63500.0,
        'takeProfit': 67000.0,
        'unrealizedProfit': 915.0,
        'volume': 0.01,
        'time': '2026-04-10T10:00:00Z',
    }
    msg = registry._build_governance_context_msg(position)
    content = str(msg.content)
    assert 'BTCUSD' in content
    assert '64200' in content
    assert '63500' in content  # stop loss
    assert 'GOVERNANCE_CONTEXT' in content


def test_parse_governance_decision_from_agent_output_hold():
    registry = AgentScopeRegistry()
    raw = {'action': 'HOLD', 'reasoning': 'Market stable', 'risk_score': 0.1, 'confidence': 0.9}
    decision = registry._parse_governance_decision(raw)
    assert decision.action == 'HOLD'


def test_parse_governance_decision_falls_back_to_hold_on_invalid():
    registry = AgentScopeRegistry()
    raw = {'action': 'BUY', 'reasoning': 'buy signal', 'risk_score': 0.5, 'confidence': 0.5}
    decision = registry._parse_governance_decision(raw)
    assert decision.action == 'HOLD'
