from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class EvolutionPromotion(Base):
    __tablename__ = 'evolution_promotions'
    __table_args__ = (
        CheckConstraint(
            '(prompt_template_id IS NOT NULL) OR (agent_skill_id IS NOT NULL)',
            name='ck_evolution_promotions_target_not_null',
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey('evolution_campaigns.id'), nullable=False, index=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey('evolution_candidates.id'), nullable=False, index=True)
    prompt_template_id: Mapped[int | None] = mapped_column(ForeignKey('prompt_templates.id'), nullable=True)
    agent_skill_id: Mapped[int | None] = mapped_column(ForeignKey('agent_skills.id'), nullable=True)
    promoted_by_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
