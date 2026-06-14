"""Valoración de la cartera: equity, P&L no realizado, snapshots, trailing stop y salidas."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Account, PortfolioSnapshot, Position
from app.schemas.config import RiskConfig


@dataclass
class PortfolioValue:
    equity: float
    cash: float
    positions_value: float
    unrealized_pnl: float
    realized_pnl: float


def get_open_positions(db: Session) -> list[Position]:
    return list(db.scalars(select(Position).where(Position.status == "open")).all())


def position_for_symbol(db: Session, symbol: str) -> Position | None:
    return db.scalar(select(Position).where(Position.status == "open", Position.symbol == symbol))


def portfolio_value(db: Session, prices: dict[str, float]) -> PortfolioValue:
    """Calcula el valor total de la cartera a precios actuales."""
    account = db.get(Account, 1)
    positions = get_open_positions(db)
    positions_value = 0.0
    unrealized = 0.0
    for p in positions:
        price = prices.get(p.symbol, p.entry_price)
        market_value = p.quantity * price
        positions_value += market_value
        unrealized += market_value - p.quantity * p.entry_price
    equity = account.cash_balance + positions_value
    # Actualiza el pico de equity (para el cálculo de drawdown).
    if equity > account.peak_equity:
        account.peak_equity = equity
    return PortfolioValue(
        equity=equity,
        cash=account.cash_balance,
        positions_value=positions_value,
        unrealized_pnl=unrealized,
        realized_pnl=account.realized_pnl,
    )


def take_snapshot(db: Session, prices: dict[str, float]) -> PortfolioSnapshot:
    pv = portfolio_value(db, prices)
    snap = PortfolioSnapshot(
        equity=pv.equity,
        cash=pv.cash,
        positions_value=pv.positions_value,
        realized_pnl=pv.realized_pnl,
        unrealized_pnl=pv.unrealized_pnl,
    )
    db.add(snap)
    db.flush()
    return snap


def update_trailing_stop(position: Position, price: float, trailing_stop_pct: float | None) -> None:
    """Sube el stop si el precio hace nuevos máximos (solo para largos). Nunca lo baja."""
    if not trailing_stop_pct:
        return
    if position.trailing_ref is None or price > position.trailing_ref:
        position.trailing_ref = price
    new_stop = position.trailing_ref * (1 - trailing_stop_pct / 100.0)
    if position.stop_loss is None or new_stop > position.stop_loss:
        position.stop_loss = new_stop


def exit_reason(position: Position, price: float) -> str | None:
    """Devuelve el motivo de salida si el precio toca SL o TP (posición larga)."""
    if position.stop_loss is not None and price <= position.stop_loss:
        return "stop_loss"
    if position.take_profit is not None and price >= position.take_profit:
        return "take_profit"
    return None
