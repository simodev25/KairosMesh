from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models.run import AnalysisRun
from app.services.agent_runtime.runtime import AgenticTradingRuntime


async def run_with_selected_runtime(
    db: Session,
    run: AnalysisRun,
    *,
    risk_percent: float,
    metaapi_account_ref: int | None = None,
) -> AnalysisRun:
    return await AgenticTradingRuntime().execute(
        db=db,
        run=run,
        risk_percent=risk_percent,
        metaapi_account_ref=metaapi_account_ref,
    )
