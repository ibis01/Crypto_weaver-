import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
import pandas as pd
from datetime import datetime, timedelta

from modules.market_data.exchanges.binance import BinanceAdapter
from modules.market_data.aggregator import PriceAggregator
from modules.market_data.indicators import TechnicalIndicators
from modules.market_data.alerts import AlertManager

@pytest.mark.asyncio
async def test_binance_adapter():
    """Test Binance WebSocket adapter"""
    adapter = BinanceAdapter()
    
    # Mock WebSocket connection
    mock_ws = AsyncMock()
    mock_session = AsyncMock()
    mock_session.ws_connect.return_value = mock_ws
    adapter.session = mock_session
    
    # Test symbol normalization
    assert adapter.normalize_symbol("BTCUSDT") == "BTC-USDT"
    assert adapter.normalize_symbol("ETHBTC") == "ETH-BTC"
    
    # Test message handling
    test_message = json.dumps({
        'e': '24hrTicker',
        's': 'BTCUSDT',
        'c': '50000.00',
        'v': '1000.0',
        'h': '51000.00',
        'l': '49000.00',
        'p': '1000.00',
        'P': '2.00',
        'E': 1672531200000
    })
    
    with patch('modules.market_data.exchanges.binance.redis_client') as mock_redis:
        mock_redis.cache_set = AsyncMock()
        mock_redis.publish = AsyncMock()
        
        await adapter.handle_message(test_message)
        
        # Verify Redis cache was called
        assert mock_redis.cache_set.called
        assert mock_redis.publish.called

@pytest.mark.asyncio
async def test_price_aggregator():
    """Test price aggregation engine"""
    aggregator = PriceAggregator()
    
    # Mock Redis responses
    mock_prices = {
        'price:binance:BTC-USDT': {'price': 50000, 'volume': 1000},
        'price:coinbase:BTC-USDT': {'price': 50100, 'volume': 800},
        'price:kraken:BTC-USDT': {'price': 49900, 'volume': 600}
    }
    
    with patch('modules.market_data.aggregator.redis_client') as mock_redis:
        mock_redis.cache_get = AsyncMock(side_effect=lambda key: mock_prices.get(key))
        
        aggregated = await aggregator.calculate_aggregated_price('BTC-USDT')
        
        assert aggregated is not None
        assert aggregated['symbol'] == 'BTC-USDT'
        assert aggregated['exchange_count'] == 3
        assert 49900 <= aggregated['price'] <= 50100
        assert aggregated['confidence'] > 0

def test_technical_indicators():
    """Test technical indicator calculations"""
    indicators = TechnicalIndicators()
    
    # Create test DataFrame
    dates = pd.date_range('2024-01-01', periods=100, freq='H')
    df = pd.DataFrame({
        'timestamp': dates,
        'close': [100 + i * 0.1 for i in range(100)],
        'volume': [1000 + i * 10 for i in range(100)],
        'high': [101 + i * 0.1 for i in range(100)],
        'low': [99 + i * 0.1 for i in range(100)]
    })
    df.set_index('timestamp', inplace=True)
    
    # Test SMA
    sma_result = asyncio.run(indicators.calculate_sma(df))
    assert 'sma_20' in sma_result
    assert 'sma_50' in sma_result
    
    # Test RSI
    rsi_result = asyncio.run(indicators.calculate_rsi(df))
    assert 'rsi' in rsi_result
    assert 0 <= rsi_result['rsi'] <= 100
    
    # Test MACD
    macd_result = asyncio.run(indicators.calculate_macd(df))
    assert 'macd' in macd_result
    assert 'signal' in macd_result

@pytest.mark.asyncio
async def test_alert_system():
    """Test alert triggering system"""
    alert_manager = AlertManager()
    
    # Create test alert
    test_alert = Mock()
    test_alert.symbol = 'BTC-USDT'
    test_alert.alert_type = 'price_above'
    test_alert.value = 50000
    test_alert.user_id = 1
    
    # Test price above condition
    price_data = {'price': 51000, 'volume': 1000}
    
    should_trigger = await alert_manager.check_price_above(test_alert, price_data)
    assert should_trigger == True
    
    # Test price below condition (should not trigger)
    test_alert.alert_type = 'price_below'
    should_trigger = await alert_manager.check_price_below(test_alert, price_data)
    assert should_trigger == False

# Load testing script
async def load_test_websocket():
    """Simulate high volume of WebSocket connections"""
    import websockets
    
    connections = []
    try:
        # Create 100 simultaneous connections
        for i in range(100):
            ws = await websockets.connect("ws://localhost:8001/ws")
            connections.append(ws)
            await ws.send(json.dumps({
                'type': 'subscribe',
                'symbols': ['BTC-USDT', 'ETH-USDT']
            }))
        
        print(f"✅ Created {len(connections)} WebSocket connections")
        
        # Send updates for 30 seconds
        for i in range(30):
            for ws in connections[:10]:  # Send from 10 connections
                await ws.send(json.dumps({'type': 'ping'}))
            await asyncio.sleep(1)
        
    finally:
        # Close all connections
        for ws in connections:
            await ws.close()
