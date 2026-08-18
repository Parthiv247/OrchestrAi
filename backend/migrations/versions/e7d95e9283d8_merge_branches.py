"""merge_branches

Revision ID: e7d95e9283d8
Revises: 85f09d0fa4e8, 004_healing_outcomes
Create Date: 2026-07-21 23:26:52.946712

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e7d95e9283d8'
down_revision: Union[str, None] = ('85f09d0fa4e8', '004_healing_outcomes')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
