"""Paquete de estrategias. Importar aquí registra cada estrategia en el registro."""

from app.strategies.base import Signal, Strategy, get_strategy, list_strategies, register
from app.strategies import builtin  # noqa: F401  (registra las estrategias incluidas)

__all__ = ["Signal", "Strategy", "get_strategy", "list_strategies", "register"]
