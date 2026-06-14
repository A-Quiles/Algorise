"""Conversión de modelos ORM a dicts JSON-serializables (para API y WebSocket)."""

from __future__ import annotations

from datetime import datetime

from app.db.models import LogEntry, Position, PortfolioSnapshot, Signal


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def position_to_dict(p: Position) -> dict:
    return {
        "id": p.id,
        "symbol": p.symbol,
        "side": p.side,
        "status": p.status,
        "quantity": p.quantity,
        "entry_price": p.entry_price,
        "exit_price": p.exit_price,
        "stop_loss": p.stop_loss,
        "take_profit": p.take_profit,
        "fee_paid": p.fee_paid,
        "pnl": p.pnl,
        "pnl_pct": p.pnl_pct,
        "strategy": p.strategy,
        "open_reason": p.open_reason,
        "close_reason": p.close_reason,
        "llm_explanation": p.llm_explanation,
        "llm_confidence": p.llm_confidence,
        "opened_at": _iso(p.opened_at),
        "closed_at": _iso(p.closed_at),
    }


def signal_to_dict(s: Signal) -> dict:
    return {
        "id": s.id,
        "timestamp": _iso(s.timestamp),
        "symbol": s.symbol,
        "action": s.action,
        "strategy": s.strategy,
        "indicators": s.indicators,
        "llm_used": s.llm_used,
        "llm_decision": s.llm_decision,
        "llm_confidence": s.llm_confidence,
        "llm_explanation": s.llm_explanation,
        "executed": s.executed,
        "position_id": s.position_id,
    }


def snapshot_to_dict(s: PortfolioSnapshot) -> dict:
    return {
        "timestamp": _iso(s.timestamp),
        "equity": s.equity,
        "cash": s.cash,
        "positions_value": s.positions_value,
        "realized_pnl": s.realized_pnl,
        "unrealized_pnl": s.unrealized_pnl,
    }


def log_to_dict(log: LogEntry) -> dict:
    return {
        "id": log.id,
        "timestamp": _iso(log.timestamp),
        "level": log.level,
        "message": log.message,
        "context": log.context,
    }
