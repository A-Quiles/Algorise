"""Proveedor de datos de mercado (Binance vía ccxt).

Datos públicos: precios en tiempo real (ticker) e histórico de velas (OHLCV). No
requiere claves para paper trading. La capa está aislada para, en el futuro, soportar
dinero real (mismas llamadas + claves) o multi-exchange sin tocar el resto del bot.
"""

from __future__ import annotations

import logging
import time

import ccxt
import pandas as pd

from app.core.config import get_settings

logger = logging.getLogger("algorise.market")

# Velas -> milisegundos, para paginar histórico.
_TIMEFRAME_MS = {
    "1m": 60_000,
    "5m": 5 * 60_000,
    "15m": 15 * 60_000,
    "30m": 30 * 60_000,
    "1h": 60 * 60_000,
    "4h": 4 * 60 * 60_000,
    "1d": 24 * 60 * 60_000,
}

OHLCV_COLUMNS = ["timestamp", "open", "high", "low", "close", "volume"]


class MarketDataProvider:
    """Envoltorio fino sobre ccxt para los datos que necesita el bot."""

    def __init__(self, exchange_id: str, api_key: str = "", api_secret: str = "") -> None:
        exchange_class = getattr(ccxt, exchange_id)
        params: dict = {"enableRateLimit": True}
        if api_key and api_secret:
            params["apiKey"] = api_key
            params["secret"] = api_secret
        self.exchange = exchange_class(params)
        self.exchange_id = exchange_id

    # --- Precio actual ---
    def fetch_price(self, symbol: str) -> float:
        """Último precio de mercado de un par (p.ej. 'BTC/USDT')."""
        ticker = self.exchange.fetch_ticker(symbol)
        return float(ticker["last"])

    def fetch_prices(self, symbols: list[str]) -> dict[str, float]:
        """Precios de varios pares. Cae a llamadas individuales si el exchange no soporta el lote."""
        try:
            tickers = self.exchange.fetch_tickers(symbols)
            return {s: float(t["last"]) for s, t in tickers.items()}
        except Exception:  # noqa: BLE001
            return {s: self.fetch_price(s) for s in symbols}

    # --- Velas (OHLCV) ---
    def fetch_ohlcv(self, symbol: str, timeframe: str = "5m", limit: int = 300) -> pd.DataFrame:
        """Últimas `limit` velas como DataFrame (para calcular indicadores en vivo)."""
        raw = self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        return self._to_dataframe(raw)

    def fetch_ohlcv_history(
        self, symbol: str, timeframe: str, since_ms: int, until_ms: int | None = None
    ) -> pd.DataFrame:
        """Histórico paginado entre dos fechas (epoch ms). Para backtesting."""
        until_ms = until_ms or self.exchange.milliseconds()
        step = _TIMEFRAME_MS.get(timeframe, 5 * 60_000)
        all_rows: list[list] = []
        cursor = since_ms
        while cursor < until_ms:
            batch = self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=cursor, limit=1000)
            if not batch:
                break
            all_rows.extend(batch)
            cursor = batch[-1][0] + step
            if len(batch) < 1000:
                break
            time.sleep(self.exchange.rateLimit / 1000)  # respeta el rate limit
        df = self._to_dataframe(all_rows)
        return df[df["timestamp"] <= until_ms].reset_index(drop=True)

    def list_symbols(self, quote: str | None = None) -> list[str]:
        """Pares disponibles, opcionalmente filtrados por moneda de cotización (p.ej. USDT)."""
        markets = self.exchange.load_markets()
        symbols = sorted(markets.keys())
        if quote:
            symbols = [s for s in symbols if s.endswith(f"/{quote}")]
        return symbols

    @staticmethod
    def _to_dataframe(rows: list[list]) -> pd.DataFrame:
        df = pd.DataFrame(rows, columns=OHLCV_COLUMNS)
        df = df.astype({c: "float64" for c in ["open", "high", "low", "close", "volume"]})
        df["timestamp"] = df["timestamp"].astype("int64")
        df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        return df


_provider: MarketDataProvider | None = None


def get_market_provider() -> MarketDataProvider:
    """Singleton del proveedor de mercado, construido desde la config de entorno."""
    global _provider
    if _provider is None:
        settings = get_settings()
        _provider = MarketDataProvider(
            exchange_id=settings.exchange_id,
            api_key=settings.exchange_api_key,
            api_secret=settings.exchange_api_secret,
        )
    return _provider
