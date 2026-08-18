"""Add healing_outcomes table for learning agent outcome tracking.

Revision ID: 004_healing_outcomes
Revises: 0002
Create Date: 2025-01-01
"""
from alembic import op
import sqlalchemy as sa

revision = "004_healing_outcomes"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "healing_outcomes",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("incident_id", sa.String(100), nullable=False),
        sa.Column("pipeline_name", sa.String(200), nullable=False),
        sa.Column("anomaly_type", sa.String(100), nullable=False),
        sa.Column("healing_strategy", sa.String(200), nullable=False),
        sa.Column("fix_code_hash", sa.String(64), nullable=True),
        sa.Column("outcome", sa.String(20), nullable=False),  # 'approved','rejected','auto_healed'
        sa.Column("mttr_seconds", sa.Float(), nullable=True),  # time from detection to resolution
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("approved_by", sa.String(100), nullable=True),
        sa.Column("detection_at", sa.DateTime(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_healing_outcomes_incident ON healing_outcomes(incident_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_healing_outcomes_anomaly ON healing_outcomes(anomaly_type)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_healing_outcomes_created ON healing_outcomes(created_at)")

    # Add workspace_id to key tables for multi-tenancy
    for table in ["pipelines", "incidents"]:
        try:
            op.add_column(
                table,
                sa.Column("workspace_id", sa.String(50), nullable=True, server_default="default"),
            )
        except Exception:
            pass  # column may already exist


def downgrade() -> None:
    op.drop_table("healing_outcomes")
