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
    # --- Riesgo a nivel de cartera (mejora: no concentrar el riesgo) ---
    max_portfolio_exposure_pct: float = Field(
        100.0, ge=5.0, le=100.0,
        description="% máximo del equity invertido en posiciones a la vez (resto en efectivo).",
    )
    max_correlated_positions: int = Field(
        2, ge=1, le=50,
        description="Máx. de posiciones con correlación alta entre sí (evita riesgo de clúster).",
    )
    correlation_threshold: float = Field(
        0.8, ge=0.1, le=1.0,
        description="Correlación a partir de la cual dos activos cuentan como 'correlacionados'.",
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


class StrategyWeight(BaseModel):
    """Una estrategia dentro del ensemble, con su peso y parámetros propios."""

    id: str = Field(description="Identificador de la estrategia (p.ej. ma_cross).")
    weight: float = Field(1.0, ge=0.0, le=10.0, description="Peso del voto de esta estrategia.")
    params: dict = Field(default_factory=dict, description="Parámetros propios (sobrescriben los por defecto).")


class EnsembleConfig(BaseModel):
    """Multi-estrategia: combina varias estrategias por votación ponderada."""

    enabled: bool = Field(False, description="Si está activo, se usa el ensemble en vez de la estrategia única.")
    strategies: list[StrategyWeight] = Field(
        default_factory=list, description="Estrategias que votan, con su peso.",
    )
    buy_threshold: float = Field(
        0.5, ge=0.0, le=1.0,
        description="Puntuación de voto ponderada mínima (0-1) para emitir una compra.",
    )
    sell_threshold: float = Field(
        0.5, ge=0.0, le=1.0,
        description="Puntuación de voto ponderada mínima (0-1) para emitir una venta.",
    )


class AlertChannel(BaseModel):
    """Un canal de notificación (webhook entrante de Discord/Telegram/Slack o genérico)."""

    type: Literal["discord", "telegram", "slack", "generic"] = "discord"
    url: str = Field("", description="URL del webhook (o de la API de bot de Telegram).")
    extra: dict = Field(default_factory=dict, description="Datos extra, p.ej. chat_id para Telegram.")
    enabled: bool = True


class AlertConfig(BaseModel):
    """Avisos multi-canal de eventos del bot (operaciones, breaker, errores)."""

    enabled: bool = Field(False, description="Activar el envío de avisos a canales externos.")
    channels: list[AlertChannel] = Field(default_factory=list)
    on_trade_open: bool = Field(True, description="Avisar al abrir una operación.")
    on_trade_close: bool = Field(True, description="Avisar al cerrar una operación.")
    on_risk_event: bool = Field(True, description="Avisar en breaker/límite diario/kill switch.")
    on_error: bool = Field(True, description="Avisar en errores del ciclo.")


class ExecutionConfig(BaseModel):
    """Modelo de ejecución para hacer el backtesting/paper más realista."""

    liquidity_aware_slippage: bool = Field(
        False,
        description="Slippage adaptativo según el tamaño de la orden frente al volumen de la vela.",
    )
    market_impact_factor: float = Field(
        0.5, ge=0.0, le=10.0,
        description="Cuánto penaliza el impacto de mercado (mayor = más slippage en órdenes grandes).",
    )
    max_volume_participation_pct: float = Field(
        5.0, ge=0.1, le=100.0,
        description="% máx. del volumen de la vela que una orden puede representar (limita el tamaño).",
    )


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
    ensemble: EnsembleConfig = Field(default_factory=EnsembleConfig)
    risk: RiskConfig = Field(default_factory=RiskConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    alerts: AlertConfig = Field(default_factory=AlertConfig)
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)

    fee_pct: float = Field(0.1, ge=0.0, le=5.0, description="Comisión simulada por operación (%).")
    slippage_pct: float = Field(0.05, ge=0.0, le=5.0, description="Slippage simulado (%).")
