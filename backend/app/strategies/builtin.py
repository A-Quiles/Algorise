"""Estrategias incluidas de serie. Todas se autoregistran al importar el módulo."""

from __future__ import annotations

import pandas as pd

from app.indicators import ta
from app.strategies.base import ParamSpec, Signal, Strategy, register


@register
class MACrossStrategy(Strategy):
    id = "ma_cross"
    name = "Cruce de medias (EMA)"
    description = (
        "Compra cuando la media rápida cruza por encima de la lenta (tendencia alcista) y "
        "vende cuando la cruza por debajo. Estrategia de seguimiento de tendencia clásica."
    )
    params = [
        ParamSpec("fast_period", "Media rápida", "int", 9, 2, 100, 1, "Periodo de la EMA rápida."),
        ParamSpec("slow_period", "Media lenta", "int", 21, 5, 300, 1, "Periodo de la EMA lenta."),
    ]

    def generate_signal(self, df: pd.DataFrame, params: dict) -> Signal:
        fast_p, slow_p = int(params["fast_period"]), int(params["slow_period"])
        if len(df) < slow_p + 2:
            return Signal("hold", 0.0, "Datos insuficientes.")
        fast = ta.ema(df["close"], fast_p)
        slow = ta.ema(df["close"], slow_p)
        f_now, f_prev = fast.iloc[-1], fast.iloc[-2]
        s_now, s_prev = slow.iloc[-1], slow.iloc[-2]
        ind = {"ema_fast": round(float(f_now), 4), "ema_slow": round(float(s_now), 4)}
        gap = abs(f_now - s_now) / s_now if s_now else 0.0
        strength = float(min(1.0, gap * 50))
        if f_prev <= s_prev and f_now > s_now:
            return Signal("buy", max(0.5, strength), f"Cruce alcista: EMA{fast_p} cruzó sobre EMA{slow_p}.", ind)
        if f_prev >= s_prev and f_now < s_now:
            return Signal("sell", max(0.5, strength), f"Cruce bajista: EMA{fast_p} cruzó bajo EMA{slow_p}.", ind)
        return Signal("hold", strength, "Sin cruce de medias.", ind)


@register
class RSIReversionStrategy(Strategy):
    id = "rsi_reversion"
    name = "Reversión por RSI"
    description = (
        "Compra cuando el RSI entra en sobreventa (rebote esperado) y vende cuando entra en "
        "sobrecompra. Estrategia de reversión a la media, mejor en mercados laterales."
    )
    params = [
        ParamSpec("rsi_period", "Periodo RSI", "int", 14, 2, 50, 1, "Periodo del RSI."),
        ParamSpec("oversold", "Sobreventa", "int", 30, 5, 45, 1, "Nivel de compra (RSI por debajo)."),
        ParamSpec("overbought", "Sobrecompra", "int", 70, 55, 95, 1, "Nivel de venta (RSI por encima)."),
    ]

    def generate_signal(self, df: pd.DataFrame, params: dict) -> Signal:
        period = int(params["rsi_period"])
        oversold, overbought = float(params["oversold"]), float(params["overbought"])
        if len(df) < period + 2:
            return Signal("hold", 0.0, "Datos insuficientes.")
        rsi = ta.rsi(df["close"], period)
        r_now, r_prev = float(rsi.iloc[-1]), float(rsi.iloc[-2])
        ind = {"rsi": round(r_now, 2)}
        if r_prev >= oversold and r_now < oversold:
            strength = float(min(1.0, (oversold - r_now) / oversold + 0.5))
            return Signal("buy", strength, f"RSI {r_now:.1f} en sobreventa (<{oversold:.0f}).", ind)
        if r_prev <= overbought and r_now > overbought:
            strength = float(min(1.0, (r_now - overbought) / (100 - overbought) + 0.5))
            return Signal("sell", strength, f"RSI {r_now:.1f} en sobrecompra (>{overbought:.0f}).", ind)
        return Signal("hold", 0.0, f"RSI {r_now:.1f} en zona neutra.", ind)


@register
class MACDTrendStrategy(Strategy):
    id = "macd_trend"
    name = "MACD con filtro de tendencia"
    description = (
        "Compra en cruce alcista del MACD solo si el precio está por encima de la media de "
        "tendencia (filtro). Vende en cruce bajista. Combina momentum y tendencia."
    )
    params = [
        ParamSpec("fast", "EMA rápida MACD", "int", 12, 2, 50, 1),
        ParamSpec("slow", "EMA lenta MACD", "int", 26, 5, 100, 1),
        ParamSpec("signal", "Señal MACD", "int", 9, 2, 50, 1),
        ParamSpec("trend_period", "Media de tendencia", "int", 200, 20, 400, 1, "Filtro: solo compra si precio > esta EMA."),
    ]

    def generate_signal(self, df: pd.DataFrame, params: dict) -> Signal:
        fast, slow, sig = int(params["fast"]), int(params["slow"]), int(params["signal"])
        trend_p = int(params["trend_period"])
        if len(df) < max(slow + sig, trend_p) + 2:
            return Signal("hold", 0.0, "Datos insuficientes.")
        macd_line, signal_line, hist = ta.macd(df["close"], fast, slow, sig)
        trend = ta.ema(df["close"], trend_p)
        price = float(df["close"].iloc[-1])
        m_now, m_prev = float(macd_line.iloc[-1]), float(macd_line.iloc[-2])
        s_now, s_prev = float(signal_line.iloc[-1]), float(signal_line.iloc[-2])
        hist_now = float(hist.iloc[-1])
        trend_now = float(trend.iloc[-1])
        uptrend = price > trend_now
        ind = {
            "macd": round(m_now, 4),
            "signal": round(s_now, 4),
            "hist": round(hist_now, 4),
            "trend_ema": round(trend_now, 4),
            "uptrend": bool(uptrend),
        }
        strength = float(min(1.0, abs(hist_now) / (abs(m_now) + 1e-9)))
        if m_prev <= s_prev and m_now > s_now and uptrend:
            return Signal("buy", max(0.5, strength), "Cruce alcista del MACD con precio en tendencia alcista.", ind)
        if m_prev >= s_prev and m_now < s_now:
            return Signal("sell", max(0.5, strength), "Cruce bajista del MACD.", ind)
        return Signal("hold", strength, "Sin señal MACD válida.", ind)
