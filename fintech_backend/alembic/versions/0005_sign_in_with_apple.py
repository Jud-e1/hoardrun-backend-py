"""Sign in with Apple: one-time tickets between Apple's callback and the web page (app/api/v1/apple_auth.py).

Revision ID: 0005_apple_tickets
Revises: 0004_google_app_proof
Create Date: 2026-11-04 21:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0005_apple_tickets'
down_revision: Union[str, None] = '0004_google_app_proof'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('auth_tickets',
    sa.Column('ticket_hash', sa.String(length=64), nullable=False),
    sa.Column('user_id', sa.String(), nullable=False),
    sa.Column('new_user', sa.Boolean(), nullable=False),
    sa.Column('next_path', sa.String(length=200), nullable=True),
    sa.Column('app_proof_hash', sa.String(length=64), nullable=True),
    sa.Column('expires_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('ticket_hash')
    )


def downgrade() -> None:
    op.drop_table('auth_tickets')
