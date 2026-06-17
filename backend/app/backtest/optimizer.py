"""Backtesting automático: prueba muchas combinaciones de estrategia + parámetros y
devuelve las mejores.

Para ser rápido, descarga el histórico de Binance UNA sola vez y luego simula en memoria
todas las combinaciones. El trabajo corre en un hilo aparte (puede tardar) y la UI consulta
el progreso por su id.
"""

from __future__ import annotations

import logging
import random
import threading
import time
import uuid
from dataclasses import dataclass, field

from app.backtest.engine import simulate
from app.market.provider import get_market_provider
from app.schemas.config import RiskConfig
from app.strategies import get_strategy, list_strategies

logger = logging.getLogger("algorise.optimizer")

# Métricas por las que se puede optimizar (todas "más alto = mejor").
OBJECTIVES: dict[str, str] = {
    "total_return_pct": "Retorno total",
    "vs_buy_hold_pct": "Ventaja sobre comprar y mantener",
    "sharpe_ratio": "Ratio de Sharpe (ajustado a riesgo)",
    "profit_factor": "Profit factor",
    "win_rate_pct": "% de aciertos",
}

_MAX_SAMPLES = 60
_MAX_JOBS = 8
_TOP_N = 10


@dataclass
class OptResult:
    strategy_id: str
    strategy_name: str
    params: dict
    metrics: dict
    score: float


@dataclass
class OptJob:
    id: str
    status: str = "running"  # running | done | error
    total: int = 0
    done: int = 0
    objective: str = "total_return_pct"
    symbol: str = ""
    timeframe: str = ""
    results: list[OptResult] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "status": self.status,
            "total": self.total,
            "done": self.done,
            "objective": self.objective,
            "objective_label": OBJECTIVES.get(self.objective, self.objective),
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "error": self.error,
            "results": [
                {
                    "rank": i + 1,
                    "strategy_id": r.strategy_id,
                    "strategy_name": r.strategy_name,
                    "params": r.params,
                    "metrics": r.metrics,
                    "score": r.score,
                }
                for i, r in enumerate(self.results)
            ],
        }


_JOBS: dict[str, OptJob] = {}
_LOCK = threading.Lock()


def _valid_params(params: dict) -> bool:
    """Descarta combinaciones sin sentido (rápido >= lento, sobreventa >= sobrecompra)."""

    def lt(a: str, b: str) -> bool:
        return a not in params or b not in params or params[a] < params[b]

    return (
        lt("fast_period", "slow_period")
        and lt("fast", "slow")
        and lt("oversold", "overbought")
        and lt("rsi_buy", "rsi_exit")
    )


def _sample_params(strat, n: int) -> list[dict]:
    """Combinaciones de parámetros a probar: las por defecto + muestreo aleatorio del rango."""
    default = strat.default_params()
    combos: list[dict] = [default]
    seen = {tuple(sorted(default.items()))}
    attempts = 0
    while len(combos) < n and attempts < n * 30:
        attempts += 1
        params = {}
        for p in strat.params:
            steps = max(1, int(round((p.max - p.min) / p.step)))
            raw = p.min + random.randint(0, steps) * p.step
            params[p.key] = int(round(raw)) if p.type == "int" else round(raw, 4)
        if not _valid_params(params):
            continue
        key = tuple(sorted(params.items()))
        if key not in seen:
            seen.add(key)
            combos.append(params)
    return combos


def _score(metrics: dict, objective: str) -> float:
    """Puntuación finita para ordenar (evita inf por compatibilidad con JSON)."""
    val = metrics.get(objective)
    if val is None:
        # profit_factor None = sin pérdidas (lo mejor posible); el resto, lo peor.
        return 1e9 if objective == "profit_factor" else -1e9
    return float(val)


def start_optimization(
    *,
    symbol: str,
    timeframe: str,
    days: int,
    starting_capital: float,
    strategy_ids: list[str] | None,
    samples_per_strategy: int,
    objective: str,
    risk: RiskConfig,
    fee_pct: float,
    slippage_pct: float,
) -> str:
    job_id = uuid.uuid4().hex[:12]
    ids = strategy_ids or [s.id for s in list_strategies()]
    samples = max(1, min(_MAX_SAMPLES, samples_per_strategy))
    if objective not in OBJECTIVES:
        objective = "total_return_pct"

    # Plan de simulaciones: (estrategia, parámetros) para cada combinación.
    plan: list[tuple[str, dict]] = []
    for sid in ids:
        try:
            strat = get_strategy(sid)
        except KeyError:
            continue
        for params in _sample_params(strat, samples):
            plan.append((sid, params))

    job = OptJob(id=job_id, total=len(plan), objective=objective, symbol=symbol, timeframe=timeframe)
    with _LOCK:
        _JOBS[job_id] = job
        # Poda de trabajos antiguos para no acumular memoria.
        while len(_JOBS) > _MAX_JOBS:
            _JOBS.pop(next(iter(_JOBS)))

    threading.Thread(
        target=_run_job,
        args=(job, plan, symbol, timeframe, days, starting_capital, risk, fee_pct, slippage_pct),
        daemon=True,
    ).start()
    return job_id


def _run_job(
    job: OptJob,
    plan: list[tuple[str, dict]],
    symbol: str,
    timeframe: str,
    days: int,
    starting_capital: float,
    risk: RiskConfig,
    fee_pct: float,
    slippage_pct: float,
) -> None:
    try:
        provider = get_market_provider()
        since_ms = int(time.time() * 1000) - days * 86_400_000
        df = provider.fetch_ohlcv_history(symbol, timeframe, since_ms)
        if len(df) < 50:
            job.status = "error"
            job.error = "Histórico insuficiente para optimizar (prueba más días o un marco temporal menor)."
            return

        results: list[OptResult] = []
        for sid, params in plan:
            try:
                res = simulate(
                    df, strategy_id=sid, strategy_params=params, risk=risk, timeframe=timeframe,
                    starting_capital=starting_capital, fee_pct=fee_pct, slippage_pct=slippage_pct,
                )
                m = res.metrics
                if not m.get("error") and m.get("num_trades", 0) >= 1:
                    results.append(
                        OptResult(sid, get_strategy(sid).name, params, m, _score(m, job.objective))
                    )
            except Exception:  # noqa: BLE001
                logger.exception("Fallo simulando %s con %s", sid, params)
            finally:
                job.done += 1

        results.sort(key=lambda r: r.score, reverse=True)
        job.results = results[:_TOP_N]
        job.status = "done"
    except Exception as exc:  # noqa: BLE001
        logger.exception("Optimización fallida")
        job.status = "error"
        job.error = str(exc)


def get_job(job_id: str) -> OptJob | None:
    return _JOBS.get(job_id)
