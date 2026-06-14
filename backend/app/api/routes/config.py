"""Configuración del bot editable desde la UI (personalizar sin tocar código)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.bot.engine import engine
from app.core.presets import PRESET_DESCRIPTIONS, RISK_PRESETS
from app.db.database import get_db
from app.db.models import Account
from app.schemas.config import BotConfig
from app.services import settings_service
from app.trading.portfolio import get_open_positions

router = APIRouter(prefix="/config", tags=["config"], dependencies=[Depends(get_current_user)])


def _apply_side_effects(db: Session, saved: BotConfig) -> None:
    """Tras guardar la config: reprograma el ciclo y, si procede, ajusta la cartera.

    Cambiar la moneda base solo se refleja en la cartera virtual si no hay posiciones
    abiertas (es dinero ficticio: se reetiqueta el saldo). Con posiciones abiertas, el
    cambio se aplica al "Reiniciar cuenta" en Ajustes.
    """
    engine.reschedule(saved.timeframe)
    account = db.get(Account, 1)
    if account and account.base_currency != saved.base_currency and not get_open_positions(db):
        account.base_currency = saved.base_currency
        db.commit()


@router.get("", response_model=BotConfig)
def read_config(db: Session = Depends(get_db)) -> BotConfig:
    return settings_service.get_config(db)


@router.put("", response_model=BotConfig)
def replace_config(config: BotConfig, db: Session = Depends(get_db)) -> BotConfig:
    saved = settings_service.save_config(db, config)
    _apply_side_effects(db, saved)
    return saved


@router.patch("", response_model=BotConfig)
def patch_config(patch: dict, db: Session = Depends(get_db)) -> BotConfig:
    try:
        saved = settings_service.update_config(db, patch)
    except Exception as exc:  # noqa: BLE001  (errores de validación de Pydantic)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    _apply_side_effects(db, saved)
    return saved


@router.get("/presets")
def list_presets() -> list[dict]:
    return [
        {"id": key, "description": PRESET_DESCRIPTIONS.get(key, ""), "risk": preset.model_dump()}
        for key, preset in RISK_PRESETS.items()
    ]


@router.post("/preset/{name}", response_model=BotConfig)
def apply_preset(name: str, db: Session = Depends(get_db)) -> BotConfig:
    try:
        return settings_service.apply_risk_preset(db, name)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
