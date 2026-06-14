"""Estado completo del panel (cartera, posiciones, trades, señales, curva de equity)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.database import get_db
from app.market.provider import get_market_provider
from app.services.dashboard import build_payload
from app.services.settings_service import get_config

router = APIRouter(tags=["dashboard"], dependencies=[Depends(get_current_user)])


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db)) -> dict:
    config = get_config(db)
    try:
        prices = get_market_provider().fetch_prices(config.pairs)
    except Exception:  # noqa: BLE001  (sin red, devolvemos el panel con lo que haya)
        prices = {}
    return build_payload(db, prices)
