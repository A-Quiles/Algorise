"""Indicadores técnicos calculados con pandas/numpy puro.

Implementación propia (sin pandas-ta) para máxima robustez en Windows con numpy 2.x.
Todas las funciones reciben una Serie de precios (normalmente 'close') y devuelven Series.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def sma(series: pd.Series, period: int) -> pd.Series:
    """Media móvil simple."""
    return series.rolling(window=period, min_periods=period).mean()


def ema(series: pd.Series, period: int) -> pd.Series:
    """Media móvil exponencial."""
    return series.ewm(span=period, adjust=False, min_periods=period).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Índice de fuerza relativa (0-100). Suavizado de Wilder."""
    delta = series.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    out = 100 - (100 / (1 + rs))
    return out.fillna(100.0)  # si no hay pérdidas, RSI = 100


def macd(
    series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Devuelve (línea MACD, línea de señal, histograma)."""
    macd_line = ema(series, fast) - ema(series, slow)
    signal_line = macd_line.ewm(span=signal, adjust=False, min_periods=signal).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def bollinger(series: pd.Series, period: int = 20, std: float = 2.0) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Devuelve (banda superior, media, banda inferior)."""
    middle = sma(series, period)
    deviation = series.rolling(window=period, min_periods=period).std()
    upper = middle + std * deviation
    lower = middle - std * deviation
    return upper, middle, lower


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average True Range (volatilidad). Usa columnas high/low/close del DataFrame."""
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    true_range = pd.concat(
        [(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    return true_range.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()


def stochastic(
    df: pd.DataFrame, k_period: int = 14, d_period: int = 3, smooth_k: int = 3
) -> tuple[pd.Series, pd.Series]:
    """Oscilador estocástico. Devuelve (%K suavizado, %D). Rango 0-100."""
    low_min = df["low"].rolling(window=k_period, min_periods=k_period).min()
    high_max = df["high"].rolling(window=k_period, min_periods=k_period).max()
    raw_k = 100 * (df["close"] - low_min) / (high_max - low_min).replace(0.0, np.nan)
    k = raw_k.rolling(window=smooth_k, min_periods=smooth_k).mean()
    d = k.rolling(window=d_period, min_periods=d_period).mean()
    return k.fillna(50.0), d.fillna(50.0)


def donchian(df: pd.DataFrame, period: int = 20) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Canal de Donchian. Devuelve (máximo, medio, mínimo) de las últimas `period` velas."""
    upper = df["high"].rolling(window=period, min_periods=period).max()
    lower = df["low"].rolling(window=period, min_periods=period).min()
    middle = (upper + lower) / 2
    return upper, middle, lower
