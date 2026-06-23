"""Modelo de ejecución realista: slippage según liquidez e impacto de mercado.

El backtesting ingenuo asume un slippage fijo, lo que sobreestima el rendimiento de
órdenes grandes en mercados poco líquidos. Aquí el slippage crece con la participación
de la orden en el volumen de la vela, y se limita el tamaño para no "comerse" todo el
volumen disponible. Funciones puras: las usan tanto el backtest como el paper en vivo.
"""

from __future__ import annotations

from app.schemas.config import ExecutionConfig


def effective_slippage_pct(
    base_slippage_pct: float,
    order_value: float,
    bar_quote_volume: float,
    exec_cfg: ExecutionConfig,
) -> float:
    """Slippage efectivo (%) ajustado por el tamaño de la orden frente al volumen de la vela.

    `bar_quote_volume` es el volumen de la vela en moneda de cotización (volumen * precio).
    Si la ejecución realista está desactivada o no hay volumen, devuelve el slippage base.
    """
    if not exec_cfg.liquidity_aware_slippage or bar_quote_volume <= 0 or order_value <= 0:
        return base_slippage_pct
    participation = order_value / bar_quote_volume  # fracción del volumen que somos
    impact_pct = exec_cfg.market_impact_factor * participation * 100.0
    return base_slippage_pct + impact_pct


def cap_quantity_by_liquidity(
    quantity: float,
    price: float,
    bar_quote_volume: float,
    exec_cfg: ExecutionConfig,
) -> float:
    """Limita la cantidad para no superar el % máximo de participación en el volumen."""
    if not exec_cfg.liquidity_aware_slippage or bar_quote_volume <= 0 or price <= 0:
        return quantity
    max_value = bar_quote_volume * exec_cfg.max_volume_participation_pct / 100.0
    max_qty = max_value / price
    return min(quantity, max_qty)
