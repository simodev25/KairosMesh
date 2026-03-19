from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.security import Role, require_roles
from app.db.models.memory_entry import MemoryEntry
from app.db.session import get_db
from app.schemas.memory import MemoryOut, MemorySearchRequest
from app.services.memory.vector_memory import VectorMemoryService

router = APIRouter(prefix='/memory', tags=['memory'])


@router.get('', response_model=list[MemoryOut])
def list_memory(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _=Depends(require_roles(Role.SUPER_ADMIN, Role.ADMIN, Role.TRADER_OPERATOR, Role.ANALYST, Role.VIEWER)),
) -> list[MemoryOut]:
    entries = db.query(MemoryEntry).order_by(MemoryEntry.created_at.desc()).limit(limit).all()
    return [MemoryOut.model_validate(entry) for entry in entries]


@router.post('/search')
def search_memory(
    payload: MemorySearchRequest,
    db: Session = Depends(get_db),
    _=Depends(require_roles(Role.SUPER_ADMIN, Role.ADMIN, Role.TRADER_OPERATOR, Role.ANALYST, Role.VIEWER)),
) -> dict:
    service = VectorMemoryService()
    retrieval_context = service.build_retrieval_context(
        payload.market_snapshot,
        decision_mode=payload.decision_mode,
    )
    results = service.search(
        db=db,
        pair=payload.pair.upper(),
        timeframe=payload.timeframe.upper(),
        query=payload.query,
        limit=payload.limit,
        retrieval_context=retrieval_context,
    )
    if not payload.include_signal:
        return {'results': results}

    memory_signal = service.compute_memory_signal(
        results,
        market_snapshot=payload.market_snapshot,
        decision_mode=payload.decision_mode,
    )
    return {'results': results, 'memory_signal': memory_signal}
