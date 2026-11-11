"""Lock password sign-in after repeated wrong passwords (app/services/login_throttle.py).

Revision ID: 0003_login_throttle
Revises: 0002_full_schema
Create Date: 2026-11-04 15:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0003_login_throttle'
down_revision: Union[str, None] = '0002_full_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('login_throttle',
    sa.Column('email_hash', sa.String(length=64), nullable=False),
    sa.Column('failures', sa.Integer(), nullable=False),
    sa.Column('first_failure_at', sa.DateTime(), nullable=False),
    sa.Column('locked_until', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('email_hash')
    )


def downgrade() -> None:
    op.drop_table('login_throttle')
