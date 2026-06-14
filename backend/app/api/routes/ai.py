"""Insights de IA: comentario en lenguaje natural sobre el estado de un par."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.ai.advisor import market_commentary
from app.api.deps import get_current_user
from app.db.database import get_db
from app.indicators import ta
from app.market.provider import get_market_provider
from app.services.settings_service import get_config

router = APIRouter(prefix="/ai", tags=["ai"], dependencies=[Depends(get_current_user)])


@router.get("/commentary/{base}/{quote}")
def commentary(base: str, quote: str, db: Session = Depends(get_db)) -> dict:
    symbol = f"{base.upper()}/{quote.upper()}"
    config = get_config(db)
    try:
        df = get_market_provider().fetch_ohlcv(symbol, config.timeframe, limit=300)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Error obteniendo datos: {exc}") from exc

    close = df["close"]
    macd_line, signal_line, hist = ta.macd(close)
    indicators = {
        "price": round(float(close.iloc[-1]), 4),
        "rsi": round(float(ta.rsi(close).iloc[-1]), 2),
        "ema_fast": round(float(ta.ema(close, 9).iloc[-1]), 4),
        "ema_slow": round(float(ta.ema(close, 21).iloc[-1]), 4),
        "macd_hist": round(float(hist.iloc[-1]), 4),
    }
    text = market_commentary(symbol, indicators, config.llm)
    return {"symbol": symbol, "indicators": indicators, "commentary": text, "provider": config.llm.provider}
