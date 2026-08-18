"""add_interceptor_columns

Revision ID: 85f09d0fa4e8
Revises: 832c90552869
Create Date: 2026-06-14 11:19:27.720576

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '85f09d0fa4e8'
down_revision: Union[str, None] = '832c90552869'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Columns required by core/query_interceptor.py logging
    op.add_column('query_optimizations', sa.Column('context', sa.Text(), nullable=True))
    op.add_column('query_optimizations', sa.Column('execution_time_ms', sa.Integer(), nullable=True))
    op.add_column('query_optimizations', sa.Column('row_count', sa.Integer(), nullable=True))
    op.add_column('query_optimizations', sa.Column('error', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('query_optimizations', 'error')
    op.drop_column('query_optimizations', 'row_count')
    op.drop_column('query_optimizations', 'execution_time_ms')
    op.drop_column('query_optimizations', 'context')
