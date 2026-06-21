from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class EvolutionCandidate(Base):
    __tablename__ = 'evolution_candidates'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey('evolution_campaigns.id'), nullable=False, index=True)
    generation: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    parent_candidate_id: Mapped[int | None] = mapped_column(ForeignKey('evolution_candidates.id'), nullable=True)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    user_prompt_template: Mapped[str] = mapped_column(Text, nullable=False)
    skills: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    fitness_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    metrics_summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    llm_cost_usd: Mapped[float] = mapped_column(Numeric(12, 6), nullable=False, default=0)
    llm_calls_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_baseline: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default='generated', index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
