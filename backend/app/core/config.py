"""Configuración de entorno de la aplicación (no confundir con la config del bot).

Esto controla cosas de infraestructura (puerto, base de datos, secretos), que se
fijan al desplegar. La configuración *del bot* (riesgo, estrategia, etc.) es editable
en caliente desde la UI y vive en la base de datos — ver `app/schemas/config.py`.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """Variables de entorno. Se leen de `.env` o del entorno del sistema."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- General ---
    app_name: str = "Algorise"
    environment: str = "local"  # local | cloud
    debug: bool = True

    # --- Base de datos ---
    # Por defecto SQLite (cero configuración). Para nube: postgresql+psycopg://...
    database_url: str = "sqlite:///./algorise.db"

    # --- Seguridad / auth ---
    # En local se autogenera una clave; en nube DEBES fijar SECRET_KEY en el entorno.
    secret_key: str = "dev-insecure-change-me-in-production"
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 días
    # Usuario único (local). La contraseña se hashea en el primer arranque.
    default_username: str = "admin"
    default_password: str = "admin"

    # --- CORS (orígenes del frontend permitidos) ---
    cors_origins: str = "*"

    # --- Datos de mercado ---
    exchange_id: str = "binance"
    # Claves SOLO para futuro dinero real. Vacías = paper / datos públicos.
    exchange_api_key: str = ""
    exchange_api_secret: str = ""

    # --- IA / LLM (valores por defecto; se pueden cambiar en la UI) ---
    ollama_base_url: str = "http://localhost:11434"
    groq_api_key: str = ""
    gemini_api_key: str = ""

    @property
    def cors_origins_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> AppSettings:
    return AppSettings()
