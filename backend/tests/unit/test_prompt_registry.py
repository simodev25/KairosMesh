from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models.prompt_template import PromptTemplate
from app.db.models.user import User  # noqa: F401
from app.services.prompts.registry import PromptTemplateService


def test_prompt_registry_version_activation() -> None:
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(bind=engine)

    service = PromptTemplateService()
    with Session(engine) as db:
        service.seed_defaults(db)

        created = service.create_version(
            db=db,
            agent_name='bullish-researcher',
            system_prompt='system v2',
            user_prompt_template='user {pair}',
            notes='test',
            created_by_id=None,
        )
        assert created.version >= 2

        activated = service.activate(db, created.id)
        assert activated is not None
        assert activated.is_active is True

        active = service.get_active(db, 'bullish-researcher')
        assert active is not None
        assert active.id == created.id

        rows = db.query(PromptTemplate).filter(PromptTemplate.agent_name == 'bullish-researcher').all()
        assert sum(1 for row in rows if row.is_active) == 1
