import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import Role, require_roles
from app.db.models.connector_config import ConnectorConfig
from app.db.models.agent_skill import AgentSkill
from app.db.session import get_db
from app.schemas.connector import (
    ConnectorConfigOut,
    ConnectorConfigUpdate,
    ExternalMcpDiscoverRequest,
    ExternalMcpSaveRequest,
    MarketSymbolsOut,
    MarketSymbolsUpdate,
    TradingConfigScopedUpdate,
)
from app.services.connectors.runtime_settings import RuntimeConnectorSettings
from app.services.config.trading_config import build_scoped_trading_settings
from app.services.llm.model_selector import (
    AgentModelSelector,
    DEFAULT_DECISION_MODE,
    SUPPORTED_DECISION_MODES,
    build_agent_tools_catalog,
    normalize_agent_tools_settings,
    normalize_agent_name,
    normalize_decision_mode,
    normalize_external_mcps,
    validate_agent_tools_payload,
)
from app.services.mcp.external_client import ExternalMCPClient, ExternalMCPUnavailableError
from app.services.llm.provider_client import LlmClient
from app.services.market.symbols import get_market_symbols_config, save_market_symbols_config
from app.services.market.news_provider import MarketProvider
from app.services.trading.metaapi_client import MetaApiClient

router = APIRouter(prefix='/connectors', tags=['connectors'])

SUPPORTED_CONNECTORS = ['ollama', 'metaapi', 'news', 'trading']
CONNECTOR_SECRET_DEFAULT_FIELDS: dict[str, dict[str, str]] = {
    'ollama': {
        'OLLAMA_API_KEY': 'ollama_api_key',
        'OPENAI_API_KEY': 'openai_api_key',
        'MISTRAL_API_KEY': 'mistral_api_key',
    },
    'metaapi': {
        'METAAPI_TOKEN': 'metaapi_token',
        'METAAPI_ACCOUNT_ID': 'metaapi_account_id',
    },
    'news': {
        'NEWSAPI_API_KEY': 'newsapi_api_key',
        'TRADINGECONOMICS_API_KEY': 'tradingeconomics_api_key',
        'FINNHUB_API_KEY': 'finnhub_api_key',
        'ALPHAVANTAGE_API_KEY': 'alphavantage_api_key',
    },
}


def _inject_env_secret_defaults(connector_name: str, settings_payload: dict, app_settings) -> tuple[dict, bool]:
    payload = dict(settings_payload or {})
    changed = False
    field_map = CONNECTOR_SECRET_DEFAULT_FIELDS.get(connector_name, {})
    for key, attr_name in field_map.items():
        if key in payload:
            continue
        value = str(getattr(app_settings, attr_name, '') or '').strip()
        if not value:
            continue
        payload[key] = value
        changed = True
    return payload, changed


def _active_agent_skills_map(db: Session) -> dict[str, list[str]]:
    rows = (
        db.query(AgentSkill.agent_name, AgentSkill.skills)
        .filter(AgentSkill.is_active.is_(True))
        .order_by(AgentSkill.agent_name.asc(), AgentSkill.version.desc())
        .all()
    )

    skills_by_agent: dict[str, list[str]] = {}
    for agent_name, skills in rows:
        if agent_name in skills_by_agent:
            continue
        if not isinstance(skills, list):
            continue
        normalized = [str(item).strip() for item in skills if str(item or '').strip()]
        if normalized:
            skills_by_agent[str(agent_name)] = normalized
    return skills_by_agent


