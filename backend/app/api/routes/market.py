"""Datos de mercado para la UI: precio actual, velas (para el gráfico) y lista de pares."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_current_user
from app.market.provider import get_market_provider

router = APIRouter(prefix="/market", tags=["market"], dependencies=[Depends(get_current_user)])


@router.get("/price/{base}/{quote}")
def price(base: str, quote: str) -> dict:
    symbol = f"{base.upper()}/{quote.upper()}"
    try:
        return {"symbol": symbol, "price": get_market_provider().fetch_price(symbol)}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Error obteniendo precio: {exc}") from exc


@router.get("/ohlcv")
def ohlcv(
    symbol: str = Query(..., description="Par, p.ej. BTC/USDT"),
    timeframe: str = Query("5m"),
    limit: int = Query(300, ge=10, le=1000),
) -> list[dict]:
    try:
        df = get_market_provider().fetch_ohlcv(symbol, timeframe, limit)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Error obteniendo velas: {exc}") from exc
    return [
        {
            "time": int(row.timestamp // 1000),  # segundos (formato lightweight-charts)
            "open": row.open,
            "high": row.high,
            "low": row.low,
            "close": row.close,
            "volume": row.volume,
        }
        for row in df.itertuples(index=False)
    ]


@router.get("/symbols")
def symbols(quote: str = Query("USDT")) -> list[str]:
    try:
        return get_market_provider().list_symbols(quote=quote.upper())
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Error listando pares: {exc}") from exc
