"""Every table the app uses.

Before this, only the core tables were migrated and the rest were made by create_all at startup.
Generated against PostgreSQL 16 from app/database/registry.py; a fresh database at head matches
the models exactly (checked by comparing the two).

Revision ID: 0002_full_schema
Revises: 58a6d0554597
Create Date: 2026-11-04 05:14:27.712395

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# Columns the app encrypts (app/database/encryption.py EncryptedString) are plain Text in the database.


# revision identifiers, used by Alembic.
revision: str = '0002_full_schema'
down_revision: Union[str, None] = '58a6d0554597'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('bank_transaction_metadata',
    sa.Column('transaction_id', sa.String(), nullable=False),
    sa.Column('data', sa.JSON(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('transaction_id')
    )
    op.create_table('oauth_states',
    sa.Column('state_hash', sa.String(length=64), nullable=False),
    sa.Column('verifier', sa.String(length=128), nullable=False),
    sa.Column('nonce', sa.String(length=64), nullable=False),
    sa.Column('mode', sa.String(length=10), nullable=False),
    sa.Column('next_path', sa.String(length=200), nullable=True),
    sa.Column('expires_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('state_hash')
    )
    op.create_table('plaid_event_cursor',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('last_event_id', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('auth_codes',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('user_id', sa.String(), nullable=False),
    sa.Column('purpose', sa.String(length=10), nullable=False),
    sa.Column('secret_hash', sa.String(length=64), nullable=False),
    sa.Column('attempts', sa.Integer(), nullable=False),
    sa.Column('expires_at', sa.DateTime(), nullable=False),
    sa.Column('used_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_auth_codes_secret_hash'), 'auth_codes', ['secret_hash'], unique=False)
    op.create_index(op.f('ix_auth_codes_user_id'), 'auth_codes', ['user_id'], unique=False)
    op.create_table('auto_save_plans',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('user_id', sa.String(), nullable=False),
    sa.Column('name', sa.String(length=80), nullable=False),
    sa.Column('amount', sa.DECIMAL(precision=18, scale=2), nullable=False),
    sa.Column('frequency', sa.String(length=8), nullable=False),
    sa.Column('next_run', sa.Date(), nullable=False),
    sa.Column('saved_total', sa.DECIMAL(precision=18, scale=2), nullable=False),
    sa.Column('runs', sa.Integer(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('last_status', sa.String(length=120), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_auto_save_plans_user_id'), 'auto_save_plans', ['user_id'], unique=False)
    op.create_table('bank_beneficiaries',
    sa.Column('beneficiary_id', sa.String(), nullable=False),
    sa.Column('user_id', sa.String(), nullable=False),
    sa.Column('beneficiary_type', sa.String(length=20), nullable=False),
    sa.Column('first_name', sa.String(length=50), nullable=False),
    sa.Column('last_name', sa.String(length=50), nullable=False),
    sa.Column('business_name', sa.String(length=100), nullable=True),
    sa.Column('email', sa.String(), nullable=True),
    sa.Column('phone_number', sa.String(), nullable=True),
    sa.Column('address_line1', sa.String(length=100), nullable=False),
    sa.Column('address_line2', sa.String(length=100), nullable=True),
    sa.Column('city', sa.String(length=50), nullable=False),
    sa.Column('state_province', sa.String(length=50), nullable=True),
    sa.Column('postal_code', sa.String(length=20), nullable=False),
    sa.Column('country', sa.String(length=2), nullable=False),
    sa.Column('bank_name', sa.String(length=100), nullable=False),
    sa.Column('bank_code', sa.String(length=20), nullable=True),
    sa.Column('swift_bic', sa.String(length=11), nullable=True),
    sa.Column('account_number', sa.Text(), nullable=False),
    sa.Column('iban', sa.Text(), nullable=True),
    sa.Column('mobile_money_provider', sa.String(), nullable=True),
    sa.Column('mobile_money_number', sa.Text(), nullable=True),
    sa.Column('status', sa.String(length=30), nullable=False),
    sa.Column('is_favorite', sa.Boolean(), nullable=False),
    sa.Column('verification_date', sa.DateTime(), nullable=True),
    sa.Column('nickname', sa.String(length=50), nullable=True),
    sa.Column('relationship', sa.String(length=50), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('beneficiary_id')
    )
    op.create_index(op.f('ix_bank_beneficiaries_user_id'), 'bank_beneficiaries', ['user_id'], unique=False)
    op.create_table('bank_links',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('user_id', sa.String(), nullable=False),
    sa.Column('item_id', sa.String(length=100), nullable=False),
    sa.Column('access_token', sa.Text(), nullable=False),
    sa.Column('institution_id', sa.String(length=40), nullable=True),
    sa.Column('institution_name', sa.String(length=120), nullable=True),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('error_code', sa.String(length=60), nullable=True),
    sa.Column('last_synced_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('item_id')
    )
    op.create_index(op.f('ix_bank_links_user_id'), 'bank_links', ['user_id'], unique=False)
    op.create_table('bank_transfer_quotes',
    sa.Column('quote_id', sa.String(), nullable=False),
    sa.Column('user_id', sa.String(), nullable=False),
    sa.Column('source_account_id', sa.String(), nullable=False),
    sa.Column('beneficiary_id', sa.String(), nullable=False),
    sa.Column('from_amount', sa.DECIMAL(precision=15, scale=2), nullable=False),
    sa.Column('from_currency', sa.String(length=3), nullable=False),
    sa.Column('to_amount', sa.DECIMAL(precision=15, scale=2), nullable=False),
    sa.Column('to_currency', sa.String(length=3), nullable=False),
    sa.Column('transfer_fee', sa.DECIMAL(precision=15, scale=2), nullable=False),
    sa.Column('exchange_fee', sa.DECIMAL(precision=15, scale=2), nullable=False),
    sa.Column('total_fees', sa.DECIMAL(precision=15, scale=2), nullable=False),
    sa.Column('total_cost', sa.DECIMAL(precision=15, scale=2), nullable=False),
    sa.Column('transfer_type', sa.String(length=30), nullable=False),
    sa.Column('expires_at', sa.DateTime(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('used_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('quote_id')
    )
    op.create_index(op.f('ix_bank_transfer_quotes_user_id'), 'bank_transfer_quotes', ['user_id'], unique=False)
    op.create_table('bank_transfers',
    sa.Column('transfer_id', sa.String(), nullable=False),
    sa.Column('user_id', sa.String(), nullable=False),
    sa.Column('source_account_id', sa.String(), nullable=False),
    sa.Column('beneficiary_id', sa.String(), nullable=False),
    sa.Column('transfer_type', sa.String(length=30), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('priority', sa.String(length=20), nullable=False),
    sa.Column('source_amount', sa.DECIMAL(precision=15, scale=2), nullable=False),
    sa.Column('source_currency', sa.String(length=3), nullable=False),
    sa.Column('destination_amount', sa.DECIMAL(precision=15, scale=2), nullable=False),
    sa.Column('destination_currency', sa.String(length=3), nullable=False),
    sa.Column('exchange_rate_used', sa.DECIMAL(precision=15, scale=6), nullable=True),
    sa.Column('transfer_fee', sa.DECIMAL(precision=15, scale=2), nullable=False),
    sa.Column('exchange_fee', sa.DECIMAL(precision=15, scale=2), nullable=False),
    sa.Column('total_fees', sa.DECIMAL(precision=15, scale=2), nullable=False),
    sa.Column('total_cost', sa.DECIMAL(precision=15, scale=2), nullable=False),
    sa.Column('purpose', sa.String(length=200), nullable=False),
    sa.Column('reference', sa.String(length=50), nullable=True),
    sa.Column('recipient_message', sa.String(length=200), nullable=True),
    sa.Column('quote_id', sa.String(), nullable=True),
    sa.Column('external_reference', sa.String(), nullable=True),
    sa.Column('failure_reason', sa.Text(), nullable=True),
    sa.Column('initiated_at', sa.DateTime(), nullable=False),
    sa.Column('processed_at', sa.DateTime(), nullable=True),
    sa.Column('completed_at', sa.DateTime(), nullable=True),
    sa.Column('estimated_arrival', sa.DateTime(), nullable=True),
    sa.Column('status_history', sa.JSON(), nullable=False),
    sa.Column('compliance_check_passed', sa.Boolean(), nullable=False),
    sa.Column('requires_documents', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('transfer_id'),
    sa.UniqueConstraint('quote_id', name='uq_bank_transfers_quote_id')
    )
    op.create_index(op.f('ix_bank_transfers_status'), 'bank_transfers', ['status'], unique=False)
    op.create_index(op.f('ix_bank_transfers_user_id'), 'bank_transfers', ['user_id'], unique=False)
    op.create_table('broker_orders',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('user_id', sa.String(), nullable=False),
    sa.Column('alpaca_order_id', sa.String(length=60), nullable=True),
    sa.Column('asset_type', sa.String(length=8), nullable=False),
    sa.Column('symbol', sa.String(length=12), nullable=False),
    sa.Column('side', sa.String(length=4), nullable=False),
    sa.Column('notional', sa.DECIMAL(precision=18, scale=2), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('filled_qty', sa.DECIMAL(precision=28, scale=10), nullable=True),
    sa.Column('filled_avg_price', sa.DECIMAL(precision=18, scale=8), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('alpaca_order_id')
    )
    op.create_index(op.f('ix_broker_orders_user_id'), 'broker_orders', ['user_id'], unique=False)
    op.create_table('brokerage_accounts',
    sa.Column('user_id', sa.String(), nullable=False),
    sa.Column('alpaca_account_id', sa.String(length=60), nullable=False),
    sa.Column('status', sa.String(length=30), nullable=False),
    sa.Column('uninvested_cash', sa.DECIMAL(precision=18, scale=2), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id'),
    sa.UniqueConstraint('alpaca_account_id')
    )
    op.create_table('budgets_store',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('user_id', sa.String(), nullable=False),
    sa.Column('name', sa.String(length=60), nullable=False),
    sa.Column('category', sa.String(length=20), nullable=False),
    sa.Column('monthly_limit', sa.DECIMAL(precision=18, scale=2), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'category', name='uq_budget_category')
    )
    op.create_index(op.f('ix_budgets_store_user_id'), 'budgets_store', ['user_id'], unique=False)
    op.create_table('cash_transfers',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('sender_user_id', sa.String(), nullable=False),
    sa.Column('recipient_user_id', sa.String(), nullable=False),
    sa.Column('amount', sa.DECIMAL(precision=18, scale=2), nullable=False),
    sa.Column('note', sa.String(length=140), nullable=True),
    sa.Column('reference', sa.String(length=20), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['recipient_user_id'], ['users.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['sender_user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('reference')
    )
    op.create_index(op.f('ix_cash_transfers_recipient_user_id'), 'cash_transfers', ['recipient_user_id'], unique=False)
    op.create_index(op.f('ix_cash_transfers_sender_user_id'), 'cash_transfers', ['sender_user_id'], unique=False)
    op.create_table('company_listings',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('owner_user_id', sa.String(), nullable=False),
    sa.Column('name', sa.String(length=80), nullable=False),
    sa.Column('category', sa.String(length=20), nullable=False),
    sa.Column('sector', sa.String(length=60), nullable=False),
    sa.Column('tagline', sa.String(length=160), nullable=False),
    sa.Column('about', sa.Text(), nullable=True),
    sa.Column('location', sa.String(length=80), nullable=True),
    sa.Column('website', sa.String(length=200), nullable=True),
    sa.Column('founded_year', sa.Integer(), nullable=True),
    sa.Column('funding_goal', sa.DECIMAL(precision=18, scale=2), nullable=False),
    sa.Column('min_investment', sa.DECIMAL(precision=18, scale=2), nullable=False),
    sa.Column('amount_raised', sa.DECIMAL(precision=18, scale=2), nullable=False),
    sa.Column('target_return', sa.String(length=40), nullable=True),
    sa.Column('term', sa.String(length=40), nullable=True),
    sa.Column('risk_level', sa.String(length=12), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['owner_user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_company_listings_category'), 'company_listings', ['category'], unique=False)
    op.create_index(op.f('ix_company_listings_owner_user_id'), 'company_listings', ['owner_user_id'], unique=False)
    op.create_table('fixed_deposits',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('user_id', sa.String(), nullable=False),
    sa.Column('principal', sa.DECIMAL(precision=18, scale=2), nullable=False),
    sa.Column('rate', sa.DECIMAL(precision=5, scale=2), nullable=False),
    sa.Column('term_months', sa.Integer(), nullable=False),
    sa.Column('start_date', sa.Date(), nullable=False),
    sa.Column('maturity_date', sa.Date(), nullable=False),
    sa.Column('auto_renew', sa.Boolean(), nullable=False),
    sa.Column('roundup_enabled', sa.Boolean(), nullable=False),
    sa.Column('status', sa.String(length=10), nullable=False),
    sa.Column('closed_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_fixed_deposits_user_id'), 'fixed_deposits', ['user_id'], unique=False)
    op.create_table('identity_checks',
    sa.Column('user_id', sa.String(), nullable=False),
    sa.Column('inquiry_id', sa.String(length=60), nullable=False),
    sa.Column('persona_status', sa.String(length=20), nullable=False),
    sa.Column('state', sa.String(length=20), nullable=False),
    sa.Column('verified_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id'),
    sa.UniqueConstraint('inquiry_id')
    )
    op.create_table('investment_circles',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('creator_user_id', sa.String(), nullable=False),
    sa.Column('name', sa.String(length=60), nullable=False),
    sa.Column('purpose', sa.String(length=160), nullable=False),
    sa.Column('min_contribution', sa.DECIMAL(precision=18, scale=2), nullable=False),
    sa.Column('pool_balance', sa.DECIMAL(precision=18, scale=2), nullable=False),
    sa.Column('total_contributed', sa.DECIMAL(precision=18, scale=2), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['creator_user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_investment_circles_creator_user_id'), 'investment_circles', ['creator_user_id'], unique=False)
    op.create_table('issued_cards',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('user_id', sa.String(), nullable=False),
    sa.Column('stripe_card_id', sa.String(length=60), nullable=False),
    sa.Column('last4', sa.String(length=4), nullable=False),
    sa.Column('brand', sa.String(length=20), nullable=False),
    sa.Column('exp_month', sa.Integer(), nullable=True),
    sa.Column('exp_year', sa.Integer(), nullable=True),
    sa.Column('status', sa.String(length=10), nullable=False),
    sa.Column('monthly_limit', sa.DECIMAL(precision=18, scale=2), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('stripe_card_id')
    )
    op.create_index(op.f('ix_issued_cards_user_id'), 'issued_cards', ['user_id'], unique=False)
    op.create_table('issuing_cardholders',
    sa.Column('user_id', sa.String(), nullable=False),
    sa.Column('stripe_cardholder_id', sa.String(length=60), nullable=False),
    sa.Column('line1', sa.String(length=120), nullable=False),
    sa.Column('line2', sa.String(length=120), nullable=True),
    sa.Column('city', sa.String(length=80), nullable=False),
    sa.Column('state', sa.String(length=2), nullable=False),
    sa.Column('postal_code', sa.String(length=10), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id'),
    sa.UniqueConstraint('stripe_cardholder_id')
    )
    op.create_table('market_positions',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('user_id', sa.String(), nullable=False),
    sa.Column('asset_type', sa.String(length=8), nullable=False),
    sa.Column('symbol', sa.String(length=12), nullable=False),
    sa.Column('quantity', sa.DECIMAL(precision=28, scale=10), nullable=False),
    sa.Column('cost_basis', sa.DECIMAL(precision=18, scale=2), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'asset_type', 'symbol', name='uq_market_position')
    )
    op.create_index(op.f('ix_market_positions_user_id'), 'market_positions', ['user_id'], unique=False)
    op.create_table('notification_prefs',
    sa.Column('user_id', sa.String(), nullable=False),
    sa.Column('email', sa.Boolean(), nullable=False),
    sa.Column('marketing', sa.Boolean(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id')
    )
    op.create_table('plaid_connections',
    sa.Column('connection_id', sa.String(), nullable=False),
    sa.Column('user_id', sa.String(), nullable=False),
    sa.Column('item_id', sa.String(), nullable=False),
    sa.Column('access_token', sa.Text(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('institution_id', sa.String(), nullable=True),
    sa.Column('institution_name', sa.String(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('last_synced_at', sa.DateTime(), nullable=True),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('connection_id'),
    sa.UniqueConstraint('item_id')
    )
    op.create_index(op.f('ix_plaid_connections_user_id'), 'plaid_connections', ['user_id'], unique=False)
    op.create_table('plaid_link_tokens',
    sa.Column('link_token_id', sa.String(), nullable=False),
    sa.Column('user_id', sa.String(), nullable=False),
    sa.Column('link_token', sa.Text(), nullable=False),
    sa.Column('expiration', sa.String(), nullable=True),
    sa.Column('request_id', sa.String(), nullable=True),
    sa.Column('used', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('link_token_id')
    )
    op.create_index(op.f('ix_plaid_link_tokens_user_id'), 'plaid_link_tokens', ['user_id'], unique=False)
    op.create_table('saved_cards',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('user_id', sa.String(), nullable=False),
    sa.Column('kind', sa.String(length=12), nullable=False),
    sa.Column('holder_name', sa.String(length=80), nullable=False),
    sa.Column('last4', sa.String(length=4), nullable=False),
    sa.Column('brand', sa.String(length=20), nullable=False),
    sa.Column('exp_month', sa.Integer(), nullable=True),
    sa.Column('exp_year', sa.Integer(), nullable=True),
    sa.Column('bank', sa.String(length=80), nullable=True),
    sa.Column('source', sa.String(length=10), nullable=False),
    sa.Column('signature', sa.String(length=64), nullable=True),
    sa.Column('status', sa.String(length=10), nullable=False),
    sa.Column('is_default', sa.Boolean(), nullable=False),
    sa.Column('contactless', sa.Boolean(), nullable=False),
    sa.Column('online_payments', sa.Boolean(), nullable=False),
    sa.Column('per_transaction_limit', sa.DECIMAL(precision=18, scale=2), nullable=True),
    sa.Column('monthly_limit', sa.DECIMAL(precision=18, scale=2), nullable=True),
    sa.Column('last_used_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'signature', name='uq_saved_card_signature')
    )
    op.create_index(op.f('ix_saved_cards_user_id'), 'saved_cards', ['user_id'], unique=False)
    op.create_table('savings_goals_store',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('user_id', sa.String(), nullable=False),
    sa.Column('name', sa.String(length=80), nullable=False),
    sa.Column('category', sa.String(length=40), nullable=False),
    sa.Column('target_amount', sa.DECIMAL(precision=18, scale=2), nullable=False),
    sa.Column('current_amount', sa.DECIMAL(precision=18, scale=2), nullable=False),
    sa.Column('monthly_contribution', sa.DECIMAL(precision=18, scale=2), nullable=False),
    sa.Column('deadline', sa.Date(), nullable=False),
    sa.Column('is_auto_save', sa.Boolean(), nullable=False),
    sa.Column('completed_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_savings_goals_store_user_id'), 'savings_goals_store', ['user_id'], unique=False)
    op.create_table('user_identities',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('user_id', sa.String(), nullable=False),
    sa.Column('provider', sa.String(length=20), nullable=False),
    sa.Column('subject', sa.String(length=255), nullable=False),
    sa.Column('email', sa.String(length=320), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('provider', 'subject', name='uq_identity_subject')
    )
    op.create_index(op.f('ix_user_identities_user_id'), 'user_identities', ['user_id'], unique=False)
    op.create_table('user_notifications',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('user_id', sa.String(), nullable=False),
    sa.Column('kind', sa.String(length=12), nullable=False),
    sa.Column('title', sa.String(length=120), nullable=False),
    sa.Column('message', sa.String(length=400), nullable=False),
    sa.Column('link', sa.String(length=120), nullable=True),
    sa.Column('dedupe_key', sa.String(length=120), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('read_at', sa.DateTime(), nullable=True),
    sa.Column('seen_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'dedupe_key', name='uq_notification_key')
    )
    op.create_index(op.f('ix_user_notifications_created_at'), 'user_notifications', ['created_at'], unique=False)
    op.create_index(op.f('ix_user_notifications_user_id'), 'user_notifications', ['user_id'], unique=False)
    op.create_table('venture_funds',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('manager_user_id', sa.String(), nullable=False),
    sa.Column('firm_name', sa.String(length=80), nullable=False),
    sa.Column('fund_name', sa.String(length=80), nullable=False),
    sa.Column('thesis', sa.String(length=160), nullable=False),
    sa.Column('about', sa.Text(), nullable=True),
    sa.Column('sectors', sa.JSON(), nullable=False),
    sa.Column('stage', sa.String(length=20), nullable=False),
    sa.Column('location', sa.String(length=80), nullable=True),
    sa.Column('website', sa.String(length=200), nullable=True),
    sa.Column('share_price', sa.DECIMAL(precision=18, scale=2), nullable=False),
    sa.Column('total_shares', sa.Integer(), nullable=False),
    sa.Column('min_shares', sa.Integer(), nullable=False),
    sa.Column('shares_sold', sa.Integer(), nullable=False),
    sa.Column('term_years', sa.Integer(), nullable=False),
    sa.Column('management_fee', sa.DECIMAL(precision=5, scale=2), nullable=False),
    sa.Column('carry', sa.DECIMAL(precision=5, scale=2), nullable=False),
    sa.Column('closes_on', sa.Date(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['manager_user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_venture_funds_manager_user_id'), 'venture_funds', ['manager_user_id'], unique=False)
    op.create_table('bank_ach_transfers',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('user_id', sa.String(), nullable=False),
    sa.Column('link_id', sa.String(), nullable=True),
    sa.Column('account_id', sa.String(length=100), nullable=False),
    sa.Column('account_label', sa.String(length=160), nullable=True),
    sa.Column('direction', sa.String(length=10), nullable=False),
    sa.Column('amount', sa.DECIMAL(precision=18, scale=2), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('plaid_transfer_id', sa.String(length=100), nullable=True),
    sa.Column('reference', sa.String(length=40), nullable=False),
    sa.Column('failure_reason', sa.String(length=300), nullable=True),
    sa.Column('money_moved', sa.Boolean(), nullable=False),
    sa.Column('undone', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['link_id'], ['bank_links.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('plaid_transfer_id'),
    sa.UniqueConstraint('reference')
    )
    op.create_index(op.f('ix_bank_ach_transfers_user_id'), 'bank_ach_transfers', ['user_id'], unique=False)
    op.create_table('bank_link_accounts',
    sa.Column('id', sa.String(length=100), nullable=False),
    sa.Column('link_id', sa.String(), nullable=False),
    sa.Column('user_id', sa.String(), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=True),
    sa.Column('official_name', sa.String(length=200), nullable=True),
    sa.Column('mask', sa.String(length=8), nullable=True),
    sa.Column('kind', sa.String(length=20), nullable=True),
    sa.Column('subtype', sa.String(length=30), nullable=True),
    sa.Column('available', sa.DECIMAL(precision=18, scale=2), nullable=True),
    sa.Column('current', sa.DECIMAL(precision=18, scale=2), nullable=True),
    sa.Column('credit_limit', sa.DECIMAL(precision=18, scale=2), nullable=True),
    sa.Column('currency', sa.String(length=3), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['link_id'], ['bank_links.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_bank_link_accounts_link_id'), 'bank_link_accounts', ['link_id'], unique=False)
    op.create_index(op.f('ix_bank_link_accounts_user_id'), 'bank_link_accounts', ['user_id'], unique=False)
    op.create_table('circle_members',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('circle_id', sa.String(), nullable=False),
    sa.Column('user_id', sa.String(), nullable=False),
    sa.Column('contributed', sa.DECIMAL(precision=18, scale=2), nullable=False),
    sa.Column('joined_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['circle_id'], ['investment_circles.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('circle_id', 'user_id', name='uq_circle_member')
    )
    op.create_index(op.f('ix_circle_members_circle_id'), 'circle_members', ['circle_id'], unique=False)
    op.create_index(op.f('ix_circle_members_user_id'), 'circle_members', ['user_id'], unique=False)
    op.create_table('circle_proposals',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('circle_id', sa.String(), nullable=False),
    sa.Column('proposer_user_id', sa.String(), nullable=False),
    sa.Column('fund_id', sa.String(), nullable=False),
    sa.Column('shares', sa.Integer(), nullable=False),
    sa.Column('amount', sa.DECIMAL(precision=18, scale=2), nullable=False),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('status', sa.String(length=12), nullable=False),
    sa.Column('outcome', sa.String(length=200), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('decided_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['circle_id'], ['investment_circles.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['fund_id'], ['venture_funds.id'], ),
    sa.ForeignKeyConstraint(['proposer_user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_circle_proposals_circle_id'), 'circle_proposals', ['circle_id'], unique=False)
    op.create_table('issuing_holds',
    sa.Column('authorization_id', sa.String(length=60), nullable=False),
    sa.Column('user_id', sa.String(), nullable=False),
    sa.Column('account_id', sa.String(), nullable=False),
    sa.Column('card_id', sa.String(), nullable=False),
    sa.Column('held', sa.DECIMAL(precision=18, scale=2), nullable=False),
    sa.Column('merchant', sa.String(length=120), nullable=True),
    sa.Column('category', sa.String(length=30), nullable=True),
    sa.Column('open', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['account_id'], ['accounts.id'], ),
    sa.ForeignKeyConstraint(['card_id'], ['issued_cards.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('authorization_id')
    )
    op.create_index(op.f('ix_issuing_holds_user_id'), 'issuing_holds', ['user_id'], unique=False)
    op.create_table('plaid_accounts',
    sa.Column('account_id', sa.String(), nullable=False),
    sa.Column('connection_id', sa.String(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('official_name', sa.String(), nullable=True),
    sa.Column('type', sa.String(), nullable=True),
    sa.Column('subtype', sa.String(), nullable=True),
    sa.Column('mask', sa.String(), nullable=True),
    sa.Column('balances', sa.JSON(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['connection_id'], ['plaid_connections.connection_id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('account_id')
    )
    op.create_index(op.f('ix_plaid_accounts_connection_id'), 'plaid_accounts', ['connection_id'], unique=False)
    op.create_table('plaid_transactions',
    sa.Column('transaction_id', sa.String(), nullable=False),
    sa.Column('account_id', sa.String(), nullable=False),
    sa.Column('connection_id', sa.String(), nullable=False),
    sa.Column('amount', sa.DECIMAL(precision=15, scale=2), nullable=False),
    sa.Column('iso_currency_code', sa.String(length=3), nullable=True),
    sa.Column('unofficial_currency_code', sa.String(), nullable=True),
    sa.Column('date', sa.String(length=10), nullable=False),
    sa.Column('authorized_date', sa.String(length=10), nullable=True),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('merchant_name', sa.String(), nullable=True),
    sa.Column('payment_channel', sa.String(), nullable=True),
    sa.Column('pending', sa.Boolean(), nullable=False),
    sa.Column('pending_transaction_id', sa.String(), nullable=True),
    sa.Column('account_owner', sa.String(), nullable=True),
    sa.Column('transaction_type', sa.String(), nullable=True),
    sa.Column('transaction_code', sa.String(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['connection_id'], ['plaid_connections.connection_id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('transaction_id')
    )
    op.create_index(op.f('ix_plaid_transactions_account_id'), 'plaid_transactions', ['account_id'], unique=False)
    op.create_index('ix_plaid_transactions_connection_date', 'plaid_transactions', ['connection_id', 'date'], unique=False)
    op.create_table('circle_holdings',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('circle_id', sa.String(), nullable=False),
    sa.Column('fund_id', sa.String(), nullable=False),
    sa.Column('proposal_id', sa.String(), nullable=False),
    sa.Column('shares', sa.Integer(), nullable=False),
    sa.Column('amount', sa.DECIMAL(precision=18, scale=2), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['circle_id'], ['investment_circles.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['fund_id'], ['venture_funds.id'], ),
    sa.ForeignKeyConstraint(['proposal_id'], ['circle_proposals.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_circle_holdings_circle_id'), 'circle_holdings', ['circle_id'], unique=False)
    op.create_table('circle_votes',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('proposal_id', sa.String(), nullable=False),
    sa.Column('user_id', sa.String(), nullable=False),
    sa.Column('choice', sa.String(length=3), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['proposal_id'], ['circle_proposals.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('proposal_id', 'user_id', name='uq_circle_vote')
    )
    op.create_index(op.f('ix_circle_votes_proposal_id'), 'circle_votes', ['proposal_id'], unique=False)
    op.create_table('fund_share_orders',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('fund_id', sa.String(), nullable=False),
    sa.Column('user_id', sa.String(), nullable=False),
    sa.Column('account_id', sa.String(), nullable=False),
    sa.Column('transaction_id', sa.String(), nullable=False),
    sa.Column('shares', sa.Integer(), nullable=False),
    sa.Column('share_price', sa.DECIMAL(precision=18, scale=2), nullable=False),
    sa.Column('amount', sa.DECIMAL(precision=18, scale=2), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['account_id'], ['accounts.id'], ),
    sa.ForeignKeyConstraint(['fund_id'], ['venture_funds.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['transaction_id'], ['transactions.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_fund_share_orders_fund_id'), 'fund_share_orders', ['fund_id'], unique=False)
    op.create_index(op.f('ix_fund_share_orders_user_id'), 'fund_share_orders', ['user_id'], unique=False)
    op.create_table('market_orders',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('user_id', sa.String(), nullable=False),
    sa.Column('asset_type', sa.String(length=8), nullable=False),
    sa.Column('symbol', sa.String(length=12), nullable=False),
    sa.Column('side', sa.String(length=4), nullable=False),
    sa.Column('quantity', sa.DECIMAL(precision=28, scale=10), nullable=False),
    sa.Column('price', sa.DECIMAL(precision=18, scale=8), nullable=False),
    sa.Column('amount', sa.DECIMAL(precision=18, scale=2), nullable=False),
    sa.Column('transaction_id', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['transaction_id'], ['transactions.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_market_orders_user_id'), 'market_orders', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_market_orders_user_id'), table_name='market_orders')
    op.drop_table('market_orders')
    op.drop_index(op.f('ix_fund_share_orders_user_id'), table_name='fund_share_orders')
    op.drop_index(op.f('ix_fund_share_orders_fund_id'), table_name='fund_share_orders')
    op.drop_table('fund_share_orders')
    op.drop_index(op.f('ix_circle_votes_proposal_id'), table_name='circle_votes')
    op.drop_table('circle_votes')
    op.drop_index(op.f('ix_circle_holdings_circle_id'), table_name='circle_holdings')
    op.drop_table('circle_holdings')
    op.drop_index('ix_plaid_transactions_connection_date', table_name='plaid_transactions')
    op.drop_index(op.f('ix_plaid_transactions_account_id'), table_name='plaid_transactions')
    op.drop_table('plaid_transactions')
    op.drop_index(op.f('ix_plaid_accounts_connection_id'), table_name='plaid_accounts')
    op.drop_table('plaid_accounts')
    op.drop_index(op.f('ix_issuing_holds_user_id'), table_name='issuing_holds')
    op.drop_table('issuing_holds')
    op.drop_index(op.f('ix_circle_proposals_circle_id'), table_name='circle_proposals')
    op.drop_table('circle_proposals')
    op.drop_index(op.f('ix_circle_members_user_id'), table_name='circle_members')
    op.drop_index(op.f('ix_circle_members_circle_id'), table_name='circle_members')
    op.drop_table('circle_members')
    op.drop_index(op.f('ix_bank_link_accounts_user_id'), table_name='bank_link_accounts')
    op.drop_index(op.f('ix_bank_link_accounts_link_id'), table_name='bank_link_accounts')
    op.drop_table('bank_link_accounts')
    op.drop_index(op.f('ix_bank_ach_transfers_user_id'), table_name='bank_ach_transfers')
    op.drop_table('bank_ach_transfers')
    op.drop_index(op.f('ix_venture_funds_manager_user_id'), table_name='venture_funds')
    op.drop_table('venture_funds')
    op.drop_index(op.f('ix_user_notifications_user_id'), table_name='user_notifications')
    op.drop_index(op.f('ix_user_notifications_created_at'), table_name='user_notifications')
    op.drop_table('user_notifications')
    op.drop_index(op.f('ix_user_identities_user_id'), table_name='user_identities')
    op.drop_table('user_identities')
    op.drop_index(op.f('ix_savings_goals_store_user_id'), table_name='savings_goals_store')
    op.drop_table('savings_goals_store')
    op.drop_index(op.f('ix_saved_cards_user_id'), table_name='saved_cards')
    op.drop_table('saved_cards')
    op.drop_index(op.f('ix_plaid_link_tokens_user_id'), table_name='plaid_link_tokens')
    op.drop_table('plaid_link_tokens')
    op.drop_index(op.f('ix_plaid_connections_user_id'), table_name='plaid_connections')
    op.drop_table('plaid_connections')
    op.drop_table('notification_prefs')
    op.drop_index(op.f('ix_market_positions_user_id'), table_name='market_positions')
    op.drop_table('market_positions')
    op.drop_table('issuing_cardholders')
    op.drop_index(op.f('ix_issued_cards_user_id'), table_name='issued_cards')
    op.drop_table('issued_cards')
    op.drop_index(op.f('ix_investment_circles_creator_user_id'), table_name='investment_circles')
    op.drop_table('investment_circles')
    op.drop_table('identity_checks')
    op.drop_index(op.f('ix_fixed_deposits_user_id'), table_name='fixed_deposits')
    op.drop_table('fixed_deposits')
    op.drop_index(op.f('ix_company_listings_owner_user_id'), table_name='company_listings')
    op.drop_index(op.f('ix_company_listings_category'), table_name='company_listings')
    op.drop_table('company_listings')
    op.drop_index(op.f('ix_cash_transfers_sender_user_id'), table_name='cash_transfers')
    op.drop_index(op.f('ix_cash_transfers_recipient_user_id'), table_name='cash_transfers')
    op.drop_table('cash_transfers')
    op.drop_index(op.f('ix_budgets_store_user_id'), table_name='budgets_store')
    op.drop_table('budgets_store')
    op.drop_table('brokerage_accounts')
    op.drop_index(op.f('ix_broker_orders_user_id'), table_name='broker_orders')
    op.drop_table('broker_orders')
    op.drop_index(op.f('ix_bank_transfers_user_id'), table_name='bank_transfers')
    op.drop_index(op.f('ix_bank_transfers_status'), table_name='bank_transfers')
    op.drop_table('bank_transfers')
    op.drop_index(op.f('ix_bank_transfer_quotes_user_id'), table_name='bank_transfer_quotes')
    op.drop_table('bank_transfer_quotes')
    op.drop_index(op.f('ix_bank_links_user_id'), table_name='bank_links')
    op.drop_table('bank_links')
    op.drop_index(op.f('ix_bank_beneficiaries_user_id'), table_name='bank_beneficiaries')
    op.drop_table('bank_beneficiaries')
    op.drop_index(op.f('ix_auto_save_plans_user_id'), table_name='auto_save_plans')
    op.drop_table('auto_save_plans')
    op.drop_index(op.f('ix_auth_codes_user_id'), table_name='auth_codes')
    op.drop_index(op.f('ix_auth_codes_secret_hash'), table_name='auth_codes')
    op.drop_table('auth_codes')
    op.drop_table('plaid_event_cursor')
    op.drop_table('oauth_states')
    op.drop_table('bank_transaction_metadata')
