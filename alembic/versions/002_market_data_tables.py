"""Create market data tables

Revision ID: 002
Revises: 001
Create Date: 2024-01-02 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None

def upgrade():
    # Enable TimescaleDB extension
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")
    
    # Price history table (will become hypertable)
    op.create_table('price_history',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('symbol', sa.String(length=50), nullable=False),
        sa.Column('price', sa.Numeric(20, 8), nullable=False),
        sa.Column('volume', sa.Numeric(20, 8), nullable=True),
        sa.Column('high', sa.Numeric(20, 8), nullable=True),
        sa.Column('low', sa.Numeric(20, 8), nullable=True),
        sa.Column('exchange_count', sa.Integer(), nullable=True),
        sa.Column('spread', sa.Numeric(10, 4), nullable=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create hypertable for time-series data
    op.execute("""
        SELECT create_hypertable(
            'price_history', 
            'timestamp',
            chunk_time_interval => INTERVAL '1 day',
            if_not_exists => TRUE
        )
    """)
    
    # Create indexes for fast queries
    op.create_index('ix_price_history_symbol_timestamp', 'price_history', ['symbol', 'timestamp'], unique=False)
    op.create_index('ix_price_history_timestamp', 'price_history', ['timestamp'], unique=False)
    
    # Aggregated price table
    op.create_table('aggregated_prices',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('symbol', sa.String(length=50), nullable=False),
        sa.Column('price', sa.Numeric(20, 8), nullable=False),
        sa.Column('volume_24h', sa.Numeric(20, 8), nullable=True),
        sa.Column('price_change_24h', sa.Numeric(10, 4), nullable=True),
        sa.Column('market_cap', sa.Numeric(30, 2), nullable=True),
        sa.Column('dominance', sa.Numeric(5, 2), nullable=True),
        sa.Column('last_updated', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('symbol')
    )
    
    # Alerts table
    op.create_table('alerts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('symbol', sa.String(length=50), nullable=False),
        sa.Column('alert_type', sa.String(length=50), nullable=False),
        sa.Column('condition', postgresql.JSONB(), nullable=True),
        sa.Column('value', sa.Numeric(20, 8), nullable=False),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('trigger_count', sa.Integer(), default=0),
        sa.Column('last_triggered', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Alert triggers history
    op.create_table('alert_triggers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('alert_id', sa.Integer(), nullable=False),
        sa.Column('triggered_value', sa.Numeric(20, 8), nullable=False),
        sa.Column('triggered_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('metadata', postgresql.JSONB(), nullable=True),
        sa.ForeignKeyConstraint(['alert_id'], ['alerts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    op.create_index('ix_alerts_user_id', 'alerts', ['user_id'])
    op.create_index('ix_alerts_symbol', 'alerts', ['symbol'])
    op.create_index('ix_alerts_is_active', 'alerts', ['is_active'])
    op.create_index('ix_alert_triggers_alert_id', 'alert_triggers', ['alert_id'])
    op.create_index('ix_alert_triggers_triggered_at', 'alert_triggers', ['triggered_at'])

def downgrade():
    op.drop_index('ix_alert_triggers_triggered_at', table_name='alert_triggers')
    op.drop_index('ix_alert_triggers_alert_id', table_name='alert_triggers')
    op.drop_index('ix_alerts_is_active', table_name='alerts')
    op.drop_index('ix_alerts_symbol', table_name='alerts')
    op.drop_index('ix_alerts_user_id', table_name='alerts')
    op.drop_table('alert_triggers')
    op.drop_table('alerts')
    op.drop_table('aggregated_prices')
    op.drop_index('ix_price_history_timestamp', table_name='price_history')
    op.drop_index('ix_price_history_symbol_timestamp', table_name='price_history')
    op.drop_table('price_history')
