"""Celery periodic task for portfolio snapshot capture.

Runs every 15 minutes during market hours:
1. Fetches account info + positions from MetaAPI
2. Saves a 'periodic' snapshot to DB
3. Updates daily_high_equity if new high
"""
import asyncio
import logging
from datetime import datetime, timezone

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.tasks.celery_app import celery_app

settings = get_settings()
logger = logging.getLogger(__name__)


def _is_market_hours() -> bool:
    """Check if current UTC time is within broad forex market hours (Sun 22:00 - Fri 22:00)."""
    now = datetime.now(timezone.utc)
    weekday = now.weekday()  # 0=Mon, 6=Sun
    hour = now.hour
    # Forex closes Friday 22:00 UTC, reopens Sunday 22:00 UTC
    if weekday == 5:  # Saturday
        return False
    if weekday == 4 and hour >= 22:  # Friday after 22:00
        return False
    if weekday == 6 and hour < 22:  # Sunday before 22:00
        return False
    return True


@celery_app.task(
    name='app.tasks.portfolio_tasks.snapshot_portfolio',
    soft_time_limit=30,
    time_limit=60,
)
def snapshot_portfolio() -> None:
    """Capture a periodic portfolio snapshot."""
    if not _is_market_hours():
        logger.debug("portfolio_snapshot skipped: outside market hours")
        return

    db = SessionLocal()
    try:
        from app.db.models.metaapi_account import MetaApiAccount
        from app.db.models.portfolio_snapshot import PortfolioSnapshot
        from app.services.risk.portfolio_state import PortfolioStateService

        # Find the default/active MetaAPI account
        account = (
            db.query(MetaApiAccount)
            .filter(MetaApiAccount.enabled.is_(True))
            .order_by(MetaApiAccount.is_default.desc(), MetaApiAccount.id.asc())
            .first()
        )
        if not account:
            logger.debug("portfolio_snapshot skipped: no MetaAPI account configured")
            return

        account_id = str(account.account_id)
        region = account.region

        # Fetch portfolio state
        state = asyncio.run(
            PortfolioStateService.get_current_state(
                account_id=account_id,
                region=region,
                db=db,
            )
        )

        if state.degraded:
            logger.warning(
                "portfolio_snapshot degraded: %s", state.degraded_reasons,
            )

        snapshot = PortfolioSnapshot(
            account_id=account_id,
            balance=state.balance,
            equity=state.equity,
            free_margin=state.free_margin,
            used_margin=state.used_margin,
            open_position_count=state.open_position_count,
            open_risk_total_pct=state.open_risk_total_pct,
            daily_realized_pnl=state.daily_realized_pnl,
            daily_high_equity=state.daily_high_equity,
            snapshot_type="periodic",
        )
        db.add(snapshot)
        db.commit()

        logger.info(
            "portfolio_snapshot saved account=%s equity=%.2f positions=%d drawdown=%.2f%%",
            account_id, state.equity, state.open_position_count,
            state.daily_drawdown_pct,
        )
    except Exception:
        logger.warning("portfolio_snapshot failed", exc_info=True)
    finally:
        db.close()


@celery_app.task(
    name='app.tasks.portfolio_tasks.refresh_correlation_matrix',
    soft_time_limit=120,
    time_limit=180,
)
def refresh_correlation_matrix() -> None:
    """Compute and cache the correlation matrix for all tradeable symbols.

    Runs once daily after the main trading session closes.
    Fetches H4 close prices for the last 30 days, computes pairwise correlations,
    and stores the result in Redis with 24h TTL.
    """
    try:
        from app.core.config import get_settings
        from app.services.market.symbols import get_market_symbols_config
        from app.services.risk.correlation_matrix import (
            compute_correlation_matrix,
            save_to_redis,
        )

        settings = get_settings()
        symbols_config = get_market_symbols_config(settings)
        all_symbols = symbols_config.get("tradeable_pairs", [])

        if not all_symbols:
            logger.debug("refresh_correlation_matrix skipped: no symbols configured")
            return

        # Fetch close prices for each symbol
        close_prices: dict[str, list[float]] = {}
        for symbol in all_symbols:
            try:
                from app.services.market.data_provider import MarketProvider
                provider = MarketProvider()
                closes = provider.get_close_prices(symbol, timeframe="H4", bars=180)
                if closes and len(closes) >= 30:
                    close_prices[symbol] = closes
            except Exception as exc:
                logger.debug("Failed to fetch closes for %s: %s", symbol, exc)

        if len(close_prices) < 2:
            logger.info(
                "refresh_correlation_matrix: insufficient data (%d symbols)",
                len(close_prices),
            )
            return

        matrix = compute_correlation_matrix(close_prices, lookback_days=30)
        save_to_redis(matrix)

        logger.info(
            "refresh_correlation_matrix completed: %d symbols, %d valid",
            len(all_symbols), len(matrix.symbols),
        )
    except Exception:
        logger.warning("refresh_correlation_matrix failed", exc_info=True)
