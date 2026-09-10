"""merge_branches

Revision ID: e7d95e9283d8
Revises: 85f09d0fa4e8, 004_healing_outcomes
Create Date: 2026-07-21 23:26:52.946712

"""
from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = 'e7d95e9283d8'
down_revision: str | None = ('85f09d0fa4e8', '004_healing_outcomes')
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
