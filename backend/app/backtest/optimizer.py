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

# Rangos de riesgo a probar automáticamente.
_RISK_RANGES = {
    "risk_per_trade_pct": (0.5, 2.5, 0.5),  # (min, max, step)
    "stop_loss_pct": (1.5, 5.0, 0.5),
    "take_profit_pct": (3.0, 10.0, 1.0),
    "atr_multiplier": (1.5, 3.5, 0.5),
    "max_open_positions": (2, 6, 1),
}

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
    params: dict  # parámetros de la estrategia
    risk_config: dict  # parámetros de riesgo (serializado)
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
                    "risk_config": r.risk_config,
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


def _sample_risks(n: int) -> list[RiskConfig]:
    """Combinaciones aleatorias de riesgo a probar."""
    default = RiskConfig()
    risks: list[RiskConfig] = [default]
    seen = set()

    for _ in range(n - 1):  # default ya cuenta como 1
        min_r, max_r, step_r = _RISK_RANGES["risk_per_trade_pct"]
        steps_r = max(1, int((max_r - min_r) / step_r))
        risk_pct = min_r + random.randint(0, steps_r) * step_r

        min_sl, max_sl, step_sl = _RISK_RANGES["stop_loss_pct"]
        steps_sl = max(1, int((max_sl - min_sl) / step_sl))
        sl = min_sl + random.randint(0, steps_sl) * step_sl

        min_tp, max_tp, step_tp = _RISK_RANGES["take_profit_pct"]
        steps_tp = max(1, int((max_tp - min_tp) / step_tp))
        tp = min_tp + random.randint(0, steps_tp) * step_tp

        use_atr = random.choice([True, False])
        min_atr, max_atr, step_atr = _RISK_RANGES["atr_multiplier"]
        steps_atr = max(1, int((max_atr - min_atr) / step_atr))
        atr_mult = min_atr + random.randint(0, steps_atr) * step_atr

        trailing = random.choice([None, 1.0, 2.0, 3.0])

        min_pos, max_pos, step_pos = _RISK_RANGES["max_open_positions"]
        max_pos_val = min_pos + random.randint(0, int((max_pos - min_pos) / step_pos)) * int(step_pos)

        risk = RiskConfig(
            risk_per_trade_pct=round(risk_pct, 2),
            stop_loss_pct=round(sl, 1),
            take_profit_pct=round(tp, 1),
            use_atr_stops=use_atr,
            atr_multiplier=round(atr_mult, 1),
            trailing_stop_pct=trailing,
            max_open_positions=int(max_pos_val),
        )
        key = (risk_pct, sl, tp, use_atr, atr_mult, trailing, max_pos_val)
        if key not in seen:
            seen.add(key)
            risks.append(risk)
    return risks[:n]


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
    samples_risk = max(1, min(20, samples // 2 + 1))  # también muestra riesgos (menos que estrategias)
    if objective not in OBJECTIVES:
        objective = "total_return_pct"

    # Plan: (estrategia, parámetros estrategia, RiskConfig) para cada combinación.
    plan: list[tuple[str, dict, RiskConfig]] = []
    risk_samples = _sample_risks(samples_risk)
    for sid in ids:
        try:
            strat = get_strategy(sid)
        except KeyError:
            continue
        for params in _sample_params(strat, samples):
            for risk_cfg in risk_samples:
                plan.append((sid, params, risk_cfg))

    job = OptJob(id=job_id, total=len(plan), objective=objective, symbol=symbol, timeframe=timeframe)
    with _LOCK:
        _JOBS[job_id] = job
        # Poda de trabajos antiguos para no acumular memoria.
        while len(_JOBS) > _MAX_JOBS:
            _JOBS.pop(next(iter(_JOBS)))

    threading.Thread(
        target=_run_job,
        args=(job, plan, symbol, timeframe, days, starting_capital, fee_pct, slippage_pct),
        daemon=True,
    ).start()
    return job_id


def _run_job(
    job: OptJob,
    plan: list[tuple[str, dict, RiskConfig]],
    symbol: str,
    timeframe: str,
    days: int,
    starting_capital: float,
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
        for sid, params, risk_cfg in plan:
            try:
                res = simulate(
                    df, strategy_id=sid, strategy_params=params, risk=risk_cfg, timeframe=timeframe,
                    starting_capital=starting_capital, fee_pct=fee_pct, slippage_pct=slippage_pct,
                )
                m = res.metrics
                if not m.get("error") and m.get("num_trades", 0) >= 1:
                    results.append(
                        OptResult(sid, get_strategy(sid).name, params, risk_cfg.model_dump(), m, _score(m, job.objective))
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
