import pytest
import asyncio
import json
from datetime import timedelta
from core.redis_client import redis_client

@pytest.mark.asyncio
async def test_redis_connection():
    """Test Redis connection"""
    result = await redis_client.redis.ping()
    assert result == True

@pytest.mark.asyncio
async def test_redis_cache():
    """Test Redis caching with compression"""
    test_data = {
        'price': 50000.50,
        'volume': 1000.25,
        'timestamp': '2024-01-01T00:00:00Z',
        'nested': {'key': 'value', 'array': [1, 2, 3]}
    }
    
    # Set cache
    success = await redis_client.cache_set('test_key', test_data, expire=60)
    assert success == True
    
    # Get cache
    cached = await redis_client.cache_get('test_key')
    assert cached == test_data
    
    # Test with compression
    large_data = {'data': 'x' * 1000}  # Large string
    await redis_client.cache_set('large_key', large_data, compress=True)
    cached_large = await redis_client.cache_get('large_key')
    assert cached_large == large_data

@pytest.mark.asyncio
async def test_redis_pubsub():
    """Test Redis Pub/Sub functionality"""
    messages_received = []
    
    async def message_handler(message):
        messages_received.append(json.loads(message['data']))
    
    # Subscribe to channel
    pubsub = redis_client.redis.pubsub()
    await pubsub.subscribe('test_channel')
    
    # Start listening in background
    async def listen():
        async for message in pubsub.listen():
            if message['type'] == 'message':
                await message_handler(message)
                break  # Stop after first message
    
    listener_task = asyncio.create_task(listen())
    
    # Wait for subscription to be ready
    await asyncio.sleep(0.1)
    
    # Publish message
    test_message = {'action': 'test', 'data': 'hello'}
    await redis_client.publish('test_channel', test_message)
    
    # Wait for message
    await asyncio.wait_for(listener_task, timeout=2)
    
    assert len(messages_received) == 1
    assert messages_received[0] == test_message
    
    # Cleanup
    await pubsub.unsubscribe('test_channel')
