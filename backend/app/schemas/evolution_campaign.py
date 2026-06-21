from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


CAMPAIGN_STATUS = {'pending', 'running', 'completed', 'cancelled', 'failed'}


class EvolutionCampaignCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    agent_name: str = Field(min_length=1, max_length=64)
    provider: str = Field(min_length=1, max_length=32)
    model_name: str = Field(min_length=1, max_length=128)
    model_parameters: dict[str, Any] = Field(default_factory=dict)
    baseline_prompt_template_id: int
    baseline_skill_id: int | None = None
    max_iterations: int = Field(default=100, ge=1)
    max_candidates: int = Field(default=50, ge=1)
    max_llm_calls: int = Field(default=1000, ge=1)
    budget_usd_limit: float = Field(default=0.0, ge=0.0)
    evaluation_config: dict[str, Any] = Field(default_factory=dict)

    model_config = {'extra': 'forbid'}


class EvolutionCampaignOut(BaseModel):
    id: int
    name: str
    agent_name: str
    provider: str
    model_name: str
    model_parameters: dict[str, Any]
    baseline_prompt_template_id: int
    baseline_skill_id: int | None
    status: str
    max_iterations: int
    max_candidates: int
    max_llm_calls: int
    budget_usd_limit: float
    evaluation_config: dict[str, Any]
    best_candidate_id: int | None
    celery_task_id: str | None
    consumed_budget_usd: float
    llm_calls_used: int
    consumed_iterations: int
    consumed_candidates: int
    created_by_id: int | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    error: str | None
    updated_at: datetime

    model_config = {'from_attributes': True}


class EvolutionCampaignListResponse(BaseModel):
    items: list[EvolutionCampaignOut]
    total: int


class EvolutionCampaignCancelResponse(BaseModel):
    id: int
    status: str

    @field_validator('status')
    @classmethod
    def validate_status(cls, value: str) -> str:
        if value not in CAMPAIGN_STATUS and value != 'cancel_requested':
            raise ValueError('invalid campaign status')
        return value