def _sanitize_ollama_settings(raw_settings: dict) -> dict:
    settings = dict(raw_settings or {})
    raw_enabled = settings.get('agent_llm_enabled')
    enabled = {normalize_agent_name(str(key)): value for key, value in dict(raw_enabled or {}).items()} if isinstance(raw_enabled, dict) else {}
    if 'market-context-analyst' not in enabled:
        for legacy_name in ('macro-analyst', 'sentiment-agent'):
            if legacy_name in dict(raw_enabled or {}):
                enabled['market-context-analyst'] = dict(raw_enabled or {}).get(legacy_name)
                break
    settings['agent_llm_enabled'] = enabled

    raw_models = settings.get('agent_models')
    agent_models = {normalize_agent_name(str(key)): value for key, value in dict(raw_models or {}).items()} if isinstance(raw_models, dict) else {}
    if 'market-context-analyst' not in agent_models:
        for legacy_name in ('macro-analyst', 'sentiment-agent'):
            if legacy_name in dict(raw_models or {}):
                agent_models['market-context-analyst'] = dict(raw_models or {}).get(legacy_name)
                break
    settings['agent_models'] = agent_models

    if not isinstance(settings.get('agent_skills'), dict):
        settings['agent_skills'] = {}
    settings['decision_mode'] = normalize_decision_mode(
        settings.get('decision_mode'),
        fallback=DEFAULT_DECISION_MODE,
    )
    normalized_agent_tools = normalize_agent_tools_settings(settings.get('agent_tools'))
    settings['agent_tools'] = normalized_agent_tools
    settings['agent_tools_catalog'] = build_agent_tools_catalog(normalized_agent_tools)

    # Preserve and normalize external MCP server configs
    settings['external_mcps'] = normalize_external_mcps(settings.get('external_mcps'))
    return settings


def _sanitize_ollama_settings_with_defaults(raw_settings: dict, app_settings) -> dict:
    base_settings = {
        **dict(raw_settings or {}),
        'provider': dict(raw_settings or {}).get('provider', app_settings.llm_provider),
        'decision_mode': dict(raw_settings or {}).get('decision_mode', app_settings.decision_mode),
    }
    return _sanitize_ollama_settings(base_settings)


def _validate_decision_mode_value(raw_settings: dict) -> None:
    if not isinstance(raw_settings, dict):
        return
    if 'decision_mode' not in raw_settings:
        return
    value = str(raw_settings.get('decision_mode', '') or '').strip().lower()
    if value not in SUPPORTED_DECISION_MODES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid decision_mode '{raw_settings.get('decision_mode')}'. Allowed: {', '.join(sorted(SUPPORTED_DECISION_MODES))}.",
        )


def _validate_agent_tools_value(raw_settings: dict) -> None:
    if not isinstance(raw_settings, dict):
        return
    if 'agent_tools' not in raw_settings:
        return
    issues = validate_agent_tools_payload(raw_settings.get('agent_tools'))
    if not issues:
        return
    raise HTTPException(
        status_code=422,
        detail='; '.join(issues),
    )


@router.get('', response_model=list[ConnectorConfigOut])
def list_connectors(
    db: Session = Depends(get_db),
    _=Depends(require_roles(Role.SUPER_ADMIN, Role.ADMIN)),
) -> list[ConnectorConfigOut]:
    settings = get_settings()
    updated_connector_names: set[str] = set()
    # Migrate legacy 'yfinance' connector row to 'news'.
    legacy_row = db.query(ConnectorConfig).filter(ConnectorConfig.connector_name == 'yfinance').first()
    if legacy_row is not None:
        news_row = db.query(ConnectorConfig).filter(ConnectorConfig.connector_name == 'news').first()
        if news_row is None:
            legacy_row.connector_name = 'news'
            updated_connector_names.add('news')
        else:
            db.delete(legacy_row)
        db.flush()
    connectors = db.query(ConnectorConfig).filter(ConnectorConfig.connector_name.in_(SUPPORTED_CONNECTORS)).all()
    existing = {conn.connector_name for conn in connectors}
    for connector_name in SUPPORTED_CONNECTORS:
        if connector_name not in existing:
            connector_settings: dict = {}
            if connector_name == 'ollama':
                connector_settings = _sanitize_ollama_settings_with_defaults({}, settings)
            connector_settings, _ = _inject_env_secret_defaults(connector_name, connector_settings, settings)
            conn = ConnectorConfig(connector_name=connector_name, enabled=True, settings=connector_settings)
            db.add(conn)
            updated_connector_names.add(connector_name)
    for conn in connectors:
        current_settings = conn.settings if isinstance(conn.settings, dict) else {}
        next_settings = dict(current_settings)
        has_changes = False

        if conn.connector_name == 'ollama':
            sanitized_settings = _sanitize_ollama_settings_with_defaults(current_settings, settings)
            if sanitized_settings != next_settings:
                next_settings = sanitized_settings
                has_changes = True

        with_env_defaults, injected = _inject_env_secret_defaults(conn.connector_name, next_settings, settings)
        if injected:
            next_settings = with_env_defaults
            has_changes = True

        if has_changes:
            conn.settings = next_settings
            updated_connector_names.add(conn.connector_name)
    db.commit()
    for connector_name in updated_connector_names:
        RuntimeConnectorSettings.clear_cache(connector_name)
    if 'ollama' in updated_connector_names:
        AgentModelSelector.clear_cache()
    connectors = db.query(ConnectorConfig).filter(ConnectorConfig.connector_name.in_(SUPPORTED_CONNECTORS)).all()

    active_skills_map = _active_agent_skills_map(db)
    if active_skills_map:
        for conn in connectors:
            if conn.connector_name != 'ollama':
                continue
            current_settings = conn.settings if isinstance(conn.settings, dict) else {}
            merged_settings = dict(current_settings)
            merged_settings['agent_skills'] = active_skills_map
            if merged_settings != current_settings:
                conn.settings = merged_settings
                db.commit()
                connectors = db.query(ConnectorConfig).filter(ConnectorConfig.connector_name.in_(SUPPORTED_CONNECTORS)).all()
            break

    return [ConnectorConfigOut.model_validate(conn) for conn in connectors]


