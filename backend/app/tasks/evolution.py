import logging
from datetime import datetime, timezone

from app.core.config import get_settings
from app.db.models.evolution_campaign import EvolutionCampaign
from app.db.session import SessionLocal
from app.services.evolution.engine import EvolutionEngine
from app.tasks.celery_app import celery_app


logger = logging.getLogger(__name__)
settings = get_settings()


@celery_app.task(
    name='app.tasks.evolution.run_evolution_campaign',
    soft_time_limit=settings.celery_evolution_soft_time_limit_seconds,
    time_limit=settings.celery_evolution_time_limit_seconds,
)
def run_evolution_campaign(campaign_id: int) -> None:
    db = SessionLocal()
    try:
        campaign = db.get(EvolutionCampaign, campaign_id)
        if campaign is None:
            return
        if campaign.status in {'completed', 'cancelled', 'failed'}:
            return

        engine = EvolutionEngine()
        engine.run_campaign(db, campaign)
    except Exception as exc:
        logger.exception('evolution campaign failed campaign_id=%s', campaign_id)
        db.rollback()
        campaign = db.get(EvolutionCampaign, campaign_id)
        if campaign is not None:
            campaign.status = 'failed'
            campaign.error = str(exc)
            campaign.completed_at = datetime.now(timezone.utc)
            db.commit()
    finally:
        db.close()
