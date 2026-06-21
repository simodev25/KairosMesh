from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class EvolutionCandidateOut(BaseModel):
    id: int
    campaign_id: int
    generation: int
    parent_candidate_id: int | None
    system_prompt: str
    user_prompt_template: str
    skills: list[str]
    fitness_score: float | None
    metrics_summary: dict[str, Any] | None
    llm_cost_usd: float
    llm_calls_count: int
    is_baseline: bool
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {'from_attributes': True}


class EvolutionCandidateListResponse(BaseModel):
    items: list[EvolutionCandidateOut]


class EvolutionFitnessPoint(BaseModel):
    generation: int
    best: float
    avg: float


class EvolutionFitnessSeriesResponse(BaseModel):
    points: list[EvolutionFitnessPoint] = Field(default_factory=list)


class EvolutionPromoteRequest(BaseModel):
    promote_prompt: bool = True
    promote_skills: bool = True

    model_config = {'extra': 'forbid'}


class EvolutionPromoteResponse(BaseModel):
    promotion_id: int
    prompt_template_id: int | None
    agent_skill_id: int | None
    created_at: datetime
