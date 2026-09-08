"""Add ETL job queue and dead-letter queue tables used by pipelines.py ETL engine.

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-01

NOTE: ALTER TABLE statements are wrapped in DO $$ IF EXISTS blocks so this is
safe to run before SQLAlchemy create_all has created the base tables.
"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def _safe_alter(table: str, ddl: str) -> None:
    """Run DDL only if the table exists — safe on fresh databases."""
    op.execute(f"""
        DO $$ BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = '{table}'
            ) THEN
                {ddl};
            END IF;
        END $$;
    """)


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

    # ── Incidents — add missing columns ───────────────────────────────────────
    _safe_alter("incidents", "ALTER TABLE incidents ADD COLUMN IF NOT EXISTS approval_email TEXT")
    _safe_alter("incidents", "ALTER TABLE incidents ADD COLUMN IF NOT EXISTS lineage_graph JSONB")
    _safe_alter("incidents", "ALTER TABLE incidents ADD COLUMN IF NOT EXISTS anomaly_details JSONB")
    _safe_alter("incidents", "ALTER TABLE incidents ADD COLUMN IF NOT EXISTS resolved_at TIMESTAMP")
    _safe_alter("incidents", "ALTER TABLE incidents ADD COLUMN IF NOT EXISTS deployment_result JSONB")
    _safe_alter("incidents", "ALTER TABLE incidents ADD COLUMN IF NOT EXISTS run_id TEXT")

    # ── Pipelines — add schedule and ETL metadata columns ────────────────────
    _safe_alter("pipelines", "ALTER TABLE pipelines ADD COLUMN IF NOT EXISTS schedule TEXT DEFAULT 'manual'")
    _safe_alter("pipelines", "ALTER TABLE pipelines ADD COLUMN IF NOT EXISTS sync_mode TEXT DEFAULT 'full_refresh'")
    _safe_alter("pipelines", "ALTER TABLE pipelines ADD COLUMN IF NOT EXISTS cursor_field TEXT")
    _safe_alter("pipelines", "ALTER TABLE pipelines ADD COLUMN IF NOT EXISTS field_mappings JSONB")
    _safe_alter("pipelines", "ALTER TABLE pipelines ADD COLUMN IF NOT EXISTS source_table TEXT")
    _safe_alter("pipelines", "ALTER TABLE pipelines ADD COLUMN IF NOT EXISTS dest_table TEXT")
    _safe_alter("pipelines", "ALTER TABLE pipelines ADD COLUMN IF NOT EXISTS enabled BOOLEAN DEFAULT TRUE")

    # ── data_connections — add type discriminator ─────────────────────────────
    _safe_alter("data_connections", "ALTER TABLE data_connections ADD COLUMN IF NOT EXISTS db_type TEXT")
    _safe_alter("data_connections", "ALTER TABLE data_connections ADD COLUMN IF NOT EXISTS encrypted_config TEXT")

    # ── pipeline_runs — add row-level stats ───────────────────────────────────
    _safe_alter("pipeline_runs", "ALTER TABLE pipeline_runs ADD COLUMN IF NOT EXISTS records_ingested BIGINT DEFAULT 0")
    _safe_alter("pipeline_runs", "ALTER TABLE pipeline_runs ADD COLUMN IF NOT EXISTS records_loaded BIGINT DEFAULT 0")
    _safe_alter("pipeline_runs", "ALTER TABLE pipeline_runs ADD COLUMN IF NOT EXISTS records_failed BIGINT DEFAULT 0")
    _safe_alter("pipeline_runs", "ALTER TABLE pipeline_runs ADD COLUMN IF NOT EXISTS duration_seconds FLOAT")
    _safe_alter("pipeline_runs", "ALTER TABLE pipeline_runs ADD COLUMN IF NOT EXISTS error_message TEXT")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS etl_job_queue")
    op.execute("DROP TABLE IF EXISTS etl_dead_letter_queue")
