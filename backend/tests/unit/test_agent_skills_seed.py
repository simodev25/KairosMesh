from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models.agent_skill import AgentSkill
from app.services.skills.service import AgentSkillsService


def test_seed_defaults_creates_active_version_one_rows() -> None:
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(bind=engine)
    service = AgentSkillsService()

    with Session(engine) as db:
        outcome = service.seed_defaults(db)
        assert outcome['created'] >= 1

        created_rows = db.query(AgentSkill).all()
        assert created_rows
        assert all(row.version == 1 for row in created_rows)
        assert all(row.is_active is True for row in created_rows)


def test_seed_defaults_skips_existing_agents() -> None:
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(bind=engine)
    service = AgentSkillsService()

    with Session(engine) as db:
        first = service.seed_defaults(db)
        second = service.seed_defaults(db)
        assert first['created'] >= 1
        assert second['created'] == 0
        assert second['skipped'] >= 1
