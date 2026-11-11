"""Business listings: admin review before they go public, and investments into approved listings.

Revision ID: 0007_listing_review
Revises: 0006_circle_votes
Create Date: 2026-11-11 15:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0007_listing_review'
down_revision: Union[str, None] = '0006_circle_votes'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Listings made before review existed wait for an admin like new ones
    op.add_column('company_listings', sa.Column('review_status', sa.String(length=10), nullable=False, server_default='pending'))
    op.add_column('company_listings', sa.Column('review_note', sa.String(length=300), nullable=True))
    op.add_column('company_listings', sa.Column('reviewed_by', sa.String(), nullable=True))
    op.add_column('company_listings', sa.Column('reviewed_at', sa.DateTime(), nullable=True))
    op.create_index('ix_company_listings_review_status', 'company_listings', ['review_status'])
    with op.batch_alter_table('company_listings') as batch:
        batch.create_foreign_key('fk_company_listings_reviewed_by', 'users', ['reviewed_by'], ['id'], ondelete='SET NULL')
    op.create_table('listing_investments',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('listing_id', sa.String(), nullable=False),
    sa.Column('user_id', sa.String(), nullable=False),
    sa.Column('amount', sa.DECIMAL(precision=18, scale=2), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['listing_id'], ['company_listings.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_listing_investments_listing_id', 'listing_investments', ['listing_id'])
    op.create_index('ix_listing_investments_user_id', 'listing_investments', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_listing_investments_user_id', table_name='listing_investments')
    op.drop_index('ix_listing_investments_listing_id', table_name='listing_investments')
    op.drop_table('listing_investments')
    with op.batch_alter_table('company_listings') as batch:
        batch.drop_constraint('fk_company_listings_reviewed_by', type_='foreignkey')
    op.drop_index('ix_company_listings_review_status', table_name='company_listings')
    for column in ('reviewed_at', 'reviewed_by', 'review_note', 'review_status'):
        op.drop_column('company_listings', column)
