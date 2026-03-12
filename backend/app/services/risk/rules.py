from dataclasses import dataclass


@dataclass
class RiskAssessment:
    accepted: bool
    reasons: list[str]
    suggested_volume: float


class RiskEngine:
    def evaluate(
        self,
        mode: str,
        decision: str,
        risk_percent: float,
        price: float,
        stop_loss: float | None,
        equity: float = 10000.0,
    ) -> RiskAssessment:
        reasons: list[str] = []

        if decision == 'HOLD':
            return RiskAssessment(accepted=True, reasons=['No trade requested (HOLD).'], suggested_volume=0.0)

        if stop_loss is None:
            return RiskAssessment(accepted=False, reasons=['Stop loss is mandatory.'], suggested_volume=0.0)

        max_risk = {'simulation': 5.0, 'paper': 3.0, 'live': 2.0}.get(mode, 2.0)
        if risk_percent > max_risk:
            reasons.append(f'Risk percent {risk_percent}% exceeds mode limit {max_risk}% for {mode}.')

        stop_distance = abs(price - stop_loss)
        if stop_distance <= 0:
            reasons.append('Stop loss distance must be > 0.')

        if stop_distance / price < 0.0005:
            reasons.append('Stop loss is too tight for FX volatility.')

        risk_amount = equity * (risk_percent / 100)
        pip_value_per_lot = 10.0
        sl_pips = max(stop_distance * 10000, 0.1)
        suggested_volume = max(min(risk_amount / (sl_pips * pip_value_per_lot), 2.0), 0.01)

        accepted = len(reasons) == 0
        if accepted:
            reasons.append('Risk checks passed.')

        return RiskAssessment(accepted=accepted, reasons=reasons, suggested_volume=round(suggested_volume, 2))
