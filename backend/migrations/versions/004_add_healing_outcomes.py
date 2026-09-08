"""Add healing_outcomes table for learning agent outcome tracking.

Revision ID: 004_healing_outcomes
Revises: 0002
Create Date: 2025-01-01

NOTE: Uses raw SQL CREATE TABLE IF NOT EXISTS and DO $$ IF EXISTS for all
DDL so this is fully idempotent and safe on any database state.
"""
from alembic import op

revision = "004_healing_outcomes"
down_revision = "0002"
branch_labels = None
depends_on = None


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
    # Create healing_outcomes — idempotent
    op.execute("""
        CREATE TABLE IF NOT EXISTS healing_outcomes (
            id               SERIAL PRIMARY KEY,
            incident_id      VARCHAR(100) NOT NULL,
            pipeline_name    VARCHAR(200) NOT NULL,
            anomaly_type     VARCHAR(100) NOT NULL,
            healing_strategy VARCHAR(200) NOT NULL,
            fix_code_hash    VARCHAR(64),
            outcome          VARCHAR(20)  NOT NULL,
            mttr_seconds     FLOAT,
            confidence_score FLOAT,
            approved_by      VARCHAR(100),
            detection_at     TIMESTAMP,
            resolved_at      TIMESTAMP DEFAULT NOW(),
            created_at       TIMESTAMP DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_healing_outcomes_incident ON healing_outcomes(incident_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_healing_outcomes_anomaly  ON healing_outcomes(anomaly_type)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_healing_outcomes_created  ON healing_outcomes(created_at)")

    # Add workspace_id to key tables — safe even when tables don't exist yet
    _safe_alter("pipelines", "ALTER TABLE pipelines  ADD COLUMN IF NOT EXISTS workspace_id VARCHAR(50) DEFAULT 'default'")
    _safe_alter("incidents", "ALTER TABLE incidents  ADD COLUMN IF NOT EXISTS workspace_id VARCHAR(50) DEFAULT 'default'")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS healing_outcomes")
