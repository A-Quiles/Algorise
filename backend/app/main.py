"""Punto de entrada de la API de Algorise (FastAPI)."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import ws
from app.api.routes import ai, auth, backtest, bot, config, dashboard, market, strategies, trades
from app.bot.engine import engine
from app.core.bootstrap import bootstrap
from app.core.config import get_settings
from app.db.database import init_db, session_scope

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("algorise")

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Arranque: crear tablas, sembrar datos por defecto y preparar el bot.
    init_db()
    with session_scope() as db:
        bootstrap(db)
    engine.init_scheduler()
    engine.sync_on_startup()
    logger.info("Algorise listo (modo paper). BBDD: %s", settings.database_url)
    yield
    # Apagado
    if engine.scheduler.running:
        engine.scheduler.shutdown(wait=False)


app = FastAPI(title="Algorise API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers de la API (todo bajo /api)
api_routers = [auth, config, bot, market, strategies, trades, dashboard, backtest, ai]
for module in api_routers:
    app.include_router(module.router, prefix="/api")
app.include_router(ws.router, prefix="/api")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "app": settings.app_name, "mode": "paper"}
