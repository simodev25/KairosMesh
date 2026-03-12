import logging
from typing import Any

import pandas as pd
import yfinance as yf
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator, MACD
from ta.volatility import AverageTrueRange

logger = logging.getLogger(__name__)


class YFinanceMarketProvider:
    interval_map = {
        'M5': ('5m', '7d'),
        'M15': ('15m', '30d'),
        'H1': ('60m', '90d'),
        'H4': ('60m', '180d'),
        'D1': ('1d', '365d'),
    }

    def _symbol(self, pair: str) -> str:
        return f"{pair}=X"

    def _prepare_frame(self, pair: str, timeframe: str) -> pd.DataFrame:
        interval, period = self.interval_map.get(timeframe.upper(), ('60m', '90d'))
        ticker = yf.Ticker(self._symbol(pair))
        frame = ticker.history(period=period, interval=interval)

        if timeframe.upper() == 'H4' and not frame.empty:
            frame = (
                frame.resample('4h')
                .agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'})
                .dropna()
            )

        return frame

    def get_market_snapshot(self, pair: str, timeframe: str) -> dict[str, Any]:
        try:
            frame = self._prepare_frame(pair, timeframe)
            if frame.empty:
                return {'degraded': True, 'error': 'No market data available', 'pair': pair, 'timeframe': timeframe}

            close = frame['Close']
            high = frame['High']
            low = frame['Low']

            rsi = RSIIndicator(close=close, window=14).rsi().iloc[-1]
            ema_fast = EMAIndicator(close=close, window=20).ema_indicator().iloc[-1]
            ema_slow = EMAIndicator(close=close, window=50).ema_indicator().iloc[-1]
            macd_diff = MACD(close=close).macd_diff().iloc[-1]
            atr = AverageTrueRange(high=high, low=low, close=close).average_true_range().iloc[-1]

            latest = float(close.iloc[-1])
            prev = float(close.iloc[-2]) if len(close) > 1 else latest
            pct_change = ((latest - prev) / prev) * 100 if prev else 0.0

            trend = 'bullish' if ema_fast > ema_slow else 'bearish'
            if abs(ema_fast - ema_slow) < latest * 0.0003:
                trend = 'neutral'

            return {
                'degraded': False,
                'pair': pair,
                'timeframe': timeframe,
                'last_price': latest,
                'change_pct': round(float(pct_change), 5),
                'rsi': round(float(rsi), 3),
                'ema_fast': round(float(ema_fast), 6),
                'ema_slow': round(float(ema_slow), 6),
                'macd_diff': round(float(macd_diff), 6),
                'atr': round(float(atr), 6),
                'trend': trend,
            }
        except Exception as exc:  # pragma: no cover - third-party failures are expected in degraded mode
            logger.exception('yfinance market snapshot failure pair=%s timeframe=%s', pair, timeframe)
            return {'degraded': True, 'error': str(exc), 'pair': pair, 'timeframe': timeframe}

    def get_historical_candles(self, pair: str, timeframe: str, start_date: str, end_date: str) -> pd.DataFrame:
        try:
            interval, _ = self.interval_map.get(timeframe.upper(), ('60m', '90d'))
            ticker = yf.Ticker(self._symbol(pair))
            frame = ticker.history(start=start_date, end=end_date, interval=interval)

            if timeframe.upper() == 'H4' and not frame.empty:
                frame = (
                    frame.resample('4h')
                    .agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'})
                    .dropna()
                )

            return frame
        except Exception as exc:  # pragma: no cover
            logger.exception('yfinance historical retrieval failure pair=%s timeframe=%s', pair, timeframe)
            return pd.DataFrame()

    def get_news_context(self, pair: str, limit: int = 5) -> dict[str, Any]:
        try:
            ticker = yf.Ticker(self._symbol(pair))
            news_items = ticker.news or []
            selected = []
            for item in news_items[:limit]:
                selected.append(
                    {
                        'title': item.get('title', ''),
                        'publisher': item.get('publisher', ''),
                        'link': item.get('link', ''),
                        'published': item.get('providerPublishTime'),
                    }
                )
            return {'degraded': False, 'pair': pair, 'news': selected}
        except Exception as exc:  # pragma: no cover
            logger.exception('yfinance news retrieval failure pair=%s', pair)
            return {'degraded': True, 'pair': pair, 'news': [], 'error': str(exc)}
