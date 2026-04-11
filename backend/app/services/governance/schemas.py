"""Pydantic output schema for governance agent decisions."""
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class GovernanceDecision(BaseModel):
    model_config = ConfigDict(extra='ignore', str_strip_whitespace=True)

    action: Literal['HOLD', 'ADJUST_SL', 'ADJUST_TP', 'ADJUST_BOTH', 'CLOSE']
    new_sl: float | None = None
    new_tp: float | None = None
    reasoning: str = Field(min_length=1)
    risk_score: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)

    @model_validator(mode='after')
    def _validate_sl_tp_requirements(self) -> 'GovernanceDecision':
        if self.action in ('ADJUST_SL', 'ADJUST_BOTH') and self.new_sl is None:
            raise ValueError('new_sl is required for action ADJUST_SL / ADJUST_BOTH')
        if self.action in ('ADJUST_TP', 'ADJUST_BOTH') and self.new_tp is None:
            raise ValueError('new_tp is required for action ADJUST_TP / ADJUST_BOTH')
        return self

    @model_validator(mode='before')
    @classmethod
    def _normalise_and_clamp(cls, values: dict) -> dict:
        if not isinstance(values, dict):
            return values
        # action: uppercase
        if 'action' in values and isinstance(values['action'], str):
            values['action'] = values['action'].upper().strip()
        # reasoning aliases
        if 'reasoning' not in values:
            for alias in ('reason', 'explanation', 'rationale', 'justification', 'analysis'):
                if alias in values:
                    values['reasoning'] = values.pop(alias)
                    break
        # score aliases
        if 'risk_score' not in values and 'risk' in values:
            values['risk_score'] = values.pop('risk')
        if 'confidence' not in values and 'conf' in values:
            values['confidence'] = values.pop('conf')
        # clamp scores to [0, 1]
        for field in ('risk_score', 'confidence'):
            v = values.get(field)
            if isinstance(v, (int, float)):
                values[field] = max(0.0, min(1.0, float(v)))
        return values
