from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import AsyncGenerator, Generator
from ..core.config import get_settings

settings = get_settings()

# Async engine for FastAPI endpoints
# connect_args timeout: fail fast if DB unreachable (don't block startup)
async_engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,
    connect_args={"timeout": 5},  # asyncpg: 5s connection timeout
)
AsyncSessionLocal = async_sessionmaker(async_engine, expire_on_commit=False, class_=AsyncSession)

# Sync engine for Alembic migrations
sync_engine = create_engine(
    settings.sync_database_url,
    echo=False,
    pool_pre_ping=True,
    connect_args={"connect_timeout": 5},  # psycopg2: 5s connection timeout
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
