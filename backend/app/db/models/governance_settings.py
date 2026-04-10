from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class GovernanceSettings(Base):
    __tablename__ = 'governance_settings'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    execution_mode: Mapped[str] = mapped_column(String(20), nullable=False, default='confirmation')
    analysis_depth: Mapped[str] = mapped_column(String(10), nullable=False, default='light')
    interval_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=15)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
