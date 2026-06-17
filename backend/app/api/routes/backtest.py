"""Backtesting: validar una estrategia+config sobre histórico antes de operar."""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.backtest import optimizer
from app.backtest.engine import run_backtest
from app.db.database import get_db
from app.schemas.config import RiskConfig, Timeframe
from app.services.settings_service import get_config

router = APIRouter(prefix="/backtest", tags=["backtest"], dependencies=[Depends(get_current_user)])


class BacktestRequest(BaseModel):
    symbol: str = "BTC/USDT"
    timeframe: Timeframe = "1h"
    strategy_id: str = "ma_cross"
    strategy_params: dict = Field(default_factory=dict)
    days: int = Field(90, ge=1, le=1000, description="Días de histórico hacia atrás.")
    starting_capital: float = Field(10_000.0, ge=10.0)
    risk: RiskConfig | None = None  # si es nulo, usa la config guardada
    fee_pct: float | None = None
    slippage_pct: float | None = None


@router.post("")
def backtest(req: BacktestRequest, db: Session = Depends(get_db)) -> dict:
    config = get_config(db)
    risk = req.risk or config.risk
    fee = req.fee_pct if req.fee_pct is not None else config.fee_pct
    slippage = req.slippage_pct if req.slippage_pct is not None else config.slippage_pct
    since_ms = int(time.time() * 1000) - req.days * 86_400_000
    try:
        result = run_backtest(
            symbol=req.symbol,
            timeframe=req.timeframe,
            strategy_id=req.strategy_id,
            strategy_params=req.strategy_params,
            risk=risk,
            since_ms=since_ms,
            starting_capital=req.starting_capital,
            fee_pct=fee,
            slippage_pct=slippage,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Error en el backtest: {exc}") from exc
    return result.to_dict()


class OptimizeRequest(BaseModel):
    """Backtesting automático: barre estrategias y parámetros buscando las mejores configs."""

    symbol: str = "BTC/USDT"
    timeframe: Timeframe = "1h"
    days: int = Field(120, ge=10, le=1000, description="Días de histórico para optimizar.")
    starting_capital: float = Field(10_000.0, ge=10.0)
    strategy_ids: list[str] | None = Field(None, description="Estrategias a probar; nulo = todas.")
    samples_per_strategy: int = Field(15, ge=1, le=60, description="Combinaciones por estrategia.")
    objective: str = Field("total_return_pct", description="Métrica a maximizar.")
    risk: RiskConfig | None = None
    fee_pct: float | None = None
    slippage_pct: float | None = None


@router.get("/objectives")
def objectives() -> dict:
    """Métricas disponibles para optimizar (clave -> etiqueta para la UI)."""
    return optimizer.OBJECTIVES


@router.post("/optimize")
def optimize(req: OptimizeRequest, db: Session = Depends(get_db)) -> dict:
    """Lanza una optimización en segundo plano y devuelve su id para consultar el progreso."""
    config = get_config(db)
    risk = req.risk or config.risk
    fee = req.fee_pct if req.fee_pct is not None else config.fee_pct
    slippage = req.slippage_pct if req.slippage_pct is not None else config.slippage_pct
    job_id = optimizer.start_optimization(
        symbol=req.symbol,
        timeframe=req.timeframe,
        days=req.days,
        starting_capital=req.starting_capital,
        strategy_ids=req.strategy_ids,
        samples_per_strategy=req.samples_per_strategy,
        objective=req.objective,
        risk=risk,
        fee_pct=fee,
        slippage_pct=slippage,
    )
    return {"job_id": job_id}


@router.get("/optimize/{job_id}")
def optimize_status(job_id: str) -> dict:
    """Estado y resultados (cuando termina) de una optimización."""
    job = optimizer.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Optimización no encontrada (pudo expirar tras reiniciar).")
    return job.to_dict()
