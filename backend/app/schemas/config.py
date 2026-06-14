"""Configuración del bot editable desde la UI (el corazón de "personalizar sin código").

Todo esto se guarda como JSON en la tabla `settings` y se valida con estos modelos
Pydantic. Añadir un parámetro nuevo aquí = aparece disponible en la API/UI sin más.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# Tipos auxiliares
BotMode = Literal["paper", "live"]
LLMProvider = Literal["ollama", "groq", "gemini"]
Timeframe = Literal["1m", "5m", "15m", "30m", "1h", "4h", "1d"]


class RiskConfig(BaseModel):
    """Gestión de riesgo. Estos son los controles más importantes para el usuario."""

    risk_per_trade_pct: float = Field(
        1.0, ge=0.05, le=100.0,
        description="% del capital total arriesgado en cada operación (define el tamaño de posición).",
    )
    stop_loss_pct: float = Field(2.0, ge=0.1, le=90.0, description="Stop-loss en % desde la entrada.")
    take_profit_pct: float = Field(4.0, ge=0.1, le=500.0, description="Take-profit en % desde la entrada.")
    use_atr_stops: bool = Field(False, description="Usar ATR (volatilidad) para los stops en vez de % fijo.")
    atr_multiplier: float = Field(2.0, ge=0.5, le=10.0, description="Multiplicador de ATR para el stop.")
    trailing_stop_pct: float | None = Field(
        None, ge=0.1, le=90.0, description="Trailing stop en %. Nulo = desactivado.",
    )
    max_open_positions: int = Field(3, ge=1, le=50, description="Máximo de posiciones abiertas a la vez.")
    max_daily_loss_pct: float = Field(
        5.0, ge=0.5, le=100.0, description="Pérdida diaria máxima (%) antes de pausar el bot.",
    )
    max_drawdown_pct: float = Field(
        20.0, ge=1.0, le=100.0, description="Drawdown máximo (%) — circuit breaker que detiene el bot.",
    )


class LLMConfig(BaseModel):
    """Capa de IA que valida y explica las operaciones."""

    enabled: bool = Field(True, description="Activar la capa de IA (validación + explicación).")
    provider: LLMProvider = Field("ollama", description="Proveedor de IA gratuito.")
    model: str = Field("llama3.1:8b", description="Modelo concreto del proveedor.")
    veto_threshold: float = Field(
        0.45, ge=0.0, le=1.0,
        description="Confianza mínima de la IA para permitir una operación. Por debajo, la veta.",
    )
    temperature: float = Field(0.3, ge=0.0, le=1.5, description="Creatividad del modelo (bajo = más estable).")
    use_news: bool = Field(False, description="Incluir titulares de noticias en el análisis (futuro).")


class BotConfig(BaseModel):
    """Configuración completa del bot. Una sola fuente de verdad, editable en caliente."""

    mode: BotMode = Field("paper", description="paper = dinero ficticio. live = dinero real (futuro).")
    base_currency: str = Field("USDT", description="Moneda de cotización (saldo del portfolio).")
    starting_capital: float = Field(10_000.0, ge=10.0, description="Capital virtual inicial.")
    pairs: list[str] = Field(
        default_factory=lambda: ["BTC/USDT", "ETH/USDT"],
        description="Pares que el bot puede operar.",
    )
    timeframe: Timeframe = Field("5m", description="Marco temporal de las velas y del ciclo del bot.")
    active_strategy: str = Field("ma_cross", description="Identificador de la estrategia activa.")
    strategy_params: dict = Field(
        default_factory=dict,
        description="Parámetros específicos de la estrategia activa (sobrescriben los por defecto).",
    )
    risk: RiskConfig = Field(default_factory=RiskConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)

    fee_pct: float = Field(0.1, ge=0.0, le=5.0, description="Comisión simulada por operación (%).")
    slippage_pct: float = Field(0.05, ge=0.0, le=5.0, description="Slippage simulado (%).")
