from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.db.models.governance_settings import GovernanceSettings

_DEFAULTS = {
    'enabled': False,
    'execution_mode': 'confirmation',
    'analysis_depth': 'light',
    'interval_minutes': 15,
}


def get_governance_settings(db: Session) -> dict:
    row = db.query(GovernanceSettings).filter(GovernanceSettings.id == 1).first()
    if not row:
        return dict(_DEFAULTS)
    return {
        'enabled': row.enabled,
        'execution_mode': row.execution_mode,
        'analysis_depth': row.analysis_depth,
        'interval_minutes': row.interval_minutes,
        'updated_at': row.updated_at.isoformat() if row.updated_at else None,
        'updated_by': row.updated_by,
    }


def update_governance_settings(
    db: Session,
    *,
    enabled: bool,
    execution_mode: str,
    analysis_depth: str,
    interval_minutes: int,
    actor: str,
) -> dict:
    row = db.query(GovernanceSettings).filter(GovernanceSettings.id == 1).first()
    if not row:
        row = GovernanceSettings(id=1)
        db.add(row)
    row.enabled = enabled
    row.execution_mode = execution_mode
    row.analysis_depth = analysis_depth
    row.interval_minutes = max(5, int(interval_minutes))
    row.updated_at = datetime.now(timezone.utc)
    row.updated_by = actor
    db.commit()
    return get_governance_settings(db)
