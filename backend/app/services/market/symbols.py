import json
import re
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models.connector_config import ConnectorConfig

MARKET_SYMBOL_CONNECTOR = 'yfinance'
FOREX_SYMBOLS_KEY = 'forex_pairs'
CRYPTO_SYMBOLS_KEY = 'crypto_pairs'
SYMBOL_GROUPS_KEY = 'symbol_groups'


def _dedupe(items: list[str], *, case_insensitive: bool = False) -> list[str]:
    if not case_insensitive:
        return list(dict.fromkeys(items))

    deduped: list[str] = []
    seen: set[str] = set()
    for item in items:
        key = item.casefold()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def canonical_symbol(value: Any) -> str:
    return str(value or '').strip().upper()


def _normalize_group_name(value: Any) -> str:
    text = str(value or '').strip().lower().replace(' ', '_')
    text = re.sub(r'[^a-z0-9_-]+', '', text)
    return text


def normalize_symbol_list(value: Any) -> list[str]:
    raw_items: list[Any]
    if isinstance(value, list):
        raw_items = value
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        if text.startswith('['):
            try:
                parsed = json.loads(text)
                if isinstance(parsed, list):
                    raw_items = parsed
                else:
                    raw_items = []
            except json.JSONDecodeError:
                raw_items = text.split(',')
        else:
            raw_items = text.split(',')
    else:
        return []

    cleaned: list[str] = []
    for item in raw_items:
        symbol = str(item).strip()
        if symbol:
            cleaned.append(symbol)
    return _dedupe(cleaned, case_insensitive=True)


def _merge_symbol_groups(items: list[tuple[str, list[str]]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[str]] = {}
    order: list[str] = []
    for raw_name, symbols in items:
        name = _normalize_group_name(raw_name)
        if not name:
            continue
        if name not in grouped:
            grouped[name] = []
            order.append(name)
        grouped[name].extend(symbols)

    merged: list[dict[str, Any]] = []
    for name in order:
        deduped = _dedupe([symbol for symbol in grouped[name] if symbol], case_insensitive=True)
        if deduped:
            merged.append({'name': name, 'symbols': deduped})
    return merged


def normalize_symbol_groups(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        if text.startswith('{') or text.startswith('['):
            try:
                parsed = json.loads(text)
                return normalize_symbol_groups(parsed)
            except json.JSONDecodeError:
                return []
        return []

    normalized_items: list[tuple[str, list[str]]] = []

    if isinstance(value, dict):
        for name, symbols in value.items():
            normalized_items.append((str(name), normalize_symbol_list(symbols)))
        return _merge_symbol_groups(normalized_items)

    if isinstance(value, list):
        for item in value:
            if not isinstance(item, dict):
                continue
            name = item.get('name') or item.get('group') or item.get('id') or ''
            symbols = normalize_symbol_list(item.get('symbols') or item.get('pairs') or [])
            normalized_items.append((str(name), symbols))
        return _merge_symbol_groups(normalized_items)

    return []


def _group_symbols(groups: list[dict[str, Any]], group_name: str) -> list[str]:
    normalized_name = _normalize_group_name(group_name)
    for group in groups:
        if _normalize_group_name(group.get('name')) == normalized_name:
            return normalize_symbol_list(group.get('symbols'))
    return []


def _default_symbol_groups(settings: Settings) -> list[dict[str, Any]]:
    forex_pairs = normalize_symbol_list(settings.default_forex_pairs)
    crypto_pairs = normalize_symbol_list(settings.default_crypto_pairs)
    groups: list[dict[str, Any]] = []
    if forex_pairs:
        groups.append({'name': 'forex', 'symbols': forex_pairs})
    if crypto_pairs:
        groups.append({'name': 'crypto', 'symbols': crypto_pairs})
    return groups


def get_market_symbols_config(db: Session, settings: Settings) -> dict[str, Any]:
    symbol_groups = _default_symbol_groups(settings)
    source = 'env'

    connector = db.query(ConnectorConfig).filter(ConnectorConfig.connector_name == MARKET_SYMBOL_CONNECTOR).first()
    connector_settings = connector.settings if connector and isinstance(connector.settings, dict) else {}

    configured_groups = normalize_symbol_groups(connector_settings.get(SYMBOL_GROUPS_KEY))
    if configured_groups:
        symbol_groups = configured_groups
        source = 'config'
    else:
        # Backward compatibility: accept legacy forex_pairs / crypto_pairs keys.
        configured_forex = normalize_symbol_list(connector_settings.get(FOREX_SYMBOLS_KEY))
        configured_crypto = normalize_symbol_list(connector_settings.get(CRYPTO_SYMBOLS_KEY))
        if configured_forex:
            source = 'config'
            symbol_groups = [
                *[group for group in symbol_groups if _normalize_group_name(group.get('name')) != 'forex'],
                {'name': 'forex', 'symbols': configured_forex},
            ]
        if configured_crypto:
            source = 'config'
            symbol_groups = [
                *[group for group in symbol_groups if _normalize_group_name(group.get('name')) != 'crypto'],
                {'name': 'crypto', 'symbols': configured_crypto},
            ]

    tradeable_pairs = _dedupe([
        symbol
        for group in symbol_groups
        for symbol in normalize_symbol_list(group.get('symbols'))
    ], case_insensitive=True)
    forex_pairs = _group_symbols(symbol_groups, 'forex')
    crypto_pairs = _group_symbols(symbol_groups, 'crypto')
    return {
        'forex_pairs': forex_pairs,
        'crypto_pairs': crypto_pairs,
        'symbol_groups': symbol_groups,
        'tradeable_pairs': tradeable_pairs,
        'source': source,
    }


def save_market_symbols_config(
    db: Session,
    *,
    symbol_groups: list[dict[str, Any]] | None = None,
    forex_pairs: list[str] | None = None,
    crypto_pairs: list[str] | None = None,
) -> ConnectorConfig:
    normalized_groups = normalize_symbol_groups(symbol_groups or [])
    if not normalized_groups:
        normalized_forex = normalize_symbol_list(forex_pairs or [])
        normalized_crypto = normalize_symbol_list(crypto_pairs or [])
        groups: list[dict[str, Any]] = []
        if normalized_forex:
            groups.append({'name': 'forex', 'symbols': normalized_forex})
        if normalized_crypto:
            groups.append({'name': 'crypto', 'symbols': normalized_crypto})
        normalized_groups = groups

    normalized_forex = _group_symbols(normalized_groups, 'forex')
    normalized_crypto = _group_symbols(normalized_groups, 'crypto')

    connector = db.query(ConnectorConfig).filter(ConnectorConfig.connector_name == MARKET_SYMBOL_CONNECTOR).first()
    if not connector:
        connector = ConnectorConfig(connector_name=MARKET_SYMBOL_CONNECTOR, enabled=True, settings={})
        db.add(connector)
        db.flush()

    next_settings = dict(connector.settings or {})
    next_settings[SYMBOL_GROUPS_KEY] = normalized_groups
    next_settings[FOREX_SYMBOLS_KEY] = normalized_forex
    next_settings[CRYPTO_SYMBOLS_KEY] = normalized_crypto
    connector.settings = next_settings
    db.commit()
    db.refresh(connector)
    return connector
