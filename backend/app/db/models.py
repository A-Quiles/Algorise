"""Modelos ORM (tablas de la base de datos)."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    """Usuario único de acceso (auth local)."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Settings(Base):
    """Fila única (id=1) con toda la configuración del bot serializada en JSON."""

    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    config_json: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


class BotState(Base):
    """Estado en tiempo de ejecución del bot (fila única id=1). Separado de la config."""

    __tablename__ = "bot_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    status: Mapped[str] = mapped_column(String(16), default="stopped")  # stopped | running | paused
    mode: Mapped[str] = mapped_column(String(16), default="paper")  # paper | live
    kill_switch: Mapped[bool] = mapped_column(Boolean, default=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_cycle_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class Account(Base):
    """Cartera virtual (fila única id=1): saldo en efectivo y métricas de capital."""

    __tablename__ = "account"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    base_currency: Mapped[str] = mapped_column(String(16), default="USDT")
    cash_balance: Mapped[float] = mapped_column(Float, default=10_000.0)
    initial_capital: Mapped[float] = mapped_column(Float, default=10_000.0)
    realized_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    peak_equity: Mapped[float] = mapped_column(Float, default=10_000.0)  # para drawdown
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    reset_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Position(Base):
    """Posición / operación. Sirve también de diario de trades (abiertas y cerradas)."""

    __tablename__ = "positions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    side: Mapped[str] = mapped_column(String(8), default="long")  # long | short (short = futuro)
    status: Mapped[str] = mapped_column(String(8), default="open", index=True)  # open | closed

    quantity: Mapped[float] = mapped_column(Float)
    entry_price: Mapped[float] = mapped_column(Float)
    exit_price: Mapped[float | None] = mapped_column(Float, nullable=True)

    stop_loss: Mapped[float | None] = mapped_column(Float, nullable=True)
    take_profit: Mapped[float | None] = mapped_column(Float, nullable=True)
    trailing_ref: Mapped[float | None] = mapped_column(Float, nullable=True)  # máximo alcanzado (trailing)

    fee_paid: Mapped[float] = mapped_column(Float, default=0.0)
    pnl: Mapped[float | None] = mapped_column(Float, nullable=True)
    pnl_pct: Mapped[float | None] = mapped_column(Float, nullable=True)

    strategy: Mapped[str | None] = mapped_column(String(64), nullable=True)
    open_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    close_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    llm_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    llm_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Signal(Base):
    """Cada decisión del bot: señal cuantitativa + veredicto del LLM + si se ejecutó."""

    __tablename__ = "signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    action: Mapped[str] = mapped_column(String(8))  # buy | sell | hold
    strategy: Mapped[str | None] = mapped_column(String(64), nullable=True)
    indicators: Mapped[dict] = mapped_column(JSON, default=dict)

    llm_used: Mapped[bool] = mapped_column(Boolean, default=False)
    llm_decision: Mapped[str | None] = mapped_column(String(16), nullable=True)  # confirm | veto
    llm_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    llm_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)

    executed: Mapped[bool] = mapped_column(Boolean, default=False)
    position_id: Mapped[int | None] = mapped_column(Integer, nullable=True)


class PortfolioSnapshot(Base):
    """Instantánea periódica del valor de la cartera (para la curva de equity)."""

    __tablename__ = "portfolio_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)
    equity: Mapped[float] = mapped_column(Float)
    cash: Mapped[float] = mapped_column(Float)
    positions_value: Mapped[float] = mapped_column(Float)
    realized_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    unrealized_pnl: Mapped[float] = mapped_column(Float, default=0.0)


class LogEntry(Base):
    """Log de eventos del bot, visible en la UI."""

    __tablename__ = "logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)
    level: Mapped[str] = mapped_column(String(16), default="info")  # debug | info | warning | error
    message: Mapped[str] = mapped_column(Text)
    context: Mapped[dict] = mapped_column(JSON, default=dict)


class OHLCVCache(Base):
    """Caché de velas para no re-descargar de Binance y acelerar el backtesting."""

    __tablename__ = "ohlcv_cache"
    __table_args__ = (UniqueConstraint("symbol", "timeframe", "timestamp", name="uq_ohlcv"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    timeframe: Mapped[str] = mapped_column(String(8), index=True)
    timestamp: Mapped[int] = mapped_column(Integer, index=True)  # epoch ms (open time de la vela)
    open: Mapped[float] = mapped_column(Float)
    high: Mapped[float] = mapped_column(Float)
    low: Mapped[float] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float)
    volume: Mapped[float] = mapped_column(Float)