@router.get('/market-symbols', response_model=MarketSymbolsOut)
def get_market_symbols(
    db: Session = Depends(get_db),
    _=Depends(require_roles(Role.SUPER_ADMIN, Role.ADMIN, Role.TRADER_OPERATOR, Role.ANALYST, Role.VIEWER)),
) -> MarketSymbolsOut:
    settings = get_settings()
    payload = get_market_symbols_config(db, settings)
    return MarketSymbolsOut.model_validate(payload)


@router.put('/market-symbols', response_model=MarketSymbolsOut)
def update_market_symbols(
    payload: MarketSymbolsUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_roles(Role.SUPER_ADMIN, Role.ADMIN)),
) -> MarketSymbolsOut:
    symbol_groups_payload = [group.model_dump() for group in payload.symbol_groups]
    save_market_symbols_config(
        db,
        symbol_groups=symbol_groups_payload,
        forex_pairs=payload.forex_pairs,
        crypto_pairs=payload.crypto_pairs,
    )
    settings = get_settings()
    resolved = get_market_symbols_config(db, settings)
    return MarketSymbolsOut.model_validate(resolved)


@router.get('/ollama/models')
def list_ollama_models(
    provider: str | None = Query(default=None),
    db: Session = Depends(get_db),
    _=Depends(require_roles(Role.SUPER_ADMIN, Role.ADMIN)),
) -> dict:
    return LlmClient().list_models(db, provider=provider)


@router.put('/trading-config')
def update_trading_config(
    payload: TradingConfigScopedUpdate,
    decision_mode: str = Query(default='balanced'),
    execution_mode: str = Query(default='simulation'),
    db: Session = Depends(get_db),
    _=Depends(require_roles(Role.SUPER_ADMIN, Role.ADMIN)),
) -> dict:
    """Persist trading parameter overrides for one execution/decision profile."""
    conn = db.query(ConnectorConfig).filter(ConnectorConfig.connector_name == 'trading').first()
    if not conn:
        conn = ConnectorConfig(connector_name='trading', enabled=True, settings={})
        db.add(conn)
        db.flush()

    current_settings = conn.settings if isinstance(conn.settings, dict) else {}
    next_settings = build_scoped_trading_settings(
        current_settings,
        decision_mode=decision_mode,
        execution_mode=execution_mode,
        gating=payload.gating,
        risk_limits=payload.risk_limits,
        sizing=payload.sizing,
    )
    conn.settings = next_settings
    # Force SQLAlchemy to detect JSON column mutation
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(conn, 'settings')

    try:
        from app.db.models.trading_config_version import TradingConfigVersion
        from sqlalchemy import func

        max_ver = db.query(func.max(TradingConfigVersion.version)).scalar() or 0
        version = TradingConfigVersion(
            version=max_ver + 1,
            changed_by='admin',
            decision_mode=str(decision_mode),
            settings_snapshot=next_settings,
            changes_summary=(
                f"scoped save for decision_mode={decision_mode}, execution_mode={execution_mode}"
            ),
        )
        db.add(version)
    except Exception:
        pass

    db.commit()
    RuntimeConnectorSettings.clear_cache('trading')

    from app.services.config.trading_config import get_current_values, get_param_catalog
    return {
        'catalog': get_param_catalog(),
        'values': get_current_values(decision_mode, execution_mode),
        'decision_mode': decision_mode,
        'execution_mode': execution_mode,
    }


