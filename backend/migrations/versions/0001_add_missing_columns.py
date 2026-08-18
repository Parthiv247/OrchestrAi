"""Add all columns previously added via ALTER TABLE startup hacks.

Revision ID: 0001
Revises:
Create Date: 2026-06-14
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── dbt_runs ──────────────────────────────────────────────────────────────
    op.execute("ALTER TABLE dbt_runs ADD COLUMN IF NOT EXISTS run_output TEXT")

    # ── incidents ─────────────────────────────────────────────────────────────
    op.execute("ALTER TABLE incidents ADD COLUMN IF NOT EXISTS pipeline_name TEXT")
    op.execute("ALTER TABLE incidents ADD COLUMN IF NOT EXISTS anomaly_type TEXT")
    op.execute("ALTER TABLE incidents ADD COLUMN IF NOT EXISTS approval_status TEXT DEFAULT 'pending'")
    op.execute("ALTER TABLE incidents ADD COLUMN IF NOT EXISTS approval_token TEXT")
    op.execute("ALTER TABLE incidents ADD COLUMN IF NOT EXISTS confidence_score FLOAT")
    op.execute("ALTER TABLE incidents ADD COLUMN IF NOT EXISTS fix_code TEXT")
    op.execute("ALTER TABLE incidents ADD COLUMN IF NOT EXISTS fix_language TEXT")
    op.execute("ALTER TABLE incidents ADD COLUMN IF NOT EXISTS root_cause TEXT")
    op.execute("ALTER TABLE incidents ADD COLUMN IF NOT EXISTS root_cause_confidence FLOAT")
    op.execute("ALTER TABLE incidents ADD COLUMN IF NOT EXISTS sandbox_results JSONB")
    op.execute("ALTER TABLE incidents ADD COLUMN IF NOT EXISTS tests_passed INTEGER DEFAULT 0")
    op.execute("ALTER TABLE incidents ADD COLUMN IF NOT EXISTS tests_failed INTEGER DEFAULT 0")

    # ── query_optimizations ───────────────────────────────────────────────────
    op.execute("ALTER TABLE query_optimizations ADD COLUMN IF NOT EXISTS context TEXT DEFAULT 'manual'")


def downgrade() -> None:
    # Column drops are destructive — require explicit confirmation in prod
    pass
