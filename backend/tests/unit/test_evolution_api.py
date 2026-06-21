import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.routes.evolution import (
    create_campaign,
    promote_candidate,
)
from app.db.base import Base
from app.db.models.agent_skill import AgentSkill
from app.db.models.evolution_campaign import EvolutionCampaign
from app.db.models.evolution_candidate import EvolutionCandidate
from app.db.models.evolution_candidate_evaluation import EvolutionCandidateEvaluation
from app.db.models.prompt_template import PromptTemplate
from app.db.models.user import User
from app.schemas.evolution_campaign import EvolutionCampaignCreateRequest
from app.schemas.evolution_candidate import EvolutionPromoteRequest
from app.services.evolution.service import EvolutionService


class _FakeTaskResult:
    id = 'task-evolution-123'


class _FakeEvolutionTask:
    def __init__(self) -> None:
        self.calls = []

    def apply_async(self, args=None, kwargs=None, queue=None, ignore_result=None):
        self.calls.append({'args': args, 'kwargs': kwargs, 'queue': queue, 'ignore_result': ignore_result})
        return _FakeTaskResult()


class _DummyUser:
    def __init__(self, user_id: int, role: str = 'admin') -> None:
        self.id = user_id
        self.role = role


def _setup_db_with_campaign(db: Session) -> tuple[User, EvolutionCampaign, EvolutionCandidate]:
    """Create a user, campaign, and evaluated candidate for testing."""
    user = User(email='api-admin@local.dev', hashed_password='x', role='admin', is_active=True)
    db.add(user)
    db.commit()
    db.refresh(user)

    prompt = PromptTemplate(
        agent_name='technical-analyst',
        version=1,
        is_active=True,
        system_prompt='baseline system',
        user_prompt_template='baseline user {pair}',
        notes='seed',
        created_by_id=user.id,
    )
    db.add(prompt)

    skill = AgentSkill(
        agent_name='technical-analyst',
        version=1,
        is_active=True,
        skills=['Skill A'],
        notes='seed',
        created_by_id=user.id,
    )
    db.add(skill)
    db.commit()
    db.refresh(prompt)
    db.refresh(skill)

    campaign = EvolutionCampaign(
        name='Test Campaign',
        agent_name='technical-analyst',
        provider='openai',
        model_name='gpt-4.1-mini',
        model_parameters={'temperature': 0.7},
        baseline_prompt_template_id=prompt.id,
        baseline_skill_id=skill.id,
        status='running',
        max_iterations=10,
        max_candidates=10,
        max_llm_calls=50,
        budget_usd_limit=10.0,
        evaluation_config={'benchmark_profile': 'standard'},
        created_by_id=user.id,
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)

    candidate = EvolutionCandidate(
        campaign_id=campaign.id,
        generation=1,
        parent_candidate_id=None,
        system_prompt='evaluated system',
        user_prompt_template='evaluated user {pair}',
        skills=['Skill B'],
        is_baseline=False,
        status='evaluated',
        fitness_score=0.85,
        metrics_summary={'schema_validity_score': 0.9},
    )
    db.add(candidate)
    db.commit()
    db.refresh(candidate)

    return user, campaign, candidate


def test_evolution_create_campaign_enqueues_task(monkeypatch) -> None:
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(bind=engine)

    with Session(engine) as db:
        user = User(email='api-admin@local.dev', hashed_password='x', role='admin', is_active=True)
        db.add(user)
        db.commit()
        db.refresh(user)

        prompt = PromptTemplate(
            agent_name='technical-analyst',
            version=1,
            is_active=True,
            system_prompt='baseline system',
            user_prompt_template='baseline user {pair}',
            notes='seed',
            created_by_id=user.id,
        )
        db.add(prompt)

        skill = AgentSkill(
            agent_name='technical-analyst',
            version=1,
            is_active=True,
            skills=['Skill A'],
            notes='seed',
            created_by_id=user.id,
        )
        db.add(skill)
        db.commit()
        db.refresh(prompt)
        db.refresh(skill)

        fake_task = _FakeEvolutionTask()
        monkeypatch.setattr('app.api.routes.evolution.run_evolution_campaign', fake_task)

        payload = EvolutionCampaignCreateRequest(
            name='API Campaign',
            agent_name='technical-analyst',
            provider='openai',
            model_name='gpt-4.1-mini',
            model_parameters={'temperature': 0.7},
            baseline_prompt_template_id=prompt.id,
            baseline_skill_id=skill.id,
            max_iterations=3,
            max_candidates=3,
            max_llm_calls=10,
            budget_usd_limit=5.0,
            evaluation_config={'benchmark_profile': 'standard'},
        )

        created = create_campaign(payload=payload, db=db, user=_DummyUser(user.id))
        assert created.status == 'pending'
        assert created.celery_task_id == 'task-evolution-123'
        assert len(fake_task.calls) == 1


