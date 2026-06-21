from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class BenchmarkCase(Base):
    __tablename__ = 'benchmark_cases'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey('benchmark_runs.id'), nullable=False, index=True)
    agent_name: Mapped[str] = mapped_column(String(80), nullable=False)
    case_order: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    aggregate_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    run = relationship('BenchmarkRun', back_populates='cases')
    attempts = relationship('BenchmarkAttempt', back_populates='case', cascade='all, delete-orphan')
