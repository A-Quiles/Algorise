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
from app.market.provider import get_async_provider, get_market_provider
from app.market.regime import correlated_symbols, detect_regime
from app.services.alerting import send_alert
from app.services.dashboard import build_payload
from app.services.settings_service import get_config
from app.strategies.combiner import resolve_signal
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
            send_alert(config.alerts, "risk", "🛑 Kill switch activado",
                       f"Cerradas {len(positions)} posiciones a mercado.")
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
        await self._prefetch_market_data()  # calienta la caché en paralelo (no bloquea el ciclo)
        try:
            payload = await asyncio.to_thread(self._run_cycle_sync)
        except Exception:  # noqa: BLE001
            logger.exception("Error en el ciclo del bot")
            payload = None
        if payload:
            await manager.broadcast(payload)

    async def _prefetch_market_data(self) -> None:
        """Descarga precios y velas de todos los pares en paralelo y puebla la caché síncrona.

        Así el ciclo síncrono (que corre en un hilo y accede a la BD) no se bloquea haciendo
        N llamadas de red en serie: cuando llega, los datos ya están en caché.
        """
        try:
            with session_scope() as db:
                state = db.get(BotState, 1)
                if state is None or state.status != "running" or state.kill_switch:
                    return
                config = get_config(db)
                symbols = list(dict.fromkeys([*config.pairs, *[p.symbol for p in portfolio.get_open_positions(db)]]))
                timeframe = config.timeframe
            if not symbols:
                return
            prices, ohlcv = await get_async_provider().fetch_bulk(symbols, timeframe, limit=300)
            sync_provider = get_market_provider()
            for sym, price in prices.items():
                sync_provider.prime_price(sym, price)
            for sym, df in ohlcv.items():
                sync_provider.prime_ohlcv(sym, timeframe, 300, df)
        except Exception:  # noqa: BLE001
            # Prefetch best-effort: si falla, el ciclo síncrono descargará bajo demanda.
            logger.debug("Prefetch concurrente falló; se usará descarga bajo demanda", exc_info=True)

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
                    self._alert_trade(config, "trade_close", pos, reason)

            # 2. Evaluar cada par para nuevas entradas / salidas por estrategia
            equity = portfolio.portfolio_value(db, prices).equity
            # Caché de velas del ciclo: se usan para la señal, el régimen y las correlaciones.
            dfs: dict[str, "object"] = {}
            open_symbols = [p.symbol for p in portfolio.get_open_positions(db)]

            def _get_df(sym: str):
                if sym not in dfs:
                    dfs[sym] = provider.fetch_ohlcv(sym, config.timeframe, limit=300)
                return dfs[sym]

            for symbol in config.pairs:
                price = prices.get(symbol)
                if price is None:
                    continue
                try:
                    df = _get_df(symbol)
                except Exception as exc:  # noqa: BLE001
                    self._log(db, "warning", f"OHLCV de {symbol} falló: {exc}")
                    continue

                signal, strat_label = resolve_signal(df, config)
                sig_row = SignalModel(symbol=symbol, action=signal.action, strategy=strat_label, indicators=signal.indicators)
                existing = portfolio.position_for_symbol(db, symbol)

                if signal.action == "buy" and existing is None:
                    check = risk.check_can_open(db, config.risk, equity)
                    if not check.allowed:
                        sig_row.llm_explanation = check.reason
                        db.add(sig_row)
                        continue

                    # Riesgo de cartera: exposición total + clúster por correlación.
                    others = {}
                    for os_sym in open_symbols:
                        try:
                            others[os_sym] = _get_df(os_sym)
                        except Exception:  # noqa: BLE001
                            pass
                    correlated = [s for s, _ in correlated_symbols(df, others, config.risk.correlation_threshold)]
                    atr_value = float(ta.atr(df).iloc[-1]) if config.risk.use_atr_stops else None
                    stops = risk.compute_stops(price, config.risk, atr_value)
                    cash = db.get(Account, 1).cash_balance
                    qty = risk.position_size(equity, price, stops.stop_loss, config.risk, cash)
                    pcheck = risk.check_portfolio_limits(
                        db, config.risk, equity, prices,
                        new_position_cost=qty * price, correlated_open=correlated,
                    )
                    if not pcheck.allowed:
                        sig_row.llm_explanation = pcheck.reason
                        db.add(sig_row)
                        self._log(db, "info", f"Entrada en {symbol} bloqueada por cartera: {pcheck.reason}")
                        continue
                    if qty <= 0:
                        sig_row.llm_explanation = "Tamaño 0 (sin efectivo)."
                        db.add(sig_row)
                        continue

                    # Contexto de mercado para la IA: régimen + correlaciones + cartera.
                    regime = detect_regime(df)
                    ai_context = {
                        "price": price,
                        "regime": regime.to_dict(),
                        "correlations": correlated,
                        "portfolio": {
                            "open_positions": len(open_symbols),
                            "exposure_pct": round(risk.current_exposure_pct(db, equity, prices), 1),
                        },
                    }
                    verdict = advise(symbol, signal, config.llm, context=ai_context)
                    sig_row.llm_used = verdict.used_llm
                    sig_row.llm_decision = verdict.decision
                    sig_row.llm_confidence = verdict.confidence
                    sig_row.llm_explanation = verdict.explanation
                    if verdict.decision == "veto":
                        db.add(sig_row)
                        self._log(db, "info", f"IA vetó la compra de {symbol}: {verdict.explanation}")
                        continue
                    pos = broker.open_position(
                        db, symbol=symbol, quantity=qty, price=price,
                        stop_loss=stops.stop_loss, take_profit=stops.take_profit, strategy=strat_label,
                        open_reason=signal.reason, llm_explanation=verdict.explanation, llm_confidence=verdict.confidence,
                    )
                    sig_row.executed = True
                    sig_row.position_id = pos.id
                    db.add(sig_row)
                    open_symbols.append(symbol)
                    self._log(db, "info", f"Abierta {symbol}: {qty:.6f} @ {pos.entry_price:.4f}", {"symbol": symbol})
                    self._alert_trade(config, "trade_open", pos, signal.reason)

                elif signal.action == "sell" and existing is not None:
                    broker.close_position(db, existing, price, "señal de venta de la estrategia")
                    sig_row.executed = True
                    sig_row.position_id = existing.id
                    db.add(sig_row)
                    self._log(db, "info", f"Cerrada {symbol} por señal de venta: P&L {existing.pnl:.2f}")
                    self._alert_trade(config, "trade_close", existing, "señal de venta")
                else:
                    db.add(sig_row)

            # 3. Snapshot de cartera + estado
            portfolio.take_snapshot(db, prices)
            state.last_cycle_at = datetime.now(timezone.utc)
            return build_payload(db, prices)

    @staticmethod
    def _alert_trade(config, event: str, pos, reason: str) -> None:
        """Envía un aviso de apertura/cierre de operación a los canales configurados."""
        verb = "Abierta" if event == "trade_open" else "Cerrada"
        fields = {"Par": pos.symbol, "Estrategia": pos.strategy or "—", "Motivo": reason}
        if event == "trade_close" and pos.pnl is not None:
            fields["P&L"] = f"{pos.pnl:.2f} ({pos.pnl_pct:.2f}%)"
        else:
            fields["Precio"] = f"{pos.entry_price:.4f}"
        send_alert(config.alerts, event, f"{verb} {pos.symbol}", "", fields)

    @staticmethod
    def _log(db, level: str, message: str, context: dict | None = None) -> None:
        db.add(LogEntry(level=level, message=message, context=context or {}))
        logger.log(getattr(logging, level.upper(), logging.INFO), message)


engine = BotEngine()
