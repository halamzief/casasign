"""SQLAlchemy Async Engine Configuration for FES microservice."""

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from src.config import settings

_engine: AsyncEngine | None = None


def get_engine() -> AsyncEngine:
    """Get or create the singleton async engine."""
    global _engine

    if _engine is None:
        _engine = create_async_engine(
            settings.database_url,
            echo=settings.debug,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            pool_recycle=3600,
        )
        logger.info("SQLAlchemy async engine created")

    return _engine


async def dispose_engine() -> None:
    """Dispose the engine and close all connections."""
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        logger.info("SQLAlchemy engine disposed")
