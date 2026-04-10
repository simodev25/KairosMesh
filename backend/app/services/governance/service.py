"""GovernanceService — orchestrates position monitoring and governance action execution."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.models.audit_log import AuditLog
from app.db.models.run import AnalysisRun
from app.services.trading.metaapi_client import MetaApiClient
from app.tasks.governance_monitor_task import run_governance_task

logger = logging.getLogger(__name__)


class GovernanceService:

    async def _fetch_open_positions(self) -> list[dict]:
        """Fetch current open positions from MetaAPI."""
        client = MetaApiClient()
        result = await client.get_positions()
        return result.get('positions', [])

    def _has_active_governance_run(self, db: Session, position_id: str) -> bool:
        """Return True if a governance run is already pending/running for this position."""
        existing = (
            db.query(AnalysisRun)
            .filter(
                AnalysisRun.run_type == 'governance',
                AnalysisRun.governance_position_id == position_id,
                AnalysisRun.status.in_(['pending', 'running']),
            )
            .first()
        )
        return existing is not None

    async def analyze_open_positions(
        self,
        db: Session,
        *,
        depth: str = 'light',
        system_user_id: int,
    ) -> list[int]:
        """Create governance runs for all open positions that don't already have one running."""
        positions = await self._fetch_open_positions()
        if not positions:
            logger.info('governance_monitor no_open_positions')
            return []

        created_run_ids: list[int] = []

        for position in positions:
            pos_id = str(position.get('id', ''))
            symbol = str(position.get('symbol', 'UNKNOWN'))

            if not pos_id:
                continue

            if self._has_active_governance_run(db, pos_id):
                logger.info('governance_monitor skipping_existing_run position_id=%s', pos_id)
                continue

            run = AnalysisRun(
                pair=symbol,
                timeframe='H1',
                mode='paper',
                status='pending',
                progress=0,
                run_type='governance',
                governance_position_id=pos_id,
                decision={},
                trace={
                    'governance_position': position,
                    'analysis_depth': depth,
                },
                created_by_id=system_user_id,
            )
            db.add(run)
            db.commit()
            db.refresh(run)

            run_governance_task.delay(run.id)
            run.status = 'queued'
            db.commit()
            created_run_ids.append(run.id)
            logger.info(
                'governance_monitor run_created run_id=%d position_id=%s symbol=%s',
                run.id, pos_id, symbol,
            )

        return created_run_ids

    async def approve_action(self, db: Session, *, run_id: int, actor: str) -> dict:
        """Execute the governance decision for a completed run.

        Risk-engine validation note
        ---------------------------
        The RiskEngine (``app.services.risk.rules``) validates *new* trade
        proposals via ``evaluate_portfolio()``, which requires a ``ProposedTrade``
        (with entry_price, stop_loss, risk_percent) and a full ``PortfolioState``.
        Governance actions differ fundamentally:

        * **CLOSE** always *reduces* portfolio risk, so further validation would
          be redundant.
        * **ADJUST_SL / ADJUST_TP / ADJUST_BOTH** modify existing positions
          rather than opening new ones; the current ``RiskEngine`` API does not
          support evaluating SL/TP changes in isolation.
        * Governance runs already operate in **confirmation mode** — a human
          must explicitly approve before execution, providing oversight that
          substitutes for an automated gate.

        TODO: Extend ``RiskEngine`` with a ``validate_governance_action()``
        method that can evaluate SL/TP adjustments against portfolio limits
        (e.g., verify the new SL does not exceed ``max_risk_per_trade_pct``).
        Until then, human confirmation is the safety barrier.
        """
        run = db.query(AnalysisRun).filter(
            AnalysisRun.id == run_id,
            AnalysisRun.run_type == 'governance',
        ).first()
        if not run:
            raise ValueError(f'Governance run {run_id} not found')

        decision = run.decision or {}
        action = decision.get('action', 'HOLD')
        pos_id = str(run.governance_position_id or '')

        client = MetaApiClient()
        result: dict = {}

        # TODO: When RiskEngine gains validate_governance_action(), call it here
        # before executing ADJUST_SL/ADJUST_TP/ADJUST_BOTH.  CLOSE is exempt
        # because it strictly reduces risk.  See docstring above for rationale.

        if action == 'HOLD':
            result = {'executed': False, 'reason': 'Action is HOLD — nothing to execute'}
        elif action in ('ADJUST_SL', 'ADJUST_TP', 'ADJUST_BOTH'):
            result = await client.modify_position(
                position_id=pos_id,
                stop_loss=decision.get('new_sl'),
                take_profit=decision.get('new_tp'),
            )
        elif action == 'CLOSE':
            result = await client.close_position(position_id=pos_id)
        else:
            raise ValueError(f'Unknown governance action: {action}')

        run.trace = {**(run.trace or {}), 'execution_result': result, 'executed_by': actor}
        db.commit()

        audit = AuditLog(
            actor_email=actor,
            action=f'governance_approve_{action.lower()}',
            target_type='governance_run',
            target_id=str(run_id),
            details={'decision': decision, 'result': result},
        )
        db.add(audit)
        db.commit()

        return result

    def reject_action(self, db: Session, *, run_id: int, actor: str) -> None:
        """Mark a governance run as rejected by the user."""
        run = db.query(AnalysisRun).filter(
            AnalysisRun.id == run_id,
            AnalysisRun.run_type == 'governance',
        ).first()
        if not run:
            raise ValueError(f'Governance run {run_id} not found')

        run.trace = {**(run.trace or {}), 'rejected_by': actor, 'rejected_at': datetime.now(timezone.utc).isoformat()}
        run.status = 'cancelled'
        db.commit()

        audit = AuditLog(
            actor_email=actor,
            action='governance_reject',
            target_type='governance_run',
            target_id=str(run_id),
            details={'decision': run.decision},
        )
        db.add(audit)
        db.commit()
