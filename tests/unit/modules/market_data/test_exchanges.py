import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from modules.market_data.exchanges.binance import BinanceAdapter

@pytest.mark.asyncio
async def test_binance_normalize_symbol():
    """Test symbol normalization"""
    adapter = BinanceAdapter()
    
    assert adapter.normalize_symbol("BTCUSDT") == "BTC-USDT"
    assert adapter.normalize_symbol("ETHBTC") == "ETH-BTC"
    assert adapter.normalize_symbol("SOLUSDC") == "SOL-USDC"

@pytest.mark.asyncio
async def test_binance_handle_message():
    """Test WebSocket message handling"""
    adapter = BinanceAdapter()
    
    # Mock Redis
    with patch('modules.market_data.exchanges.binance.redis_client') as mock_redis:
        mock_redis.cache_set = AsyncMock()
        mock_redis.publish = AsyncMock()
        
        # Simulate Binance ticker message
        message = '{"e":"24hrTicker","s":"BTCUSDT","c":"50000.00","v":"1000.0","h":"51000.00","l":"49000.00","p":"1000.00","P":"2.00","E":1672531200000}'
        
        await adapter.handle_message(message)
        
        # Verify Redis was called
        assert mock_redis.cache_set.called
        assert mock_redis.publish.called
        
        # Check cache key
        args, kwargs = mock_redis.cache_set.call_args
        assert "price:binance:BTC-USDT" in args[0]
        assert kwargs['expire'] == 10

@pytest.mark.asyncio
async def test_binance_reconnection():
    """Test exponential backoff reconnection"""
    adapter = BinanceAdapter()
    
    with patch('aiohttp.ClientSession.ws_connect', side_effect=Exception("Connection failed")):
        # First attempt
        try:
            await adapter.connect_websocket()
        except:
            pass
        
        # Should increase reconnect attempts
        assert adapter.reconnect_attempts == 1
        
        # Simulate multiple failures
        for _ in range(3):
            adapter.reconnect_attempts += 1
        
        # Calculate delay with exponential backoff
        delay = adapter.reconnect_delay * (2 ** adapter.reconnect_attempts)
        assert delay == 16  # 1 * 2^4 = 16
