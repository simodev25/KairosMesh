from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class BenchmarkRun(Base):
    __tablename__ = 'benchmark_runs'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    fixture_id: Mapped[int] = mapped_column(ForeignKey('benchmark_fixtures.id'), nullable=False, index=True)
    fixture_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    model_spec: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    scenario_type: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default='PENDING', index=True)
    repetitions: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    max_llm_calls: Mapped[int | None] = mapped_column(Integer, nullable=True)
    effective_scoring_weights: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_by_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    celery_task_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    fixture = relationship('BenchmarkFixture', back_populates='runs')
    cases = relationship('BenchmarkCase', back_populates='run', cascade='all, delete-orphan')
