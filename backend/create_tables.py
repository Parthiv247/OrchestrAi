"""
Standalone script: create all SQLAlchemy-defined tables using the sync
psycopg2 engine. Run BEFORE alembic so tables exist when migrations run.

Called from startup.sh:
    python3 /app/backend/create_tables.py
"""
import os
import sys
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("create_tables")

sys.path.insert(0, "/app")

from sqlalchemy import create_engine, text

# Build sync connection URL from env vars (parsed by startup.sh from DATABASE_URL)
_host = os.getenv("POSTGRES_HOST", "localhost")
_port = os.getenv("POSTGRES_PORT", "5432")
_db   = os.getenv("POSTGRES_DB", "orchestrai")
_user = os.getenv("POSTGRES_USER", "admin")
_pass = os.getenv("POSTGRES_PASSWORD", "orchestrai_secret")

_url = f"postgresql+psycopg2://{_user}:{_pass}@{_host}:{_port}/{_db}"

try:
    engine = create_engine(_url, echo=False, pool_pre_ping=True, connect_args={"connect_timeout": 10})

    # Import all models so Base.metadata knows about them
    from backend.db.models import Base  # noqa: F401

    with engine.begin() as conn:
        Base.metadata.create_all(conn)

        # Extra safety DDL that lives in main.py lifespan but needs to run early
        _safety_sql = [
            "ALTER TABLE incidents          ADD COLUMN IF NOT EXISTS approval_status TEXT DEFAULT 'pending'",
            "ALTER TABLE query_optimizations ADD COLUMN IF NOT EXISTS context TEXT DEFAULT 'manual'",
            """CREATE TABLE IF NOT EXISTS connector_configs (
                id TEXT PRIMARY KEY,
                connector_id TEXT NOT NULL,
                name TEXT NOT NULL,
                encrypted_creds TEXT NOT NULL,
                status TEXT DEFAULT 'untested',
                notes TEXT DEFAULT '',
                last_tested_at TIMESTAMP,
                test_message TEXT,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )""",
        ]
        for sql in _safety_sql:
            try:
                conn.execute(text(sql))
            except Exception as e:
                log.warning("Safety DDL skipped: %s", e)

    log.info("All tables created / verified OK")
    sys.exit(0)

except Exception as e:
    log.error("create_tables failed: %s", e)
    sys.exit(1)
