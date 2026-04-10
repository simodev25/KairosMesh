"""Unit tests for runtime trading configuration."""

from app.services.config import trading_config as trading_config_module
from app.services.config.trading_config import (
    get_current_values,
    get_effective_gating_policy,
    get_effective_risk_limits,
    get_effective_sizing,
    get_param_catalog,
)


def test_catalog_has_three_sections() -> None:
    catalog = get_param_catalog()
    assert "gating" in catalog
    assert "risk_limits" in catalog
    assert "sizing" in catalog


def test_catalog_params_have_descriptions() -> None:
    catalog = get_param_catalog()
    for section, params in catalog.items():
        for param in params:
            assert "key" in param, f"Missing key in {section}"
            assert "label" in param, f"Missing label in {section}/{param.get('key')}"
            assert "description" in param, f"Missing description in {section}/{param.get('key')}"
            assert len(param["description"]) > 10, f"Description too short for {section}/{param['key']}"


def test_currency_notional_block_catalog_max_supports_high_concentration_books() -> None:
    catalog = get_param_catalog()
    warn_field = next(param for param in catalog["risk_limits"] if param["key"] == "max_currency_notional_exposure_pct_warn")
    block_field = next(param for param in catalog["risk_limits"] if param["key"] == "max_currency_notional_exposure_pct_block")
    assert warn_field["max"] == 2000.0
    assert block_field["max"] == 2000.0


def test_gating_defaults_match_constants() -> None:
    """Without runtime overrides, should return the code defaults."""
    policy = get_effective_gating_policy("balanced")
    assert policy.min_combined_score == 0.22
    assert policy.min_confidence == 0.28


def test_gating_conservative_defaults() -> None:
    policy = get_effective_gating_policy("conservative")
    assert policy.min_combined_score == 0.32
    assert policy.min_aligned_sources == 2


def test_risk_limits_defaults_match() -> None:
    limits = get_effective_risk_limits("live")
    assert limits.max_daily_loss_pct == 3.0
    assert limits.max_positions == 3
    assert limits.max_currency_notional_exposure_pct_warn == 12.0
    assert limits.max_currency_notional_exposure_pct_block == 15.0
    assert limits.max_currency_open_risk_pct == 6.0


def test_sizing_defaults_match() -> None:
    sizing = get_effective_sizing()
    assert sizing["sl_atr_multiplier"] == 1.5
    assert sizing["tp_atr_multiplier"] == 2.5


def test_decision_mode_changes_risk_limits_and_sizing() -> None:
    conservative = get_current_values("conservative", "live")
    balanced = get_current_values("balanced", "live")
    permissive = get_current_values("permissive", "live")

    assert conservative["risk_limits"]["max_risk_per_trade_pct"] < balanced["risk_limits"]["max_risk_per_trade_pct"]
    assert permissive["risk_limits"]["max_risk_per_trade_pct"] > balanced["risk_limits"]["max_risk_per_trade_pct"]
    assert conservative["risk_limits"]["max_open_risk_pct"] < balanced["risk_limits"]["max_open_risk_pct"]
    assert permissive["risk_limits"]["max_open_risk_pct"] > balanced["risk_limits"]["max_open_risk_pct"]
    assert conservative["sizing"]["sl_atr_multiplier"] > balanced["sizing"]["sl_atr_multiplier"]
    assert permissive["sizing"]["sl_atr_multiplier"] < balanced["sizing"]["sl_atr_multiplier"]
    assert conservative["sizing"]["min_sl_distance_pct"] > balanced["sizing"]["min_sl_distance_pct"]
    assert permissive["sizing"]["min_sl_distance_pct"] < balanced["sizing"]["min_sl_distance_pct"]


def test_runtime_overrides_take_precedence_over_decision_mode_presets(monkeypatch) -> None:
    monkeypatch.setattr(
        trading_config_module,
        "_get_runtime_settings",
        lambda: {
            "risk_limits": {"max_open_risk_pct": 11.5},
            "sizing": {"sl_atr_multiplier": 1.9},
        },
    )

    values = get_current_values("conservative", "live")

    assert values["risk_limits"]["max_open_risk_pct"] == 11.5
    assert values["sizing"]["sl_atr_multiplier"] == 1.9


