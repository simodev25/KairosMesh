from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import Role, require_roles
from app.db.models.memory_entry import MemoryEntry
from app.db.session import get_db
from app.schemas.memory import MemoryOut, MemorySearchRequest
from app.services.memory.vector_memory import VectorMemoryService

router = APIRouter(prefix='/memory', tags=['memory'])


@router.get('', response_model=list[MemoryOut])
def list_memory(
    limit: int = 50,
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
    results = service.search(
        db=db,
        pair=payload.pair.upper(),
        timeframe=payload.timeframe.upper(),
        query=payload.query,
        limit=payload.limit,
    )
    return {'results': results}
