"""Estrategias incluidas de serie. Todas se autoregistran al importar el módulo."""

from __future__ import annotations

import pandas as pd

from app.indicators import ta
from app.strategies.base import ParamSpec, Signal, Strategy, register

_INSUFFICIENT_DATA = "Datos insuficientes."


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
            return Signal("hold", 0.0, _INSUFFICIENT_DATA)
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
            return Signal("hold", 0.0, _INSUFFICIENT_DATA)
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
            return Signal("hold", 0.0, _INSUFFICIENT_DATA)
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


@register
class BollingerReversionStrategy(Strategy):
    id = "bollinger_reversion"
    name = "Reversión por Bandas de Bollinger"
    description = (
        "Compra cuando el precio rebota desde la banda inferior (sobreventa estadística) y vende "
        "al volver a la media o tocar la banda superior. Reversión a la media; rinde mejor en "
        "mercados laterales o en rango."
    )
    params = [
        ParamSpec("period", "Periodo", "int", 20, 5, 100, 1, "Periodo de la media y las bandas."),
        ParamSpec("std", "Desviaciones", "float", 2.0, 1.0, 4.0, 0.1, "Anchura de las bandas (nº de desviaciones típicas)."),
    ]

    def generate_signal(self, df: pd.DataFrame, params: dict) -> Signal:
        period, std = int(params["period"]), float(params["std"])
        if len(df) < period + 2:
            return Signal("hold", 0.0, _INSUFFICIENT_DATA)
        upper, middle, lower = ta.bollinger(df["close"], period, std)
        c_now, c_prev = float(df["close"].iloc[-1]), float(df["close"].iloc[-2])
        u, m, l = float(upper.iloc[-1]), float(middle.iloc[-1]), float(lower.iloc[-1])
        l_prev, m_prev = float(lower.iloc[-2]), float(middle.iloc[-2])
        ind = {"bb_upper": round(u, 4), "bb_middle": round(m, 4), "bb_lower": round(l, 4)}
        width = (u - l) / m if m else 0.0
        # Rebote alcista: el precio cierra de nuevo sobre la banda inferior tras caer bajo ella.
        if c_prev <= l_prev and c_now > l:
            return Signal("buy", 0.6, f"Rebote desde la banda inferior ({l:.2f}).", ind)
        # Salida: vuelta a la media o sobrecompra en la banda superior.
        if (c_prev < m_prev and c_now >= m) or c_now >= u:
            return Signal("sell", 0.6, "Precio de vuelta a la media / banda superior.", ind)
        return Signal("hold", float(min(1.0, width)), "Dentro de las bandas.", ind)


@register
class DonchianBreakoutStrategy(Strategy):
    id = "donchian_breakout"
    name = "Ruptura de canal (Donchian)"
    description = (
        "Compra cuando el precio rompe por encima del máximo de las últimas N velas (inicio de "
        "tendencia) y vende cuando rompe por debajo del mínimo de N velas. Seguimiento de "
        "tendencia y momentum; capta movimientos amplios."
    )
    params = [
        ParamSpec("period", "Periodo del canal", "int", 20, 5, 200, 1, "Nº de velas para el máximo/mínimo."),
    ]

    def generate_signal(self, df: pd.DataFrame, params: dict) -> Signal:
        period = int(params["period"])
        if len(df) < period + 2:
            return Signal("hold", 0.0, _INSUFFICIENT_DATA)
        # Canal de las N velas ANTERIORES (shift) para no incluir la vela actual en el máx/mín.
        upper_prev = df["high"].rolling(period, min_periods=period).max().shift(1)
        lower_prev = df["low"].rolling(period, min_periods=period).min().shift(1)
        close = float(df["close"].iloc[-1])
        up, lo = float(upper_prev.iloc[-1]), float(lower_prev.iloc[-1])
        ind = {"donchian_high": round(up, 4), "donchian_low": round(lo, 4)}
        if close > up:
            strength = float(min(1.0, (close - up) / up * 50)) if up else 0.6
            return Signal("buy", max(0.5, strength), f"Ruptura alcista sobre el máximo de {period} velas.", ind)
        if close < lo:
            strength = float(min(1.0, (lo - close) / lo * 50)) if lo else 0.6
            return Signal("sell", max(0.5, strength), f"Ruptura bajista bajo el mínimo de {period} velas.", ind)
        return Signal("hold", 0.0, "Dentro del canal.", ind)


