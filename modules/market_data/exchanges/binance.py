import json
import aiohttp
from typing import Dict, List
from datetime import datetime
from .base import ExchangeAdapter

class BinanceAdapter(ExchangeAdapter):
    """Binance exchange adapter"""
    
    def __init__(self):
        super().__init__(
            name="binance",
            base_url="https://api.binance.com",
            websocket_url="wss://stream.binance.com:9443/ws"
        )
        self.symbol_map = {}
    
    async def connect_websocket(self):
        """Connect to Binance WebSocket"""
        self.session = aiohttp.ClientSession()
        self.ws = await self.session.ws_connect(
            self.websocket_url,
            heartbeat=30,
            receive_timeout=30,
            autoping=True
        )
    
    def normalize_symbol(self, symbol: str) -> str:
        """Convert BTCUSDT to BTC-USDT"""
        # Handle common pairs
        for quote in ['USDT', 'BTC', 'ETH', 'BNB', 'USD']:
            if symbol.endswith(quote):
                base = symbol[:-len(quote)]
                return f"{base}-{quote}"
        return symbol
    
    async def subscribe(self, symbols: List[str]):
        """Subscribe to ticker streams"""
        streams = [f"{s.lower()}@ticker" for s in symbols]
        subscription_msg = {
            "method": "SUBSCRIBE",
            "params": streams,
            "id": 1
        }
        await self.ws.send_json(subscription_msg)
        logger.info(f"Subscribed to {len(symbols)} symbols on Binance")
    
    async def handle_message(self, data: str):
        """Process Binance WebSocket messages"""
        try:
            message = json.loads(data)
            
            # Check if it's a ticker update
            if 'e' in message and message['e'] == '24hrTicker':
                symbol = self.normalize_symbol(message['s'])  # BTCUSDT
                ticker_data = {
                    'exchange': self.name,
                    'symbol': symbol,
                    'price': float(message['c']),  # Current price
                    'volume': float(message['v']),  # 24h volume
                    'high': float(message['h']),    # 24h high
                    'low': float(message['l']),     # 24h low
                    'change': float(message['p']),  # Price change
                    'change_percent': float(message['P']),  # Change percent
                    'timestamp': datetime.utcnow().isoformat(),
                    'exchange_timestamp': message['E']  # Binance event time
                }
                
                # Cache in Redis
                cache_key = f"price:{self.name}:{symbol}"
                await redis_client.cache_set(cache_key, ticker_data, expire=10)
                
                # Publish to Redis Pub/Sub for real-time updates
                await redis_client.publish(f"price_updates:{symbol}", ticker_data)
                
                # Broadcast to subscribers
                await self.broadcast(symbol, ticker_data)
                
                # Update price aggregator
                await self.update_aggregated_price(symbol, ticker_data)
                
        except Exception as e:
            logger.error(f"Error processing Binance message: {e}")
    
    async def update_aggregated_price(self, symbol: str, ticker_data: Dict):
        """Update aggregated price across exchanges"""
        # Create a unique key for this symbol across exchanges
        agg_key = f"price_agg:{symbol}"
        
        # Get current aggregated data
        current_agg = await redis_client.cache_get(agg_key) or {
            'symbol': symbol,
            'exchanges': {},
            'average_price': 0,
            'total_volume': 0,
            'price_count': 0,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Update this exchange's data
        current_agg['exchanges'][self.name] = {
            'price': ticker_data['price'],
            'volume': ticker_data['volume'],
            'timestamp': ticker_data['timestamp']
        }
        
        # Recalculate average price (weighted by volume)
        total_volume = sum(ex['volume'] for ex in current_agg['exchanges'].values())
        weighted_sum = sum(ex['price'] * ex['volume'] for ex in current_agg['exchanges'].values())
        
        if total_volume > 0:
            current_agg['average_price'] = weighted_sum / total_volume
            current_agg['total_volume'] = total_volume
            current_agg['price_count'] = len(current_agg['exchanges'])
            current_agg['last_updated'] = datetime.utcnow().isoformat()
            
            # Save aggregated price
            await redis_client.cache_set(agg_key, current_agg, expire=5)
            
            # Publish aggregated price update
            await redis_client.publish(f"price_agg:{symbol}", current_agg)
