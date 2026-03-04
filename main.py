"""
OpcnySimulator Agent Worker — Entry Point

Spustí FastAPI server (health checks + internal API) a APScheduler (agent joby).
"""

import asyncio
import logging

import uvicorn
from fastapi import FastAPI

from api.routes import router
from config.settings import settings
from models.base import init_db
from tasks.scheduler import AgentScheduler

logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s | %(name)-20s | %(levelname)-7s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger("opcny-agents")

app = FastAPI(
    title="OpcnySimulator Agents",
    version="0.1.0",
    docs_url="/docs" if settings.is_development else None,
)
app.include_router(router)


@app.on_event("startup")
async def startup():
    logger.info("Inicializácia databázy...")
    await init_db()

    logger.info("Spúšťam agent scheduler...")
    scheduler = AgentScheduler()
    await scheduler.start()
    app.state.scheduler = scheduler

    logger.info("Agent Worker Service je pripravený.")


@app.on_event("shutdown")
async def shutdown():
    logger.info("Zastavujem scheduler...")
    if hasattr(app.state, "scheduler"):
        await app.state.scheduler.stop()


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.agent_api_port,
        log_level=settings.log_level.lower(),
    )
