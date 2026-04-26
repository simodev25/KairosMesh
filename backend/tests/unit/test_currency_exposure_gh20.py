"""Tests ciblés GH-20 pour l'exposition notionnelle par devise."""

from pathlib import Path

from pytest import approx

from app.services.risk.currency_exposure import compute_currency_exposure
from app.services.risk.portfolio_state import OpenPosition


def _usdchf_position() -> OpenPosition:
    return OpenPosition(
        symbol="USDCHF.PRO",
        side="BUY",
        volume=9.81,
        entry_price=0.9015,
        current_price=0.9015,
        unrealized_pnl=0.0,
        risk_pct=1.0,
    )


def test_gh20_tc01_usdchf_leverage_100_notional_is_20_5pct() -> None:
    """TC-01: run-101 reproduit ~20.5% avec levier 100."""
    report = compute_currency_exposure(
        [_usdchf_position()],
        equity=47_914.0,
        account_leverage=100.0,
    )

    usd = report.exposures["USD"]
    assert usd.currency_notional_exposure_pct == approx(20.5, abs=0.1)


def test_gh20_tc02_leverage_1_matches_legacy_raw_notional() -> None:
    """TC-02: levier 1 doit retrouver le calcul historique brut."""
    report = compute_currency_exposure(
        [_usdchf_position()],
        equity=47_914.0,
        account_leverage=1.0,
    )

    usd = report.exposures["USD"]
    assert usd.currency_notional_exposure_pct == approx(2047.4, abs=0.1)


def test_gh20_tc03_leverage_0_falls_back_to_100() -> None:
    """TC-03: levier invalide 0 => fallback 100.0."""
    report = compute_currency_exposure(
        [_usdchf_position()],
        equity=47_914.0,
        account_leverage=0.0,
    )

    usd = report.exposures["USD"]
    assert usd.currency_notional_exposure_pct == approx(20.5, abs=0.1)


def test_gh20_tc04_callsites_propagate_account_leverage_argument() -> None:
    """TC-04: les 4 callsites de production passent le levier explicite."""
    repo_root = Path(__file__).resolve().parents[2]
    expected_snippets = {
        "app/services/risk/rules.py": "account_leverage=portfolio.leverage",
        "app/services/mcp/trading_server.py": "account_leverage=state.leverage",
        "app/main.py": "account_leverage=state.leverage",
        "app/api/routes/portfolio.py": "account_leverage=state.leverage",
    }

    for rel_path, snippet in expected_snippets.items():
        content = (repo_root / rel_path).read_text(encoding="utf-8")
        assert snippet in content, f"Snippet manquant dans {rel_path}: {snippet}"
