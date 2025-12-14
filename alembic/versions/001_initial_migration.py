
"""Initial migration

Revision ID: 001
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # Users table
    op.create_table('users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('telegram_id', sa.String(length=100), nullable=False),
        sa.Column('username', sa.String(length=100), nullable=True),
        sa.Column('first_name', sa.String(length=100), nullable=True),
        sa.Column('last_name', sa.String(length=100), nullable=True),
        sa.Column('language_code', sa.String(length=10), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('last_active', sa.DateTime(), nullable=True),
        sa.Column('settings', postgresql.JSONB(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('telegram_id')
    )
    
    # User sessions for JWT
    op.create_table('user_sessions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('token', sa.String(length=500), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token')
    )
    
    # Create indexes
    op.create_index(op.f('ix_users_telegram_id'), 'users', ['telegram_id'], unique=True)
    op.create_index(op.f('ix_user_sessions_token'), 'user_sessions', ['token'], unique=True)
    op.create_index(op.f('ix_user_sessions_user_id'), 'user_sessions', ['user_id'])

def downgrade():
    op.drop_index(op.f('ix_user_sessions_user_id'), table_name='user_sessions')
    op.drop_index(op.f('ix_user_sessions_token'), table_name='user_sessions')
    op.drop_index(op.f('ix_users_telegram_id'), table_name='users')
    op.drop_table('user_sessions')
    op.drop_table('users')
