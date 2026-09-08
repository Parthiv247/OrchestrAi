"""add_interceptor_columns

Revision ID: 85f09d0fa4e8
Revises: 832c90552869
Create Date: 2026-06-14 11:19:27.720576

NOTE: Wrapped in existence checks so safe to run before create_all.
"""
from typing import Sequence, Union
from alembic import op

revision: str = '85f09d0fa4e8'
down_revision: Union[str, None] = '832c90552869'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _safe_alter(table: str, ddl: str) -> None:
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
    # Columns required by core/query_interceptor.py logging
    _safe_alter("query_optimizations", "ALTER TABLE query_optimizations ADD COLUMN IF NOT EXISTS context TEXT")
    _safe_alter("query_optimizations", "ALTER TABLE query_optimizations ADD COLUMN IF NOT EXISTS execution_time_ms INTEGER")
    _safe_alter("query_optimizations", "ALTER TABLE query_optimizations ADD COLUMN IF NOT EXISTS row_count INTEGER")
    _safe_alter("query_optimizations", "ALTER TABLE query_optimizations ADD COLUMN IF NOT EXISTS error TEXT")


def downgrade() -> None:
    _safe_alter("query_optimizations", "ALTER TABLE query_optimizations DROP COLUMN IF EXISTS error")
    _safe_alter("query_optimizations", "ALTER TABLE query_optimizations DROP COLUMN IF EXISTS row_count")
    _safe_alter("query_optimizations", "ALTER TABLE query_optimizations DROP COLUMN IF EXISTS execution_time_ms")
    _safe_alter("query_optimizations", "ALTER TABLE query_optimizations DROP COLUMN IF EXISTS context")
