import logging
from typing import AsyncGenerator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

logger = logging.getLogger(__name__)

# Initialize asynchronous SQLAlchemy 2.0 engine
# Note: Production database target is Supabase PostgreSQL.
# statement_cache_size=0 ensures compatibility with Supabase connection poolers (Supavisor / PgBouncer).
async_engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    future=True,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    connect_args={"statement_cache_size": 0},
)

# Asynchronous session factory
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """Base Declarative Class for all future SQLAlchemy models.
    No business tables are defined in Step 5 foundation.
    """
    pass


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for providing asynchronous database sessions to FastAPI routes."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def check_database_health() -> bool:
    """Execute a minimal query (SELECT 1) to verify database connectivity safely.
    Never exposes passwords, tokens, or connection strings in logs or exceptions.
    """
    try:
        async with async_engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            scalar = result.scalar()
            return scalar == 1
    except Exception as exc:
        # Log only the error class name — never log connection strings or credentials
        logger.warning(f"Database connectivity check failed: {type(exc).__name__}")
        return False
