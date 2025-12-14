import pytest
import asyncio
import sys
import os
from pathlib import Path

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Async event loop fixture
@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

# Environment variables for testing
@pytest.fixture(autouse=True)
def setup_test_env(monkeypatch):
    """Set up test environment variables"""
    monkeypatch.setenv('ENVIRONMENT', 'testing')
    monkeypatch.setenv('DATABASE_URL', 'postgresql://test:test@localhost:5432/test_db')
    monkeypatch.setenv('REDIS_URL', 'redis://localhost:6379/1')
    monkeypatch.setenv('TELEGRAM_BOT_TOKEN', 'test_token')
    monkeypatch.setenv('JWT_SECRET_KEY', 'test_secret_key')
