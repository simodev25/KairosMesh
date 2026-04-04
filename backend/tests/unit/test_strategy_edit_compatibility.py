from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.routes.strategies import StrategyEditRequest, edit_strategy
from app.db.models.strategy import Strategy


class _FakeDB:
    def __init__(self, strategy: object) -> None:
        self._strategy = strategy
        self.committed = False

    def get(self, model, strategy_id):  # noqa: ANN001, ARG002
        if model is Strategy and strategy_id == self._strategy.id:
            return self._strategy
        return None

    def commit(self) -> None:
        self.committed = True

    def refresh(self, obj) -> None:  # noqa: ANN001, ARG002
        return None


def _legacy_strategy() -> SimpleNamespace:
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=1,
        strategy_id='STRAT-001',
        name='legacy-ema',
        description='legacy strategy',
        status='DRAFT',
        score=0.0,
        template='ema_rsi',
        symbol='EURUSD.PRO',
        timeframe='H1',
        params={'ema_fast': 12, 'ema_slow': 26, 'legacy_mode': True},
        metrics={},
        is_monitoring=False,
        monitoring_mode='simulation',
        monitoring_risk_percent=1.0,
        last_signal_key=None,
        prompt_history=[],
        last_backtest_id=None,
        created_by_id=42,
        created_at=now,
        updated_at=now,
    )


def _user(*, user_id: int, role: str = 'trader-operator') -> SimpleNamespace:
    return SimpleNamespace(id=user_id, role=role)


@pytest.mark.asyncio
async def test_edit_strategy_preserves_legacy_params_without_raising(monkeypatch) -> None:
    strategy = _legacy_strategy()
    db = _FakeDB(strategy)

    async def fake_llm_edit(history, edit_prompt, current_params, template):  # noqa: ANN001
        return {
            'template': 'ema_rsi',
            'params': {'ema_fast': 8, 'ema_slow': 21, 'legacy_mode': True},
            'name': 'legacy-ema-edited',
            'description': 'edited legacy strategy',
        }

    monkeypatch.setattr('app.api.routes.strategies._llm_edit', fake_llm_edit)

    result = await edit_strategy(
        strategy_id=1,
        payload=StrategyEditRequest(prompt='keep the legacy strategy compatible'),
        db=db,
        user=None,
    )

    assert result.template == 'ema_rsi'
    assert result.params == {'ema_fast': 8, 'ema_slow': 21, 'legacy_mode': True}
    assert db.committed is True


@pytest.mark.asyncio
async def test_edit_strategy_ignores_template_switch_for_legacy_strategy(monkeypatch) -> None:
    strategy = _legacy_strategy()
    db = _FakeDB(strategy)

    async def fake_llm_edit(history, edit_prompt, current_params, template):  # noqa: ANN001
        return {
            'template': 'bollinger_breakout',
            'params': {'bb_period': 20, 'bb_std': 2.0, 'volume_filter': True},
            'name': 'bollinger-edited',
            'description': 'moved to executable',
        }

    monkeypatch.setattr('app.api.routes.strategies._llm_edit', fake_llm_edit)

    result = await edit_strategy(
        strategy_id=1,
        payload=StrategyEditRequest(prompt='convert this legacy strategy'),
        db=db,
        user=None,
    )

    assert result.template == 'ema_rsi'
    assert result.params == {'ema_fast': 12, 'ema_slow': 26, 'legacy_mode': True}


@pytest.mark.asyncio
async def test_edit_strategy_does_not_reset_validated_strategy_when_llm_edit_fails(monkeypatch) -> None:
    strategy = _legacy_strategy()
    strategy.status = 'VALIDATED'
    strategy.score = 55.0
    strategy.metrics = {'profit_factor': 1.8}
    db = _FakeDB(strategy)

    async def fake_llm_edit(history, edit_prompt, current_params, template):  # noqa: ANN001
        return None

    monkeypatch.setattr('app.api.routes.strategies._llm_edit', fake_llm_edit)

    result = await edit_strategy(
        strategy_id=1,
        payload=StrategyEditRequest(prompt='tighten the entry logic'),
        db=db,
        user=_user(user_id=42),
    )

    assert result.status == 'VALIDATED'
    assert result.score == 55.0
    assert result.metrics == {'profit_factor': 1.8}


@pytest.mark.asyncio
async def test_edit_strategy_resets_to_draft_when_validated_strategy_changes(monkeypatch) -> None:
    strategy = _legacy_strategy()
    strategy.template = 'ema_crossover'
    strategy.params = {'ema_fast': 12, 'ema_slow': 26, 'rsi_filter': 30}
    strategy.status = 'VALIDATED'
    strategy.score = 55.0
    strategy.metrics = {'profit_factor': 1.8}
    db = _FakeDB(strategy)

    async def fake_llm_edit(history, edit_prompt, current_params, template):  # noqa: ANN001
        return {
            'template': 'ema_crossover',
            'params': {'ema_fast': 9, 'ema_slow': 21, 'rsi_filter': 30},
            'name': 'ema-edited',
            'description': 'edited strategy',
        }

    monkeypatch.setattr('app.api.routes.strategies._llm_edit', fake_llm_edit)

    result = await edit_strategy(
        strategy_id=1,
        payload=StrategyEditRequest(prompt='make it faster'),
        db=db,
        user=_user(user_id=42),
    )

    assert result.status == 'DRAFT'
    assert result.score == 0.0
    assert result.metrics == {}
    assert result.params == {'ema_fast': 9, 'ema_slow': 21, 'rsi_filter': 30}


@pytest.mark.asyncio
async def test_edit_strategy_locks_template_and_preserves_current_params_when_llm_proposes_other_template(monkeypatch) -> None:
    strategy = _legacy_strategy()
    strategy.template = 'ema_crossover'
    strategy.params = {'ema_fast': 12, 'ema_slow': 26, 'rsi_filter': 30}
    db = _FakeDB(strategy)

    async def fake_llm_edit(history, edit_prompt, current_params, template):  # noqa: ANN001
        return {
            'template': 'bollinger_breakout',
            'params': {'bb_period': 20, 'bb_std': 2.0},
            'name': 'new-name-should-not-apply',
            'description': 'new-description-should-not-apply',
        }

    monkeypatch.setattr('app.api.routes.strategies._llm_edit', fake_llm_edit)

    result = await edit_strategy(
        strategy_id=1,
        payload=StrategyEditRequest(prompt='switch this to a breakout strategy'),
        db=db,
        user=_user(user_id=42),
    )

    assert result.template == 'ema_crossover'
    assert result.params == {'ema_fast': 12, 'ema_slow': 26, 'rsi_filter': 30}
    assert result.name == 'legacy-ema'
    assert result.description == 'legacy strategy'


@pytest.mark.asyncio
async def test_edit_strategy_rejects_non_owner_for_non_admin(monkeypatch) -> None:
    strategy = _legacy_strategy()
    db = _FakeDB(strategy)

    async def fake_llm_edit(history, edit_prompt, current_params, template):  # noqa: ANN001, ARG001
        raise AssertionError('LLM should not be called for unauthorized edit')

    monkeypatch.setattr('app.api.routes.strategies._llm_edit', fake_llm_edit)

    with pytest.raises(HTTPException) as exc_info:
        await edit_strategy(
            strategy_id=1,
            payload=StrategyEditRequest(prompt='change params'),
            db=db,
            user=_user(user_id=7),
        )

    assert exc_info.value.status_code == 404
