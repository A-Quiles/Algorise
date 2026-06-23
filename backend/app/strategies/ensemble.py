"""Ensemble de estrategias: combina varias señales por votación ponderada.

En vez de depender de una sola estrategia, el bot puede ejecutar N estrategias en
paralelo (cada una con su peso) y combinar sus votos. Esto suele dar señales más
robustas: una entrada solo se confirma si varias estrategias coinciden.

Es una función pura sobre DataFrames, así que la usa tanto el bot en vivo como el
backtesting sin cambios.
"""

from __future__ import annotations

import pandas as pd

from app.schemas.config import EnsembleConfig
from app.strategies.base import Signal, get_strategy


def _vote(df: pd.DataFrame, item_id: str, params: dict) -> tuple[Signal, str]:
    """Ejecuta una estrategia del ensemble; devuelve su señal y su id (tolerante a fallos)."""
    try:
        strat = get_strategy(item_id)
    except KeyError:
        return Signal("hold", 0.0, f"estrategia '{item_id}' desconocida"), item_id
    resolved = strat.resolve_params(params)
    return strat.generate_signal(df, resolved), strat.id


def generate_ensemble_signal(df: pd.DataFrame, cfg: EnsembleConfig) -> Signal:
    """Combina las estrategias del ensemble en una sola señal por votación ponderada.

    Cada estrategia aporta `peso * fuerza` a favor de su acción (buy/sell). Se normaliza
    por el peso total y se decide según los umbrales configurados. La señal resultante
    guarda el desglose de votos en `indicators` para poder explicarla.
    """
    active = [s for s in cfg.strategies if s.weight > 0]
    if not active:
        return Signal("hold", 0.0, "Ensemble sin estrategias.", {})

    total_weight = sum(s.weight for s in active)
    buy_score = 0.0
    sell_score = 0.0
    breakdown: list[dict] = []

    for item in active:
        signal, sid = _vote(df, item.id, item.params)
        contribution = item.weight * max(0.0, min(1.0, signal.strength or 0.0))
        if signal.action == "buy":
            buy_score += contribution
        elif signal.action == "sell":
            sell_score += contribution
        breakdown.append({
            "strategy": sid,
            "weight": item.weight,
            "action": signal.action,
            "strength": round(float(signal.strength or 0.0), 3),
            "reason": signal.reason,
        })

    buy_norm = buy_score / total_weight if total_weight else 0.0
    sell_norm = sell_score / total_weight if total_weight else 0.0
    indicators = {
        "ensemble": True,
        "buy_score": round(buy_norm, 3),
        "sell_score": round(sell_norm, 3),
        "votes": breakdown,
    }

    n_buy = sum(1 for b in breakdown if b["action"] == "buy")
    n_sell = sum(1 for b in breakdown if b["action"] == "sell")

    if buy_norm >= cfg.buy_threshold and buy_norm > sell_norm:
        reason = f"Ensemble: {n_buy}/{len(active)} estrategias compran (voto {buy_norm:.0%})."
        return Signal("buy", buy_norm, reason, indicators)
    if sell_norm >= cfg.sell_threshold and sell_norm > buy_norm:
        reason = f"Ensemble: {n_sell}/{len(active)} estrategias venden (voto {sell_norm:.0%})."
        return Signal("sell", sell_norm, reason, indicators)

    return Signal("hold", max(buy_norm, sell_norm), "Ensemble sin consenso suficiente.", indicators)
