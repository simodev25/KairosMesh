from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class GovernanceRun(Base):
    """One governance evaluation cycle for a single open position.

    Created by the Celery Beat governance task each time it evaluates a position.
    Links back to the analysis run that originally opened the position (when resolvable).
    """
    __tablename__ = 'governance_runs'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # The MetaAPI position ticket being governed (e.g. "91203847").
    position_ticket: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # Symbol and side for quick filtering without a join.
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    side: Mapped[str] = mapped_column(String(10), nullable=False)

    # Link to the analysis run that opened this position (nullable: may be unknown
    # if position was opened before governance was deployed or through external tool).
    origin_run_id: Mapped[int | None] = mapped_column(
        ForeignKey('analysis_runs.id'), nullable=True, index=True
    )

    # Pipeline execution status.
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default='pending'
    )  # pending | running | completed | failed

    # Governance decision produced by the trader-agent in governance mode.
    action: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # HOLD | ADJUST_SL | ADJUST_TP | ADJUST_SL_TP | CLOSE

    new_sl: Mapped[float | None] = mapped_column(Float, nullable=True)
    new_tp: Mapped[float | None] = mapped_column(Float, nullable=True)
    conviction: Mapped[float | None] = mapped_column(Float, nullable=True)
    urgency: Mapped[str | None] = mapped_column(String(10), nullable=True)
    # low | medium | high | critical

    # Full agent reasoning (trader-agent governance decision text).
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Full pipeline trace (Phase 1 summaries, debate result if run, risk output).
    trace: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    # Whether the action requires human approval before executing.
    requires_approval: Mapped[bool] = mapped_column(default=True, nullable=False)

    # Approval workflow fields (for supervised mode).
    approval_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default='pending'
    )  # pending | approved | rejected | expired | auto_executed
    approved_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Whether the action was actually executed against the broker.
    executed: Mapped[bool] = mapped_column(default=False, nullable=False)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    execution_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    origin_run = relationship('AnalysisRun', foreign_keys=[origin_run_id])
