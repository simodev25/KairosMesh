from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class EvolutionCandidateEvaluation(Base):
    __tablename__ = 'evolution_candidate_evaluations'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey('evolution_candidates.id'), nullable=False, index=True)
    evaluation_type: Mapped[str] = mapped_column(String(32), nullable=False, default='benchmark')
    benchmark_run_id: Mapped[int | None] = mapped_column(ForeignKey('benchmark_runs.id'), nullable=True)
    metrics: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    aggregate_score: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
