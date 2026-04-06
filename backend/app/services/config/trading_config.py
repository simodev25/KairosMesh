"""Runtime trading configuration — resolves parameters from DB > env > code defaults.

Provides configurable decision gating thresholds, risk limits, and trade sizing
multipliers. All values can be overridden at runtime via the ConnectorConfig
'trading' connector without restarting the application.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from app.services.agentscope.constants import (
    DECISION_MODES,
    DecisionGatingPolicy,
)
from app.services.risk.limits import RISK_LIMITS, RiskLimits

CONNECTOR_NAME = "trading"
SCOPED_PROFILES_KEY = "profiles"

DECISION_MODE_RISK_PRESETS: dict[str, dict[str, float | int]] = {
    "conservative": {
        "max_risk_per_trade_pct": 1.5,
        "max_daily_loss_pct": 2.0,
        "max_open_risk_pct": 4.5,
        "max_positions": 2,
        "max_positions_per_symbol": 1,
        "min_free_margin_pct": 60.0,
        "max_currency_notional_exposure_pct_warn": 10.0,
        "max_currency_notional_exposure_pct_block": 12.0,
        "max_currency_open_risk_pct": 5.0,
        "max_weekly_loss_pct": 4.0,
    },
    "balanced": {},
    "permissive": {
        "max_risk_per_trade_pct": 2.5,
        "max_daily_loss_pct": 4.0,
        "max_open_risk_pct": 8.0,
        "max_positions": 4,
        "max_positions_per_symbol": 2,
        "min_free_margin_pct": 40.0,
        "max_currency_notional_exposure_pct_warn": 18.0,
        "max_currency_notional_exposure_pct_block": 22.0,
        "max_currency_open_risk_pct": 7.0,
        "max_weekly_loss_pct": 6.0,
    },
}

DECISION_MODE_SIZING_PRESETS: dict[str, dict[str, float]] = {
    "conservative": {
        "sl_atr_multiplier": 1.8,
        "tp_atr_multiplier": 3.0,
        "min_sl_distance_pct": 0.07,
    },
    "balanced": {},
    "permissive": {
        "sl_atr_multiplier": 1.2,
        "tp_atr_multiplier": 2.0,
        "min_sl_distance_pct": 0.03,
    },
}

# ── Parameter catalog with descriptions ──
# Each entry: (key, description, type, default_per_mode)

GATING_PARAMS: list[dict[str, Any]] = [
    {
        "key": "min_combined_score",
        "label": "Min Combined Score",
        "description": "Score minimum pour declencher un trade. Plus c'est haut, moins de trades sont pris.",
        "type": "float",
        "min": 0.0,
        "max": 1.0,
        "step": 0.01,
    },
    {
        "key": "min_confidence",
        "label": "Min Confidence",
        "description": "Niveau de confiance minimum requis. En dessous, le trade est bloque meme si le score est bon.",
        "type": "float",
        "min": 0.0,
        "max": 1.0,
        "step": 0.01,
    },
    {
        "key": "min_aligned_sources",
        "label": "Min Aligned Sources",
        "description": "Nombre minimum d'agents (tech, news, context) qui doivent etre d'accord sur la direction. 1 = un seul agent suffit, 2 = consensus requis.",
        "type": "int",
        "min": 0,
        "max": 3,
        "step": 1,
    },
    {
        "key": "allow_technical_single_source_override",
        "label": "Allow Technical Override",
        "description": "Si actif, l'analyse technique seule peut declencher un trade meme si news et context sont neutres.",
        "type": "bool",
    },
]

RISK_PARAMS: list[dict[str, Any]] = [
    {
        "key": "max_risk_per_trade_pct",
        "label": "Max Risk Per Trade (%)",
        "description": "Risque maximum par trade en pourcentage de l'equity. Ex: 2% = on risque max 200 sur un compte de 10 000.",
        "type": "float",
        "min": 0.1,
        "max": 10.0,
        "step": 0.1,
    },
    {
        "key": "max_daily_loss_pct",
        "label": "Max Daily Loss (%)",
        "description": "Perte maximale autorisee sur une journee. Au-dela, tous les trades sont bloques jusqu'au lendemain.",
        "type": "float",
        "min": 0.5,
        "max": 20.0,
        "step": 0.5,
    },
    {
        "key": "max_open_risk_pct",
        "label": "Max Open Risk (%)",
        "description": "Risque total maximum de toutes les positions ouvertes combinees. Empeche la surexposition.",
        "type": "float",
        "min": 1.0,
        "max": 30.0,
        "step": 0.5,
    },
    {
        "key": "max_positions",
        "label": "Max Positions",
        "description": "Nombre maximum de positions ouvertes en meme temps. Limite la complexite du portefeuille.",
        "type": "int",
        "min": 1,
        "max": 20,
        "step": 1,
    },
    {
        "key": "max_positions_per_symbol",
        "label": "Max Positions Per Symbol",
        "description": "Nombre maximum de positions sur le meme instrument. 1 = une seule position par paire.",
        "type": "int",
        "min": 1,
        "max": 5,
        "step": 1,
    },
    {
        "key": "min_free_margin_pct",
        "label": "Min Free Margin (%)",
        "description": "Pourcentage minimum de marge libre requis. Protege contre le margin call en gardant une reserve.",
        "type": "float",
        "min": 5.0,
        "max": 80.0,
        "step": 5.0,
    },
    {
        "key": "max_currency_notional_exposure_pct_warn",
        "label": "Max Currency Notional Exposure Warn (%)",
        "description": "Seuil d'alerte de concentration notionnelle par devise. Mesure de concentration, pas de risque stop-based.",
        "type": "float",
        "min": 5.0,
        "max": 2000.0,
        "step": 5.0,
    },
    {
        "key": "max_currency_notional_exposure_pct_block",
        "label": "Max Currency Notional Exposure Block (%)",
        "description": "Seuil de blocage dur de concentration notionnelle par devise. A utiliser avec prudence pendant la transition.",
        "type": "float",
        "min": 5.0,
        "max": 2000.0,
        "step": 5.0,
    },
    {
        "key": "max_currency_open_risk_pct",
        "label": "Max Currency Open Risk (%)",
        "description": "Risque stop-based agrege par devise. Expose pour observabilite en phase 1, pas encore utilise comme hard gate.",
        "type": "float",
        "min": 1.0,
        "max": 100.0,
        "step": 1.0,
    },
    {
        "key": "max_weekly_loss_pct",
        "label": "Max Weekly Loss (%)",
        "description": "Perte maximale autorisee sur une semaine. Au-dela, les trades sont bloques jusqu'a la semaine suivante.",
        "type": "float",
        "min": 1.0,
        "max": 30.0,
        "step": 1.0,
    },
]

SIZING_PARAMS: list[dict[str, Any]] = [
    {
        "key": "sl_atr_multiplier",
        "label": "Stop Loss ATR Multiplier",
        "description": "Multiplicateur ATR pour le stop loss. Ex: 1.5 = SL place a 1.5x la volatilite moyenne. Plus c'est haut, plus le SL est loin.",
        "type": "float",
        "min": 0.5,
        "max": 5.0,
        "step": 0.1,
    },
    {
        "key": "tp_atr_multiplier",
        "label": "Take Profit ATR Multiplier",
        "description": "Multiplicateur ATR pour le take profit. Ex: 2.5 = TP place a 2.5x la volatilite. Ratio R:R = TP/SL (2.5/1.5 = 1.67).",
        "type": "float",
        "min": 0.5,
        "max": 10.0,
        "step": 0.1,
    },
    {
        "key": "min_sl_distance_pct",
        "label": "Min SL Distance (%)",
        "description": "Distance minimum du stop loss en % du prix. En dessous, le trade est refuse (SL trop serre). Baisser pour les petits timeframes (M5/M15). Ex: 0.02 = SL doit etre a au moins 0.02% du prix.",
        "type": "float",
        "min": 0.005,
        "max": 0.5,
        "step": 0.005,
    },
]


def _get_runtime_settings() -> dict[str, Any]:
    """Load trading runtime settings from ConnectorConfig DB (cached 5s)."""
    try:
        from app.services.connectors.runtime_settings import RuntimeConnectorSettings
        return RuntimeConnectorSettings.settings(CONNECTOR_NAME)
    except Exception:
        return {}


def _normalize_decision_mode_name(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in DECISION_MODES:
        return normalized
    return "balanced"


def _normalize_execution_mode_name(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in RISK_LIMITS:
        return normalized
    return "live"


def _get_section_overrides(
    runtime: dict[str, Any],
    *,
    section: str,
    decision_mode: str,
    execution_mode: str | None = None,
) -> dict[str, Any]:
    profiles = runtime.get(SCOPED_PROFILES_KEY, {})
    if execution_mode and isinstance(profiles, dict):
        scoped_by_decision = profiles.get(_normalize_decision_mode_name(decision_mode), {})
        if isinstance(scoped_by_decision, dict):
            scoped_profile = scoped_by_decision.get(_normalize_execution_mode_name(execution_mode), {})
            if isinstance(scoped_profile, dict):
                scoped_section = scoped_profile.get(section)
                if isinstance(scoped_section, dict):
                    return scoped_section

    legacy_section = runtime.get(section, {})
    if isinstance(legacy_section, dict):
        return legacy_section
    return {}


def _collect_overrides(raw_values: dict[str, Any], params: list[dict[str, Any]]) -> dict[str, Any]:
    overrides: dict[str, Any] = {}
    for param in params:
        key = param["key"]
        if key not in raw_values:
            continue
        try:
            if param["type"] == "float":
                overrides[key] = float(raw_values[key])
            elif param["type"] == "int":
                overrides[key] = int(raw_values[key])
            elif param["type"] == "bool":
                overrides[key] = bool(raw_values[key])
        except (TypeError, ValueError):
            pass
    return overrides


def build_scoped_trading_settings(
    current_settings: dict[str, Any] | None,
    *,
    decision_mode: str,
    execution_mode: str,
    gating: dict[str, Any] | None = None,
    risk_limits: dict[str, Any] | None = None,
    sizing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    next_settings = dict(current_settings or {})
    profiles = next_settings.get(SCOPED_PROFILES_KEY, {})
    if not isinstance(profiles, dict):
        profiles = {}

    resolved_decision_mode = _normalize_decision_mode_name(decision_mode)
    resolved_execution_mode = _normalize_execution_mode_name(execution_mode)

    scoped_by_decision = profiles.get(resolved_decision_mode, {})
    if not isinstance(scoped_by_decision, dict):
        scoped_by_decision = {}

    scoped_profile = scoped_by_decision.get(resolved_execution_mode, {})
    if not isinstance(scoped_profile, dict):
        scoped_profile = {}

    scoped_profile["gating"] = dict(gating or {})
    scoped_profile["risk_limits"] = dict(risk_limits or {})
    scoped_profile["sizing"] = dict(sizing or {})
    scoped_by_decision[resolved_execution_mode] = scoped_profile
    profiles[resolved_decision_mode] = scoped_by_decision
    next_settings[SCOPED_PROFILES_KEY] = profiles
    return next_settings


def get_effective_gating_policy(mode: str, execution_mode: str | None = None) -> DecisionGatingPolicy:
    """Resolve DecisionGatingPolicy: scoped DB overrides > legacy DB overrides > code defaults."""
    resolved_mode = _normalize_decision_mode_name(mode)
    base = DECISION_MODES.get(resolved_mode, DECISION_MODES["balanced"])
    runtime = _get_runtime_settings()

    gating_overrides = _get_section_overrides(
        runtime,
        section="gating",
        decision_mode=resolved_mode,
        execution_mode=execution_mode,
    )
    overrides = _collect_overrides(gating_overrides, GATING_PARAMS)
    if not overrides:
        return base

    # Merge: override fields on top of base
    base_dict = {
        "min_combined_score": base.min_combined_score,
        "min_confidence": base.min_confidence,
        "min_aligned_sources": base.min_aligned_sources,
        "allow_technical_single_source_override": base.allow_technical_single_source_override,
        "block_major_contradiction": base.block_major_contradiction,
        "contradiction_penalty_weak": base.contradiction_penalty_weak,
        "contradiction_penalty_moderate": base.contradiction_penalty_moderate,
        "contradiction_penalty_major": base.contradiction_penalty_major,
        "confidence_multiplier_moderate": base.confidence_multiplier_moderate,
        "confidence_multiplier_major": base.confidence_multiplier_major,
    }
    base_dict.update(overrides)
    return DecisionGatingPolicy(**base_dict)


def get_effective_risk_limits(mode: str, decision_mode: str = "balanced") -> RiskLimits:
    """Resolve RiskLimits: execution defaults > decision preset > scoped DB overrides > legacy DB overrides."""
    resolved_mode = _normalize_execution_mode_name(mode)
    resolved_decision_mode = _normalize_decision_mode_name(decision_mode)
    base = RISK_LIMITS.get(resolved_mode, RISK_LIMITS["live"])
    decision_overrides = DECISION_MODE_RISK_PRESETS.get(
        resolved_decision_mode,
        DECISION_MODE_RISK_PRESETS["balanced"],
    )
    runtime = _get_runtime_settings()

    risk_overrides = _get_section_overrides(
        runtime,
        section="risk_limits",
        decision_mode=resolved_decision_mode,
        execution_mode=resolved_mode,
    )
    if not isinstance(risk_overrides, dict):
        base_dict = asdict(base)
        base_dict.update(decision_overrides)
        return RiskLimits(**base_dict)

    overrides: dict[str, Any] = dict(decision_overrides)
    overrides.update(_collect_overrides(risk_overrides, RISK_PARAMS))

    base_dict = asdict(base)
    base_dict.update(overrides)
    # frozen dataclass — rebuild
    return RiskLimits(**base_dict)


def get_effective_sizing(decision_mode: str = "balanced", execution_mode: str | None = None) -> dict[str, float]:
    """Resolve trade sizing: defaults > decision preset > scoped DB overrides > legacy DB overrides."""
    from app.services.agentscope.constants import SL_ATR_MULTIPLIER, TP_ATR_MULTIPLIER

    resolved_decision_mode = _normalize_decision_mode_name(decision_mode)
    defaults: dict[str, float] = {
        "sl_atr_multiplier": SL_ATR_MULTIPLIER,
        "tp_atr_multiplier": TP_ATR_MULTIPLIER,
        "min_sl_distance_pct": 0.05,
    }
    defaults.update(
        DECISION_MODE_SIZING_PRESETS.get(
            resolved_decision_mode,
            DECISION_MODE_SIZING_PRESETS["balanced"],
        )
    )
    runtime = _get_runtime_settings()
    sizing_overrides = _get_section_overrides(
        runtime,
        section="sizing",
        decision_mode=resolved_decision_mode,
        execution_mode=execution_mode,
    )
    if not isinstance(sizing_overrides, dict):
        return defaults

    for key, value in _collect_overrides(sizing_overrides, SIZING_PARAMS).items():
        defaults[key] = float(value)

    return defaults


def get_param_catalog() -> dict[str, list[dict[str, Any]]]:
    """Return full parameter catalog with descriptions for frontend rendering."""
    return {
        "gating": GATING_PARAMS,
        "risk_limits": RISK_PARAMS,
        "sizing": SIZING_PARAMS,
    }


def get_active_config_version(db: Any = None) -> int:
    """Return the latest trading config version number, or 0 if none."""
    if db is None:
        try:
            from app.db.session import SessionLocal
            db = SessionLocal()
            try:
                return _query_max_version(db)
            finally:
                db.close()
        except Exception:
            return 0
    return _query_max_version(db)


def _query_max_version(db: Any) -> int:
    try:
        from app.db.models.trading_config_version import TradingConfigVersion
        from sqlalchemy import func
        result = db.query(func.max(TradingConfigVersion.version)).scalar()
        return result or 0
    except Exception:
        return 0


def get_current_values(decision_mode: str, execution_mode: str) -> dict[str, dict[str, Any]]:
    """Return current effective values for all configurable parameters."""
    gating = get_effective_gating_policy(decision_mode, execution_mode)
    limits = get_effective_risk_limits(execution_mode, decision_mode)
    sizing = get_effective_sizing(decision_mode, execution_mode)

    return {
        "gating": {
            "min_combined_score": gating.min_combined_score,
            "min_confidence": gating.min_confidence,
            "min_aligned_sources": gating.min_aligned_sources,
            "allow_technical_single_source_override": gating.allow_technical_single_source_override,
        },
        "risk_limits": {
            "max_risk_per_trade_pct": limits.max_risk_per_trade_pct,
            "max_daily_loss_pct": limits.max_daily_loss_pct,
            "max_open_risk_pct": limits.max_open_risk_pct,
            "max_positions": limits.max_positions,
            "max_positions_per_symbol": limits.max_positions_per_symbol,
            "min_free_margin_pct": limits.min_free_margin_pct,
            "max_currency_notional_exposure_pct_warn": limits.max_currency_notional_exposure_pct_warn,
            "max_currency_notional_exposure_pct_block": limits.max_currency_notional_exposure_pct_block,
            "max_currency_open_risk_pct": limits.max_currency_open_risk_pct,
            "max_weekly_loss_pct": limits.max_weekly_loss_pct,
        },
        "sizing": sizing,
    }
