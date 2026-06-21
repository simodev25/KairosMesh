from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class EvolutionCampaign(Base):
    __tablename__ = 'evolution_campaigns'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    agent_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    model_parameters: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    baseline_prompt_template_id: Mapped[int] = mapped_column(ForeignKey('prompt_templates.id'), nullable=False)
    baseline_skill_id: Mapped[int | None] = mapped_column(ForeignKey('agent_skills.id'), nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default='pending', index=True)
    max_iterations: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    max_candidates: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    max_llm_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=1000)
    budget_usd_limit: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False, default=0)
    evaluation_config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    best_candidate_id: Mapped[int | None] = mapped_column(ForeignKey('evolution_candidates.id'), nullable=True)
    celery_task_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    consumed_budget_usd: Mapped[float] = mapped_column(Numeric(12, 6), nullable=False, default=0)
    llm_calls_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    consumed_iterations: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    consumed_candidates: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
