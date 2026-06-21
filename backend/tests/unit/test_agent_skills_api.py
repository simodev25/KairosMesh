from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.routes.agent_skills import (
    activate_agent_skill_version,
    create_agent_skill_version,
    list_agent_skills,
    list_agents_catalog,
)
from app.db.base import Base
from app.schemas.agent_skill import AgentSkillCreateRequest


class _DummyUser:
    id = 1


def test_agent_skills_routes_create_list_activate_catalog() -> None:
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(bind=engine)

    with Session(engine) as db:
        created = create_agent_skill_version(
            agent_name='news-analyst',
            payload=AgentSkillCreateRequest(skills=['Rule A', 'Rule B'], notes='v1', activate=True),
            db=db,
            user=_DummyUser(),
        )
        assert created.agent_name == 'news-analyst'
        assert created.is_active is True

        rows = list_agent_skills(agent_name='news-analyst', active_only=False, db=db, _=None)
        assert len(rows) == 1

        v2 = create_agent_skill_version(
            agent_name='news-analyst',
            payload=AgentSkillCreateRequest(skills=['Rule C'], notes='v2', activate=False),
            db=db,
            user=_DummyUser(),
        )
        assert v2.version == 2

        activated = activate_agent_skill_version(agent_name='news-analyst', skill_id=v2.id, db=db, _=None)
        assert activated.id == v2.id
        assert activated.is_active is True

        active_only = list_agent_skills(agent_name='news-analyst', active_only=True, db=db, _=None)
        assert len(active_only) == 1
        assert active_only[0].id == v2.id

        catalog = list_agents_catalog(db=db, _=None)
        assert any(row['agent_name'] == 'news-analyst' for row in catalog)