def test_evolution_create_campaign_rbac_rejects_viewer(monkeypatch) -> None:
    """Viewer role should be rejected by the RBAC dependency (403)."""
    from app.core.security import require_roles, Role

    # Simulate what happens when require_roles is called with a viewer
    role_dep = require_roles(Role.SUPER_ADMIN, Role.ADMIN)
    viewer_user = User(email='viewer@local.dev', hashed_password='x', role='viewer', is_active=True)
    viewer_user.id = 99
    with pytest.raises(HTTPException) as exc_info:
        role_dep(user=viewer_user)
    assert exc_info.value.status_code == 403


def test_evolution_cancel_campaign_running() -> None:
    """Cancel a running campaign transitions to cancel_requested."""
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(bind=engine)

    with Session(engine) as db:
        user, campaign, _ = _setup_db_with_campaign(db)
        service = EvolutionService()
        result = service.request_cancel(db, campaign.id)
        assert result.status == 'cancel_requested'


def test_evolution_cancel_campaign_pending_becomes_cancelled() -> None:
    """Cancel a pending campaign transitions directly to cancelled."""
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(bind=engine)

    with Session(engine) as db:
        user, campaign, _ = _setup_db_with_campaign(db)
        campaign.status = 'pending'
        db.commit()
        service = EvolutionService()
        result = service.request_cancel(db, campaign.id)
        assert result.status == 'cancelled'


def test_evolution_cancel_campaign_already_completed_noop() -> None:
    """Cancel an already completed campaign is a no-op."""
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(bind=engine)

    with Session(engine) as db:
        user, campaign, _ = _setup_db_with_campaign(db)
        campaign.status = 'completed'
        db.commit()
        service = EvolutionService()
        result = service.request_cancel(db, campaign.id)
        assert result.status == 'completed'


def test_evolution_promote_candidate_success(monkeypatch) -> None:
    """Promote an evaluated candidate creates prompt + skill versions."""
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(bind=engine)

    with Session(engine) as db:
        user, campaign, candidate = _setup_db_with_campaign(db)
        payload = EvolutionPromoteRequest(promote_prompt=True, promote_skills=True)
        result = promote_candidate(
            candidate_id=candidate.id,
            payload=payload,
            db=db,
            user=_DummyUser(user.id),
        )
        assert result.promotion_id is not None
        assert result.prompt_template_id is not None
        assert result.agent_skill_id is not None


def test_evolution_promote_unevaluated_candidate_fails() -> None:
    """Promoting a non-evaluated candidate raises 409."""
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(bind=engine)

    with Session(engine) as db:
        user, campaign, candidate = _setup_db_with_campaign(db)
        candidate.status = 'generated'
        db.commit()
        payload = EvolutionPromoteRequest(promote_prompt=True, promote_skills=True)
        with pytest.raises(HTTPException) as exc_info:
            promote_candidate(
                candidate_id=candidate.id,
                payload=payload,
                db=db,
                user=_DummyUser(user.id),
            )
        assert exc_info.value.status_code == 409


def test_evolution_fitness_series_returns_points() -> None:
    """Fitness series returns generation-aggregated data points."""
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(bind=engine)

    with Session(engine) as db:
        user, campaign, candidate = _setup_db_with_campaign(db)

        # Add an evaluation for the candidate
        evaluation = EvolutionCandidateEvaluation(
            candidate_id=candidate.id,
            evaluation_type='benchmark',
            benchmark_run_id=None,
            metrics={'schema_validity_score': 0.9},
            aggregate_score=0.85,
        )
        db.add(evaluation)
        db.commit()

        service = EvolutionService()
        points = service.fitness_series(db, campaign.id)
        assert len(points) >= 1
        point = points[0]
        assert point['generation'] == 1
        assert point['best'] == pytest.approx(0.85)


def test_evolution_fitness_series_not_found_raises_404() -> None:
    """Fitness series for non-existent campaign raises 404."""
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(bind=engine)

    with Session(engine) as db:
        User(email='x@x.dev', hashed_password='x', role='admin', is_active=True)
        service = EvolutionService()
        with pytest.raises(HTTPException) as exc_info:
            service.fitness_series(db, 9999)
        assert exc_info.value.status_code == 404


def test_evolution_list_campaigns_filters_by_status() -> None:
    """List campaigns can filter by status."""
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(bind=engine)

    with Session(engine) as db:
        user, campaign, _ = _setup_db_with_campaign(db)
        service = EvolutionService()
        items, total = service.list_campaigns(db, status='running')
        assert total >= 1
        assert all(item.status == 'running' for item in items)

        items_empty, total_empty = service.list_campaigns(db, status='failed')
        assert total_empty == 0