@register
class StochasticStrategy(Strategy):
    id = "stochastic"
    name = "Oscilador estocástico"
    description = (
        "Compra cuando %K cruza por encima de %D viniendo de sobreventa y vende cuando %K cruza "
        "por debajo de %D en sobrecompra. Oscilador de momentum, útil en mercados en rango."
    )
    params = [
        ParamSpec("k_period", "Periodo %K", "int", 14, 3, 50, 1),
        ParamSpec("d_period", "Suavizado %D", "int", 3, 1, 20, 1),
        ParamSpec("smooth_k", "Suavizado %K", "int", 3, 1, 20, 1),
        ParamSpec("oversold", "Sobreventa", "int", 20, 5, 40, 1, "Nivel de %K para zona de compra."),
        ParamSpec("overbought", "Sobrecompra", "int", 80, 60, 95, 1, "Nivel de %K para zona de venta."),
    ]

    def generate_signal(self, df: pd.DataFrame, params: dict) -> Signal:
        k_p, d_p, sk = int(params["k_period"]), int(params["d_period"]), int(params["smooth_k"])
        oversold, overbought = float(params["oversold"]), float(params["overbought"])
        if len(df) < k_p + d_p + sk + 2:
            return Signal("hold", 0.0, _INSUFFICIENT_DATA)
        k, d = ta.stochastic(df, k_p, d_p, sk)
        k_now, k_prev = float(k.iloc[-1]), float(k.iloc[-2])
        d_now, d_prev = float(d.iloc[-1]), float(d.iloc[-2])
        ind = {"stoch_k": round(k_now, 2), "stoch_d": round(d_now, 2)}
        if k_prev <= d_prev and k_now > d_now and k_prev < oversold:
            return Signal("buy", 0.6, f"%K cruzó sobre %D saliendo de sobreventa ({k_now:.0f}).", ind)
        if k_prev >= d_prev and k_now < d_now and k_prev > overbought:
            return Signal("sell", 0.6, f"%K cruzó bajo %D en sobrecompra ({k_now:.0f}).", ind)
        return Signal("hold", 0.0, f"Estocástico %K {k_now:.0f}.", ind)


@register
class TrendPullbackStrategy(Strategy):
    id = "trend_pullback"
    name = "Tendencia + pullback (EMA & RSI)"
    description = (
        "Opera a favor de la tendencia: solo compra si el precio está por encima de la EMA de "
        "tendencia y el RSI se recupera tras un retroceso (pullback). Vende si el RSI se "
        "sobrecalienta o se pierde la tendencia. Combina tendencia y momentum."
    )
    params = [
        ParamSpec("ema_period", "EMA de tendencia", "int", 50, 10, 300, 1, "Filtro de tendencia (solo compra por encima)."),
        ParamSpec("rsi_period", "Periodo RSI", "int", 14, 2, 50, 1),
        ParamSpec("rsi_buy", "RSI de entrada", "int", 40, 10, 60, 1, "Umbral de pullback que, al recuperarse, da la compra."),
        ParamSpec("rsi_exit", "RSI de salida", "int", 70, 55, 95, 1, "Sobrecompra a la que se vende."),
    ]

    def generate_signal(self, df: pd.DataFrame, params: dict) -> Signal:
        ema_p, rsi_p = int(params["ema_period"]), int(params["rsi_period"])
        rsi_buy, rsi_exit = float(params["rsi_buy"]), float(params["rsi_exit"])
        if len(df) < max(ema_p, rsi_p) + 2:
            return Signal("hold", 0.0, _INSUFFICIENT_DATA)
        trend = ta.ema(df["close"], ema_p)
        rsi = ta.rsi(df["close"], rsi_p)
        price = float(df["close"].iloc[-1])
        trend_now = float(trend.iloc[-1])
        r_now, r_prev = float(rsi.iloc[-1]), float(rsi.iloc[-2])
        uptrend = price > trend_now
        ind = {"trend_ema": round(trend_now, 4), "rsi": round(r_now, 2), "uptrend": bool(uptrend)}
        # Pullback en tendencia alcista: el RSI vuelve a subir cruzando el umbral de entrada.
        if uptrend and r_prev <= rsi_buy and r_now > rsi_buy:
            return Signal("buy", 0.6, f"Pullback en tendencia alcista: RSI recupera {rsi_buy:.0f}.", ind)
        if (not uptrend) or r_now > rsi_exit:
            return Signal("sell", 0.55, "Tendencia perdida o RSI sobrecomprado.", ind)
        return Signal("hold", 0.0, "A la espera de un pullback en tendencia.", ind)
