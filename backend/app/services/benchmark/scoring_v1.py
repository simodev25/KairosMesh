from __future__ import annotations

from math import isfinite, sqrt
from typing import Any

from app.services.benchmark.agent_output_registry import AGENT_OUTPUT_SCHEMA_MAP


DEFAULT_SCORING_WEIGHTS = {
    'schema_validity_score': 0.2,
    'completeness_score': 0.2,
    'tool_policy_compliance_score': 0.2,
    'reference_consistency_score': 0.2,
    'stability_score': 0.2,
}


def _clamp01(value: float) -> float:
    if not isfinite(value):
        return 0.0
    return max(0.0, min(1.0, value))


def _extract_required_schema_fields(schema_model) -> set[str]:
    return {
        field_name
        for field_name, field_info in schema_model.model_fields.items()
        if field_info.is_required()
    }


def compute_schema_validity_score(agent_name: str, raw_output: dict[str, Any]) -> float:
    schema_model = AGENT_OUTPUT_SCHEMA_MAP.get(agent_name)
    if schema_model is None:
        return 0.0
    try:
        schema_model.model_validate(raw_output)
        return 1.0
    except Exception:
        return 0.0


def compute_completeness_score(agent_name: str, raw_output: dict[str, Any]) -> float:
    schema_model = AGENT_OUTPUT_SCHEMA_MAP.get(agent_name)
    if schema_model is None:
        return 0.0

    required_fields = _extract_required_schema_fields(schema_model)
    if not required_fields:
        return 1.0

    present_count = 0
    for field_name in required_fields:
        value = raw_output.get(field_name)
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        if isinstance(value, list | dict) and len(value) == 0:
            continue
        present_count += 1

    return _clamp01(present_count / len(required_fields))


def compute_reference_consistency_score(raw_output: dict[str, Any], fixture_inputs: dict[str, Any]) -> float:
    expected_symbol = str(fixture_inputs.get('symbol') or '').strip()
    expected_timeframe = str(fixture_inputs.get('timeframe') or '').strip()

    checks_total = 0
    checks_ok = 0

    if expected_symbol:
        checks_total += 1
        raw_symbol = str(raw_output.get('symbol') or fixture_inputs.get('pair') or '').strip()
        if raw_symbol and raw_symbol.lower() == expected_symbol.lower():
            checks_ok += 1

    if expected_timeframe:
        checks_total += 1
        raw_timeframe = str(raw_output.get('timeframe') or '').strip()
        if raw_timeframe and raw_timeframe.upper() == expected_timeframe.upper():
            checks_ok += 1

    if checks_total == 0:
        return 1.0
    return _clamp01(checks_ok / checks_total)


def compute_tool_policy_compliance_score(tool_calls: list[dict[str, Any]], fixture_config: dict[str, Any]) -> float:
    if not tool_calls:
        return 1.0

    expected_preset_kwargs = fixture_config.get('preset_kwargs') or {}
    expected_force_kwargs = fixture_config.get('force_kwargs') or {}

    compliant_calls = 0
    for call in tool_calls:
        kwargs = call.get('kwargs') or {}
        is_compliant = True

        for key, expected_value in expected_preset_kwargs.items():
            actual_value = kwargs.get(key)
            if actual_value is None:
                continue
            if actual_value != expected_value:
                is_compliant = False
                break

        if is_compliant:
            for key, expected_value in expected_force_kwargs.items():
                actual_value = kwargs.get(key)
                if actual_value != expected_value:
                    is_compliant = False
                    break

        if is_compliant:
            compliant_calls += 1

    return _clamp01(compliant_calls / len(tool_calls))


def compute_aggregate_score(metric_scores: dict[str, float], weights: dict[str, float] | None = None) -> float:
    effective_weights = dict(DEFAULT_SCORING_WEIGHTS)
    if weights:
        for key, value in weights.items():
            if key in effective_weights:
                effective_weights[key] = max(0.0, float(value))

    denominator = sum(effective_weights.values())
    if denominator <= 0:
        return 0.0

    weighted_sum = 0.0
    for metric_name, metric_value in metric_scores.items():
        weighted_sum += _clamp01(float(metric_value)) * effective_weights.get(metric_name, 0.0)

    return _clamp01(weighted_sum / denominator)


def compute_stability_score(aggregate_scores: list[float]) -> float | None:
    if len(aggregate_scores) < 2:
        return None

    values = [float(score) for score in aggregate_scores]
    mean_value = sum(values) / len(values)
    if mean_value <= 0:
        return 0.0

    variance = sum((value - mean_value) ** 2 for value in values) / len(values)
    std_dev = sqrt(variance)
    cv = std_dev / mean_value if mean_value else 0.0
    return _clamp01(1.0 - cv)


def score_attempt(
    *,
    agent_name: str,
    raw_output: dict[str, Any],
    fixture_inputs: dict[str, Any],
    fixture_config: dict[str, Any],
    tool_calls: list[dict[str, Any]] | None = None,
    scoring_weights: dict[str, float] | None = None,
) -> dict[str, float]:
    metrics = {
        'schema_validity_score': compute_schema_validity_score(agent_name, raw_output),
        'completeness_score': compute_completeness_score(agent_name, raw_output),
        'tool_policy_compliance_score': compute_tool_policy_compliance_score(tool_calls or [], fixture_config),
        'reference_consistency_score': compute_reference_consistency_score(raw_output, fixture_inputs),
        'stability_score': 0.0,
    }
    metrics['aggregate_score'] = compute_aggregate_score(metrics, scoring_weights)
    return metrics
