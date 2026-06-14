"""Estrategias disponibles (para que la UI las liste y pinte sus parámetros)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_current_user
from app.strategies import get_strategy, list_strategies

router = APIRouter(prefix="/strategies", tags=["strategies"], dependencies=[Depends(get_current_user)])


@router.get("")
def all_strategies() -> list[dict]:
    return [s.to_dict() for s in list_strategies()]


@router.get("/{strategy_id}")
def one_strategy(strategy_id: str) -> dict:
    try:
        return get_strategy(strategy_id).to_dict()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
