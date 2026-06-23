"""Resuelve qué señal usar según la config: estrategia única o ensemble ponderado.

Centraliza la decisión para que el motor del bot no tenga que saber si está operando
con una sola estrategia o con varias combinadas.
"""

from __future__ import annotations

import pandas as pd

from app.schemas.config import BotConfig
from app.strategies.base import Signal, get_strategy
from app.strategies.ensemble import generate_ensemble_signal


def resolve_signal(df: pd.DataFrame, config: BotConfig) -> tuple[Signal, str]:
    """Devuelve (señal, etiqueta_de_estrategia) según la configuración activa."""
    ens = config.ensemble
    if ens.enabled and any(s.weight > 0 for s in ens.strategies):
        return generate_ensemble_signal(df, ens), "ensemble"
    strat = get_strategy(config.active_strategy)
    params = strat.resolve_params(config.strategy_params)
    return strat.generate_signal(df, params), strat.id
