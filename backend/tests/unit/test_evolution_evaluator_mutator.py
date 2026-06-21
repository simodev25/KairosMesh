from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models.agent_skill import AgentSkill
from app.db.models.evolution_campaign import EvolutionCampaign
from app.db.models.evolution_candidate import EvolutionCandidate
from app.db.models.prompt_template import PromptTemplate
from app.db.models.user import User
from app.services.evolution.mutator import PromptMutator


def _seed_campaign_and_candidate(db: Session) -> tuple[EvolutionCampaign, EvolutionCandidate]:
    user = User(email='evaluator-admin@local.dev', hashed_password='x', role='admin', is_active=True)
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
        name='Mutator Campaign',
        agent_name='technical-analyst',
        provider='openai',
        model_name='gpt-4.1-mini',
        model_parameters={'temperature': 0.7},
        baseline_prompt_template_id=prompt.id,
        baseline_skill_id=skill.id,
        status='running',
        max_iterations=3,
        max_candidates=3,
        max_llm_calls=20,
        budget_usd_limit=10.0,
        evaluation_config={'benchmark_profile': 'standard'},
        created_by_id=user.id,
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)

    parent = EvolutionCandidate(
        campaign_id=campaign.id,
        generation=0,
        parent_candidate_id=None,
        system_prompt='parent system',
        user_prompt_template='parent user {pair}',
        skills=['Skill Parent'],
        is_baseline=True,
        status='evaluated',
    )
    db.add(parent)
    db.commit()
    db.refresh(parent)
    return campaign, parent


def test_prompt_mutator_generates_valid_candidate(monkeypatch) -> None:
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(bind=engine)

    with Session(engine) as db:
        campaign, parent = _seed_campaign_and_candidate(db)
        mutator = PromptMutator()

        def _fake_chat_json(*_args, **_kwargs):
            return {
                'json': {
                    'system_prompt': 'mutated system prompt',
                    'user_prompt_template': 'mutated user template {pair}',
                    'skills': ['Skill 1', 'Skill 2'],
                }
            }

        monkeypatch.setattr(mutator.llm_client, 'chat_json', _fake_chat_json)

        candidate = mutator.mutate(db, campaign=campaign, parent=parent, generation=1)
        assert candidate.id is not None
        assert candidate.status == 'generated'
        assert candidate.system_prompt == 'mutated system prompt'
        assert candidate.skills == ['Skill 1', 'Skill 2']
