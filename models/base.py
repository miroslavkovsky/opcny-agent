"""
SQLAlchemy async engine + session factory.
Zdieľa PostgreSQL databázu s hlavnou opcnysimulator appkou.
"""

import asyncio
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from config.settings import settings

logger = logging.getLogger("opcny-agents.db")

engine = create_async_engine(
    settings.database_url,
    echo=settings.is_development,
    pool_size=5,        # Agent worker nepotrebuje veľký pool
    max_overflow=2,
)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def init_db(max_retries: int = 5, base_delay: float = 2.0) -> None:
    """Vytvorí tabuľky ak neexistujú. Retry s exponential backoff pri nedostupnej DB."""
    for attempt in range(1, max_retries + 1):
        try:
            has_pgvector = False
            async with engine.begin() as conn:
                # pgvector extension — optional, memory feature won't work without it
                try:
                    await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                    has_pgvector = True
                except Exception as vec_exc:
                    logger.warning(
                        "pgvector extension not available — agent memory disabled: %s",
                        vec_exc,
                    )

            # Vytvor tabuľky v novej transakcii
            tables = [
                t for t in Base.metadata.sorted_tables
                if has_pgvector or t.name != "agent_memory"
            ]
            async with engine.begin() as conn:
                await conn.run_sync(
                    lambda sync_conn: Base.metadata.create_all(
                        sync_conn, tables=tables, checkfirst=True,
                    )
                )

            if not has_pgvector:
                logger.info(
                    "Databáza inicializovaná (bez agent_memory — pgvector chýba)."
                )
            else:
                logger.info("Databáza inicializovaná úspešne.")
            return
        except Exception as exc:
            if attempt == max_retries:
                logger.error("DB connection failed after %d attempts: %s", max_retries, exc)
                raise
            delay = base_delay * (2 ** (attempt - 1))
            logger.warning(
                "DB connection attempt %d/%d failed: %s — retry in %.1fs",
                attempt, max_retries, exc, delay,
            )
            await asyncio.sleep(delay)


async def get_session() -> AsyncSession:
    """Dependency pre FastAPI alebo manuálne použitie."""
    async with async_session() as session:
        yield session
