from datetime import datetime

from pydantic import BaseModel, Field


class PromptTemplateCreate(BaseModel):
    agent_name: str = Field(min_length=3, max_length=100)
    system_prompt: str = Field(min_length=5)
    user_prompt_template: str = Field(min_length=5)
    notes: str | None = None


class PromptTemplateOut(BaseModel):
    id: int
    agent_name: str
    version: int
    is_active: bool
    system_prompt: str
    user_prompt_template: str
    notes: str | None
    created_by_id: int | None
    created_at: datetime
    updated_at: datetime

    model_config = {'from_attributes': True}
