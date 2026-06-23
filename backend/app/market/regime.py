"""Análisis de contexto de mercado: régimen (tendencia) y correlaciones entre activos.

La capa de IA decide mejor si, además de la señal de una estrategia, conoce el "clima"
del mercado (alcista/bajista/lateral) y si el activo está muy correlacionado con lo que
ya tenemos en cartera (riesgo de clúster). Todo se calcula con pandas puro.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from app.indicators import ta


@dataclass
class MarketRegime:
    regime: str  # "bull" | "bear" | "sideways"
    trend_strength: float  # 0..1 (cuán marcada es la tendencia)
    volatility_pct: float  # ATR como % del precio
    momentum_pct: float  # variación % en la ventana reciente

    def to_dict(self) -> dict:
        return {
            "regime": self.regime,
            "trend_strength": round(self.trend_strength, 3),
            "volatility_pct": round(self.volatility_pct, 2),
            "momentum_pct": round(self.momentum_pct, 2),
        }


def detect_regime(df: pd.DataFrame, fast: int = 50, slow: int = 200) -> MarketRegime:
    """Clasifica el mercado en alcista/bajista/lateral a partir de las velas.

    Usa la separación entre dos EMAs (dirección y fuerza de la tendencia), el ATR
    normalizado (volatilidad) y el momentum reciente. Es robusto con poco histórico:
    si no llega para la EMA lenta, usa una ventana proporcional a los datos.
    """
    n = len(df)
    if n < 20:
        return MarketRegime("sideways", 0.0, 0.0, 0.0)

    slow = min(slow, max(10, n - 2))
    fast = min(fast, max(5, slow // 2))
    close = df["close"]
    price = float(close.iloc[-1])

    ema_fast = float(ta.ema(close, fast).iloc[-1])
    ema_slow = float(ta.ema(close, slow).iloc[-1])
    sep = (ema_fast - ema_slow) / ema_slow if ema_slow else 0.0  # separación relativa

    atr_val = float(ta.atr(df).iloc[-1]) if n > 15 else 0.0
    volatility_pct = atr_val / price * 100 if price else 0.0

    window = min(20, n - 1)
    past = float(close.iloc[-window])
    momentum_pct = (price / past - 1) * 100 if past else 0.0

    # Fuerza de tendencia: separación de EMAs escalada (saturada a 1).
    trend_strength = min(1.0, abs(sep) * 40)

    # Umbral relativo a la volatilidad: en mercados volátiles exige más separación.
    threshold = max(0.005, volatility_pct / 100 * 0.5)
    if sep > threshold and price > ema_slow:
        regime = "bull"
    elif sep < -threshold and price < ema_slow:
        regime = "bear"
    else:
        regime = "sideways"

    return MarketRegime(regime, trend_strength, volatility_pct, momentum_pct)


def _returns(df: pd.DataFrame) -> pd.Series:
    return df["close"].pct_change().dropna()


def correlation(df_a: pd.DataFrame, df_b: pd.DataFrame, window: int = 100) -> float:
    """Correlación de retornos entre dos activos (alineando por las últimas N velas).

    Devuelve un valor en [-1, 1]; 0 si no hay solape suficiente.
    """
    ra = _returns(df_a).tail(window).reset_index(drop=True)
    rb = _returns(df_b).tail(window).reset_index(drop=True)
    m = min(len(ra), len(rb))
    if m < 10:
        return 0.0
    corr = ra.tail(m).reset_index(drop=True).corr(rb.tail(m).reset_index(drop=True))
    if corr is None or pd.isna(corr):
        return 0.0
    return float(max(-1.0, min(1.0, corr)))


def correlated_symbols(
    candidate_df: pd.DataFrame,
    others: dict[str, pd.DataFrame],
    threshold: float,
    window: int = 100,
) -> list[tuple[str, float]]:
    """De entre `others`, los símbolos cuya correlación con el candidato supera el umbral."""
    hits: list[tuple[str, float]] = []
    for symbol, df in others.items():
        corr = correlation(candidate_df, df, window)
        if abs(corr) >= threshold:
            hits.append((symbol, round(corr, 3)))
    return sorted(hits, key=lambda x: -abs(x[1]))
