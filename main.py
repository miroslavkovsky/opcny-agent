"""
OpcnySimulator Agent Worker — Entry Point

Spustí FastAPI server (health checks + internal API) a APScheduler (agent joby).
"""

import asyncio
import logging
from contextlib import asynccontextmanager

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


async def _init_background(app: FastAPI) -> None:
    """Inicializácia DB a schedulera na pozadí — neblokuje štart servera."""
    try:
        logger.info("Inicializácia databázy (s retry)...")
        await init_db()

        logger.info("Spúšťam agent scheduler...")
        scheduler = AgentScheduler()
        await scheduler.start()
        app.state.scheduler = scheduler
        app.state.ready = True

        logger.info("Agent Worker Service je plne pripravený.")
    except Exception:
        logger.exception("Background init failed — server beží, ale agenti nie sú aktívni.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup a shutdown lifecycle pre FastAPI."""
    app.state.ready = False
    task = asyncio.create_task(_init_background(app))

    logger.info("Server štartuje na porte %d...", settings.server_port)

    yield

    # --- Shutdown ---
    if not task.done():
        task.cancel()
    logger.info("Zastavujem scheduler...")
    if hasattr(app.state, "scheduler"):
        await app.state.scheduler.stop()


app = FastAPI(
    title="OpcnySimulator Agents",
    version="0.1.0",
    docs_url="/docs" if settings.is_development else None,
    lifespan=lifespan,
)
app.include_router(router)


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.server_port,
        log_level=settings.log_level.lower(),
    )
