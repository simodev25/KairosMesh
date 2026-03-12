from app.services.trading.metaapi_client import MetaApiClient


def test_trade_result_ok_accepts_success_codes() -> None:
    ok, reason = MetaApiClient._trade_result_ok(
        {
            'numericCode': 10009,
            'stringCode': 'TRADE_RETCODE_DONE',
            'message': 'Request completed',
        }
    )
    assert ok is True
    assert reason is None


def test_trade_result_ok_accepts_no_changes_code() -> None:
    ok, reason = MetaApiClient._trade_result_ok(
        {
            'numericCode': 10025,
            'stringCode': 'TRADE_RETCODE_NO_CHANGES',
            'message': 'No changes',
        }
    )
    assert ok is True
    assert reason is None


def test_trade_result_ok_rejects_unknown_code() -> None:
    ok, reason = MetaApiClient._trade_result_ok(
        {
            'numericCode': -1,
            'stringCode': 'TRADE_RETCODE_UNKNOWN',
            'message': 'Unknown trade return code',
        }
    )
    assert ok is False
    assert reason is not None
    assert 'Unknown trade return code' in reason


def test_validate_symbol_for_market_order_rejects_disabled_trade_mode() -> None:
    ok, reason = MetaApiClient._validate_symbol_for_market_order(
        'EURUSD',
        {'tradeMode': 'SYMBOL_TRADE_MODE_DISABLED', 'allowedOrderTypes': ['SYMBOL_ORDER_MARKET']},
    )
    assert ok is False
    assert reason is not None
    assert 'disabled' in reason.lower()


def test_validate_symbol_for_market_order_accepts_market_tradable_symbol() -> None:
    ok, reason = MetaApiClient._validate_symbol_for_market_order(
        'EURUSD',
        {'tradeMode': 'SYMBOL_TRADE_MODE_FULL', 'allowedOrderTypes': ['SYMBOL_ORDER_MARKET']},
    )
    assert ok is True
    assert reason is None
