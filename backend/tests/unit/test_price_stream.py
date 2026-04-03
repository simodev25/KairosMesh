import asyncio

from app.services.trading import price_stream


def test_price_stream_connect_configures_sdk_logging_before_metaapi_init(monkeypatch) -> None:
    manager = price_stream.PriceStreamManager()
    monkeypatch.setattr(price_stream, '_HAS_METAAPI_SDK', True)

    class FakeConnection:
        async def connect(self) -> None:
            return None

        async def wait_synchronized(self) -> None:
            return None

        def add_synchronization_listener(self, listener) -> None:
            self.listener = listener

    class FakeAccount:
        def get_streaming_connection(self) -> FakeConnection:
            return FakeConnection()

    class FakeAccountApi:
        async def get_account(self, account_id: str) -> FakeAccount:
            return FakeAccount()

    class FakeMetaApi:
        logging_ready = False

        def __init__(self, token: str) -> None:
            assert self.logging_ready is True
            self.metatrader_account_api = FakeAccountApi()

    def fake_configure(metaapi_cls) -> None:
        assert metaapi_cls is FakeMetaApi
        FakeMetaApi.logging_ready = True

    monkeypatch.setattr(price_stream, 'MetaApi', FakeMetaApi)
    monkeypatch.setattr(
        'app.services.trading.metaapi_client.MetaApiClient._configure_sdk_logging',
        fake_configure,
    )

    asyncio.run(manager.connect('token', 'account-1'))

    assert manager.is_connected is True
