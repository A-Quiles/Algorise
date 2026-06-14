"""Motor de backtesting: simula una estrategia+config sobre histórico de Binance.

Es una simulación pura (no toca la base de datos). Permite validar una configuración
antes de poner el bot en marcha — pieza clave para que el bot sea "experto".

Por velocidad, el backtest usa solo la señal cuantitativa (sin LLM): la capa de IA está
pensada para el modo en vivo, donde el coste por decisión es asumible.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import pandas as pd

from app.indicators import ta
from app.market.provider import _TIMEFRAME_MS, get_market_provider
from app.schemas.config import RiskConfig
from app.strategies import get_strategy
from app.trading.risk import compute_stops, position_size


@dataclass
class BTTrade:
    entry_time: str
    exit_time: str
    entry_price: float
    exit_price: float
    quantity: float
    pnl: float
    pnl_pct: float
    reason: str


@dataclass
class BacktestResult:
    metrics: dict
    equity_curve: list[dict]
    trades: list[BTTrade] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "metrics": self.metrics,
            "equity_curve": self.equity_curve,
            "trades": [t.__dict__ for t in self.trades],
        }


def run_backtest(
    *,
    symbol: str,
    timeframe: str,
    strategy_id: str,
    strategy_params: dict,
    risk: RiskConfig,
    since_ms: int,
    until_ms: int | None = None,
    starting_capital: float = 10_000.0,
    fee_pct: float = 0.1,
    slippage_pct: float = 0.05,
) -> BacktestResult:
    provider = get_market_provider()
    df = provider.fetch_ohlcv_history(symbol, timeframe, since_ms, until_ms)
    if len(df) < 50:
        return BacktestResult(metrics={"error": "Histórico insuficiente para el backtest."}, equity_curve=[])

    strat = get_strategy(strategy_id)
    params = strat.resolve_params(strategy_params)

    cash = starting_capital
    qty = 0.0
    entry_price = 0.0
    stop_loss = take_profit = trailing_ref = 0.0
    entry_time = ""

    trades: list[BTTrade] = []
    equity_curve: list[dict] = []
    warmup = 50  # barras de calentamiento para que los indicadores se estabilicen

    fee_f = fee_pct / 100.0
    slip_f = slippage_pct / 100.0

    for i in range(warmup, len(df)):
        window = df.iloc[: i + 1]
        bar = df.iloc[i]
        close = float(bar["close"])
        high = float(bar["high"])
        low = float(bar["low"])
        ts = bar["datetime"].isoformat()

        # --- Gestión de posición abierta ---
        if qty > 0:
            # Trailing stop (sobre el cierre)
            if risk.trailing_stop_pct:
                trailing_ref = max(trailing_ref, close)
                new_stop = trailing_ref * (1 - risk.trailing_stop_pct / 100.0)
                stop_loss = max(stop_loss, new_stop)

            exit_price = None
            reason = ""
            # Salidas intrabar: el stop tiene prioridad sobre el take-profit (conservador)
            if stop_loss and low <= stop_loss:
                exit_price, reason = stop_loss, "stop_loss"
            elif take_profit and high >= take_profit:
                exit_price, reason = take_profit, "take_profit"
            else:
                sig = strat.generate_signal(window, params)
                if sig.action == "sell":
                    exit_price, reason = close, "señal de venta"

            if exit_price is not None:
                fill = exit_price * (1 - slip_f)
                proceeds = qty * fill
                exit_fee = proceeds * fee_f
                cash += proceeds - exit_fee
                cost_basis = qty * entry_price * (1 + fee_f)
                pnl = (proceeds - exit_fee) - cost_basis
                trades.append(
                    BTTrade(entry_time, ts, entry_price, fill, qty, pnl,
                            pnl / cost_basis * 100 if cost_basis else 0.0, reason)
                )
                qty = 0.0

        # --- Nueva entrada ---
        if qty == 0:
            sig = strat.generate_signal(window, params)
            if sig.action == "buy":
                fill = close * (1 + slip_f)
                equity_now = cash
                atr_value = float(ta.atr(window).iloc[-1]) if risk.use_atr_stops else None
                stops = compute_stops(fill, risk, atr_value)
                size = position_size(equity_now, fill, stops.stop_loss, risk, cash)
                if size > 0:
                    cost = size * fill
                    fee = cost * fee_f
                    if cost + fee <= cash:
                        cash -= cost + fee
                        qty = size
                        entry_price = fill
                        stop_loss = stops.stop_loss
                        take_profit = stops.take_profit
                        trailing_ref = fill
                        entry_time = ts

        equity = cash + qty * close
        equity_curve.append({"timestamp": ts, "equity": equity})

    # Cierre forzoso al final si queda posición abierta
    if qty > 0:
        last = df.iloc[-1]
        fill = float(last["close"]) * (1 - slip_f)
        proceeds = qty * fill
        cash += proceeds * (1 - fee_f)
        cost_basis = qty * entry_price * (1 + fee_f)
        pnl = proceeds * (1 - fee_f) - cost_basis
        trades.append(
            BTTrade(entry_time, last["datetime"].isoformat(), entry_price, fill, qty, pnl,
                    pnl / cost_basis * 100 if cost_basis else 0.0, "fin del backtest")
        )

    metrics = _compute_metrics(equity_curve, trades, starting_capital, timeframe)
    return BacktestResult(metrics=metrics, equity_curve=equity_curve, trades=trades)


def _compute_metrics(equity_curve: list[dict], trades: list[BTTrade], starting_capital: float, timeframe: str) -> dict:
    final_equity = equity_curve[-1]["equity"] if equity_curve else starting_capital
    total_return_pct = (final_equity / starting_capital - 1) * 100 if starting_capital else 0.0

    wins = [t for t in trades if t.pnl > 0]
    losses = [t for t in trades if t.pnl <= 0]
    win_rate = len(wins) / len(trades) * 100 if trades else 0.0
    gross_profit = sum(t.pnl for t in wins)
    gross_loss = abs(sum(t.pnl for t in losses))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else (math.inf if gross_profit > 0 else 0.0)

    # Máximo drawdown
    peak = starting_capital
    max_dd = 0.0
    for point in equity_curve:
        peak = max(peak, point["equity"])
        dd = (peak - point["equity"]) / peak * 100 if peak else 0.0
        max_dd = max(max_dd, dd)

    # Sharpe anualizado a partir de retornos por barra
    equities = [p["equity"] for p in equity_curve]
    returns = [(equities[i] / equities[i - 1] - 1) for i in range(1, len(equities)) if equities[i - 1] > 0]
    sharpe = 0.0
    if len(returns) > 1:
        mean = sum(returns) / len(returns)
        var = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
        std = math.sqrt(var)
        if std > 0:
            bars_per_year = (365 * 24 * 3600 * 1000) / _TIMEFRAME_MS.get(timeframe, 300_000)
            sharpe = mean / std * math.sqrt(bars_per_year)

    return {
        "starting_capital": starting_capital,
        "final_equity": round(final_equity, 2),
        "total_return_pct": round(total_return_pct, 2),
        "num_trades": len(trades),
        "win_rate_pct": round(win_rate, 2),
        "profit_factor": round(profit_factor, 2) if profit_factor != math.inf else None,
        "max_drawdown_pct": round(max_dd, 2),
        "sharpe_ratio": round(sharpe, 2),
        "avg_trade_pnl": round(sum(t.pnl for t in trades) / len(trades), 2) if trades else 0.0,
    }
