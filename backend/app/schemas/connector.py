from pydantic import BaseModel, Field


class ConnectorConfigUpdate(BaseModel):
    enabled: bool = True
    settings: dict = Field(default_factory=dict)


class ConnectorConfigOut(BaseModel):
    id: int
    connector_name: str
    enabled: bool
    settings: dict

    model_config = {'from_attributes': True}
