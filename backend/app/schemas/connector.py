from pydantic import BaseModel, Field


class ConnectorConfigUpdate(BaseModel):
    enabled: bool = True
    settings: dict = Field(default_factory=dict)


class TradingConfigScopedUpdate(BaseModel):
    gating: dict = Field(default_factory=dict)
    risk_limits: dict = Field(default_factory=dict)
    sizing: dict = Field(default_factory=dict)


class MarketSymbolGroup(BaseModel):
    name: str
    symbols: list[str] = Field(default_factory=list)


class MarketSymbolsUpdate(BaseModel):
    forex_pairs: list[str] = Field(default_factory=list)
    crypto_pairs: list[str] = Field(default_factory=list)
    symbol_groups: list[MarketSymbolGroup] = Field(default_factory=list)


class MarketSymbolsOut(BaseModel):
    forex_pairs: list[str]
    crypto_pairs: list[str]
    symbol_groups: list[MarketSymbolGroup]
    tradeable_pairs: list[str]
    source: str


class ConnectorConfigOut(BaseModel):
    id: int
    connector_name: str
    enabled: bool
    settings: dict

    model_config = {'from_attributes': True}


class ExternalMcpDiscoverRequest(BaseModel):
    url: str
    headers: dict[str, str] = {}


class ExternalMcpSaveRequest(BaseModel):
    id: str | None = None          # None = new server
    name: str
    url: str
    headers: dict[str, str] = {}
    assigned_agents: list[str] = []
    discovered_tools: list[dict] = []


class ExternalMcpDeleteRequest(BaseModel):
    id: str
    agent_name: str
