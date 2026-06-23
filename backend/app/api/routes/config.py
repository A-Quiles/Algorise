"""Configuración del bot editable desde la UI (personalizar sin tocar código)."""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.backtest.engine import run_backtest
from app.bot.engine import engine
from app.core.presets import PRESET_DESCRIPTIONS, RISK_PRESETS
from app.db.database import get_db
from app.db.models import Account, SavedConfig
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


# --- Configuraciones guardadas (biblioteca personal del usuario) ---


class SaveConfigRequest(BaseModel):
    name: str
    config: BotConfig | None = None  # nulo = guarda la configuración activa actual
    note: str | None = None
    source: str | None = "manual"  # manual | optimizer
    # Autobacktest
    auto_backtest_enabled: bool = False
    auto_backtest_symbol: str = "BTC/USDT"
    auto_backtest_days: int = 90


def _saved_to_dict(row: SavedConfig) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "note": row.note,
        "source": row.source,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "config": row.config_json,
        "auto_backtest_enabled": row.auto_backtest_enabled,
        "auto_backtest_symbol": row.auto_backtest_symbol,
        "auto_backtest_days": row.auto_backtest_days,
    }


@router.get("/saved")
def list_saved(db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(SavedConfig).order_by(SavedConfig.created_at.desc())).all()
    return [_saved_to_dict(r) for r in rows]


@router.post("/saved")
def create_saved(req: SaveConfigRequest, db: Session = Depends(get_db)) -> dict:
    config = req.config or settings_service.get_config(db)
    row = SavedConfig(
        name=(req.name or "").strip() or "Sin nombre",
        config_json=config.model_dump(),
        note=req.note,
        source=req.source or "manual",
        auto_backtest_enabled=req.auto_backtest_enabled,
        auto_backtest_symbol=req.auto_backtest_symbol,
        auto_backtest_days=req.auto_backtest_days,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _saved_to_dict(row)


class ApplySavedResponse(BaseModel):
    config: BotConfig
    backtest_result: dict | None = None


@router.post("/saved/{saved_id}/apply", response_model=ApplySavedResponse)
def apply_saved(saved_id: int, db: Session = Depends(get_db)) -> ApplySavedResponse:
    row = db.get(SavedConfig, saved_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Configuración guardada no encontrada.")
    config = BotConfig.model_validate(row.config_json)
    saved = settings_service.save_config(db, config)
    _apply_side_effects(db, saved)

    # Ejecutar backtesting automático si está habilitado
    backtest_result = None
    if row.auto_backtest_enabled:
        try:
            since_ms = int(time.time() * 1000) - row.auto_backtest_days * 86_400_000
            backtest_result = run_backtest(
                symbol=row.auto_backtest_symbol,
                timeframe=saved.timeframe,
                strategy_id=saved.active_strategy,
                strategy_params=saved.strategy_params,
                risk=saved.risk,
                since_ms=since_ms,
                starting_capital=saved.starting_capital,
                fee_pct=saved.fee_pct,
                slippage_pct=saved.slippage_pct,
                execution=saved.execution,
            ).to_dict()
        except Exception as exc:  # noqa: BLE001
            # El backtesting automático no debe fallar la aplicación de config
            backtest_result = {"error": str(exc)}

    return ApplySavedResponse(config=saved, backtest_result=backtest_result)


class UpdateSavedRequest(BaseModel):
    name: str | None = None
    note: str | None = None
    auto_backtest_enabled: bool | None = None
    auto_backtest_symbol: str | None = None
    auto_backtest_days: int | None = None


@router.put("/saved/{saved_id}")
def update_saved(saved_id: int, req: UpdateSavedRequest, db: Session = Depends(get_db)) -> dict:
    row = db.get(SavedConfig, saved_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Configuración guardada no encontrada.")
    if req.name is not None:
        row.name = req.name.strip() or row.name
    if req.note is not None:
        row.note = req.note
    if req.auto_backtest_enabled is not None:
        row.auto_backtest_enabled = req.auto_backtest_enabled
    if req.auto_backtest_symbol is not None:
        row.auto_backtest_symbol = req.auto_backtest_symbol
    if req.auto_backtest_days is not None:
        row.auto_backtest_days = max(1, req.auto_backtest_days)
    db.commit()
    db.refresh(row)
    return _saved_to_dict(row)


@router.delete("/saved/{saved_id}")
def delete_saved(saved_id: int, db: Session = Depends(get_db)) -> dict:
    row = db.get(SavedConfig, saved_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Configuración guardada no encontrada.")
    db.delete(row)
    db.commit()
    return {"deleted": saved_id}
