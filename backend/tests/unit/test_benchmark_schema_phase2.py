import pytest

from pydantic import ValidationError

from app.schemas.benchmark import BenchmarkModelSpec, BenchmarkRunCreateRequest


def test_benchmark_model_spec_accepts_supported_provider() -> None:
    payload = BenchmarkModelSpec(provider='openai', model_name='gpt-4o-mini', parameters={'temperature': 0.1})
    assert payload.provider == 'openai'
    assert payload.model_name == 'gpt-4o-mini'


def test_benchmark_model_spec_rejects_unsupported_provider() -> None:
    with pytest.raises(ValidationError):
        BenchmarkModelSpec(provider='anthropic', model_name='claude-3', parameters={})


def test_run_create_request_rejects_repetitions_lower_than_two() -> None:
    with pytest.raises(ValidationError):
        BenchmarkRunCreateRequest(
            fixture_id=1,
            fixture_hash='a' * 64,
            model_spec={'provider': 'ollama', 'model_name': 'deepseek-v3.2', 'parameters': {}},
            scenario_type='single-agent',
            repetitions=1,
        )


def test_run_create_request_defaults_repetitions_to_three() -> None:
    payload = BenchmarkRunCreateRequest(
        fixture_id=1,
        fixture_hash='b' * 64,
        model_spec={'provider': 'mistral', 'model_name': 'mistral-small-latest', 'parameters': {}},
        scenario_type='single-agent',
    )
    assert payload.repetitions == 3
