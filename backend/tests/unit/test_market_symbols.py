from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models.connector_config import ConnectorConfig
from app.services.market.symbols import (
    get_market_symbols_config,
    normalize_symbol_groups,
    normalize_symbol_list,
    save_market_symbols_config,
)


class _SettingsStub:
    default_forex_pairs = ['EURUSD.PRO', 'GBPUSD.PRO']
    default_crypto_pairs = ['BTCUSD', 'ETHUSD']


def test_normalize_symbol_list_supports_csv_and_json_list() -> None:
    assert normalize_symbol_list('eurusd.pro, gbpusd.pro, eurusd.pro') == ['eurusd.pro', 'gbpusd.pro']
    assert normalize_symbol_list('["btcusd", "ethusd"]') == ['btcusd', 'ethusd']


def test_normalize_symbol_groups_supports_dict_and_list_shapes() -> None:
    assert normalize_symbol_groups({'indices': ['spx500', 'nsdq100']}) == [
        {'name': 'indices', 'symbols': ['spx500', 'nsdq100']},
    ]
    assert normalize_symbol_groups(
        [
            {'name': 'metaux', 'symbols': ['xauusd']},
            {'name': 'metaux', 'symbols': ['xagusd']},
        ]
    ) == [
        {'name': 'metaux', 'symbols': ['xauusd', 'xagusd']},
    ]


def test_get_market_symbols_config_falls_back_to_env_defaults() -> None:
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(bind=engine)

    with Session(engine) as db:
        payload = get_market_symbols_config(db, _SettingsStub())

    assert payload['forex_pairs'] == ['EURUSD.PRO', 'GBPUSD.PRO']
    assert payload['crypto_pairs'] == ['BTCUSD', 'ETHUSD']
    assert payload['symbol_groups'] == [
        {'name': 'forex', 'symbols': ['EURUSD.PRO', 'GBPUSD.PRO']},
        {'name': 'crypto', 'symbols': ['BTCUSD', 'ETHUSD']},
    ]
    assert payload['tradeable_pairs'] == ['EURUSD.PRO', 'GBPUSD.PRO', 'BTCUSD', 'ETHUSD']
    assert payload['source'] == 'env'


def test_get_market_symbols_config_uses_connector_overrides() -> None:
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(bind=engine)

    with Session(engine) as db:
        db.add(
            ConnectorConfig(
                connector_name='yfinance',
                enabled=True,
                settings={
                    'forex_pairs': 'USDJPY.pro,EURUSD.pro',
                    'crypto_pairs': ['solusd', 'btcusd'],
                },
            )
        )
        db.commit()

        payload = get_market_symbols_config(db, _SettingsStub())

    assert payload['forex_pairs'] == ['USDJPY.pro', 'EURUSD.pro']
    assert payload['crypto_pairs'] == ['solusd', 'btcusd']
    assert payload['symbol_groups'] == [
        {'name': 'forex', 'symbols': ['USDJPY.pro', 'EURUSD.pro']},
        {'name': 'crypto', 'symbols': ['solusd', 'btcusd']},
    ]
    assert payload['tradeable_pairs'] == ['USDJPY.pro', 'EURUSD.pro', 'solusd', 'btcusd']
    assert payload['source'] == 'config'


def test_get_market_symbols_config_prefers_symbol_groups_over_legacy_keys() -> None:
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(bind=engine)

    with Session(engine) as db:
        db.add(
            ConnectorConfig(
                connector_name='yfinance',
                enabled=True,
                settings={
                    'forex_pairs': ['EURUSD.PRO'],
                    'crypto_pairs': ['BTCUSD'],
                    'symbol_groups': [
                        {'name': 'indices', 'symbols': ['spx500', 'nsdq100']},
                        {'name': 'metaux', 'symbols': ['xauusd']},
                    ],
                },
            )
        )
        db.commit()
        payload = get_market_symbols_config(db, _SettingsStub())

    assert payload['symbol_groups'] == [
        {'name': 'indices', 'symbols': ['spx500', 'nsdq100']},
        {'name': 'metaux', 'symbols': ['xauusd']},
    ]
    assert payload['tradeable_pairs'] == ['spx500', 'nsdq100', 'xauusd']
    assert payload['forex_pairs'] == []
    assert payload['crypto_pairs'] == []


def test_save_market_symbols_config_preserves_symbol_casing() -> None:
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(bind=engine)

    with Session(engine) as db:
        save_market_symbols_config(
            db,
            symbol_groups=[
                {'name': 'forex', 'symbols': ['eurusd.pro', 'gbpusd.pro']},
                {'name': 'indices', 'symbols': ['spx500']},
            ],
        )
        row = db.query(ConnectorConfig).filter(ConnectorConfig.connector_name == 'yfinance').first()

    assert row is not None
    assert row.settings['forex_pairs'] == ['eurusd.pro', 'gbpusd.pro']
    assert row.settings['crypto_pairs'] == []
    assert row.settings['symbol_groups'] == [
        {'name': 'forex', 'symbols': ['eurusd.pro', 'gbpusd.pro']},
        {'name': 'indices', 'symbols': ['spx500']},
    ]
