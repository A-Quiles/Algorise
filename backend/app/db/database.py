"""Conexión a la base de datos (SQLAlchemy). Portable entre SQLite y Postgres/Supabase.

El motor se elige por `DATABASE_URL`:
  - SQLite (local, por defecto):  sqlite:///./algorise.db
  - Supabase / Postgres (nube):   postgresql+psycopg://USER:PASS@HOST:5432/postgres
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()

# SQLite necesita check_same_thread=False porque el scheduler del bot corre en otro hilo.
_is_sqlite = settings.database_url.startswith("sqlite")
_connect_args = {"check_same_thread": False} if _is_sqlite else {}

engine = create_engine(
    settings.database_url,
    connect_args=_connect_args,
    pool_pre_ping=not _is_sqlite,  # reconecta automáticamente en Postgres/Supabase
    echo=False,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


class Base(DeclarativeBase):
    """Clase base de todos los modelos ORM."""


def get_db() -> Iterator[Session]:
    """Dependencia de FastAPI: una sesión por petición."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    """Sesión transaccional para usar fuera de FastAPI (p.ej. en el bucle del bot)."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db() -> None:
    """Crea las tablas si no existen. Importa los modelos para registrarlos en metadata."""
    from app.db import models  # noqa: F401  (registra los modelos)

    Base.metadata.create_all(bind=engine)
