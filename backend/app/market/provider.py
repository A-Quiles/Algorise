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

# TTL (segundos) de las cachés en memoria. Evitan repetir llamadas idénticas a Binance
# dentro de un mismo ciclo (precio + OHLCV de varios símbolos, snapshot, etc.).
_PRICE_TTL = 3.0
_OHLCV_TTL = 20.0

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
        # Cachés en memoria con TTL: {symbol: (monotónico, precio)} y {(symbol,tf,limit): (mono, df)}
        self._price_cache: dict[str, tuple[float, float]] = {}
        self._ohlcv_cache: dict[tuple[str, str, int], tuple[float, pd.DataFrame]] = {}

    # --- Priming de caché (lo usa el prefetch async para calentar antes del ciclo) ---
    def prime_price(self, symbol: str, price: float) -> None:
        self._price_cache[symbol] = (time.monotonic(), price)

    def prime_ohlcv(self, symbol: str, timeframe: str, limit: int, df: pd.DataFrame) -> None:
        self._ohlcv_cache[(symbol, timeframe, limit)] = (time.monotonic(), df)

    # --- Precio actual ---
    def fetch_price(self, symbol: str) -> float:
        """Último precio de mercado de un par (p.ej. 'BTC/USDT'). Cacheado por TTL corto."""
        cached = self._price_cache.get(symbol)
        if cached and (time.monotonic() - cached[0]) < _PRICE_TTL:
            return cached[1]
        ticker = self.exchange.fetch_ticker(symbol)
        price = float(ticker["last"])
        self._price_cache[symbol] = (time.monotonic(), price)
        return price

    def fetch_prices(self, symbols: list[str]) -> dict[str, float]:
        """Precios de varios pares. Sirve desde caché los recientes y agrupa el resto."""
        now = time.monotonic()
        result: dict[str, float] = {}
        missing: list[str] = []
        for s in symbols:
            cached = self._price_cache.get(s)
            if cached and (now - cached[0]) < _PRICE_TTL:
                result[s] = cached[1]
            else:
                missing.append(s)
        if not missing:
            return result
        try:
            tickers = self.exchange.fetch_tickers(missing)
            for s, t in tickers.items():
                price = float(t["last"])
                result[s] = price
                self._price_cache[s] = (now, price)
        except Exception:  # noqa: BLE001
            for s in missing:
                result[s] = self.fetch_price(s)
        return result

    # --- Velas (OHLCV) ---
    def fetch_ohlcv(self, symbol: str, timeframe: str = "5m", limit: int = 300) -> pd.DataFrame:
        """Últimas `limit` velas como DataFrame (para indicadores en vivo). Cacheado por TTL."""
        key = (symbol, timeframe, limit)
        cached = self._ohlcv_cache.get(key)
        if cached and (time.monotonic() - cached[0]) < _OHLCV_TTL:
            return cached[1]
        raw = self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        df = self._to_dataframe(raw)
        self._ohlcv_cache[key] = (time.monotonic(), df)
        return df

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


# --- Proveedor asíncrono (ccxt.async_support): paraleliza las llamadas de red ---

import asyncio  # noqa: E402

import ccxt.async_support as ccxt_async  # noqa: E402


class AsyncMarketProvider:
    """Versión asíncrona para descargar precios + velas de muchos pares en paralelo.

    Se usa para "calentar" la caché del proveedor síncrono antes del ciclo del bot: en vez
    de pedir los datos par a par (en serie), `asyncio.gather` lanza todas las llamadas a la
    vez. El resto del bot sigue siendo síncrono y lee de la caché ya poblada.
    """

    def __init__(self, exchange_id: str, api_key: str = "", api_secret: str = "") -> None:
        exchange_class = getattr(ccxt_async, exchange_id)
        params: dict = {"enableRateLimit": True}
        if api_key and api_secret:
            params["apiKey"] = api_key
            params["secret"] = api_secret
        self.exchange = exchange_class(params)

    async def fetch_bulk(
        self, symbols: list[str], timeframe: str, limit: int = 300
    ) -> tuple[dict[str, float], dict[str, pd.DataFrame]]:
        """Descarga, concurrentemente, los precios y las velas de todos los símbolos."""
        prices: dict[str, float] = {}
        try:
            tickers = await self.exchange.fetch_tickers(symbols)
            prices = {s: float(t["last"]) for s, t in tickers.items() if t.get("last") is not None}
        except Exception:  # noqa: BLE001
            logger.debug("fetch_tickers en lote falló; los precios se resolverán por símbolo")

        async def _one(sym: str) -> tuple[str, pd.DataFrame | None]:
            try:
                raw = await self.exchange.fetch_ohlcv(sym, timeframe=timeframe, limit=limit)
                return sym, MarketDataProvider._to_dataframe(raw)
            except Exception:  # noqa: BLE001
                return sym, None

        ohlcv: dict[str, pd.DataFrame] = {}
        for sym, df in await asyncio.gather(*[_one(s) for s in symbols]):
            if df is not None and not df.empty:
                ohlcv[sym] = df
                if sym not in prices:
                    prices[sym] = float(df["close"].iloc[-1])
        return prices, ohlcv

    async def close(self) -> None:
        try:
            await self.exchange.close()
        except Exception:  # noqa: BLE001
            pass


_async_provider: AsyncMarketProvider | None = None


def get_async_provider() -> AsyncMarketProvider:
    """Singleton del proveedor asíncrono (comparte la config de entorno con el síncrono)."""
    global _async_provider
    if _async_provider is None:
        settings = get_settings()
        _async_provider = AsyncMarketProvider(
            exchange_id=settings.exchange_id,
            api_key=settings.exchange_api_key,
            api_secret=settings.exchange_api_secret,
        )
    return _async_provider


async def close_async_provider() -> None:
    """Cierra la sesión aiohttp del proveedor asíncrono (llamar en el apagado)."""
    global _async_provider
    if _async_provider is not None:
        await _async_provider.close()
        _async_provider = None
