from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class BenchmarkAttempt(Base):
    __tablename__ = 'benchmark_attempts'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    case_id: Mapped[int] = mapped_column(ForeignKey('benchmark_cases.id'), nullable=False, index=True)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_output: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    schema_validity_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    completeness_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    tool_policy_compliance_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    reference_consistency_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    stability_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    aggregate_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    llm_calls_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    analysis_run_id: Mapped[int | None] = mapped_column(ForeignKey('analysis_runs.id'), nullable=True, index=True)
    executed_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    case = relationship('BenchmarkCase', back_populates='attempts')
