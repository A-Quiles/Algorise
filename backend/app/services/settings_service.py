"""Servicio de configuración del bot: leer, guardar, fusionar y aplicar perfiles.

Es la pieza que hace posible "personalizar sin tocar código": la UI llama a estas
funciones a través de la API y la config se persiste en la tabla `settings`.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.presets import RISK_PRESETS
from app.db.models import Settings
from app.schemas.config import BotConfig


def get_config(db: Session) -> BotConfig:
    """Devuelve la config actual validada. Si no existe, crea la de por defecto."""
    row = db.get(Settings, 1)
    if row is None or not row.config_json:
        config = BotConfig()
        _persist(db, config)
        return config
    return BotConfig.model_validate(row.config_json)


def save_config(db: Session, config: BotConfig) -> BotConfig:
    """Sobrescribe la config completa (ya validada)."""
    _persist(db, config)
    return config


def update_config(db: Session, patch: dict) -> BotConfig:
    """Fusiona un parche parcial sobre la config actual y revalida.

    Soporta parches anidados, p.ej. {"risk": {"risk_per_trade_pct": 1.5}}.
    """
    current = get_config(db).model_dump()
    merged = _deep_merge(current, patch)
    config = BotConfig.model_validate(merged)  # lanza ValidationError si algo no cumple
    _persist(db, config)
    return config


def apply_risk_preset(db: Session, preset: str) -> BotConfig:
    """Aplica un perfil de riesgo (conservador/equilibrado/agresivo) a la config actual."""
    key = preset.lower().strip()
    if key not in RISK_PRESETS:
        raise ValueError(f"Perfil desconocido: {preset}. Opciones: {list(RISK_PRESETS)}")
    config = get_config(db)
    config.risk = RISK_PRESETS[key].model_copy(deep=True)
    _persist(db, config)
    return config


def _persist(db: Session, config: BotConfig) -> None:
    row = db.get(Settings, 1)
    payload = config.model_dump()
    if row is None:
        row = Settings(id=1, config_json=payload)
        db.add(row)
    else:
        row.config_json = payload
    db.commit()


def _deep_merge(base: dict, patch: dict) -> dict:
    out = dict(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out
