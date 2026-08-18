"""Add ETL job queue and dead-letter queue tables used by pipelines.py ETL engine.

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-01
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── ETL Job Queue ─────────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS etl_job_queue (
            id          TEXT PRIMARY KEY,
            pipeline_id TEXT NOT NULL,
            run_id      TEXT NOT NULL,
            status      TEXT DEFAULT 'queued',
            priority    INTEGER DEFAULT 5,
            payload     JSONB,
            created_at  TIMESTAMP DEFAULT NOW(),
            started_at  TIMESTAMP,
            completed_at TIMESTAMP,
            error       TEXT
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_etl_queue_status ON etl_job_queue(status)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_etl_queue_pipeline ON etl_job_queue(pipeline_id)")

    # ── ETL Dead-Letter Queue ─────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS etl_dead_letter_queue (
            id             TEXT PRIMARY KEY,
            pipeline_id    TEXT NOT NULL,
            run_id         TEXT NOT NULL,
            error          TEXT,
            payload        JSONB,
            retry_count    INTEGER DEFAULT 0,
            acknowledged   BOOLEAN DEFAULT FALSE,
            created_at     TIMESTAMP DEFAULT NOW(),
            acknowledged_at TIMESTAMP
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_dlq_acknowledged ON etl_dead_letter_queue(acknowledged)")

    # ── Incidents — add missing columns added via startup ALTER TABLE hacks ───
    op.execute("ALTER TABLE incidents ADD COLUMN IF NOT EXISTS approval_email TEXT")
    op.execute("ALTER TABLE incidents ADD COLUMN IF NOT EXISTS lineage_graph JSONB")
    op.execute("ALTER TABLE incidents ADD COLUMN IF NOT EXISTS anomaly_details JSONB")
    op.execute("ALTER TABLE incidents ADD COLUMN IF NOT EXISTS resolved_at TIMESTAMP")
    op.execute("ALTER TABLE incidents ADD COLUMN IF NOT EXISTS deployment_result JSONB")
    op.execute("ALTER TABLE incidents ADD COLUMN IF NOT EXISTS run_id TEXT")

    # ── Pipelines — add schedule and ETL metadata columns ────────────────────
    op.execute("ALTER TABLE pipelines ADD COLUMN IF NOT EXISTS schedule TEXT DEFAULT 'manual'")
    op.execute("ALTER TABLE pipelines ADD COLUMN IF NOT EXISTS sync_mode TEXT DEFAULT 'full_refresh'")
    op.execute("ALTER TABLE pipelines ADD COLUMN IF NOT EXISTS cursor_field TEXT")
    op.execute("ALTER TABLE pipelines ADD COLUMN IF NOT EXISTS field_mappings JSONB")
    op.execute("ALTER TABLE pipelines ADD COLUMN IF NOT EXISTS source_table TEXT")
    op.execute("ALTER TABLE pipelines ADD COLUMN IF NOT EXISTS dest_table TEXT")
    op.execute("ALTER TABLE pipelines ADD COLUMN IF NOT EXISTS enabled BOOLEAN DEFAULT TRUE")

    # ── data_connections — add type discriminator and Fernet-encrypted creds ─
    op.execute("ALTER TABLE data_connections ADD COLUMN IF NOT EXISTS db_type TEXT")
    op.execute("ALTER TABLE data_connections ADD COLUMN IF NOT EXISTS encrypted_config TEXT")

    # ── pipeline_runs — add row-level stats ───────────────────────────────────
    op.execute("ALTER TABLE pipeline_runs ADD COLUMN IF NOT EXISTS records_ingested BIGINT DEFAULT 0")
    op.execute("ALTER TABLE pipeline_runs ADD COLUMN IF NOT EXISTS records_loaded BIGINT DEFAULT 0")
    op.execute("ALTER TABLE pipeline_runs ADD COLUMN IF NOT EXISTS records_failed BIGINT DEFAULT 0")
    op.execute("ALTER TABLE pipeline_runs ADD COLUMN IF NOT EXISTS duration_seconds FLOAT")
    op.execute("ALTER TABLE pipeline_runs ADD COLUMN IF NOT EXISTS error_message TEXT")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS etl_job_queue")
    op.execute("DROP TABLE IF EXISTS etl_dead_letter_queue")
