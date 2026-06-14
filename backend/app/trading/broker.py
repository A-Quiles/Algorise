"""Broker abstracto + implementación de papel (PaperBroker).

El bot solo conoce la interfaz `Broker`, así que pasar a dinero real en el futuro será
añadir un `LiveBroker` (ccxt + claves) sin tocar la lógica de estrategias ni del bucle.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.models import Account, Position


class Broker(ABC):
    """Contrato común para ejecución paper y (futuro) real."""

    @abstractmethod
    def open_position(self, db: Session, *, symbol: str, quantity: float, price: float, **meta) -> Position: ...

    @abstractmethod
    def close_position(self, db: Session, position: Position, price: float, reason: str) -> Position: ...


class PaperBroker(Broker):
    """Ejecuta operaciones con dinero ficticio: aplica comisión y slippage simulados y
    actualiza la cartera virtual (`Account`) y las posiciones (`Position`)."""

    def __init__(self, fee_pct: float = 0.1, slippage_pct: float = 0.05) -> None:
        self.fee_pct = fee_pct
        self.slippage_pct = slippage_pct

    def _entry_fill(self, price: float) -> float:
        return price * (1 + self.slippage_pct / 100.0)

    def _exit_fill(self, price: float) -> float:
        return price * (1 - self.slippage_pct / 100.0)

    def open_position(
        self,
        db: Session,
        *,
        symbol: str,
        quantity: float,
        price: float,
        stop_loss: float | None = None,
        take_profit: float | None = None,
        strategy: str | None = None,
        open_reason: str | None = None,
        llm_explanation: str | None = None,
        llm_confidence: float | None = None,
        **_,
    ) -> Position:
        account = db.get(Account, 1)
        fill = self._entry_fill(price)
        cost = quantity * fill
        fee = cost * self.fee_pct / 100.0
        total = cost + fee
        if account.cash_balance < total:
            raise ValueError("Efectivo insuficiente para abrir la posición.")
        account.cash_balance -= total

        position = Position(
            symbol=symbol,
            side="long",
            status="open",
            quantity=quantity,
            entry_price=fill,
            stop_loss=stop_loss,
            take_profit=take_profit,
            trailing_ref=fill,
            fee_paid=fee,
            strategy=strategy,
            open_reason=open_reason,
            llm_explanation=llm_explanation,
            llm_confidence=llm_confidence,
            opened_at=datetime.now(timezone.utc),
        )
        db.add(position)
        db.flush()  # asigna id
        return position

    def close_position(self, db: Session, position: Position, price: float, reason: str) -> Position:
        account = db.get(Account, 1)
        fill = self._exit_fill(price)
        proceeds = position.quantity * fill
        exit_fee = proceeds * self.fee_pct / 100.0
        account.cash_balance += proceeds - exit_fee

        cost_basis = position.quantity * position.entry_price + position.fee_paid
        net_proceeds = proceeds - exit_fee
        pnl = net_proceeds - cost_basis
        pnl_pct = pnl / cost_basis * 100.0 if cost_basis else 0.0

        account.realized_pnl += pnl
        position.status = "closed"
        position.exit_price = fill
        position.fee_paid += exit_fee
        position.pnl = pnl
        position.pnl_pct = pnl_pct
        position.close_reason = reason
        position.closed_at = datetime.now(timezone.utc)
        db.flush()
        return position
