import pytest
from datetime import datetime
from modules.auth.models import User, UserSession

def test_user_creation():
    """Test User model creation"""
    user = User(
        telegram_id="123456",
        username="testuser",
        first_name="Test",
        last_name="User"
    )
    
    assert user.telegram_id == "123456"
    assert user.username == "testuser"
    assert user.is_active == True  # Default value
    assert isinstance(user.created_at, datetime)

def test_user_session_expired():
    """Test UserSession expiration logic"""
    from datetime import datetime, timedelta
    
    # Create session that expired 1 hour ago
    expired_time = datetime.utcnow() - timedelta(hours=2)
    session = UserSession(
        user_id=1,
        token="test_token",
        expires_at=expired_time
    )
    
    assert session.is_expired() == True
    
    # Create session that expires in 1 hour
    future_time = datetime.utcnow() + timedelta(hours=1)
    session.expires_at = future_time
    
    assert session.is_expired() == False
