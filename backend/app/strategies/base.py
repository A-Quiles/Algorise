"""Arquitectura de estrategias enchufables.

Cada estrategia declara sus parámetros (para que la UI los pinte automáticamente) e
implementa `generate_signal`. Añadir una estrategia nueva = crear una clase y decorarla
con @register; aparece sola en la API/UI sin tocar nada más.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Literal

import pandas as pd

Action = Literal["buy", "sell", "hold"]


@dataclass
class Signal:
    """Resultado del análisis de una estrategia para un par en un momento dado."""

    action: Action = "hold"
    strength: float = 0.0  # 0..1, confianza de la señal cuantitativa
    reason: str = ""  # explicación corta en lenguaje natural
    indicators: dict = field(default_factory=dict)  # valores usados (para guardar/explicar)


@dataclass
class ParamSpec:
    """Descriptor de un parámetro configurable (la UI lo usa para generar el formulario)."""

    key: str
    label: str
    type: Literal["int", "float"]
    default: float
    min: float
    max: float
    step: float = 1.0
    description: str = ""


class Strategy(ABC):
    id: str = "base"
    name: str = "Base"
    description: str = ""
    params: list[ParamSpec] = []

    def default_params(self) -> dict:
        return {p.key: p.default for p in self.params}

    def resolve_params(self, overrides: dict | None) -> dict:
        """Mezcla los parámetros por defecto con los que el usuario haya fijado."""
        merged = self.default_params()
        if overrides:
            merged.update({k: v for k, v in overrides.items() if k in merged})
        return merged

    @abstractmethod
    def generate_signal(self, df: pd.DataFrame, params: dict) -> Signal:
        """Analiza el DataFrame OHLCV y devuelve una señal buy/sell/hold."""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "params": [p.__dict__ for p in self.params],
            "default_params": self.default_params(),
        }


_REGISTRY: dict[str, Strategy] = {}


def register(cls: type[Strategy]) -> type[Strategy]:
    """Decorador que registra una estrategia por su id."""
    instance = cls()
    _REGISTRY[instance.id] = instance
    return cls


def get_strategy(strategy_id: str) -> Strategy:
    if strategy_id not in _REGISTRY:
        raise KeyError(f"Estrategia desconocida: {strategy_id}. Disponibles: {list(_REGISTRY)}")
    return _REGISTRY[strategy_id]


def list_strategies() -> list[Strategy]:
    return list(_REGISTRY.values())
