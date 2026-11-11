"""Google sign-in from the phone apps: the hash of the app's one-time secret (app/api/v1/google_auth.py).

Revision ID: 0004_google_app_proof
Revises: 0003_login_throttle
Create Date: 2026-11-04 18:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0004_google_app_proof'
down_revision: Union[str, None] = '0003_login_throttle'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('oauth_states') as batch:
        batch.add_column(sa.Column('app_proof_hash', sa.String(length=64), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('oauth_states') as batch:
        batch.drop_column('app_proof_hash')
