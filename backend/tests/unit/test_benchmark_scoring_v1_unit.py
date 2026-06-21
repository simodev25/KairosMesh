from app.services.benchmark.scoring_v1 import (
    compute_completeness_score,
    compute_reference_consistency_score,
    compute_schema_validity_score,
    compute_stability_score,
    compute_tool_policy_compliance_score,
    score_attempt,
)


def test_schema_validity_score_returns_binary_values() -> None:
    valid_output = {
        'structural_bias': 'bullish',
        'local_momentum': 'bullish',
        'setup_quality': 'medium',
        'summary': 'valid summary',
        'tradability': 'medium',
    }
    invalid_output = {'unexpected': True}

    assert compute_schema_validity_score('technical-analyst', valid_output) == 1.0
    assert compute_schema_validity_score('technical-analyst', invalid_output) == 0.0


def test_completeness_score_handles_missing_required_fields() -> None:
    partial_output = {
        'decision': 'BUY',
        'reasoning': 'missing conviction should reduce completeness',
    }
    score = compute_completeness_score('trader-agent', partial_output)
    assert 0.0 <= score < 1.0


def test_reference_consistency_score_uses_symbol_and_timeframe() -> None:
    fixture_inputs = {'symbol': 'EURUSD.PRO', 'timeframe': 'H1'}
    perfect = {'symbol': 'EURUSD.PRO', 'timeframe': 'H1'}
    mismatch = {'symbol': 'BTCUSD', 'timeframe': 'M15'}

    assert compute_reference_consistency_score(perfect, fixture_inputs) == 1.0
    assert compute_reference_consistency_score(mismatch, fixture_inputs) == 0.0


def test_tool_policy_compliance_score_reflects_compliance_ratio() -> None:
    fixture_config = {
        'preset_kwargs': {'symbol': 'EURUSD.PRO'},
        'force_kwargs': {'timeframe': 'H1'},
    }
    tool_calls = [
        {'kwargs': {'symbol': 'EURUSD.PRO', 'timeframe': 'H1'}},
        {'kwargs': {'symbol': 'BTCUSD', 'timeframe': 'H1'}},
    ]

    score = compute_tool_policy_compliance_score(tool_calls, fixture_config)
    assert score == 0.5


def test_stability_score_is_computed_for_two_or_more_values() -> None:
    assert compute_stability_score([0.5]) is None
    stability = compute_stability_score([0.8, 0.8, 0.8])
    assert stability is not None
    assert abs(stability - 1.0) < 1e-9


def test_score_attempt_is_deterministic_for_identical_inputs() -> None:
    raw_output = {
        'structural_bias': 'bullish',
        'local_momentum': 'bullish',
        'setup_quality': 'medium',
        'summary': 'stable summary',
        'tradability': 'high',
        'symbol': 'EURUSD.PRO',
        'timeframe': 'H1',
    }
    fixture_inputs = {'symbol': 'EURUSD.PRO', 'timeframe': 'H1'}
    fixture_config = {'preset_kwargs': {}, 'force_kwargs': {}}

    first = score_attempt(
        agent_name='technical-analyst',
        raw_output=raw_output,
        fixture_inputs=fixture_inputs,
        fixture_config=fixture_config,
        tool_calls=[],
        scoring_weights=None,
    )
    second = score_attempt(
        agent_name='technical-analyst',
        raw_output=raw_output,
        fixture_inputs=fixture_inputs,
        fixture_config=fixture_config,
        tool_calls=[],
        scoring_weights=None,
    )

    assert first == second
