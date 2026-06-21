"""Pydantic schemas for the Strategy Optimizer campaign endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class OptimizerLaunchRequest(BaseModel):
    """Request body to launch an optimization campaign."""
    max_iterations: int | None = Field(default=None, ge=1, le=200, description='Maximum iterations (default: from config)')
    time_budget_seconds: int | None = Field(default=None, ge=10, le=1800, description='Time budget in seconds (default: from config)')
    max_candidates_per_iteration: int | None = Field(default=None, ge=1, le=10, description='Candidates per iteration')


class OptimizerCampaignOut(BaseModel):
    """Response schema for an optimizer campaign."""
    id: int
    strategy_id: int
    status: str
    current_iteration: int
    max_iterations: int
    best_score: float | None = None
    best_params: dict[str, Any] | None = None
    initial_params: dict[str, Any]
    initial_score: float | None = None
    best_metrics: dict[str, Any] | None = None
    elapsed_seconds: float | None = None
    error_message: str | None = None
    created_at: datetime
    completed_at: datetime | None = None

    model_config = {'from_attributes': True}

    @classmethod
    def from_campaign(cls, campaign: Any) -> 'OptimizerCampaignOut':
        """Build response from a StrategyOptimizerCampaign model instance."""
        config = campaign.config or {}
        max_iterations = int(config.get('max_iterations', 50))

        elapsed: float | None = None
        if campaign.completed_at and campaign.created_at:
            elapsed = (campaign.completed_at - campaign.created_at).total_seconds()
        elif campaign.status == 'RUNNING' and campaign.created_at:
            from datetime import timezone
            elapsed = (datetime.now(timezone.utc) - campaign.created_at).total_seconds()

        return cls(
            id=campaign.id,
            strategy_id=campaign.strategy_id,
            status=campaign.status,
            current_iteration=campaign.current_iteration,
            max_iterations=max_iterations,
            best_score=campaign.best_score,
            best_params=campaign.best_params,
            initial_params=campaign.initial_params,
            initial_score=campaign.initial_score,
            best_metrics=campaign.best_metrics,
            elapsed_seconds=elapsed,
            error_message=campaign.error_message,
            created_at=campaign.created_at,
            completed_at=campaign.completed_at,
        )
