"""Configuración del bot editable desde la UI (personalizar sin tocar código)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.bot.engine import engine
from app.core.presets import PRESET_DESCRIPTIONS, RISK_PRESETS
from app.db.database import get_db
from app.db.models import BotState
from app.schemas.config import BotConfig
from app.services import settings_service

router = APIRouter(prefix="/config", tags=["config"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=BotConfig)
def read_config(db: Session = Depends(get_db)) -> BotConfig:
    return settings_service.get_config(db)


@router.put("", response_model=BotConfig)
def replace_config(config: BotConfig, db: Session = Depends(get_db)) -> BotConfig:
    saved = settings_service.save_config(db, config)
    # Si cambia el timeframe y el bot está activo, reprograma el ciclo.
    engine.reschedule(saved.timeframe)
    return saved


@router.patch("", response_model=BotConfig)
def patch_config(patch: dict, db: Session = Depends(get_db)) -> BotConfig:
    try:
        saved = settings_service.update_config(db, patch)
    except Exception as exc:  # noqa: BLE001  (errores de validación de Pydantic)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    engine.reschedule(saved.timeframe)
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
