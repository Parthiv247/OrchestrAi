"""Add all columns previously added via ALTER TABLE startup hacks.

Revision ID: 0001
Revises:
Create Date: 2026-06-14

NOTE: All statements are wrapped in existence checks so this migration is safe
to run on a fresh database (tables are created later by SQLAlchemy create_all).
"""
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def _safe_alter(table: str, ddl: str) -> None:
    """Run ALTER TABLE only if the table exists — safe on fresh databases."""
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
    # ── dbt_runs ──────────────────────────────────────────────────────────────
    _safe_alter("dbt_runs", "ALTER TABLE dbt_runs ADD COLUMN IF NOT EXISTS run_output TEXT")

    # ── incidents ─────────────────────────────────────────────────────────────
    _safe_alter("incidents", "ALTER TABLE incidents ADD COLUMN IF NOT EXISTS pipeline_name TEXT")
    _safe_alter("incidents", "ALTER TABLE incidents ADD COLUMN IF NOT EXISTS anomaly_type TEXT")
    _safe_alter("incidents", "ALTER TABLE incidents ADD COLUMN IF NOT EXISTS approval_status TEXT DEFAULT 'pending'")
    _safe_alter("incidents", "ALTER TABLE incidents ADD COLUMN IF NOT EXISTS approval_token TEXT")
    _safe_alter("incidents", "ALTER TABLE incidents ADD COLUMN IF NOT EXISTS confidence_score FLOAT")
    _safe_alter("incidents", "ALTER TABLE incidents ADD COLUMN IF NOT EXISTS fix_code TEXT")
    _safe_alter("incidents", "ALTER TABLE incidents ADD COLUMN IF NOT EXISTS fix_language TEXT")
    _safe_alter("incidents", "ALTER TABLE incidents ADD COLUMN IF NOT EXISTS root_cause TEXT")
    _safe_alter("incidents", "ALTER TABLE incidents ADD COLUMN IF NOT EXISTS root_cause_confidence FLOAT")
    _safe_alter("incidents", "ALTER TABLE incidents ADD COLUMN IF NOT EXISTS sandbox_results JSONB")
    _safe_alter("incidents", "ALTER TABLE incidents ADD COLUMN IF NOT EXISTS tests_passed INTEGER DEFAULT 0")
    _safe_alter("incidents", "ALTER TABLE incidents ADD COLUMN IF NOT EXISTS tests_failed INTEGER DEFAULT 0")

    # ── query_optimizations ───────────────────────────────────────────────────
    _safe_alter("query_optimizations", "ALTER TABLE query_optimizations ADD COLUMN IF NOT EXISTS context TEXT DEFAULT 'manual'")


def downgrade() -> None:
    # Column drops are destructive — require explicit confirmation in prod
    pass
