"""Historial: posiciones abiertas/cerradas, señales (diario de decisiones) y logs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.database import get_db
from app.db.models import LogEntry, Position, Signal
from app.services.serializers import log_to_dict, position_to_dict, signal_to_dict

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
