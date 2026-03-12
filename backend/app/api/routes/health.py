from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.schemas.health import HealthResponse

router = APIRouter(prefix='/health', tags=['health'])


@router.get('', response_model=HealthResponse)
def health(db: Session = Depends(get_db)) -> HealthResponse:
    settings = get_settings()
    services = {'api': 'ok'}

    try:
        db.execute(text('SELECT 1'))
        services['postgres'] = 'ok'
    except Exception:
        services['postgres'] = 'degraded'

    services['ollama'] = 'configured' if bool(settings.ollama_api_key) else 'degraded'
    services['metaapi'] = 'configured' if bool(settings.metaapi_token and settings.metaapi_account_id) else 'degraded'
    services['qdrant'] = 'configured' if bool(settings.qdrant_url) else 'degraded'

    status = 'ok' if services.get('postgres') == 'ok' else 'degraded'
    return HealthResponse(status=status, services=services)
