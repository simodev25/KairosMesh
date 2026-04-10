import pytest
from pydantic import ValidationError
from app.services.governance.schemas import GovernanceDecision


def test_hold_requires_no_sl_tp():
    d = GovernanceDecision(
        action='HOLD', reasoning='Market is stable', risk_score=0.1, confidence=0.9
    )
    assert d.action == 'HOLD'
    assert d.new_sl is None
    assert d.new_tp is None


def test_adjust_sl_requires_new_sl():
    d = GovernanceDecision(
        action='ADJUST_SL', new_sl=63500.0,
        reasoning='Breakeven protection', risk_score=0.15, confidence=0.85
    )
    assert d.new_sl == 63500.0


def test_adjust_sl_without_new_sl_raises():
    with pytest.raises(ValidationError, match='new_sl is required'):
        GovernanceDecision(
            action='ADJUST_SL', reasoning='test', risk_score=0.1, confidence=0.8
        )


def test_adjust_tp_requires_new_tp():
    with pytest.raises(ValidationError, match='new_tp is required'):
        GovernanceDecision(
            action='ADJUST_TP', reasoning='test', risk_score=0.1, confidence=0.8
        )


def test_adjust_both_requires_sl_and_tp():
    with pytest.raises(ValidationError, match='new_sl is required'):
        GovernanceDecision(
            action='ADJUST_BOTH', new_tp=67000.0,
            reasoning='test', risk_score=0.1, confidence=0.8
        )


def test_close_requires_no_sl_tp():
    d = GovernanceDecision(
        action='CLOSE', reasoning='Volatility spike', risk_score=0.9, confidence=0.7
    )
    assert d.action == 'CLOSE'


def test_risk_score_clamped_between_0_and_1():
    d = GovernanceDecision(
        action='HOLD', reasoning='test', risk_score=1.5, confidence=0.5
    )
    assert d.risk_score == 1.0

    d2 = GovernanceDecision(
        action='HOLD', reasoning='test', risk_score=-0.3, confidence=0.5
    )
    assert d2.risk_score == 0.0


def test_invalid_action_raises():
    with pytest.raises(ValidationError):
        GovernanceDecision(
            action='BUY', reasoning='test', risk_score=0.1, confidence=0.5
        )
