from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ExecutionOrderOut(BaseModel):
    id: int
    run_id: int
    timeframe: str | None = None
    mode: str
    side: str
    symbol: str
    volume: float
    status: str
    request_payload: dict[str, Any]
    response_payload: dict[str, Any]
    error: str | None
    created_at: datetime

    model_config = {'from_attributes': True}
