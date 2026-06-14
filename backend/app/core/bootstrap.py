"""Inicialización en el primer arranque: crea filas por defecto si faltan."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.models import Account, BotState, Settings, User
from app.schemas.config import BotConfig

app_settings = get_settings()


def bootstrap(db: Session) -> None:
    """Crea usuario, configuración, estado del bot y cartera virtual por defecto."""
    # Usuario único
    user = db.scalar(select(User).where(User.username == app_settings.default_username))
    if user is None:
        db.add(
            User(
                username=app_settings.default_username,
                hashed_password=hash_password(app_settings.default_password),
            )
        )

    # Configuración del bot
    config_row = db.get(Settings, 1)
    config = BotConfig()
    if config_row is None:
        db.add(Settings(id=1, config_json=config.model_dump()))
    else:
        config = BotConfig.model_validate(config_row.config_json)

    # Estado del bot
    if db.get(BotState, 1) is None:
        db.add(BotState(id=1, status="stopped", mode=config.mode))

    # Cartera virtual
    if db.get(Account, 1) is None:
        db.add(
            Account(
                id=1,
                base_currency=config.base_currency,
                cash_balance=config.starting_capital,
                initial_capital=config.starting_capital,
                peak_equity=config.starting_capital,
            )
        )

    db.commit()
