import asyncio
import json

from agentscope.message import Msg
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models.benchmark_attempt import BenchmarkAttempt
from app.db.models.benchmark_fixture import BenchmarkFixture
from app.db.models.benchmark_run import BenchmarkRun
from app.db.models.user import User
from app.services.benchmark.engine import BenchmarkEngine
from app.services.benchmark.scenarios import _extract_output_payload
from app.services.benchmark.scoring_v1 import score_attempt


def _seed_user_fixture_run(db: Session, *, repetitions: int = 1) -> BenchmarkRun:
    user = User(email='benchmark-e2e@local.dev', hashed_password='x', role='admin', is_active=True)
    db.add(user)
    db.commit()
    db.refresh(user)

    fixture = BenchmarkFixture(
        name='fixture-benchmark-e2e',
        agent_name='technical-analyst',
        version=1,
        hash='e' * 64,
        inputs={
            'symbol': 'EURUSD.PRO',
            'timeframe': 'H1',
            'context': 'Analyze EURUSD.PRO in H1 with recent candles and levels',
        },
        config={'llm_enabled': True},
        created_by_id=user.id,
    )
    db.add(fixture)
    db.commit()
    db.refresh(fixture)

    run = BenchmarkRun(
        fixture_id=fixture.id,
        fixture_hash=fixture.hash,
        model_spec={'provider': 'ollama', 'model_name': 'deepseek-v3.2', 'parameters': {'temperature': 0.0}},
        scenario_type='single-agent',
        status='PENDING',
        repetitions=repetitions,
        created_by_id=user.id,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def test_execute_run_single_agent_e2e_extracts_structured_payload_and_scores(monkeypatch) -> None:
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(bind=engine)

    valid_output = {
        'symbol': 'EURUSD.PRO',
        'timeframe': 'H1',
        'structural_bias': 'bullish',
        'local_momentum': 'bullish',
        'setup_quality': 'high',
        'key_levels': ['1.0800', '1.0850'],
        'patterns_found': ['higher highs', 'bull flag'],
        'contradictions': ['RSI slightly overbought'],
        'summary': 'Trend remains bullish with pullback opportunities near support.',
        'tradability': 'high',
        'degraded': False,
    }

    async def _fake_build_agent(self, **_kwargs):
        async def _agent(_context_msg):
            # Structured output is present both in metadata and JSON text.
            return Msg(
                'technical-analyst',
                json.dumps(valid_output),
                'assistant',
                metadata=valid_output,
            )

        return _agent

    monkeypatch.setattr(BenchmarkEngine, '_build_agent', _fake_build_agent)

    with Session(engine) as db:
        run = _seed_user_fixture_run(db, repetitions=1)

        benchmark_engine = BenchmarkEngine()
        result_run = asyncio.run(benchmark_engine.execute_run(db, run))
        db.refresh(result_run)

        attempts = db.query(BenchmarkAttempt).all()
        assert len(attempts) == 1

        attempt = attempts[0]
        assert attempt.raw_output != {'text': ''}
        assert attempt.raw_output['summary'] == valid_output['summary']
        assert attempt.schema_validity_score > 0.0
        assert attempt.completeness_score > 0.0
        assert attempt.reference_consistency_score > 0.0


class _FakeMsg:
    def __init__(self, *, metadata=None, text: str = '', content=None) -> None:
        self.metadata = metadata
        self._text = text
        # If content not explicitly set, use text as content (simulates Msg with string content)
        self.content = content if content is not None else text

    def get_text_content(self) -> str:
        return self._text


def test_extract_output_payload_prefers_metadata_when_present() -> None:
    metadata_payload = {'summary': 'metadata wins', 'structural_bias': 'bullish'}
    msg = _FakeMsg(metadata=metadata_payload, text='{"summary":"text"}')

    extracted = _extract_output_payload(msg)

    assert extracted == metadata_payload


def test_extract_output_payload_parses_json_text_when_metadata_empty() -> None:
    text_payload = {'summary': 'from json text', 'structural_bias': 'bearish'}
    msg = _FakeMsg(metadata={}, text=json.dumps(text_payload))

    extracted = _extract_output_payload(msg)

    assert extracted == text_payload


def test_extract_output_payload_falls_back_to_text_for_non_json() -> None:
    msg = _FakeMsg(metadata={}, text='plain response without json')

    extracted = _extract_output_payload(msg)

    assert extracted == {'text': 'plain response without json'}


def test_extract_output_payload_extracts_json_from_thinking_blocks() -> None:
    """DeepSeek models put structured output in ThinkingBlocks, not TextBlocks.
    The extractor must parse JSON from thinking block content."""
    json_payload = {'structural_bias': 'bullish', 'signal': 'neutral', 'score': 0.8}
    # Simulate Msg with only thinking blocks (content is a list of block dicts)
    msg = _FakeMsg(
        metadata={},
        text='',
        content=[{'type': 'thinking', 'thinking': json.dumps(json_payload)}],
    )

    extracted = _extract_output_payload(msg)

    assert extracted == json_payload


def test_extract_output_payload_extracts_from_mixed_blocks() -> None:
    """When both thinking and text blocks exist, extract from all."""
    json_payload = {'signal': 'bullish', 'confidence': 0.9}
    msg = _FakeMsg(
        metadata={},
        text='',
        content=[
            {'type': 'thinking', 'thinking': 'Let me analyze...'},
            {'type': 'text', 'text': json.dumps(json_payload)},
        ],
    )

    extracted = _extract_output_payload(msg)

    assert extracted == json_payload


def test_score_attempt_technical_analyst_valid_output_reference_matches_fixture() -> None:
    output = {
        'symbol': 'EURUSD.PRO',
        'timeframe': 'H1',
        'structural_bias': 'bullish',
        'local_momentum': 'bullish',
        'setup_quality': 'medium',
        'key_levels': ['1.0800', '1.0850'],
        'patterns_found': ['trend continuation'],
        'contradictions': [],
        'summary': 'Bullish market structure with acceptable momentum.',
        'tradability': 'medium',
        'degraded': False,
    }
    fixture_inputs = {'symbol': 'EURUSD.PRO', 'timeframe': 'H1'}

    score = score_attempt(
        agent_name='technical-analyst',
        raw_output=output,
        fixture_inputs=fixture_inputs,
        fixture_config={},
        tool_calls=[],
    )

    assert score['schema_validity_score'] == 1.0
    assert score['completeness_score'] > 0.0
    assert score['reference_consistency_score'] == 1.0
