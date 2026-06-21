from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


BenchmarkProvider = Literal['ollama', 'openai', 'mistral']
BenchmarkScenarioType = Literal['single-agent', 'debate-bundle', 'full-pipeline']


class BenchmarkModelSpec(BaseModel):
    provider: BenchmarkProvider
    model_name: str = Field(min_length=1, max_length=120)
    parameters: dict[str, Any] = Field(default_factory=dict)

    model_config = {'extra': 'forbid'}


class BenchmarkFixtureCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    agent_name: str = Field(min_length=1, max_length=80)
    inputs: dict[str, Any]
    config: dict[str, Any]
    default_scoring_weights: dict[str, float] | None = None

    model_config = {'extra': 'forbid'}


class BenchmarkFixturePatchRequest(BaseModel):
    is_active: bool

    model_config = {'extra': 'forbid'}


class BenchmarkFixtureOut(BaseModel):
    id: int
    name: str
    agent_name: str
    version: int
    hash: str
    inputs: dict[str, Any]
    config: dict[str, Any]
    default_scoring_weights: dict[str, float] | None = None
    is_active: bool
    is_deleted: bool
    created_by_id: int
    created_at: datetime
    updated_at: datetime

    model_config = {'from_attributes': True}


class BenchmarkRunCreateRequest(BaseModel):
    fixture_id: int
    fixture_hash: str = Field(min_length=32, max_length=128)
    model_spec: BenchmarkModelSpec
    scenario_type: BenchmarkScenarioType
    repetitions: int = Field(default=3, ge=2)
    max_llm_calls: int | None = Field(default=None, ge=1)
    scoring_weights: dict[str, float] | None = None

    model_config = {'extra': 'forbid'}


class BenchmarkAttemptOut(BaseModel):
    id: int
    attempt_number: int
    raw_output: dict[str, Any]
    schema_validity_score: float
    completeness_score: float
    tool_policy_compliance_score: float
    reference_consistency_score: float
    stability_score: float | None = None
    aggregate_score: float
    llm_calls_count: int
    analysis_run_id: int | None = None
    executed_at: datetime

    model_config = {'from_attributes': True}


class BenchmarkCaseOut(BaseModel):
    id: int
    agent_name: str
    case_order: int
    aggregate_score: float | None = None
    created_at: datetime
    attempts: list[BenchmarkAttemptOut] = Field(default_factory=list)

    model_config = {'from_attributes': True}


class BenchmarkRunOut(BaseModel):
    id: int
    fixture_id: int
    fixture_hash: str
    model_spec: dict[str, Any]
    scenario_type: str
    status: str
    repetitions: int
    max_llm_calls: int | None = None
    effective_scoring_weights: dict[str, float] | None = None
    error: str | None = None
    created_by_id: int
    celery_task_id: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    updated_at: datetime

    model_config = {'from_attributes': True}


class BenchmarkRunDetailOut(BenchmarkRunOut):
    cases: list[BenchmarkCaseOut] = Field(default_factory=list)


class BenchmarkScoresV1Out(BaseModel):
    schema_validity: float
    completeness: float
    tool_policy: float
    reference_consistency: float
    stability: float
    overall: float


class BenchmarkAgentResultsOut(BaseModel):
    agent_key: str
    attempts_count: int
    avg_scores: BenchmarkScoresV1Out


class BenchmarkRunResultsOut(BaseModel):
    run_id: int
    fixture_id: int
    model_spec: dict[str, Any]
    scenario_type: str
    status: str
    overall_scores: BenchmarkScoresV1Out
    agent_results: list[BenchmarkAgentResultsOut] = Field(default_factory=list)
    total_attempts: int


class BenchmarkRunListFilters(BaseModel):
    fixture_id: int | None = None
    agent_name: str | None = None
    provider: BenchmarkProvider | None = None
    model_name: str | None = None
    status: str | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1, le=200)

    @model_validator(mode='after')
    def validate_date_range(self):
        if self.date_from and self.date_to and self.date_to < self.date_from:
            raise ValueError('date_to must be greater than or equal to date_from')
        return self


class BenchmarkFixtureListFilters(BaseModel):
    agent_name: str | None = None
    is_active: bool | None = None
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1, le=200)


class BenchmarkStatus:
    PENDING = 'PENDING'
    RUNNING = 'RUNNING'
    COMPLETED = 'COMPLETED'
    FAILED = 'FAILED'
    SKIPPED_DEBATE = 'SKIPPED_DEBATE'
    CANCELLED = 'CANCELLED'


class BenchmarkScenario:
    SINGLE_AGENT = 'single-agent'
    DEBATE_BUNDLE = 'debate-bundle'
    FULL_PIPELINE = 'full-pipeline'
