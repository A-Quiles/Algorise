"""Analítica y atribución de operaciones: ¿de dónde viene el rendimiento (y las pérdidas)?

En vez de mirar solo el P&L global, desglosa los trades cerrados por estrategia, símbolo,
motivo de salida y franja horaria, y calcula métricas de calidad (expectancy, profit
factor, rachas). Sirve para entender qué funciona y dejar de optimizar a ciegas.
"""

from __future__ import annotations

import math
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Position


def _stats(pnls: list[float]) -> dict:
    """Métricas de un grupo de operaciones a partir de su lista de P&L."""
    n = len(pnls)
    if n == 0:
        return {"trades": 0, "win_rate": 0.0, "total_pnl": 0.0, "avg_pnl": 0.0,
                "profit_factor": None, "expectancy": 0.0}
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    win_rate = len(wins) / n * 100
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (math.inf if gross_profit > 0 else 0.0)
    avg_win = gross_profit / len(wins) if wins else 0.0
    avg_loss = gross_loss / len(losses) if losses else 0.0
    # Expectancy: P&L medio esperado por operación.
    expectancy = (win_rate / 100 * avg_win) - ((1 - win_rate / 100) * avg_loss)
    return {
        "trades": n,
        "win_rate": round(win_rate, 1),
        "total_pnl": round(sum(pnls), 2),
        "avg_pnl": round(sum(pnls) / n, 2),
        "profit_factor": round(profit_factor, 2) if profit_factor != math.inf else None,
        "expectancy": round(expectancy, 2),
    }


def _grouped(trades: list[Position], key) -> list[dict]:
    """Agrupa trades por una clave (función) y devuelve sus métricas ordenadas por P&L."""
    buckets: dict[str, list[float]] = defaultdict(list)
    for t in trades:
        buckets[key(t)].append(t.pnl or 0.0)
    rows = [{"group": g, **_stats(pnls)} for g, pnls in buckets.items()]
    return sorted(rows, key=lambda r: r["total_pnl"], reverse=True)


def _max_streak(trades: list[Position], winning: bool) -> int:
    """Mayor racha de operaciones ganadoras (o perdedoras) consecutivas."""
    best = cur = 0
    for t in trades:
        is_win = (t.pnl or 0.0) > 0
        if is_win == winning:
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    return best


def build_analytics(db: Session) -> dict:
    """Atribución completa de las operaciones cerradas."""
    trades = list(
        db.scalars(select(Position).where(Position.status == "closed").order_by(Position.closed_at)).all()
    )
    if not trades:
        return {"overall": _stats([]), "by_strategy": [], "by_symbol": [],
                "by_exit_reason": [], "by_hour": [], "streaks": {"max_wins": 0, "max_losses": 0},
                "best_trade": None, "worst_trade": None}

    pnls = [t.pnl or 0.0 for t in trades]

    def _hour(t: Position) -> str:
        return f"{t.opened_at.hour:02d}:00" if t.opened_at else "—"

    def _exit(t: Position) -> str:
        return (t.close_reason or "—").split(":")[0][:24]

    best = max(trades, key=lambda t: t.pnl or 0.0)
    worst = min(trades, key=lambda t: t.pnl or 0.0)

    def _brief(t: Position) -> dict:
        return {"symbol": t.symbol, "strategy": t.strategy, "pnl": round(t.pnl or 0.0, 2),
                "pnl_pct": round(t.pnl_pct or 0.0, 2), "reason": t.close_reason}

    return {
        "overall": _stats(pnls),
        "by_strategy": _grouped(trades, lambda t: t.strategy or "—"),
        "by_symbol": _grouped(trades, lambda t: t.symbol),
        "by_exit_reason": _grouped(trades, _exit),
        "by_hour": sorted(_grouped(trades, _hour), key=lambda r: r["group"]),
        "streaks": {"max_wins": _max_streak(trades, True), "max_losses": _max_streak(trades, False)},
        "best_trade": _brief(best),
        "worst_trade": _brief(worst),
    }
