"""Analítica de operaciones: atribución del rendimiento por estrategia, símbolo, etc."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.database import get_db
from app.services.analytics import build_analytics

router = APIRouter(prefix="/analytics", tags=["analytics"], dependencies=[Depends(get_current_user)])


@router.get("")
def analytics(db: Session = Depends(get_db)) -> dict:
    return build_analytics(db)