@router.post('/external-mcp/discover')
async def discover_external_mcp(
    payload: ExternalMcpDiscoverRequest,
    _=Depends(require_roles(Role.SUPER_ADMIN, Role.ADMIN)),
) -> dict:
    """Query an external MCP server and return its tool list."""
    client = ExternalMCPClient()
    try:
        tools = await client.discover_tools(payload.url, payload.headers)
    except ExternalMCPUnavailableError as exc:
        raise HTTPException(status_code=502, detail=f"MCP server unavailable: {exc}")
    return {"status": "ok", "tools": tools, "count": len(tools)}


@router.put('/external-mcp')
def save_external_mcp(
    payload: ExternalMcpSaveRequest,
    db: Session = Depends(get_db),
    _=Depends(require_roles(Role.SUPER_ADMIN, Role.ADMIN)),
) -> dict:
    """Save or update an external MCP server config for the ollama connector."""
    conn = db.query(ConnectorConfig).filter(ConnectorConfig.connector_name == 'ollama').first()
    if not conn:
        conn = ConnectorConfig(connector_name='ollama', enabled=True, settings={})
        db.add(conn)

    settings = dict(conn.settings or {})
    external_mcps: list[dict] = list(settings.get('external_mcps') or [])
    agent_tools: dict = dict(settings.get('agent_tools') or {})

    # Build the MCP entry
    mcp_id = payload.id or str(uuid.uuid4())
    idx = next((i for i, m in enumerate(external_mcps) if m.get('id') == mcp_id), None)
    old_entry = external_mcps[idx] if idx is not None else {}
    entry = {
        'id': mcp_id,
        'name': payload.name,
        'url': payload.url,
        'headers': payload.headers,
        'assigned_agents': payload.assigned_agents,
        'discovered_tools': payload.discovered_tools,
        'discovery_status': 'ok' if payload.discovered_tools else 'pending',
        'last_discovery_at': old_entry.get('last_discovery_at'),
    }

    # Replace or insert
    if idx is not None:
        external_mcps[idx] = entry
    else:
        external_mcps.append(entry)

    # Merge ext__ tool IDs into agent_tools (disabled by default)
    for agent_name in payload.assigned_agents:
        if agent_name not in agent_tools:
            agent_tools[agent_name] = {}
        for tool in payload.discovered_tools:
            tool_id = str(tool.get('tool_id') or '')
            if tool_id and tool_id not in agent_tools[agent_name]:
                agent_tools[agent_name][tool_id] = False  # off by default

    settings['external_mcps'] = external_mcps
    settings['agent_tools'] = agent_tools
    conn.settings = _sanitize_ollama_settings(settings)
    db.commit()
    db.refresh(conn)
    AgentModelSelector.clear_cache()
    return {'status': 'ok', 'id': mcp_id}


@router.delete('/external-mcp/{mcp_id}')
def delete_external_mcp(
    mcp_id: str,
    agent_name: str = Query(...),
    db: Session = Depends(get_db),
    _=Depends(require_roles(Role.SUPER_ADMIN, Role.ADMIN)),
) -> dict:
    """Remove an external MCP server from an agent (or entirely if no agents remain)."""
    conn = db.query(ConnectorConfig).filter(ConnectorConfig.connector_name == 'ollama').first()
    if not conn:
        raise HTTPException(status_code=404, detail='Ollama connector not found')

    settings = dict(conn.settings or {})
    external_mcps: list[dict] = list(settings.get('external_mcps') or [])
    agent_tools: dict = dict(settings.get('agent_tools') or {})

    entry = next((m for m in external_mcps if m.get('id') == mcp_id), None)
    if not entry:
        raise HTTPException(status_code=404, detail=f'External MCP {mcp_id} not found')

    # Remove agent from assigned_agents
    entry['assigned_agents'] = [a for a in entry.get('assigned_agents', []) if a != agent_name]

    # Remove ext__ tool IDs from this agent's tool state
    if agent_name in agent_tools and isinstance(agent_tools[agent_name], dict):
        tool_ids_to_remove = {
            t.get('tool_id') for t in entry.get('discovered_tools', [])
            if t.get('tool_id')
        }
        agent_tools[agent_name] = {
            k: v for k, v in agent_tools[agent_name].items()
            if k not in tool_ids_to_remove
        }

    # If no agents left, remove the MCP entry entirely
    if not entry['assigned_agents']:
        external_mcps = [m for m in external_mcps if m.get('id') != mcp_id]

    settings['external_mcps'] = external_mcps
    settings['agent_tools'] = agent_tools
    conn.settings = _sanitize_ollama_settings(settings)
    db.commit()
    AgentModelSelector.clear_cache()
    return {'status': 'ok'}


