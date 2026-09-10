import os
from collections.abc import AsyncGenerator, Generator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

from ..core.config import get_settings

settings = get_settings()

# Supabase (and most hosted Postgres) require SSL. asyncpg needs ssl="require"
# explicitly when connecting to a pooler / cloud host.
_is_production = bool(os.getenv("DATABASE_URL", ""))
_async_connect_args: dict = {"timeout": 5}
if _is_production:
    # asyncpg accepts ssl as a string or ssl.SSLContext
    _async_connect_args["ssl"] = "require"

# Async engine for FastAPI endpoints
async_engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,
    connect_args=_async_connect_args,
)
AsyncSessionLocal = async_sessionmaker(async_engine, expire_on_commit=False, class_=AsyncSession)

# Sync engine for Alembic migrations (psycopg2 — handles SSL via sslmode param in URL)
sync_engine = create_engine(
    settings.sync_database_url,
    echo=False,
    pool_pre_ping=True,
    connect_args={"connect_timeout": 5},
)
SyncSessionLocal = sessionmaker(bind=sync_engine, autocommit=False, autoflush=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def get_sync_db() -> Generator[Session, None, None]:
    db = SyncSessionLocal()
    try:
        yield db
    finally:
        db.close()
