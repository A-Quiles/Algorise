"""Avisos multi-canal: envía eventos del bot a Discord, Telegram, Slack o un webhook genérico.

Es best-effort: nunca lanza excepciones hacia el bot (un fallo de red no debe tumbar el
ciclo). Se llama desde el motor en eventos clave (abrir/cerrar operación, breaker, error).
Como el ciclo del bot corre en un hilo aparte, usamos httpx síncrono con timeout corto.
"""

from __future__ import annotations

import logging

import httpx

from app.schemas.config import AlertChannel, AlertConfig

logger = logging.getLogger("algorise.alerts")

# Mapa evento -> atributo de AlertConfig que lo habilita.
_EVENT_GATES = {
    "trade_open": "on_trade_open",
    "trade_close": "on_trade_close",
    "risk": "on_risk_event",
    "error": "on_error",
}


def _format_text(title: str, message: str, fields: dict | None) -> str:
    text = f"**{title}**\n{message}" if message else f"**{title}**"
    if fields:
        text += "\n" + "\n".join(f"• {k}: {v}" for k, v in fields.items())
    return text


def _dispatch(channel: AlertChannel, title: str, message: str, fields: dict | None) -> None:
    text = _format_text(title, message, fields)
    try:
        if channel.type == "discord":
            httpx.post(channel.url, json={"content": text}, timeout=8)
        elif channel.type == "slack":
            httpx.post(channel.url, json={"text": text}, timeout=8)
        elif channel.type == "telegram":
            chat_id = channel.extra.get("chat_id")
            # channel.url = https://api.telegram.org/bot<token>
            httpx.post(f"{channel.url}/sendMessage",
                       json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}, timeout=8)
        else:  # generic
            httpx.post(channel.url, json={"title": title, "message": message, "fields": fields or {}}, timeout=8)
    except Exception as exc:  # noqa: BLE001
        logger.warning("No se pudo enviar el aviso a %s: %s", channel.type, exc)


def send_alert(
    cfg: AlertConfig,
    event: str,
    title: str,
    message: str = "",
    fields: dict | None = None,
) -> None:
    """Envía un aviso a todos los canales habilitados si el evento está activado."""
    if not cfg.enabled:
        return
    gate = _EVENT_GATES.get(event)
    if gate and not getattr(cfg, gate, True):
        return
    for channel in cfg.channels:
        if channel.enabled and channel.url:
            _dispatch(channel, title, message, fields)
