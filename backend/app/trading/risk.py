"""Gestión de riesgo: tamaño de posición, stops y guardas (límites de pérdida/drawdown).

La parte matemática son funciones puras (fáciles de testear). Las guardas que consultan
la base de datos viven al final y las usa el bucle del bot antes de abrir operaciones.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Account, Position
from app.schemas.config import RiskConfig


@dataclass
class Stops:
    stop_loss: float
    take_profit: float


def compute_stops(entry_price: float, risk: RiskConfig, atr_value: float | None = None) -> Stops:
    """Calcula stop-loss y take-profit para una posición larga.

    Si `use_atr_stops` y hay ATR, la distancia del stop = ATR * multiplicador; el TP mantiene
    la misma proporción riesgo/beneficio que los porcentajes configurados. Si no, % fijos.
    """
    if risk.use_atr_stops and atr_value:
        sl_distance = atr_value * risk.atr_multiplier
        rr = risk.take_profit_pct / risk.stop_loss_pct if risk.stop_loss_pct else 2.0
        tp_distance = sl_distance * rr
    else:
        sl_distance = entry_price * risk.stop_loss_pct / 100.0
        tp_distance = entry_price * risk.take_profit_pct / 100.0
    return Stops(
        stop_loss=max(0.0, entry_price - sl_distance),
        take_profit=entry_price + tp_distance,
    )


def position_size(equity: float, entry_price: float, stop_loss: float, risk: RiskConfig, cash: float) -> float:
    """Cantidad a comprar para que la pérdida en el stop = `risk_per_trade_pct` del equity.

    Se limita por el efectivo disponible. Devuelve la cantidad en unidades del activo (0 si no
    se puede dimensionar con sentido).
    """
    risk_amount = equity * risk.risk_per_trade_pct / 100.0
    stop_distance = entry_price - stop_loss
    if stop_distance <= 0 or entry_price <= 0:
        return 0.0
    qty = risk_amount / stop_distance
    # No gastar más efectivo del disponible.
    max_qty_by_cash = cash / entry_price
    qty = min(qty, max_qty_by_cash)
    return max(0.0, qty)


# --- Guardas con acceso a la base de datos ---

@dataclass
class RiskCheck:
    allowed: bool
    reason: str


def open_positions_count(db: Session) -> int:
    from sqlalchemy import func

    return db.scalar(select(func.count()).select_from(Position).where(Position.status == "open")) or 0


def realized_pnl_today(db: Session) -> float:
    today = datetime.now(timezone.utc).date()
    closed = db.scalars(select(Position).where(Position.status == "closed")).all()
    return sum(
        (p.pnl or 0.0) for p in closed if p.closed_at and p.closed_at.astimezone(timezone.utc).date() == today
    )


def check_can_open(db: Session, risk: RiskConfig, equity: float) -> RiskCheck:
    """Comprueba los límites globales antes de abrir una nueva operación."""
    account = db.get(Account, 1)
    if account is None:
        return RiskCheck(False, "No hay cuenta inicializada.")

    # Límite de posiciones simultáneas
    if open_positions_count(db) >= risk.max_open_positions:
        return RiskCheck(False, f"Máximo de posiciones abiertas alcanzado ({risk.max_open_positions}).")

    # Límite de pérdida diaria (sobre el capital inicial)
    daily = realized_pnl_today(db)
    daily_limit = -account.initial_capital * risk.max_daily_loss_pct / 100.0
    if daily <= daily_limit:
        return RiskCheck(False, f"Límite de pérdida diaria alcanzado ({daily:.2f}).")

    # Circuit breaker por drawdown
    if account.peak_equity > 0:
        drawdown_pct = (account.peak_equity - equity) / account.peak_equity * 100.0
        if drawdown_pct >= risk.max_drawdown_pct:
            return RiskCheck(False, f"Drawdown máximo superado ({drawdown_pct:.1f}%).")

    return RiskCheck(True, "OK")
