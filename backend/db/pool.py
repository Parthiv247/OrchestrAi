"""
Singleton psycopg2 ThreadedConnectionPool.

Usage:
    from backend.db.pool import get_conn, put_conn, pool_context

    # Context manager (recommended — always returns conn to pool)
    with pool_context() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")

    # Manual (must call put_conn in finally block)
    conn = get_conn()
    try:
        ...
    finally:
        put_conn(conn)
"""
from __future__ import annotations

import logging
import os
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

import psycopg2
from dotenv import load_dotenv
from psycopg2.pool import ThreadedConnectionPool

# Load backend/.env (override=True so host.docker.internal wins over Docker service names)
# In Docker:  __file__ = /app/backend/db/pool.py  →  .parent.parent / ".env" = /app/backend/.env  ✓
# Natively:   __file__ = .../backend/db/pool.py   →  .parent.parent / ".env" = backend/.env       ✓
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env", override=True)

logger = logging.getLogger(__name__)

_pool: ThreadedConnectionPool | None = None

def _get_db_config() -> dict:
    """Build DB config from current env — called lazily so reloads pick up changes."""
    host = os.getenv("POSTGRES_HOST", "localhost")
    # Safety: Docker service name 'postgres' only works inside Docker network;
    # remap to 'localhost' when running natively.
    if host == "postgres":
        host = "localhost"
    return {
        "host":     host,
        "port":     int(os.getenv("POSTGRES_PORT", 5432)),
        "dbname":   os.getenv("POSTGRES_DB", "orchestrai"),
        "user":     os.getenv("POSTGRES_USER", "admin"),
        "password": os.getenv("POSTGRES_PASSWORD", "orchestrai_secret"),
    }

_DB_CONFIG = _get_db_config()

_MIN_CONN = 2
_MAX_CONN = 10


def _get_pool() -> ThreadedConnectionPool:
    global _pool
    if _pool is None or _pool.closed:
        logger.info("db.pool: initialising ThreadedConnectionPool (min=%d max=%d)", _MIN_CONN, _MAX_CONN)
        _pool = ThreadedConnectionPool(_MIN_CONN, _MAX_CONN, **_get_db_config())
    return _pool


def get_conn() -> psycopg2.extensions.connection:
    """Borrow a connection from the pool."""
    return _get_pool().getconn()


def put_conn(conn: psycopg2.extensions.connection, close: bool = False) -> None:
    """Return a connection to the pool. Pass close=True on unrecoverable errors."""
    try:
        _get_pool().putconn(conn, close=close)
    except Exception as exc:
        logger.warning("db.pool: putconn failed: %s", exc)


@contextmanager
def pool_context() -> Generator[psycopg2.extensions.connection, None, None]:
    """Context manager that always returns the connection to the pool."""
    conn = get_conn()
    try:
        yield conn
    except Exception:
        # Roll back any open transaction before returning conn to pool
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        put_conn(conn)


def close_pool() -> None:
    """Close all connections — call on application shutdown."""
    global _pool
    if _pool and not _pool.closed:
        _pool.closeall()
        _pool = None
        logger.info("db.pool: all connections closed")
