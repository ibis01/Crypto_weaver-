import json
import aiohttp
from typing import Dict, List
from datetime import datetime
from .base import ExchangeAdapter

class CoinbaseAdapter(ExchangeAdapter):
    """Coinbase Pro exchange adapter"""
    
    def __init__(self):
        super().__init__(
            name="coinbase",
            base_url="https://api.pro.coinbase.com",
            websocket_url="wss://ws-feed.pro.coinbase.com"
        )
    
    async def connect_websocket(self):
        """Connect to Coinbase WebSocket"""
        self.session = aiohttp.ClientSession()
        self.ws = await self.session.ws_connect(
            self.websocket_url,
            heartbeat=30,
            receive_timeout=30
        )
        
        # Send subscription message
        await self.ws.send_json({
            "type": "subscribe",
            "product_ids": ["BTC-USD", "ETH-USD", "SOL-USD"],  # Will be updated
            "channels": ["ticker", "heartbeat"]
        })
    
    def normalize_symbol(self, symbol: str) -> str:
        """Coinbase already uses BTC-USD format"""
        return symbol.replace('_', '-').upper()
    
    async def subscribe(self, symbols: List[str]):
        """Update subscription"""
        subscription_msg = {
            "type": "subscribe",
            "product_ids": symbols,
            "channels": ["ticker"]
        }
        await self.ws.send_json(subscription_msg)
    
    async def handle_message(self, data: str):
        """Process Coinbase WebSocket messages"""
        try:
            message = json.loads(data)
            
            if message['type'] == 'ticker':
                symbol = message['product_id']  # BTC-USD
                ticker_data = {
                    'exchange': self.name,
                    'symbol': symbol,
                    'price': float(message['price']),
                    'volume': float(message.get('volume_24h', 0)),
                    'high': float(message.get('high_24h', 0)),
                    'low': float(message.get('low_24h', 0)),
                    'change': float(message.get('open_24h', 0)) - float(message['price']),
                    'timestamp': datetime.utcnow().isoformat(),
                    'exchange_timestamp': message['time']
                }
                
                # Cache and broadcast (similar to Binance)
                cache_key = f"price:{self.name}:{symbol}"
                await redis_client.cache_set(cache_key, ticker_data, expire=10)
                await redis_client.publish(f"price_updates:{symbol}", ticker_data)
                await self.broadcast(symbol, ticker_data)
                
        except Exception as e:
            logger.error(f"Error processing Coinbase message: {e}")
