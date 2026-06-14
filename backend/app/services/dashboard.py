"""Construye el estado completo del panel (cartera, posiciones, trades, señales, equity).

Se reutiliza tanto en el endpoint REST del dashboard como en cada emisión por WebSocket.
"""

from __future__ import annotations

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.db.models import Account, BotState, LogEntry, Position, PortfolioSnapshot, Signal
from app.services.serializers import log_to_dict, position_to_dict, signal_to_dict, snapshot_to_dict
from app.trading import portfolio


def build_payload(db: Session, prices: dict[str, float]) -> dict:
    """Estado del panel a partir de precios ya obtenidos (sin acceso a red)."""
    account = db.get(Account, 1)
    state = db.get(BotState, 1)
    pv = portfolio.portfolio_value(db, prices)

    open_positions = []
    for p in portfolio.get_open_positions(db):
        price = prices.get(p.symbol, p.entry_price)
        d = position_to_dict(p)
        d["current_price"] = price
        d["market_value"] = p.quantity * price
        d["unrealized_pnl"] = (price - p.entry_price) * p.quantity
        d["unrealized_pnl_pct"] = (price / p.entry_price - 1) * 100 if p.entry_price else 0.0
        open_positions.append(d)

    closed = db.scalars(
        select(Position).where(Position.status == "closed").order_by(desc(Position.closed_at)).limit(20)
    ).all()
    signals = db.scalars(select(Signal).order_by(desc(Signal.timestamp)).limit(20)).all()
    snapshots = db.scalars(
        select(PortfolioSnapshot).order_by(desc(PortfolioSnapshot.timestamp)).limit(500)
    ).all()
    logs = db.scalars(select(LogEntry).order_by(desc(LogEntry.timestamp)).limit(30)).all()

    drawdown_pct = 0.0
    if account.peak_equity > 0:
        drawdown_pct = max(0.0, (account.peak_equity - pv.equity) / account.peak_equity * 100.0)

    return {
        "type": "dashboard",
        "account": {
            "base_currency": account.base_currency,
            "cash": account.cash_balance,
            "initial_capital": account.initial_capital,
            "realized_pnl": account.realized_pnl,
            "peak_equity": account.peak_equity,
        },
        "bot": {
            "status": state.status,
            "mode": state.mode,
            "kill_switch": state.kill_switch,
            "started_at": state.started_at.isoformat() if state.started_at else None,
            "last_cycle_at": state.last_cycle_at.isoformat() if state.last_cycle_at else None,
            "last_error": state.last_error,
        },
        "portfolio": {
            "equity": pv.equity,
            "cash": pv.cash,
            "positions_value": pv.positions_value,
            "unrealized_pnl": pv.unrealized_pnl,
            "realized_pnl": pv.realized_pnl,
            "total_pnl": pv.equity - account.initial_capital,
            "total_pnl_pct": (pv.equity / account.initial_capital - 1) * 100 if account.initial_capital else 0.0,
            "drawdown_pct": drawdown_pct,
        },
        "prices": prices,
        "open_positions": open_positions,
        "recent_trades": [position_to_dict(p) for p in closed],
        "recent_signals": [signal_to_dict(s) for s in signals],
        "equity_curve": [snapshot_to_dict(s) for s in reversed(snapshots)],
        "logs": [log_to_dict(log) for log in logs],
    }
