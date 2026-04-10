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
    def _clamp_scores(cls, values: dict) -> dict:
        for field in ('risk_score', 'confidence'):
            v = values.get(field)
            if isinstance(v, (int, float)):
                values[field] = max(0.0, min(1.0, float(v)))
        return values
