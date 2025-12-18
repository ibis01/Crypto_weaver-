import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timedelta

from modules.social import SocialTradingManager, LeaderboardManager, CommunityManager
from modules.social.profiles import UserProfileManager, ReferralManager

@pytest.mark.asyncio
async def test_social_trading_follow():
    """Test following a trader"""
    manager = SocialTradingManager()
    
    follower_id = 1
    trader_id = 2
    
    with patch('modules.social.SocialTradingManager.get_db') as mock_db:
        mock_session = MagicMock()
        mock_db.return_value.__enter__.return_value = mock_session
        
        # Mock follow relationship query
        mock_session.query.return_value.filter.return_value.first.return_value = None
        
        # Mock commit
        mock_session.commit.return_value = None
        
        # Mock Redis publish
        with patch('modules.social.redis_client.publish', new_callable=AsyncMock) as mock_publish:
            result = await manager.follow_trader(follower_id, trader_id)
            
            assert result is not None
            assert mock_session.add.called
            assert mock_session.commit.called
            assert mock_publish.called

@pytest.mark.asyncio
async def test_leaderboard_update():
    """Test leaderboard updates"""
    manager = LeaderboardManager()
    
    user_id = 1
    metric = "daily_pnl"
    value = 1000.50
    
    with patch('modules.social.leaderboards.redis_client') as mock_redis:
        mock_redis.zadd = AsyncMock()
        mock_redis.publish = AsyncMock()
        
        await manager.update_leaderboard(user_id, metric, value)
        
        assert mock_redis.zadd.called
        assert mock_redis.publish.called

@pytest.mark.asyncio
async def test_community_signal_post():
    """Test posting community signal"""
    manager = CommunityManager()
    
    user_id = 1
    signal_data = {
        'symbol': 'BTC-USDT',
        'action': 'buy',
        'confidence': 0.8,
        'analysis': 'Bullish momentum'
    }
    
    with patch('modules.social.community.get_db') as mock_db:
        mock_session = MagicMock()
        mock_db.return_value.__enter__.return_value = mock_session
        
        # Mock user query
        mock_user = MagicMock()
        mock_user.username = 'testuser'
        mock_session.query.return_value.filter.return_value.first.return_value = mock_user
        
        # Mock Redis publish
        with patch('modules.social.community.redis_client.publish', new_callable=AsyncMock) as mock_publish:
            result = await manager.post_signal(user_id, signal_data)
            
            assert 'signal_id' in result
            assert result['username'] == 'testuser'
            assert result['symbol'] == 'BTC-USDT'
            assert mock_session.add.called
            assert mock_session.commit.called
            assert mock_publish.called

@pytest.mark.asyncio
async def test_user_profile_get():
    """Test getting user profile"""
    manager = UserProfileManager()
    
    user_id = 1
    
    with patch('modules.social.profiles.get_db') as mock_db:
        mock_session = MagicMock()
        mock_db.return_value.__enter__.return_value = mock_session
        
        # Mock user query
        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.username = 'testuser'
        mock_user.created_at = datetime.utcnow()
        mock_user.last_active = datetime.utcnow()
        mock_session.query.return_value.filter.return_value.first.return_value = mock_user
        
        # Mock Redis cache
        with patch('modules.social.profiles.redis_client.cache_set', new_callable=AsyncMock):
            profile = await manager.get_user_profile(user_id)
            
            assert profile['user_id'] == 1
            assert profile['username'] == 'testuser'
            assert 'total_pnl' in profile
            assert 'achievements' in profile
            assert 'recent_trades' in profile

@pytest.mark.asyncio
async def test_referral_code_generation():
    """Test referral code generation"""
    manager = ReferralManager()
    
    user_id = 1
    
    with patch('modules.social.profiles.get_db') as mock_db:
        mock_session = MagicMock()
        mock_db.return_value.__enter__.return_value = mock_session
        
        # Mock no existing code
        mock_session.query.return_value.filter.return_value.first.return_value = None
        
        code = await manager.generate_referral_code(user_id)
        
        assert code is not None
        assert len(code) == 8  # Default length
        assert mock_session.add.called
        assert mock_session.commit.called

# Load testing for social features
@pytest.mark.performance
@pytest.mark.asyncio
async def test_social_features_load():
    """Load test social features"""
    import time
    
    manager = SocialTradingManager()
    start_time = time.time()
    
    # Simulate 1000 follow operations
    tasks = []
    for i in range(100):
        task = asyncio.create_task(
            manager.follow_trader(i, i + 100)
        )
        tasks.append(task)
    
    await asyncio.gather(*tasks)
    
    end_time = time.time()
    operations_per_second = 100 / (end_time - start_time)
    
    print(f"\n📊 Social Features Load Test:")
    print(f"Operations: 100 follow actions")
    print(f"Duration: {end_time - start_time:.2f}s")
    print(f"Ops/sec: {operations_per_second:.1f}")
    
    assert operations_per_second > 10  # Should handle at least 10 ops/sec
