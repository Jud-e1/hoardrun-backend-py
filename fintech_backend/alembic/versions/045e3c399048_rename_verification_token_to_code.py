"""rename_verification_token_to_code

Revision ID: 045e3c399048
Revises: 43e5494d96e6
Create Date: 2025-11-15 (auto-generated)

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

# revision identifiers, used by Alembic.
revision: str = '045e3c399048'
down_revision: Union[str, None] = '43e5494d96e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def column_exists(table_name, column_name):
    """Check if a column exists in a table"""
    bind = op.get_bind()
    inspector = Inspector.from_engine(bind)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    """Rename email_verification_token to email_verification_code"""
    
    # Check if we need to rename
    if column_exists('users', 'email_verification_token'):
        if not column_exists('users', 'email_verification_code'):
            # Rename the column
            op.alter_column('users', 'email_verification_token',
                          new_column_name='email_verification_code',
                          existing_type=sa.String(length=6),
                          existing_nullable=True)
            print("✓ Renamed email_verification_token to email_verification_code")
        else:
            # Both exist, drop the old one
            op.drop_column('users', 'email_verification_token')
            print("✓ Dropped email_verification_token (email_verification_code already exists)")
    elif not column_exists('users', 'email_verification_code'):
        # Neither exists, create the new one
        op.add_column('users', sa.Column('email_verification_code', 
                                        sa.String(length=6), 
                                        nullable=True))
        print("✓ Added email_verification_code column")
    else:
        print("✓ email_verification_code already exists")
    
    # Ensure all other required columns exist
    columns_to_add = {
        'email_verified': sa.Column('email_verified', sa.Boolean(), nullable=True, server_default='false'),
        'password_reset_token': sa.Column('password_reset_token', sa.String(length=255), nullable=True),
        'password_reset_expires': sa.Column('password_reset_expires', sa.DateTime(timezone=True), nullable=True),
        'last_login_at': sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
        'date_of_birth': sa.Column('date_of_birth', sa.Date(), nullable=True),
        'country': sa.Column('country', sa.String(length=3), nullable=True),
        'id_number': sa.Column('id_number', sa.String(length=50), nullable=True),
        'bio': sa.Column('bio', sa.Text(), nullable=True),
        'profile_picture_url': sa.Column('profile_picture_url', sa.String(length=500), nullable=True),
        'status': sa.Column('status', sa.String(length=20), nullable=True, server_default='ACTIVE'),
        'role': sa.Column('role', sa.String(length=20), nullable=True, server_default='USER'),
    }
    
    for column_name, column_def in columns_to_add.items():
        if not column_exists('users', column_name):
            op.add_column('users', column_def)
            print(f"✓ Added {column_name} column")


def downgrade() -> None:
    """Revert email_verification_code back to email_verification_token"""
    
    if column_exists('users', 'email_verification_code'):
        if not column_exists('users', 'email_verification_token'):
            op.alter_column('users', 'email_verification_code',
                          new_column_name='email_verification_token',
                          existing_type=sa.String(length=6),
                          existing_nullable=True)
            print("✓ Reverted email_verification_code to email_verification_token")
    
    # Drop added columns
    columns_to_drop = [
        'email_verified', 'password_reset_token', 'password_reset_expires',
        'last_login_at', 'date_of_birth', 'country', 'id_number',
        'bio', 'profile_picture_url', 'status', 'role'
    ]
    
    for column_name in columns_to_drop:
        if column_exists('users', column_name):
            try:
                op.drop_column('users', column_name)
                print(f"✓ Dropped {column_name} column")
            except Exception as e:
                print(f"Warning: Could not drop {column_name}: {e}")