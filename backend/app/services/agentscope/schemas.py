"""Pydantic output schemas for structured agent output (msg.metadata)."""
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class _SchemaBase(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)


class TechnicalAnalysisResult(_SchemaBase):
    signal: Literal["bullish", "bearish", "neutral"]
    score: float = Field(ge=-1.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    setup_state: Literal["non_actionable", "conditional", "weak_actionable", "actionable", "high_conviction"]
    summary: str = Field(min_length=1)
    structural_bias: Literal["bullish", "bearish", "neutral"] = "neutral"
    local_momentum: Literal["bullish", "bearish", "neutral", "mixed"] = "neutral"
    tradability: float = Field(default=0.0, ge=0.0, le=1.0)
    degraded: bool = False
    reason: str | None = None


class NewsAnalysisResult(_SchemaBase):
    signal: Literal["bullish", "bearish", "neutral"]
    score: float = Field(ge=-1.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    coverage: Literal["none", "low", "medium", "high"]
    evidence_strength: float = Field(ge=0.0, le=1.0)
    summary: str = Field(min_length=1)
    degraded: bool = False
    reason: str | None = None


class MarketContextResult(_SchemaBase):
    signal: Literal["bullish", "bearish", "neutral"]
    score: float = Field(ge=-1.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    regime: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    tradability_score: float = Field(default=1.0, ge=0.0, le=1.0)
    execution_penalty: float = Field(default=0.0, ge=0.0, le=1.0)
    hard_block: bool = False
    degraded: bool = False
    reason: str | None = None


class DebateThesis(_SchemaBase):
    arguments: list[str] = Field(default_factory=list)
    thesis: str = ""
    confidence: float = Field(ge=0.0, le=1.0)
    invalidation_conditions: list[str] = Field(default_factory=list)
    degraded: bool = False


class DebateResult(_SchemaBase):
    finished: bool
    winning_side: Literal["bullish", "bearish", "neutral"] | None = None
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    reason: str = ""


class TraderDecisionDraft(_SchemaBase):
    decision: Literal["BUY", "SELL", "HOLD"]
    confidence: float = Field(ge=0.0, le=1.0)
    combined_score: float = Field(ge=-1.0, le=1.0)
    execution_allowed: bool
    reason: str = Field(min_length=1)
    entry: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    degraded: bool = False

    @model_validator(mode="after")
    def validate_execution_levels(self) -> "TraderDecisionDraft":
        if self.decision == "HOLD" or not self.execution_allowed:
            return self
        if self.entry is None or self.stop_loss is None or self.take_profit is None:
            raise ValueError("entry, stop_loss, and take_profit required for executable BUY/SELL")
        if self.decision == "BUY" and not (self.stop_loss < self.entry < self.take_profit):
            raise ValueError("BUY requires stop_loss < entry < take_profit")
        if self.decision == "SELL" and not (self.take_profit < self.entry < self.stop_loss):
            raise ValueError("SELL requires take_profit < entry < stop_loss")
        return self


class RiskAssessmentResult(_SchemaBase):
    accepted: bool
    suggested_volume: float = Field(ge=0.0)
    reasons: list[str] = Field(default_factory=list)
    degraded: bool = False


class ExecutionPlanResult(_SchemaBase):
    decision: Literal["BUY", "SELL", "HOLD"]
    should_execute: bool
    side: Literal["BUY", "SELL"] | None = None
    volume: float = Field(ge=0.0)
    reason: str = Field(min_length=1)
    degraded: bool = False
