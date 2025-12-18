"""Add social trading features

Revision ID: 003
Revises: 002
Create Date: 2024-01-05 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None

def upgrade():
    # Social trading tables
    op.create_table('follow_relationships',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('follower_id', sa.Integer(), nullable=False),
        sa.Column('trader_id', sa.Integer(), nullable=False),
        sa.Column('settings', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['follower_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['trader_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('follower_id', 'trader_id', name='unique_follow')
    )
    
    op.create_table('trader_stats',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('total_pnl', sa.Numeric(20, 8), nullable=True),
        sa.Column('daily_pnl', sa.Numeric(20, 8), nullable=True),
        sa.Column('weekly_pnl', sa.Numeric(20, 8), nullable=True),
        sa.Column('monthly_pnl', sa.Numeric(20, 8), nullable=True),
        sa.Column('win_rate', sa.Numeric(5, 2), nullable=True),
        sa.Column('total_trades', sa.Integer(), nullable=True),
        sa.Column('follower_count', sa.Integer(), nullable=True),
        sa.Column('copied_trades', sa.Integer(), nullable=True),
        sa.Column('risk_score', sa.Integer(), nullable=True),
        sa.Column('last_updated', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id')
    )
    
    # Community features
    op.create_table('community_signals',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('symbol', sa.String(length=50), nullable=False),
        sa.Column('signal_type', sa.String(length=50), nullable=False),
        sa.Column('action', sa.String(length=20), nullable=False),
        sa.Column('price_target', sa.Numeric(20, 8), nullable=True),
        sa.Column('stop_loss', sa.Numeric(20, 8), nullable=True),
        sa.Column('confidence', sa.Numeric(5, 2), nullable=True),
        sa.Column('analysis', sa.Text(), nullable=True),
        sa.Column('tags', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_table('signal_likes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('signal_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['signal_id'], ['community_signals.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'signal_id', name='unique_signal_like')
    )
    
    op.create_table('signal_comments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('signal_id', sa.Integer(), nullable=False),
        sa.Column('comment', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['signal_id'], ['community_signals.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Achievements
    op.create_table('user_achievements',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('achievement_type', sa.String(length=50), nullable=False),
        sa.Column('unlocked_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'achievement_type', name='unique_achievement')
    )
    
    # Discussion rooms
    op.create_table('discussion_rooms',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('creator_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('symbol', sa.String(length=50), nullable=True),
        sa.Column('is_public', sa.Boolean(), default=True),
        sa.Column('max_participants', sa.Integer(), default=100),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['creator_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_table('room_participants',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('room_id', sa.Integer(), nullable=False),
        sa.Column('joined_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['room_id'], ['discussion_rooms.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'room_id', name='unique_participant')
    )
    
    # Referral system
    op.create_table('referral_codes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code')
    )
    
    op.create_table('referrals',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('referrer_id', sa.Integer(), nullable=False),
        sa.Column('referred_id', sa.Integer(), nullable=False),
        sa.Column('code_used', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('status', sa.String(length=20), default='pending'),
        sa.ForeignKeyConstraint(['referrer_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['referred_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('referred_id', name='unique_referral')
    )
    
    op.create_table('referral_bonuses',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('referral_id', sa.Integer(), nullable=True),
        sa.Column('amount', sa.Numeric(10, 2), nullable=False),
        sa.Column('currency', sa.String(length=10), default='USD'),
        sa.Column('bonus_type', sa.String(length=20), nullable=False),
        sa.Column('awarded_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['referral_id'], ['referrals.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    op.create_index('ix_follow_relationships_follower_id', 'follow_relationships', ['follower_id'])
    op.create_index('ix_follow_relationships_trader_id', 'follow_relationships', ['trader_id'])
    op.create_index('ix_trader_stats_user_id', 'trader_stats', ['user_id'])
    op.create_index('ix_community_signals_user_id', 'community_signals', ['user_id'])
    op.create_index('ix_community_signals_created_at', 'community_signals', ['created_at'])
    op.create_index('ix_signal_likes_signal_id', 'signal_likes', ['signal_id'])
    op.create_index('ix_signal_comments_signal_id', 'signal_comments', ['signal_id'])
    op.create_index('ix_user_achievements_user_id', 'user_achievements', ['user_id'])
    op.create_index('ix_referral_codes_user_id', 'referral_codes', ['user_id'])
    op.create_index('ix_referrals_referrer_id', 'referrals', ['referrer_id'])
    
    # Add new columns to users table for social features
    op.add_column('users', sa.Column('display_name', sa.String(length=100), nullable=True))
    op.add_column('users', sa.Column('bio', sa.Text(), nullable=True))
    op.add_column('users', sa.Column('avatar_url', sa.String(length=500), nullable=True))
    op.add_column('users', sa.Column('location', sa.String(length=100), nullable=True))
    op.add_column('users', sa.Column('website', sa.String(length=200), nullable=True))
    op.add_column('users', sa.Column('social_score', sa.Integer(), default=0))
    
    # Add paper trading table for social features
    op.create_table('paper_trades',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('symbol', sa.String(length=50), nullable=False),
        sa.Column('side', sa.String(length=10), nullable=False),
        sa.Column('quantity', sa.Numeric(20, 8), nullable=False),
        sa.Column('entry_price', sa.Numeric(20, 8), nullable=False),
        sa.Column('exit_price', sa.Numeric(20, 8), nullable=True),
        sa.Column('profit_loss', sa.Numeric(20, 8), nullable=True),
        sa.Column('trade_type', sa.String(length=50), nullable=True),
        sa.Column('source_trader_id', sa.Integer(), nullable=True),
        sa.Column('source_trade_id', sa.Integer(), nullable=True),
        sa.Column('is_public', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('closed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['source_trader_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_index('ix_paper_trades_user_id', 'paper_trades', ['user_id'])
    op.create_index('ix_paper_trades_created_at', 'paper_trades', ['created_at'])

def downgrade():
    # Drop paper trades table
    op.drop_index('ix_paper_trades_created_at', table_name='paper_trades')
    op.drop_index('ix_paper_trades_user_id', table_name='paper_trades')
    op.drop_table('paper_trades')
    
    # Drop new user columns
    op.drop_column('users', 'social_score')
    op.drop_column('users', 'website')
    op.drop_column('users', 'location')
    op.drop_column('users', 'avatar_url')
    op.drop_column('users', 'bio')
    op.drop_column('users', 'display_name')
    
    # Drop indexes
    op.drop_index('ix_referrals_referrer_id', table_name='referrals')
    op.drop_index('ix_referral_codes_user_id', table_name='referral_codes')
    op.drop_index('ix_user_achievements_user_id', table_name='user_achievements')
    op.drop_index('ix_signal_comments_signal_id', table_name='signal_comments')
    op.drop_index('ix_signal_likes_signal_id', table_name='signal_likes')
    op.drop_index('ix_community_signals_created_at', table_name='community_signals')
    op.drop_index('ix_community_signals_user_id', table_name='community_signals')
    op.drop_index('ix_trader_stats_user_id', table_name='trader_stats')
    op.drop_index('ix_follow_relationships_trader_id', table_name='follow_relationships')
    op.drop_index('ix_follow_relationships_follower_id', table_name='follow_relationships')
    
    # Drop tables
    op.drop_table('referral_bonuses')
    op.drop_table('referrals')
    op.drop_table('referral_codes')
    op.drop_table('room_participants')
    op.drop_table('discussion_rooms')
    op.drop_table('user_achievements')
    op.drop_table('signal_comments')
    op.drop_table('signal_likes')
    op.drop_table('community_signals')
    op.drop_table('trader_stats')
    op.drop_table('follow_relationships')
