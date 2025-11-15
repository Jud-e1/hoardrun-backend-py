"""add_missing_user_columns - Fixed version
Revision ID: 43e5494d96e6
Revises: 84bbb189512d
Create Date: 2025-11-15 17:35:54.769061
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

# revision identifiers, used by Alembic.
revision: str = '43e5494d96e6'
down_revision: Union[str, None] = '84bbb189512d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def column_exists(table_name, column_name):
    """Check if a column exists in a table"""
    bind = op.get_bind()
    inspector = Inspector.from_engine(bind)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns

def upgrade() -> None:
    # Check if table exists first
    bind = op.get_bind()
    inspector = Inspector.from_engine(bind)
    
    if 'users' not in inspector.get_table_names():
        print("Table 'users' does not exist. Skipping migration.")
        return
    
    # Get existing columns
    existing_columns = [col['name'] for col in inspector.get_columns('users')]
    print(f"Existing columns in users table: {existing_columns}")
    
    # Only add columns that don't exist
    columns_to_add = {
        'password_hash': sa.Column('password_hash', sa.String(length=255), nullable=True),
        'status': sa.Column('status', sa.String(length=20), nullable=True),
        'role': sa.Column('role', sa.String(length=20), nullable=True),
        'email_verified': sa.Column('email_verified', sa.Boolean(), nullable=True),
        'email_verification_code': sa.Column('email_verification_code', sa.String(length=6), nullable=True),
        'password_reset_token': sa.Column('password_reset_token', sa.String(length=255), nullable=True),
        'password_reset_expires': sa.Column('password_reset_expires', sa.DateTime(), nullable=True),
        'last_login_at': sa.Column('last_login_at', sa.DateTime(), nullable=True),
        'date_of_birth': sa.Column('date_of_birth', sa.Date(), nullable=True),
        'country': sa.Column('country', sa.String(length=3), nullable=True),
        'id_number': sa.Column('id_number', sa.String(length=50), nullable=True),
        'bio': sa.Column('bio', sa.Text(), nullable=True),
        'profile_picture_url': sa.Column('profile_picture_url', sa.String(length=500), nullable=True),
        'created_at': sa.Column('created_at', sa.DateTime(), nullable=True),
        'updated_at': sa.Column('updated_at', sa.DateTime(), nullable=True),
    }
    
    for column_name, column_def in columns_to_add.items():
        if column_name not in existing_columns:
            try:
                op.add_column('users', column_def)
                print(f"Added column: {column_name}")
            except Exception as e:
                print(f"Error adding column {column_name}: {e}")
        else:
            print(f"Column {column_name} already exists, skipping")

def downgrade() -> None:
    # Only drop columns that exist
    bind = op.get_bind()
    inspector = Inspector.from_engine(bind)
    
    if 'users' not in inspector.get_table_names():
        return
    
    existing_columns = [col['name'] for col in inspector.get_columns('users')]
    
    columns_to_remove = [
        'password_hash', 'status', 'role', 'email_verified',
        'email_verification_code', 'password_reset_token',
        'password_reset_expires', 'last_login_at', 'date_of_birth',
        'country', 'id_number', 'bio', 'profile_picture_url',
        'created_at', 'updated_at'
    ]
    
    for column_name in columns_to_remove:
        if column_name in existing_columns:
            try:
                op.drop_column('users', column_name)
            except Exception as e:
                print(f"Error dropping column {column_name}: {e}")