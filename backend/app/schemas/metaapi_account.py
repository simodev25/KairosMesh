from datetime import datetime

from pydantic import BaseModel, Field


class MetaApiAccountCreate(BaseModel):
    label: str = Field(min_length=2, max_length=120)
    account_id: str = Field(min_length=3, max_length=120)
    region: str = Field(default='new-york', min_length=2, max_length=50)
    enabled: bool = True
    is_default: bool = False


class MetaApiAccountUpdate(BaseModel):
    label: str | None = Field(default=None, min_length=2, max_length=120)
    region: str | None = Field(default=None, min_length=2, max_length=50)
    enabled: bool | None = None
    is_default: bool | None = None


class MetaApiAccountOut(BaseModel):
    id: int
    label: str
    account_id: str
    region: str
    enabled: bool
    is_default: bool
    created_at: datetime
    updated_at: datetime

    model_config = {'from_attributes': True}
