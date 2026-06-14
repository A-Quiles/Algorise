"""Control del bot: arrancar, parar, pausar, kill switch y reiniciar la cuenta virtual."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.bot.engine import engine
from app.db.database import get_db
from app.db.models import Account, BotState, LogEntry, PortfolioSnapshot, Position, Signal
from app.services import settings_service

router = APIRouter(prefix="/bot", tags=["bot"], dependencies=[Depends(get_current_user)])


def _state(db: Session) -> dict:
    s = db.get(BotState, 1)
    return {
        "status": s.status,
        "mode": s.mode,
        "kill_switch": s.kill_switch,
        "started_at": s.started_at.isoformat() if s.started_at else None,
        "last_cycle_at": s.last_cycle_at.isoformat() if s.last_cycle_at else None,
        "last_error": s.last_error,
    }


@router.get("/status")
def status(db: Session = Depends(get_db)) -> dict:
    return _state(db)


@router.post("/start")
async def start(db: Session = Depends(get_db)) -> dict:
    await engine.start()
    return _state(db)


@router.post("/stop")
async def stop(db: Session = Depends(get_db)) -> dict:
    await engine.stop()
    return _state(db)


@router.post("/pause")
async def pause(db: Session = Depends(get_db)) -> dict:
    await engine.pause()
    return _state(db)


@router.post("/resume")
async def resume(db: Session = Depends(get_db)) -> dict:
    await engine.resume()
    return _state(db)


@router.post("/kill")
async def kill(db: Session = Depends(get_db)) -> dict:
    await engine.kill()
    return _state(db)


class ResetRequest(BaseModel):
    starting_capital: float | None = None


@router.post("/reset")
async def reset_account(payload: ResetRequest, db: Session = Depends(get_db)) -> dict:
    """Borra el historial y reinicia la cartera virtual al capital inicial. Para el bot."""
    await engine.stop()
    config = settings_service.get_config(db)
    capital = payload.starting_capital or config.starting_capital

    db.execute(delete(Position))
    db.execute(delete(Signal))
    db.execute(delete(PortfolioSnapshot))
    db.execute(delete(LogEntry))

    account = db.get(Account, 1)
    account.cash_balance = capital
    account.initial_capital = capital
    account.realized_pnl = 0.0
    account.peak_equity = capital
    account.base_currency = config.base_currency
    account.reset_at = datetime.now(timezone.utc)

    state = db.get(BotState, 1)
    state.status = "stopped"
    state.kill_switch = False
    state.last_error = None
    state.last_cycle_at = None
    db.commit()
    return {"ok": True, "starting_capital": capital}
