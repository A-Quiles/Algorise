"""Historial y control manual: posiciones, señales, logs y acciones sobre operaciones."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.bot.engine import engine
from app.db.database import get_db
from app.db.models import LogEntry, Position, Signal
from app.market.provider import get_market_provider
from app.services.serializers import log_to_dict, position_to_dict, signal_to_dict
from app.services.settings_service import get_config
from app.trading.broker import PaperBroker

router = APIRouter(tags=["history"], dependencies=[Depends(get_current_user)])


@router.get("/positions")
def open_positions(db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(Position).where(Position.status == "open").order_by(desc(Position.opened_at))).all()
    return [position_to_dict(p) for p in rows]


@router.get("/trades")
def closed_trades(limit: int = Query(100, ge=1, le=1000), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(
        select(Position).where(Position.status == "closed").order_by(desc(Position.closed_at)).limit(limit)
    ).all()
    return [position_to_dict(p) for p in rows]


@router.get("/signals")
def signals(limit: int = Query(100, ge=1, le=1000), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(Signal).order_by(desc(Signal.timestamp)).limit(limit)).all()
    return [signal_to_dict(s) for s in rows]


@router.get("/logs")
def logs(limit: int = Query(100, ge=1, le=1000), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(LogEntry).order_by(desc(LogEntry.timestamp)).limit(limit)).all()
    return [log_to_dict(log) for log in rows]


# --- Control manual de posiciones (intervención del usuario en caliente) ---


def _open_or_404(db: Session, position_id: int) -> Position:
    pos = db.get(Position, position_id)
    if pos is None or pos.status != "open":
        raise HTTPException(status_code=404, detail="Posición abierta no encontrada.")
    return pos


@router.post("/positions/{position_id}/close")
async def close_position(position_id: int, db: Session = Depends(get_db)) -> dict:
    """Cierra una posición concreta a precio de mercado (acción manual del usuario)."""
    pos = _open_or_404(db, position_id)
    config = get_config(db)
    provider = get_market_provider()
    try:
        price = provider.fetch_price(pos.symbol)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"No se pudo obtener el precio: {exc}") from exc
    broker = PaperBroker(config.fee_pct, config.slippage_pct)
    broker.close_position(db, pos, price, "cierre manual")
    db.add(LogEntry(level="info", message=f"Cierre manual de {pos.symbol}: P&L {pos.pnl:.2f}",
                    context={"symbol": pos.symbol, "manual": True}))
    db.commit()
    await engine.broadcast_state()
    return position_to_dict(pos)


class AdjustStopsRequest(BaseModel):
    stop_loss: float | None = None
    take_profit: float | None = None


@router.patch("/positions/{position_id}/stops")
async def adjust_stops(position_id: int, req: AdjustStopsRequest, db: Session = Depends(get_db)) -> dict:
    """Ajusta manualmente el stop-loss y/o take-profit de una posición abierta."""
    pos = _open_or_404(db, position_id)
    if req.stop_loss is not None:
        if req.stop_loss <= 0:
            raise HTTPException(status_code=422, detail="El stop-loss debe ser positivo.")
        pos.stop_loss = req.stop_loss
    if req.take_profit is not None:
        if req.take_profit <= 0:
            raise HTTPException(status_code=422, detail="El take-profit debe ser positivo.")
        pos.take_profit = req.take_profit
    db.add(LogEntry(level="info", message=f"Stops ajustados manualmente en {pos.symbol}",
                    context={"symbol": pos.symbol, "stop_loss": pos.stop_loss, "take_profit": pos.take_profit}))
    db.commit()
    await engine.broadcast_state()
    return position_to_dict(pos)
