import pandas as pd

from app.services.market.yfinance_provider import YFinanceMarketProvider


def _frame(rows: int = 3) -> pd.DataFrame:
    index = pd.date_range('2026-01-01', periods=rows, freq='h')
    return pd.DataFrame(
        {
            'Open': [1.0, 1.1, 1.2][:rows],
            'High': [1.1, 1.2, 1.3][:rows],
            'Low': [0.9, 1.0, 1.1][:rows],
            'Close': [1.05, 1.15, 1.25][:rows],
            'Volume': [100, 120, 140][:rows],
        },
        index=index,
    )


def test_ticker_candidates_include_suffixless_fx_variant() -> None:
    candidates = YFinanceMarketProvider._ticker_candidates('EURUSD.PRO')
    assert 'EURUSD.PRO' not in candidates
    assert 'EURUSD=X' in candidates


def test_ticker_candidates_include_index_alias() -> None:
    candidates = YFinanceMarketProvider._ticker_candidates('SPX500')
    assert '^GSPC' in candidates


def test_get_historical_candles_tries_fallback_candidates(monkeypatch) -> None:
    provider = YFinanceMarketProvider()
    calls: list[str] = []

    class _FakeTicker:
        def __init__(self, symbol: str) -> None:
            self.symbol = symbol

        def history(self, **kwargs):
            calls.append(self.symbol)
            if self.symbol == 'EURUSD=X':
                return _frame()
            return pd.DataFrame()

    monkeypatch.setattr('app.services.market.yfinance_provider.yf.Ticker', _FakeTicker)

    frame = provider.get_historical_candles('EURUSD.PRO', 'H1', '2026-01-01', '2026-01-02')
    assert not frame.empty
    assert 'EURUSD=X' in calls


def test_get_news_context_tries_fallback_candidates(monkeypatch) -> None:
    provider = YFinanceMarketProvider()
    calls: list[str] = []

    class _FakeTicker:
        def __init__(self, symbol: str) -> None:
            self.symbol = symbol

        @property
        def news(self):
            calls.append(self.symbol)
            if self.symbol == 'EURUSD=X':
                return [{'title': 'Test headline', 'publisher': 'unit', 'link': 'https://example.com', 'providerPublishTime': 1}]
            return []

    monkeypatch.setattr('app.services.market.yfinance_provider.yf.Ticker', _FakeTicker)

    payload = provider.get_news_context('EURUSD.PRO', limit=5)
    assert payload['degraded'] is False
    assert payload['symbol'] == 'EURUSD=X'
    assert len(payload['news']) == 1
    assert 'EURUSD=X' in calls