@router.put('/{connector_name}', response_model=ConnectorConfigOut)
def update_connector(
    connector_name: str,
    payload: ConnectorConfigUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_roles(Role.SUPER_ADMIN, Role.ADMIN)),
) -> ConnectorConfigOut:
    connector_name = connector_name.lower()
    if connector_name not in SUPPORTED_CONNECTORS:
        raise HTTPException(status_code=404, detail='Unsupported connector')

    conn = db.query(ConnectorConfig).filter(ConnectorConfig.connector_name == connector_name).first()
    if not conn:
        conn = ConnectorConfig(connector_name=connector_name)
        db.add(conn)

    conn.enabled = payload.enabled
    if connector_name == 'ollama':
        _validate_decision_mode_value(payload.settings)
        _validate_agent_tools_value(payload.settings)
        conn.settings = _sanitize_ollama_settings(payload.settings)
    else:
        conn.settings = payload.settings

    # Save version snapshot for trading config changes
    if connector_name == 'trading':
        try:
            from app.db.models.trading_config_version import TradingConfigVersion
            from sqlalchemy import func

            max_ver = db.query(func.max(TradingConfigVersion.version)).scalar() or 0
            new_settings = payload.settings if isinstance(payload.settings, dict) else {}

            # Build changes summary
            old_settings = (conn.settings if isinstance(conn.settings, dict) else {}) if conn.id else {}
            changes: list[str] = []
            for section in ('gating', 'risk_limits', 'sizing'):
                old_sec = old_settings.get(section, {}) if isinstance(old_settings.get(section), dict) else {}
                new_sec = new_settings.get(section, {}) if isinstance(new_settings.get(section), dict) else {}
                for key in set(list(old_sec.keys()) + list(new_sec.keys())):
                    old_val = old_sec.get(key)
                    new_val = new_sec.get(key)
                    if old_val != new_val:
                        changes.append(f"{section}.{key}: {old_val} -> {new_val}")

            # decision_mode lives in the ollama connector, not trading
            _ollama_conn = db.query(ConnectorConfig).filter(
                ConnectorConfig.connector_name == "ollama"
            ).first()
            _effective_mode = "balanced"
            if _ollama_conn and isinstance(_ollama_conn.settings, dict):
                _effective_mode = _ollama_conn.settings.get("decision_mode", "balanced")

            version = TradingConfigVersion(
                version=max_ver + 1,
                changed_by="admin",
                decision_mode=str(_effective_mode),
                settings_snapshot=new_settings,
                changes_summary="; ".join(changes) if changes else "initial save",
            )
            db.add(version)
        except Exception:
            pass  # Non-blocking — don't fail the save

    db.commit()
    db.refresh(conn)
    RuntimeConnectorSettings.clear_cache(connector_name)
    if connector_name == 'news':
        try:
            MarketProvider().clear_news_cache()
        except Exception:
            pass
    if connector_name == 'ollama':
        AgentModelSelector.clear_cache()
    return ConnectorConfigOut.model_validate(conn)


@router.get('/trading-config')
def get_trading_config(
    decision_mode: str = Query(default='balanced'),
    execution_mode: str = Query(default='simulation'),
    _=Depends(require_roles(Role.SUPER_ADMIN, Role.ADMIN)),
) -> dict:
    """Return the trading parameter catalog with descriptions and current effective values."""
    from app.services.config.trading_config import get_current_values, get_param_catalog
    return {
        "catalog": get_param_catalog(),
        "values": get_current_values(decision_mode, execution_mode),
        "decision_mode": decision_mode,
        "execution_mode": execution_mode,
    }


