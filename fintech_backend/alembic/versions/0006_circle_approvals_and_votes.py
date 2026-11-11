"""Circles: admin-approved joining, focus and size, and asset proposals paid by the people who vote yes.

Revision ID: 0006_circle_votes
Revises: 0005_apple_tickets
Create Date: 2026-11-11 12:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0006_circle_votes'
down_revision: Union[str, None] = '0005_apple_tickets'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('investment_circles', sa.Column('focus', sa.String(length=24), nullable=True))
    op.add_column('investment_circles', sa.Column('max_members', sa.Integer(), nullable=True))
    op.add_column('circle_members', sa.Column('status', sa.String(length=10), nullable=False, server_default='active'))
    op.add_column('circle_members', sa.Column('requested_note', sa.String(length=200), nullable=True))
    op.add_column('circle_proposals', sa.Column('kind', sa.String(length=8), nullable=False, server_default='fund'))
    op.add_column('circle_proposals', sa.Column('asset_type', sa.String(length=24), nullable=True))
    op.add_column('circle_proposals', sa.Column('title', sa.String(length=80), nullable=True))
    op.add_column('circle_proposals', sa.Column('amount_per_member', sa.DECIMAL(precision=18, scale=2), nullable=True))
    with op.batch_alter_table('circle_proposals') as batch:
        batch.alter_column('fund_id', existing_type=sa.String(), nullable=True)
        batch.alter_column('shares', existing_type=sa.Integer(), nullable=True)
    op.create_table('circle_investments',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('circle_id', sa.String(), nullable=False),
    sa.Column('proposal_id', sa.String(), nullable=False),
    sa.Column('user_id', sa.String(), nullable=False),
    sa.Column('amount', sa.DECIMAL(precision=18, scale=2), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['circle_id'], ['investment_circles.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['proposal_id'], ['circle_proposals.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('proposal_id', 'user_id', name='uq_circle_investment')
    )
    op.create_index('ix_circle_investments_circle_id', 'circle_investments', ['circle_id'])
    op.create_index('ix_circle_investments_proposal_id', 'circle_investments', ['proposal_id'])
    op.create_index('ix_circle_investments_user_id', 'circle_investments', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_circle_investments_user_id', table_name='circle_investments')
    op.drop_index('ix_circle_investments_proposal_id', table_name='circle_investments')
    op.drop_index('ix_circle_investments_circle_id', table_name='circle_investments')
    op.drop_table('circle_investments')
    op.execute("DELETE FROM circle_proposals WHERE kind = 'asset'")
    with op.batch_alter_table('circle_proposals') as batch:
        batch.alter_column('shares', existing_type=sa.Integer(), nullable=False)
        batch.alter_column('fund_id', existing_type=sa.String(), nullable=False)
    for column in ('amount_per_member', 'title', 'asset_type', 'kind'):
        op.drop_column('circle_proposals', column)
    op.execute("DELETE FROM circle_members WHERE status <> 'active'")
    op.drop_column('circle_members', 'requested_note')
    op.drop_column('circle_members', 'status')
    op.drop_column('investment_circles', 'max_members')
    op.drop_column('investment_circles', 'focus')
