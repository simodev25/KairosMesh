from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models.agent_skill import AgentSkill
from app.services.skills.service import AgentSkillsService


def test_agent_skills_service_create_activate_and_get_active() -> None:
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(bind=engine)
    service = AgentSkillsService()

    with Session(engine) as db:
        v1 = service.create_version(
            db=db,
            agent_name='news-analyst',
            skills=['A', 'B'],
            notes='v1',
            created_by_id=None,
            activate=True,
        )
        assert v1.version == 1
        assert v1.is_active is True

        v2 = service.create_version(
            db=db,
            agent_name='news-analyst',
            skills=['C'],
            notes='v2',
            created_by_id=None,
            activate=False,
        )
        assert v2.version == 2
        assert v2.is_active is False

        active = service.get_active(db, 'news-analyst')
        assert active is not None
        assert active.id == v1.id

        activated = service.activate(db, v2.id)
        assert activated is not None
        assert activated.id == v2.id
        assert activated.is_active is True

        rows = db.query(AgentSkill).filter(AgentSkill.agent_name == 'news-analyst').all()
        assert sum(1 for row in rows if row.is_active) == 1


def test_agent_skills_service_seed_defaults_is_idempotent() -> None:
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(bind=engine)
    service = AgentSkillsService()

    with Session(engine) as db:
        first = service.seed_defaults(db)
        assert first['created'] >= 1

        second = service.seed_defaults(db)
        assert second['created'] == 0
        assert second['skipped'] >= 1
