from __future__ import annotations

import json
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.db.models.evolution_campaign import EvolutionCampaign
from app.db.models.evolution_candidate import EvolutionCandidate
from app.services.llm.provider_client import LlmClient


class PromptMutator:
    def __init__(self) -> None:
        self.llm_client = LlmClient()

    @staticmethod
    def _validate_candidate_payload(payload: dict[str, Any]) -> None:
        system_prompt = str(payload.get('system_prompt') or '').strip()
        user_prompt_template = str(payload.get('user_prompt_template') or '').strip()
        skills = payload.get('skills')
        if not system_prompt:
            raise ValueError('system_prompt is required')
        if not user_prompt_template:
            raise ValueError('user_prompt_template is required')
        if not isinstance(skills, list) or not all(str(item or '').strip() for item in skills):
            raise ValueError('skills must be a non-empty list of strings')

    def mutate(
        self,
        db: Session,
        *,
        campaign: EvolutionCampaign,
        parent: EvolutionCandidate,
        generation: int,
    ) -> EvolutionCandidate:
        if int(campaign.llm_calls_used or 0) >= int(campaign.max_llm_calls):
            raise HTTPException(status_code=409, detail='max_llm_calls reached for campaign')

        prompt = (
            'You are a mutation engine for trading agent prompts and skills. '
            'Return strictly JSON with keys system_prompt, user_prompt_template, skills. '
            f'Agent: {campaign.agent_name}.\n\n'
            f'Current system prompt:\n{parent.system_prompt}\n\n'
            f'Current user prompt template:\n{parent.user_prompt_template}\n\n'
            f'Current skills:\n{json.dumps(parent.skills, ensure_ascii=False)}\n\n'
            'Mutate conservatively: keep behavior domain-compatible, improve clarity, no live trading references.'
        )

        response = self.llm_client.chat_json(
            'You output only valid JSON.',
            prompt,
            model=campaign.model_name,
            db=db,
            temperature=float((campaign.model_parameters or {}).get('temperature', 0.7)),
            max_tokens=int((campaign.model_parameters or {}).get('max_tokens', 900)),
        )

        raw_payload = response.get('json') if isinstance(response, dict) else None
        if not isinstance(raw_payload, dict):
            raise HTTPException(status_code=422, detail='Mutator returned invalid JSON payload')

        try:
            self._validate_candidate_payload(raw_payload)
        except ValueError as exc:
            candidate = EvolutionCandidate(
                campaign_id=campaign.id,
                generation=generation,
                parent_candidate_id=parent.id,
                system_prompt=parent.system_prompt,
                user_prompt_template=parent.user_prompt_template,
                skills=list(parent.skills or []),
                status='rejected',
            )
            db.add(candidate)
            db.commit()
            db.refresh(candidate)
            raise HTTPException(status_code=422, detail=f'Invalid candidate payload: {exc}')

        candidate = EvolutionCandidate(
            campaign_id=campaign.id,
            generation=generation,
            parent_candidate_id=parent.id,
            system_prompt=str(raw_payload.get('system_prompt')).strip(),
            user_prompt_template=str(raw_payload.get('user_prompt_template')).strip(),
            skills=[str(item).strip() for item in list(raw_payload.get('skills') or [])],
            status='generated',
            is_baseline=False,
            llm_calls_count=1,
        )
        campaign.llm_calls_used = int(campaign.llm_calls_used or 0) + 1
        db.add(candidate)
        db.commit()
        db.refresh(candidate)
        return candidate