@router.get('/trading-config/versions')
def get_trading_config_versions(
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _=Depends(require_roles(Role.SUPER_ADMIN, Role.ADMIN)),
) -> dict:
    """Return version history of trading config changes."""
    from app.db.models.trading_config_version import TradingConfigVersion

    rows = (
        db.query(TradingConfigVersion)
        .order_by(TradingConfigVersion.version.desc())
        .limit(limit)
        .all()
    )

    return {
        "count": len(rows),
        "versions": [
            {
                "version": row.version,
                "changed_by": row.changed_by,
                "changed_at": row.changed_at.isoformat() if row.changed_at else None,
                "decision_mode": row.decision_mode,
                "changes_summary": row.changes_summary,
                "settings_snapshot": row.settings_snapshot,
            }
            for row in rows
        ],
    }


@router.post('/trading-config/versions/{version_id}/restore')
def restore_trading_config_version(
    version_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_roles(Role.SUPER_ADMIN, Role.ADMIN)),
) -> dict:
    """Restore a previous trading config version as the active config."""
    from app.db.models.trading_config_version import TradingConfigVersion

    target = db.query(TradingConfigVersion).filter(TradingConfigVersion.version == version_id).first()
    if not target:
        raise HTTPException(status_code=404, detail=f"Version {version_id} not found")

    snapshot = target.settings_snapshot if isinstance(target.settings_snapshot, dict) else {}

    # Apply to the trading connector
    conn = db.query(ConnectorConfig).filter(ConnectorConfig.connector_name == 'trading').first()
    if not conn:
        conn = ConnectorConfig(connector_name='trading', enabled=True, settings={})
        db.add(conn)

    old_settings = conn.settings if isinstance(conn.settings, dict) else {}
    conn.settings = snapshot

    # Create a new version entry for the restore
    from sqlalchemy import func
    max_ver = db.query(func.max(TradingConfigVersion.version)).scalar() or 0
    restore_version = TradingConfigVersion(
        version=max_ver + 1,
        changed_by="admin",
        decision_mode=target.decision_mode,
        settings_snapshot=snapshot,
        changes_summary=f"restored from v{version_id}",
    )
    db.add(restore_version)
    db.commit()

    RuntimeConnectorSettings.clear_cache('trading')

    return {
        "restored_from": version_id,
        "new_version": max_ver + 1,
        "settings": snapshot,
    }


@router.post('/{connector_name}/test')
async def test_connector(
    connector_name: str,
    db: Session = Depends(get_db),
    _=Depends(require_roles(Role.SUPER_ADMIN, Role.ADMIN)),
) -> dict:
    connector_name = connector_name.lower()
    if connector_name == 'ollama':
        client = LlmClient()
        return client.chat('You are a health-check bot.', 'Reply with OK in one word.', db=db)
    if connector_name == 'metaapi':
        client = MetaApiClient()
        return await client.get_account_information()
    if connector_name == 'news':
        provider = MarketProvider()
        settings = get_settings()
        symbols_config = get_market_symbols_config(db, settings)
        sample_symbol = next(iter(symbols_config.get('tradeable_pairs', [])), 'SPY')
        return {
            'sample_symbol': sample_symbol,
            'market': provider.get_market_snapshot(sample_symbol, 'H1'),
            'news': provider.get_news_context(sample_symbol),
        }
    raise HTTPException(status_code=404, detail='Unsupported connector')


@router.post('/news/news-providers/{provider_name}/test')
async def test_yfinance_news_provider(
    provider_name: str,
    pair: str | None = None,
    db: Session = Depends(get_db),
    _=Depends(require_roles(Role.SUPER_ADMIN, Role.ADMIN)),
) -> dict:
    provider = MarketProvider()
    settings = get_settings()
    symbols_config = get_market_symbols_config(db, settings)
    sample_symbol = str(pair or next(iter(symbols_config.get('tradeable_pairs', [])), 'SPY')).strip() or 'SPY'
    result = provider.test_news_provider(provider_name, pair=sample_symbol, max_items=5)
    return {
        'sample_symbol': sample_symbol,
        **result,
    }
