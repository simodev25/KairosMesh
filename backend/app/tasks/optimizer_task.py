"""Celery task for strategy optimizer campaigns.

Executes on a dedicated queue (strategy-optimizer) to isolate from backtests.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from celery import current_task

from app.core.config import get_settings
from app.db.models.strategy_optimizer_campaign import StrategyOptimizerCampaign
from app.db.session import SessionLocal
from app.services.strategy.optimizer_service import run_optimization_loop
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)
settings = get_settings()


@celery_app.task(
    name='app.tasks.optimizer_task.execute',
    bind=True,
    acks_late=True,
    soft_time_limit=settings.celery_optimizer_soft_time_limit_seconds,
    time_limit=settings.celery_optimizer_time_limit_seconds,
    queue=settings.celery_optimizer_queue,
)
def execute(self, campaign_id: int) -> dict:
    """Execute optimization campaign loop."""
    db = SessionLocal()
    try:
        campaign = db.get(StrategyOptimizerCampaign, campaign_id)
        if campaign is None:
            logger.error('optimizer_task_campaign_not_found id=%s', campaign_id)
            return {'status': 'error', 'message': f'Campaign {campaign_id} not found'}

        # Store celery task id for potential revocation
        campaign.celery_task_id = current_task.request.id
        db.commit()

        logger.info('optimizer_task_started campaign_id=%s strategy_id=%s', campaign_id, campaign.strategy_id)

        run_optimization_loop(db, campaign_id)

        db.refresh(campaign)
        return {
            'status': campaign.status,
            'campaign_id': campaign_id,
            'best_score': campaign.best_score,
            'iterations': campaign.current_iteration,
        }
    except Exception as exc:
        logger.error('optimizer_task_failed campaign_id=%s err=%s', campaign_id, str(exc)[:300], exc_info=True)
        # Mark campaign as FAILED
        try:
            campaign = db.get(StrategyOptimizerCampaign, campaign_id)
            if campaign and campaign.status in ('PENDING', 'RUNNING'):
                campaign.status = 'FAILED'
                campaign.error_message = str(exc)[:500]
                campaign.completed_at = datetime.now(timezone.utc)
                db.commit()
        except Exception:
            logger.warning('optimizer_task_failed_to_mark_failed campaign_id=%s', campaign_id, exc_info=True)
        return {'status': 'error', 'campaign_id': campaign_id, 'message': str(exc)[:300]}
    finally:
        db.close()
