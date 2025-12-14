import pytest
import asyncio
from sqlalchemy import text
from core.database import get_db, init_db, Base

@pytest.fixture
def db_session():
    """Provide a database session for testing"""
    from core.database import SessionLocal
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

def test_database_connection(db_session):
    """Test database connection works"""
    result = db_session.execute(text("SELECT 1")).scalar()
    assert result == 1

def test_database_migrations():
    """Test that all tables can be created"""
    # This will create all tables
    init_db()
    
    # Verify tables exist
    from sqlalchemy import inspect
    inspector = inspect(Base.metadata.bind)
    tables = inspector.get_table_names()
    
    assert 'users' in tables
    assert 'price_history' in tables
    assert 'alerts' in tables

def test_database_transaction_rollback(db_session):
    """Test transaction rollback on error"""
    from modules.auth.models import User
    
    # Start transaction
    user = User(telegram_id="test_transaction", username="test")
    db_session.add(user)
    db_session.flush()  # Not committed yet
    
    # Count before rollback
    count_before = db_session.query(User).count()
    
    # Force rollback
    db_session.rollback()
    
    # Count after rollback
    count_after = db_session.query(User).count()
    
    assert count_before == count_after  # No change because rolled back
