"""Tests de los indicadores técnicos."""

import pandas as pd

from app.indicators import ta


def _series(values):
    return pd.Series(values, dtype="float64")


def test_sma():
    s = _series([1, 2, 3, 4, 5])
    result = ta.sma(s, 3)
    assert result.iloc[-1] == 4.0  # media de 3,4,5


def test_rsi_bounds():
    # Serie estrictamente creciente -> RSI alto (cercano a 100)
    s = _series(list(range(1, 60)))
    rsi = ta.rsi(s, 14)
    assert rsi.iloc[-1] > 90


def test_ema_responds_faster_than_sma():
    s = _series([10] * 20 + [20] * 20)
    ema = ta.ema(s, 10)
    sma = ta.sma(s, 10)
    # Tras el salto, la EMA debe estar por encima de la SMA (reacciona antes).
    assert ema.iloc[25] > sma.iloc[25]


def test_macd_shapes():
    s = _series(list(range(1, 100)))
    macd_line, signal_line, hist = ta.macd(s)
    assert len(macd_line) == len(s)
    assert len(signal_line) == len(s)
    assert len(hist) == len(s)


def test_atr_positive():
    df = pd.DataFrame(
        {
            "high": [10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25],
            "low": [9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24],
            "close": [9.5, 10.5, 11.5, 12.5, 13.5, 14.5, 15.5, 16.5, 17.5, 18.5, 19.5, 20.5, 21.5, 22.5, 23.5, 24.5],
        }
    )
    atr = ta.atr(df, 14)
    assert atr.iloc[-1] > 0
