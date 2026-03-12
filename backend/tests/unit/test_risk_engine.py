from app.services.risk.rules import RiskEngine


def test_risk_engine_accepts_valid_simulation_order() -> None:
    engine = RiskEngine()
    result = engine.evaluate(
        mode='simulation',
        decision='BUY',
        risk_percent=1.0,
        price=1.1,
        stop_loss=1.095,
    )
    assert result.accepted is True
    assert result.suggested_volume >= 0.01


def test_risk_engine_rejects_missing_stop_loss() -> None:
    engine = RiskEngine()
    result = engine.evaluate(
        mode='paper',
        decision='SELL',
        risk_percent=1.0,
        price=1.2,
        stop_loss=None,
    )
    assert result.accepted is False
    assert 'Stop loss is mandatory.' in result.reasons
