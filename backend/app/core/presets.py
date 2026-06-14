"""Perfiles de riesgo de un clic: Conservador / Equilibrado / Agresivo.

El usuario aplica uno y luego puede afinar a mano. Solo tocan el bloque de riesgo y
algún parámetro asociado; el resto de la config se mantiene.
"""

from __future__ import annotations

from app.schemas.config import RiskConfig

RISK_PRESETS: dict[str, RiskConfig] = {
    "conservador": RiskConfig(
        risk_per_trade_pct=0.5,
        stop_loss_pct=1.5,
        take_profit_pct=3.0,
        use_atr_stops=False,
        trailing_stop_pct=1.0,
        max_open_positions=2,
        max_daily_loss_pct=2.0,
        max_drawdown_pct=10.0,
    ),
    "equilibrado": RiskConfig(
        risk_per_trade_pct=1.0,
        stop_loss_pct=2.0,
        take_profit_pct=4.0,
        use_atr_stops=False,
        trailing_stop_pct=None,
        max_open_positions=3,
        max_daily_loss_pct=5.0,
        max_drawdown_pct=20.0,
    ),
    "agresivo": RiskConfig(
        risk_per_trade_pct=2.5,
        stop_loss_pct=4.0,
        take_profit_pct=8.0,
        use_atr_stops=True,
        atr_multiplier=2.5,
        trailing_stop_pct=None,
        max_open_positions=6,
        max_daily_loss_pct=10.0,
        max_drawdown_pct=35.0,
    ),
}

PRESET_DESCRIPTIONS: dict[str, str] = {
    "conservador": "Riesgo bajo: posiciones pequeñas, stops ajustados y límites estrictos. Prioriza preservar capital.",
    "equilibrado": "Punto medio entre riesgo y rendimiento. Buen punto de partida por defecto.",
    "agresivo": "Riesgo alto: posiciones grandes, más operaciones simultáneas y mayor tolerancia a pérdidas.",
}
