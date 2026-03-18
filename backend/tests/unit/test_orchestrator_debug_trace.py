import asyncio
import json
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models.run import AnalysisRun
from app.db.models.user import User
from app.services.orchestrator.engine import ForexOrchestrator


def _seed_run(db: Session, *, mode: str = 'simulation') -> AnalysisRun:
    user = User(email='debug@local.dev', hashed_password='x', role='admin', is_active=True)
    db.add(user)
    db.commit()
    db.refresh(user)

    run = AnalysisRun(
        pair='EURUSD',
        timeframe='H1',
        mode=mode,
        status='pending',
        trace={},
        created_by_id=user.id,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def test_orchestrator_writes_debug_trade_trace_json(monkeypatch, tmp_path: Path) -> None:
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(bind=engine)

    with Session(engine) as db:
        run = _seed_run(db)
        orchestrator = ForexOrchestrator()

        orchestrator.settings.debug_trade_json_enabled = True
        orchestrator.settings.debug_trade_json_dir = str(tmp_path)
        orchestrator.settings.debug_trade_json_include_price_history = True
        orchestrator.settings.debug_trade_json_price_history_limit = 50
        orchestrator.settings.debug_trade_json_inline_in_run_trace = False

        monkeypatch.setattr(orchestrator.prompt_service, 'seed_defaults', lambda _db: None)
        monkeypatch.setattr(orchestrator.market_provider, 'get_market_snapshot', lambda *_args, **_kwargs: {
            'degraded': False,
            'pair': 'EURUSD',
            'timeframe': 'H1',
            'last_price': 1.102,
            'atr': 0.001,
            'trend': 'bullish',
        })
        monkeypatch.setattr(orchestrator.market_provider, 'get_news_context', lambda *_args, **_kwargs: {
            'degraded': False,
            'pair': 'EURUSD',
            'news': [{'title': 'ECB keeps rates unchanged'}],
        })
        monkeypatch.setattr(orchestrator.market_provider, 'get_recent_candles', lambda *_args, **_kwargs: [
            {'ts': '2026-03-18T12:00:00+00:00', 'open': 1.101, 'high': 1.103, 'low': 1.1, 'close': 1.102, 'volume': 1000}
        ])
        monkeypatch.setattr(orchestrator.memory_service, 'search', lambda **_kwargs: [{'summary': 'Memo context'}])
        monkeypatch.setattr(orchestrator.memory_service, 'add_run_memory', lambda *_args, **_kwargs: None)

        def fake_analyze_context(*_args, **kwargs):
            local_db = kwargs.get('db')
            local_run = kwargs.get('run')
            if local_db is not None and local_run is not None:
                orchestrator._record_step(
                    local_db,
                    local_run,
                    'technical-analyst',
                    {'pair': 'EURUSD', 'timeframe': 'H1'},
                    {
                        'signal': 'bullish',
                        'score': 0.2,
                        'prompt_meta': {
                            'llm_enabled': False,
                            'skills_count': 1,
                            'skills': ['Convergence technique stricte'],
                        },
                    },
                )
            return {
                'analysis_outputs': {'technical-analyst': {'signal': 'bullish', 'score': 0.2}},
                'bullish': {'arguments': ['Trend aligns'], 'confidence': 0.7},
                'bearish': {'arguments': ['No strong bearish trigger'], 'confidence': 0.2},
                'trader_decision': {
                    'decision': 'BUY',
                    'entry': 1.102,
                    'stop_loss': 1.1,
                    'take_profit': 1.106,
                    'confidence': 0.6,
                },
                'risk': {
                    'accepted': True,
                    'suggested_volume': 0.1,
                    'reasons': ['Risk checks passed'],
                },
            }

        monkeypatch.setattr(orchestrator, 'analyze_context', fake_analyze_context)
        monkeypatch.setattr(
            orchestrator.execution_manager_agent,
            'run',
            lambda *_args, **_kwargs: {
                'decision': 'HOLD',
                'should_execute': False,
                'side': None,
                'volume': 0.0,
                'reason': 'Execution deferred by policy',
                'prompt_meta': {'llm_enabled': False, 'skills_count': 0, 'skills': []},
            },
        )

        completed_run = asyncio.run(orchestrator.execute(db, run, risk_percent=1.0))

        assert completed_run.status == 'completed'
        assert completed_run.trace['debug_trace_meta']['enabled'] is True
        debug_path = Path(completed_run.trace['debug_trace_file'])
        assert debug_path.exists()

        payload = json.loads(debug_path.read_text(encoding='utf-8'))
        assert payload['run']['id'] == completed_run.id
        assert payload['run']['status'] == 'completed'
        assert payload['context']['price_history'][0]['close'] == 1.102
        assert payload['analysis_bundle']['execution_result']['status'] == 'skipped'
        assert any(step['agent_name'] == 'execution-manager' for step in payload['agent_steps'])


def test_orchestrator_fails_live_run_when_llm_output_is_degraded(monkeypatch) -> None:
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(bind=engine)

    with Session(engine) as db:
        run = _seed_run(db, mode='live')
        orchestrator = ForexOrchestrator()

        monkeypatch.setattr(orchestrator.prompt_service, 'seed_defaults', lambda _db: None)
        monkeypatch.setattr(orchestrator.market_provider, 'get_market_snapshot', lambda *_args, **_kwargs: {
            'degraded': False,
            'pair': 'EURUSD',
            'timeframe': 'H1',
            'last_price': 1.102,
            'atr': 0.001,
            'trend': 'bullish',
        })
        monkeypatch.setattr(orchestrator.market_provider, 'get_news_context', lambda *_args, **_kwargs: {
            'degraded': False,
            'pair': 'EURUSD',
            'news': [],
        })
        monkeypatch.setattr(orchestrator.memory_service, 'search', lambda **_kwargs: [])
        monkeypatch.setattr(orchestrator.memory_service, 'add_run_memory', lambda *_args, **_kwargs: None)

        execution_called = {'value': False}

        def fake_analyze_context(*_args, **_kwargs):
            return {
                'analysis_outputs': {
                    'technical-analyst': {'signal': 'bullish', 'score': 0.2, 'degraded': True},
                    'news-analyst': {'signal': 'neutral', 'score': 0.0},
                    'macro-analyst': {'signal': 'bullish', 'score': 0.1},
                    'sentiment-agent': {'signal': 'bullish', 'score': 0.1},
                },
                'bullish': {'arguments': ['Trend aligns'], 'confidence': 0.7},
                'bearish': {'arguments': [], 'confidence': 0.0},
                'trader_decision': {
                    'decision': 'BUY',
                    'entry': 1.102,
                    'stop_loss': 1.1,
                    'take_profit': 1.106,
                    'confidence': 0.6,
                },
                'risk': {
                    'accepted': True,
                    'suggested_volume': 0.1,
                    'reasons': ['Risk checks passed'],
                },
            }

        def fake_execution_manager(*_args, **_kwargs):
            execution_called['value'] = True
            return {
                'decision': 'BUY',
                'should_execute': True,
                'side': 'BUY',
                'volume': 0.1,
                'reason': 'Should never be reached',
            }

        monkeypatch.setattr(orchestrator, 'analyze_context', fake_analyze_context)
        monkeypatch.setattr(orchestrator.execution_manager_agent, 'run', fake_execution_manager)

        failed_run = asyncio.run(orchestrator.execute(db, run, risk_percent=1.0))

        assert failed_run.status == 'failed'
        assert 'degraded LLM response from technical-analyst' in str(failed_run.error)
        assert execution_called['value'] is False
