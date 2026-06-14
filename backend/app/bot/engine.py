"""Motor del bot: bucle de trading + control (start/stop/pause/kill) + scheduler.

El ciclo se ejecuta en un hilo aparte (`asyncio.to_thread`) para no bloquear el event
loop con las llamadas de red de ccxt/LLM, y luego difunde el estado por WebSocket.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.ai.advisor import advise
from app.bot.ws_manager import manager
from app.db.database import session_scope
from app.db.models import Account, BotState, LogEntry, Signal as SignalModel
from app.indicators import ta
from app.market.provider import get_market_provider
from app.services.dashboard import build_payload
from app.services.settings_service import get_config
from app.strategies import get_strategy
from app.trading import portfolio, risk
from app.trading.broker import PaperBroker

logger = logging.getLogger("algorise.bot")

_TIMEFRAME_SECONDS = {
    "1m": 60, "5m": 300, "15m": 900, "30m": 1800, "1h": 3600, "4h": 14400, "1d": 86400,
}


class BotEngine:
    def __init__(self) -> None:
        self.scheduler = AsyncIOScheduler()
        self._job = None

    # --- Ciclo de vida del scheduler ---
    def init_scheduler(self) -> None:
        if not self.scheduler.running:
            self.scheduler.start()

    def sync_on_startup(self) -> None:
        """Si el bot estaba en marcha antes de reiniciar el proceso, reanuda el scheduling."""
        with session_scope() as db:
            state = db.get(BotState, 1)
            config = get_config(db)
            running = state is not None and state.status == "running"
            tf = config.timeframe
        if running:
            self._schedule(tf)

    def _interval_seconds(self, timeframe: str) -> int:
        return _TIMEFRAME_SECONDS.get(timeframe, 300)

    def _schedule(self, timeframe: str) -> None:
        secs = self._interval_seconds(timeframe)
        self._job = self.scheduler.add_job(
            self.run_cycle, "interval", seconds=secs, id="bot_cycle", replace_existing=True, max_instances=1
        )

    def reschedule(self, timeframe: str) -> None:
        if self._job is not None:
            self._schedule(timeframe)

    # --- Control ---
    async def start(self) -> None:
        with session_scope() as db:
            state = db.get(BotState, 1)
            config = get_config(db)
            state.status = "running"
            state.kill_switch = False
            state.started_at = datetime.now(timezone.utc)
            tf = config.timeframe
        self._schedule(tf)
        await self.run_cycle()  # ejecuta un ciclo de inmediato

    async def stop(self) -> None:
        with session_scope() as db:
            state = db.get(BotState, 1)
            state.status = "stopped"
        self._remove_job()

    async def pause(self) -> None:
        with session_scope() as db:
            state = db.get(BotState, 1)
            state.status = "paused"
        if self._job is not None:
            self._job.pause()

    async def resume(self) -> None:
        await self.start()

    async def kill(self) -> None:
        """Kill switch: cierra TODAS las posiciones a mercado y detiene el bot."""
        provider = get_market_provider()
        with session_scope() as db:
            config = get_config(db)
            broker = PaperBroker(config.fee_pct, config.slippage_pct)
            positions = portfolio.get_open_positions(db)
            symbols = [p.symbol for p in positions]
            prices = provider.fetch_prices(symbols) if symbols else {}
            for pos in positions:
                price = prices.get(pos.symbol, pos.entry_price)
                broker.close_position(db, pos, price, "kill switch")
            state = db.get(BotState, 1)
            state.status = "stopped"
            state.kill_switch = True
            self._log(db, "warning", "Kill switch activado: todas las posiciones cerradas.")
        self._remove_job()
        await self.broadcast_state()

    def _remove_job(self) -> None:
        if self._job is not None:
            try:
                self._job.remove()
            except Exception:  # noqa: BLE001
                pass
            self._job = None

    # --- Ejecución del ciclo ---
    async def run_cycle(self) -> None:
        try:
            payload = await asyncio.to_thread(self._run_cycle_sync)
        except Exception:  # noqa: BLE001
            logger.exception("Error en el ciclo del bot")
            payload = None
        if payload:
            await manager.broadcast(payload)

    async def broadcast_state(self) -> None:
        """Difunde el estado actual sin ejecutar el bot (para acciones manuales)."""
        try:
            payload = await asyncio.to_thread(self._snapshot_sync)
            if payload:
                await manager.broadcast(payload)
        except Exception:  # noqa: BLE001
            logger.exception("Error difundiendo estado")

    def _snapshot_sync(self) -> dict | None:
        provider = get_market_provider()
        with session_scope() as db:
            config = get_config(db)
            try:
                prices = provider.fetch_prices(config.pairs)
            except Exception:  # noqa: BLE001
                prices = {}
            return build_payload(db, prices)

    def _run_cycle_sync(self) -> dict | None:
        provider = get_market_provider()
        with session_scope() as db:
            state = db.get(BotState, 1)
            if state is None or state.status != "running" or state.kill_switch:
                return None
            config = get_config(db)
            broker = PaperBroker(config.fee_pct, config.slippage_pct)

            try:
                prices = provider.fetch_prices(config.pairs)
            except Exception as exc:  # noqa: BLE001
                self._log(db, "error", f"No se pudieron obtener precios: {exc}")
                state.last_error = str(exc)
                return None
            state.last_error = None

            # 1. Gestionar posiciones abiertas: trailing stop + salidas por SL/TP
            for pos in portfolio.get_open_positions(db):
                price = prices.get(pos.symbol)
                if price is None:
                    continue
                portfolio.update_trailing_stop(pos, price, config.risk.trailing_stop_pct)
                reason = portfolio.exit_reason(pos, price)
                if reason:
                    broker.close_position(db, pos, price, reason)
                    self._log(db, "info", f"Cerrada {pos.symbol} por {reason}: P&L {pos.pnl:.2f}", {"symbol": pos.symbol})

            # 2. Evaluar cada par para nuevas entradas / salidas por estrategia
            equity = portfolio.portfolio_value(db, prices).equity
            strat = get_strategy(config.active_strategy)
            params = strat.resolve_params(config.strategy_params)

            for symbol in config.pairs:
                price = prices.get(symbol)
                if price is None:
                    continue
                try:
                    df = provider.fetch_ohlcv(symbol, config.timeframe, limit=300)
                except Exception as exc:  # noqa: BLE001
                    self._log(db, "warning", f"OHLCV de {symbol} falló: {exc}")
                    continue

                signal = strat.generate_signal(df, params)
                sig_row = SignalModel(symbol=symbol, action=signal.action, strategy=strat.id, indicators=signal.indicators)
                existing = portfolio.position_for_symbol(db, symbol)

                if signal.action == "buy" and existing is None:
                    check = risk.check_can_open(db, config.risk, equity)
                    if not check.allowed:
                        sig_row.llm_explanation = check.reason
                        db.add(sig_row)
                        continue
                    verdict = advise(symbol, signal, config.llm, context={"price": price})
                    sig_row.llm_used = verdict.used_llm
                    sig_row.llm_decision = verdict.decision
                    sig_row.llm_confidence = verdict.confidence
                    sig_row.llm_explanation = verdict.explanation
                    if verdict.decision == "veto":
                        db.add(sig_row)
                        self._log(db, "info", f"IA vetó la compra de {symbol}: {verdict.explanation}")
                        continue
                    atr_value = float(ta.atr(df).iloc[-1]) if config.risk.use_atr_stops else None
                    stops = risk.compute_stops(price, config.risk, atr_value)
                    cash = db.get(Account, 1).cash_balance
                    qty = risk.position_size(equity, price, stops.stop_loss, config.risk, cash)
                    if qty <= 0:
                        sig_row.llm_explanation = (sig_row.llm_explanation or "") + " | Tamaño 0 (sin efectivo)."
                        db.add(sig_row)
                        continue
                    pos = broker.open_position(
                        db, symbol=symbol, quantity=qty, price=price,
                        stop_loss=stops.stop_loss, take_profit=stops.take_profit, strategy=strat.id,
                        open_reason=signal.reason, llm_explanation=verdict.explanation, llm_confidence=verdict.confidence,
                    )
                    sig_row.executed = True
                    sig_row.position_id = pos.id
                    db.add(sig_row)
                    self._log(db, "info", f"Abierta {symbol}: {qty:.6f} @ {pos.entry_price:.4f}", {"symbol": symbol})

                elif signal.action == "sell" and existing is not None:
                    broker.close_position(db, existing, price, "señal de venta de la estrategia")
                    sig_row.executed = True
                    sig_row.position_id = existing.id
                    db.add(sig_row)
                    self._log(db, "info", f"Cerrada {symbol} por señal de venta: P&L {existing.pnl:.2f}")
                else:
                    db.add(sig_row)

            # 3. Snapshot de cartera + estado
            portfolio.take_snapshot(db, prices)
            state.last_cycle_at = datetime.now(timezone.utc)
            return build_payload(db, prices)

    @staticmethod
    def _log(db, level: str, message: str, context: dict | None = None) -> None:
        db.add(LogEntry(level=level, message=message, context=context or {}))
        logger.log(getattr(logging, level.upper(), logging.INFO), message)


engine = BotEngine()
