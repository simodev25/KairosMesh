"""Celery task for governance monitoring of open positions.

This stub is created by Task 5 (GovernanceService) and will be fully
implemented in Task 6 (Celery governance task + Beat schedule).
"""
import logging

logger = logging.getLogger(__name__)


class _StubTask:
    """Placeholder until Task 6 registers the real Celery task."""

    def delay(self, run_id: int) -> None:  # noqa: D401
        """Queue the governance task (no-op stub)."""
        logger.info('governance_monitor_task.delay run_id=%d (stub, Task 6 not yet implemented)', run_id)

    def __call__(self, run_id: int) -> dict:
        logger.info('governance_monitor_task run_id=%d (stub)', run_id)
        return {'run_id': run_id, 'status': 'queued'}


run_governance_task = _StubTask()
