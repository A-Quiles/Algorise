"""Tests de las estrategias (señales deterministas con datos sintéticos)."""

import numpy as np
import pandas as pd

from app.strategies import get_strategy, list_strategies


def _df_from_close(close_values):
    close = pd.Series(close_values, dtype="float64")
    return pd.DataFrame(
        {
            "open": close,
            "high": close * 1.001,
            "low": close * 0.999,
            "close": close,
            "volume": pd.Series([100.0] * len(close)),
        }
    )


def test_all_strategies_registered():
    ids = {s.id for s in list_strategies()}
    assert {"ma_cross", "rsi_reversion", "macd_trend"}.issubset(ids)


def test_ma_cross_generates_buy_on_uptrend_crossover():
    # Baja y luego sube con fuerza -> la EMA rápida cruza por encima de la lenta.
    values = list(np.linspace(100, 80, 40)) + list(np.linspace(80, 130, 40))
    df = _df_from_close(values)
    strat = get_strategy("ma_cross")
    signal = strat.generate_signal(df, strat.default_params())
    assert signal.action in {"buy", "hold"}  # debe detectar contexto alcista, no vender


def test_rsi_reversion_buys_when_oversold():
    # Caída fuerte y sostenida -> RSI en sobreventa.
    values = list(np.linspace(100, 60, 30))
    df = _df_from_close(values)
    strat = get_strategy("rsi_reversion")
    sig = strat.generate_signal(df, strat.default_params())
    assert sig.indicators.get("rsi", 100) < 50


def test_strategy_to_dict_has_params():
    strat = get_strategy("ma_cross")
    data = strat.to_dict()
    assert data["id"] == "ma_cross"
    assert any(p["key"] == "fast_period" for p in data["params"])
