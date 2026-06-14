"""Capa de IA: valida y explica las señales del bot usando un LLM gratuito.

Proveedores soportados vía LiteLLM (una sola interfaz): Ollama (local), Groq y Gemini.
El LLM NO inventa operaciones: recibe una señal cuantitativa ya calculada y decide si
**confirmarla o vetarla**, con un nivel de confianza y una explicación en lenguaje natural.

Es tolerante a fallos: si el LLM no está disponible, deja pasar la señal cuantitativa
(con una nota), para que el bot siga funcionando sin depender de la IA.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

import litellm

from app.core.config import get_settings
from app.schemas.config import LLMConfig
from app.strategies.base import Signal

logger = logging.getLogger("algorise.ai")
litellm.suppress_debug_info = True

app_settings = get_settings()


@dataclass
class AdvisorVerdict:
    decision: str  # "confirm" | "veto"
    confidence: float  # 0..1
    explanation: str
    used_llm: bool


def _resolve_model(cfg: LLMConfig) -> tuple[str, dict]:
    """Traduce (proveedor, modelo) al formato de LiteLLM y sus kwargs de conexión."""
    kwargs: dict = {}
    if cfg.provider == "ollama":
        model = f"ollama/{cfg.model}"
        kwargs["api_base"] = app_settings.ollama_base_url
    elif cfg.provider == "groq":
        model = f"groq/{cfg.model}"
        kwargs["api_key"] = app_settings.groq_api_key
    elif cfg.provider == "gemini":
        model = f"gemini/{cfg.model}"
        kwargs["api_key"] = app_settings.gemini_api_key
    else:
        model = cfg.model
    return model, kwargs


_SYSTEM_PROMPT = (
    "Eres un analista de trading de criptomonedas experto y prudente. Recibes una señal "
    "generada por una estrategia cuantitativa y tu trabajo es decidir si CONFIRMARLA o "
    "VETARLA según el contexto. Sé conservador ante señales débiles o contradictorias. "
    "Responde SIEMPRE y SOLO con un objeto JSON válido con esta forma exacta: "
    '{"decision": "confirm"|"veto", "confidence": 0.0-1.0, "explanation": "texto breve en español"}'
)


def _build_user_prompt(symbol: str, signal: Signal, context: dict) -> str:
    return (
        f"Par: {symbol}\n"
        f"Acción propuesta por la estrategia: {signal.action.upper()}\n"
        f"Fuerza de la señal (0-1): {signal.strength:.2f}\n"
        f"Razón cuantitativa: {signal.reason}\n"
        f"Indicadores: {json.dumps(signal.indicators, ensure_ascii=False)}\n"
        f"Contexto de mercado: {json.dumps(context, ensure_ascii=False)}\n\n"
        "¿Confirmas o vetas esta operación? Devuelve solo el JSON."
    )


def _parse_verdict(text: str) -> tuple[str, float, str] | None:
    """Extrae el JSON del veredicto del texto del modelo (tolerante a texto alrededor)."""
    try:
        start = text.index("{")
        end = text.rindex("}") + 1
        data = json.loads(text[start:end])
        decision = str(data.get("decision", "")).lower()
        if decision not in ("confirm", "veto"):
            return None
        confidence = float(data.get("confidence", 0.5))
        explanation = str(data.get("explanation", "")).strip()
        return decision, max(0.0, min(1.0, confidence)), explanation
    except (ValueError, json.JSONDecodeError, TypeError):
        return None


def advise(symbol: str, signal: Signal, cfg: LLMConfig, context: dict | None = None) -> AdvisorVerdict:
    """Consulta al LLM para validar una señal accionable (buy/sell)."""
    context = context or {}

    # IA desactivada: pasa la señal cuantitativa tal cual.
    if not cfg.enabled:
        return AdvisorVerdict("confirm", signal.strength, signal.reason, used_llm=False)

    model, kwargs = _resolve_model(cfg)
    try:
        response = litellm.completion(
            model=model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": _build_user_prompt(symbol, signal, context)},
            ],
            temperature=cfg.temperature,
            timeout=30,
            **kwargs,
        )
        text = response["choices"][0]["message"]["content"]
        parsed = _parse_verdict(text)
        if parsed is None:
            logger.warning("Respuesta del LLM no parseable; se usa la señal cuantitativa.")
            return AdvisorVerdict("confirm", signal.strength, f"{signal.reason} (IA: respuesta no válida)", used_llm=False)

        decision, confidence, explanation = parsed
        # Aplica el umbral de veto: confianza baja => vetar.
        if decision == "confirm" and confidence < cfg.veto_threshold:
            decision = "veto"
            explanation = f"{explanation} (confianza {confidence:.2f} < umbral {cfg.veto_threshold:.2f})"
        return AdvisorVerdict(decision, confidence, explanation or signal.reason, used_llm=True)

    except Exception as exc:  # noqa: BLE001
        logger.warning("LLM no disponible (%s); se usa la señal cuantitativa.", exc)
        return AdvisorVerdict("confirm", signal.strength, f"{signal.reason} (IA no disponible)", used_llm=False)


def market_commentary(symbol: str, indicators: dict, cfg: LLMConfig) -> str:
    """Comentario breve de la IA sobre el estado del mercado (para la vista Insights)."""
    if not cfg.enabled:
        return "Capa de IA desactivada."
    model, kwargs = _resolve_model(cfg)
    try:
        response = litellm.completion(
            model=model,
            messages=[
                {"role": "system", "content": "Eres un analista de cripto conciso. Responde en español, 2-3 frases."},
                {"role": "user", "content": f"Estado de {symbol}. Indicadores: {json.dumps(indicators, ensure_ascii=False)}. Da una lectura breve del momento de mercado."},
            ],
            temperature=cfg.temperature,
            timeout=30,
            **kwargs,
        )
        return response["choices"][0]["message"]["content"].strip()
    except Exception as exc:  # noqa: BLE001
        return f"IA no disponible ({exc})."
