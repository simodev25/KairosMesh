"""Tests for optimizer_adapter — encode/decode, bounds validation, evaluator."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest

from app.services.strategy.optimizer_adapter import (
    build_evaluator,
    decode_program_to_params,
    encode_params_to_program,
    validate_params_in_bounds,
)


class TestEncodeDecode:
    def test_roundtrip(self):
        """Encode then decode produces identical params."""
        params = {'ema_fast': 9, 'ema_slow': 21, 'rsi_filter': 30}
        program = encode_params_to_program('ema_crossover', params)
        decoded = decode_program_to_params(program)
        assert decoded == params

    def test_roundtrip_float_params(self):
        """Float params survive encode/decode."""
        params = {'atr_period': 10, 'atr_multiplier': 2.5}
        program = encode_params_to_program('supertrend', params)
        decoded = decode_program_to_params(program)
        assert decoded == params

    def test_encode_is_json_string(self):
        """Encoded program is a valid JSON string."""
        import json
        params = {'bb_period': 20, 'bb_std': 2.0}
        program = encode_params_to_program('bollinger_breakout', params)
        payload = json.loads(program)
        assert payload['template'] == 'bollinger_breakout'
        assert payload['params'] == params


class TestValidateParamsInBounds:
    def test_valid_params(self):
        """Valid params within bounds pass."""
        params = {'ema_fast': 9, 'ema_slow': 21, 'rsi_filter': 30}
        assert validate_params_in_bounds('ema_crossover', params) is True

    def test_out_of_bounds(self):
        """Params outside bounds fail."""
        params = {'ema_fast': 100, 'ema_slow': 21, 'rsi_filter': 30}
        assert validate_params_in_bounds('ema_crossover', params) is False

    def test_unknown_template(self):
        """Unknown template always passes (no bounds to check)."""
        assert validate_params_in_bounds('unknown_template', {'x': 999}) is True

    def test_negative_bounds_williams(self):
        """Williams %R has negative bounds — check they validate correctly."""
        params = {'period': 14, 'oversold': -80, 'overbought': -20}
        assert validate_params_in_bounds('williams_r', params) is True

        params_bad = {'period': 14, 'oversold': -80, 'overbought': -2}
        assert validate_params_in_bounds('williams_r', params_bad) is False

    def test_ema_fast_greater_than_slow_still_in_bounds(self):
        """
        The bounds checker does not enforce cross-param constraints
        (ema_fast < ema_slow). Those are handled by BacktestEngine.
        """
        params = {'ema_fast': 20, 'ema_slow': 15, 'rsi_filter': 30}
        # Both values within bounds individually
        assert validate_params_in_bounds('ema_crossover', params) is True


class TestBuildEvaluator:
    def test_evaluator_returns_score_and_metrics(self):
        """Evaluator calls BacktestEngine and returns score."""
        mock_result = MagicMock()
        mock_result.metrics = {'win_rate_pct': 60, 'profit_factor': 1.5, 'total_trades': 20, 'max_drawdown_pct': 10, 'total_return_pct': 15}

        with patch('app.services.backtest.engine.BacktestEngine') as MockEngine:
            instance = MagicMock()
            instance.run.return_value = mock_result
            MockEngine.return_value = instance

            evaluator = build_evaluator('ema_crossover', 'EURUSD.PRO', 'H1')
            result = evaluator({'ema_fast': 9, 'ema_slow': 21, 'rsi_filter': 30})

        assert 'score' in result
        assert 'metrics' in result
        assert result['score'] > 0

    def test_evaluator_handles_exception(self):
        """Evaluator returns 0 score on backtest failure."""
        with patch('app.services.backtest.engine.BacktestEngine') as MockEngine:
            instance = MagicMock()
            instance.run.side_effect = RuntimeError('Backtest failed')
            MockEngine.return_value = instance

            evaluator = build_evaluator('ema_crossover', 'EURUSD.PRO', 'H1')
            result = evaluator({'ema_fast': 9, 'ema_slow': 21, 'rsi_filter': 30})

        assert result['score'] == 0.0
        assert result['metrics'] == {}