def test_scoped_runtime_overrides_apply_only_to_matching_profile(monkeypatch) -> None:
    monkeypatch.setattr(
        trading_config_module,
        "_get_runtime_settings",
        lambda: {
            "profiles": {
                "permissive": {
                    "live": {
                        "gating": {"min_confidence": 0.25},
                        "risk_limits": {
                            "max_open_risk_pct": 3.0,
                            "enforce_max_risk_per_trade": True,
                            "max_risk_per_trade_behavior": "clamp",
                            "log_risk_adjustments": True,
                        },
                        "sizing": {"sl_atr_multiplier": 2.2},
                    }
                }
            }
        },
    )

    live_permissive = get_current_values("permissive", "live")
    simulation_permissive = get_current_values("permissive", "simulation")
    live_balanced = get_current_values("balanced", "live")

    assert live_permissive["gating"]["min_confidence"] == 0.25
    assert live_permissive["risk_limits"]["max_open_risk_pct"] == 3.0
    assert live_permissive["risk_limits"]["enforce_max_risk_per_trade"] is True
    assert live_permissive["risk_limits"]["max_risk_per_trade_behavior"] == "clamp"
    assert live_permissive["risk_limits"]["log_risk_adjustments"] is True
    assert live_permissive["sizing"]["sl_atr_multiplier"] == 2.2

    assert simulation_permissive["risk_limits"]["max_open_risk_pct"] == 8.0
    assert simulation_permissive["risk_limits"]["enforce_max_risk_per_trade"] is False
    assert simulation_permissive["sizing"]["sl_atr_multiplier"] == 1.2
    assert live_balanced["risk_limits"]["max_open_risk_pct"] == 6.0
    assert live_balanced["gating"]["min_confidence"] == 0.28


def test_scoped_runtime_overrides_take_precedence_over_legacy_globals(monkeypatch) -> None:
    monkeypatch.setattr(
        trading_config_module,
        "_get_runtime_settings",
        lambda: {
            "gating": {"min_confidence": 0.31},
            "risk_limits": {"max_open_risk_pct": 11.5},
            "sizing": {"sl_atr_multiplier": 1.9},
            "profiles": {
                "permissive": {
                    "live": {
                        "gating": {"min_confidence": 0.25},
                        "risk_limits": {"max_open_risk_pct": 3.0},
                        "sizing": {"sl_atr_multiplier": 2.2},
                    }
                }
            },
        },
    )

    live_permissive = get_current_values("permissive", "live")
    live_balanced = get_current_values("balanced", "live")

    assert live_permissive["gating"]["min_confidence"] == 0.25
    assert live_permissive["risk_limits"]["max_open_risk_pct"] == 3.0
    assert live_permissive["sizing"]["sl_atr_multiplier"] == 2.2

    assert live_balanced["gating"]["min_confidence"] == 0.31
    assert live_balanced["risk_limits"]["max_open_risk_pct"] == 11.5
    assert live_balanced["sizing"]["sl_atr_multiplier"] == 1.9


def test_current_values_structure() -> None:
    values = get_current_values("balanced", "simulation")
    assert "gating" in values
    assert "risk_limits" in values
    assert "sizing" in values
    assert "min_combined_score" in values["gating"]
    assert "max_daily_loss_pct" in values["risk_limits"]
    assert "enforce_max_risk_per_trade" in values["risk_limits"]
    assert "max_risk_per_trade_behavior" in values["risk_limits"]
    assert "log_risk_adjustments" in values["risk_limits"]
    assert "sl_atr_multiplier" in values["sizing"]


def test_catalog_exposes_risk_limit_behavior_controls() -> None:
    catalog = get_param_catalog()
    risk_params = {param["key"]: param for param in catalog["risk_limits"]}

    assert risk_params["enforce_max_risk_per_trade"]["type"] == "bool"
    assert risk_params["max_risk_per_trade_behavior"]["type"] == "enum"
    assert risk_params["max_risk_per_trade_behavior"]["options"] == ["clamp", "reject", "warn_only"]
    assert risk_params["log_risk_adjustments"]["type"] == "bool"


def test_unknown_mode_falls_back() -> None:
    """Unknown decision mode → balanced, unknown risk mode → live."""
    policy = get_effective_gating_policy("nonexistent")
    assert policy.min_combined_score == 0.22  # balanced default

    limits = get_effective_risk_limits("nonexistent")
    assert limits.max_daily_loss_pct == 3.0  # live default
