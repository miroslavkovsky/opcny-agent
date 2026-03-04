"""
SQLAlchemy async engine + session factory.
Zdieľa PostgreSQL databázu s hlavnou opcnysimulator appkou.
"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from config.settings import settings

engine = create_async_engine(
    settings.database_url,
    echo=settings.is_development,
    pool_size=5,        # Agent worker nepotrebuje veľký pool
    max_overflow=2,
)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def init_db():
    """Vytvorí tabuľky ak neexistujú. V produkcii radšej použi Alembic migrácie."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncSession:
    """Dependency pre FastAPI alebo manuálne použitie."""
    async with async_session() as session:
        yield session
