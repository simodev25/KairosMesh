from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class StrategyOptimizerCampaign(Base):
    __tablename__ = 'strategy_optimizer_campaigns'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    strategy_id: Mapped[int] = mapped_column(Integer, ForeignKey('strategies.id'), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default='PENDING',
    )  # PENDING|RUNNING|COMPLETED|CANCELLED|FAILED|REJECTED_BY_USER|ACCEPTED
    config: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    initial_params: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    initial_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    best_params: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    best_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    best_metrics: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    current_iteration: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    celery_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
