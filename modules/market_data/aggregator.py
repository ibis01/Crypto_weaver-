import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import numpy as np
from collections import defaultdict

from core.redis_client import redis_client
from core.database import get_db
from modules.market_data.models import PriceHistory, AggregatedPrice

logger = logging.getLogger(__name__)

class PriceAggregator:
    """Aggregate prices from multiple exchanges with volume weighting"""
    
    def __init__(self):
        self.exchange_weights = {
            'binance': 1.0,
            'coinbase': 1.0,
            'kraken': 0.9,
            'bybit': 0.8,
            'okx': 0.8
        }
        self.min_exchanges = 2  # Minimum exchanges for reliable price
        self.price_history = defaultdict(list)  # In-memory cache for recent prices
    
    async def get_aggregated_price(self, symbol: str) -> Optional[Dict]:
        """Get aggregated price for symbol across all exchanges"""
        # Try cache first
        cache_key = f"price_agg:{symbol}"
        cached = await redis_client.cache_get(cache_key)
        if cached:
            return cached
        
        # Calculate fresh aggregated price
        return await self.calculate_aggregated_price(symbol)
    
    async def calculate_aggregated_price(self, symbol: str) -> Optional[Dict]:
        """Calculate aggregated price from all available exchanges"""
        exchanges = ['binance', 'coinbase', 'kraken']
        prices = []
        volumes = []
        timestamps = []
        
        for exchange in exchanges:
            cache_key = f"price:{exchange}:{symbol}"
            price_data = await redis_client.cache_get(cache_key)
            
            if price_data:
                weight = self.exchange_weights.get(exchange, 0.5)
                prices.append(price_data['price'] * weight)
                volumes.append(price_data.get('volume', 0) * weight)
                timestamps.append(price_data['timestamp'])
        
        if len(prices) >= self.min_exchanges:
            # Calculate volume-weighted average
            total_volume = sum(volumes)
            if total_volume > 0:
                weighted_avg = sum(p * v for p, v in zip(prices, volumes)) / total_volume
            else:
                weighted_avg = np.mean(prices)
            
            # Calculate spread
            price_spread = (max(prices) - min(prices)) / weighted_avg * 100
            
            aggregated = {
                'symbol': symbol,
                'price': float(weighted_avg),
                'spread_percent': float(price_spread),
                'exchange_count': len(prices),
                'exchanges': exchanges[:len(prices)],
                'high': float(max(prices)),
                'low': float(min(prices)),
                'total_volume': float(total_volume),
                'timestamp': datetime.utcnow().isoformat(),
                'confidence': min(1.0, len(prices) / 3)  # 0-1 confidence score
            }
            
            # Cache for 5 seconds
            await redis_client.cache_set(
                f"price_agg:{symbol}",
                aggregated,
                expire=5
            )
            
            # Store in database for historical analysis
            await self.store_price_history(symbol, aggregated)
            
            return aggregated
        
        return None
    
    async def store_price_history(self, symbol: str, price_data: Dict):
        """Store price history in database with TimescaleDB"""
        try:
            with get_db() as db:
                # Store in PriceHistory table (TimescaleDB hypertable)
                price_history = PriceHistory(
                    symbol=symbol,
                    price=price_data['price'],
                    volume=price_data.get('total_volume', 0),
                    high=price_data.get('high', price_data['price']),
                    low=price_data.get('low', price_data['price']),
                    exchange_count=price_data['exchange_count'],
                    spread=price_data['spread_percent'],
                    timestamp=datetime.utcnow()
                )
                db.add(price_history)
                db.commit()
                
                # Update aggregated price table
                agg_price = db.query(AggregatedPrice).filter(
                    AggregatedPrice.symbol == symbol
                ).first()
                
                if agg_price:
                    agg_price.price = price_data['price']
                    agg_price.volume_24h = await self.calculate_24h_volume(symbol)
                    agg_price.price_change_24h = await self.calculate_24h_change(symbol)
                    agg_price.last_updated = datetime.utcnow()
                else:
                    agg_price = AggregatedPrice(
                        symbol=symbol,
                        price=price_data['price'],
                        volume_24h=0,
                        price_change_24h=0,
                        last_updated=datetime.utcnow()
                    )
                    db.add(agg_price)
                
                db.commit()
                
        except Exception as e:
            logger.error(f"Error storing price history: {e}")
    
    async def calculate_24h_volume(self, symbol: str) -> float:
        """Calculate 24-hour volume from historical data"""
        with get_db() as db:
            twenty_four_hours_ago = datetime.utcnow() - timedelta(hours=24)
            result = db.query(db.func.sum(PriceHistory.volume)).filter(
                PriceHistory.symbol == symbol,
                PriceHistory.timestamp >= twenty_four_hours_ago
            ).scalar()
            return float(result or 0)
    
    async def calculate_24h_change(self, symbol: str) -> float:
        """Calculate 24-hour price change percentage"""
        with get_db() as db:
            twenty_four_hours_ago = datetime.utcnow() - timedelta(hours=24)
            old_price = db.query(PriceHistory.price).filter(
                PriceHistory.symbol == symbol,
                PriceHistory.timestamp >= twenty_four_hours_ago
            ).order_by(PriceHistory.timestamp.asc()).first()
            
            current_price = db.query(PriceHistory.price).filter(
                PriceHistory.symbol == symbol
            ).order_by(PriceHistory.timestamp.desc()).first()
            
            if old_price and current_price:
                return ((current_price[0] - old_price[0]) / old_price[0]) * 100
            return 0.0
    
    async def get_top_gainers(self, limit: int = 10) -> List[Dict]:
        """Get top gaining symbols in last 24 hours"""
        with get_db() as db:
            # Get symbols with sufficient data
            symbols = db.query(PriceHistory.symbol).distinct().limit(100).all()
            gainers = []
            
            for (symbol,) in symbols:
                change = await self.calculate_24h_change(symbol)
                if change != 0:
                    gainers.append({
                        'symbol': symbol,
                        'price_change_24h': change,
                        'current_price': await self.get_current_price(symbol)
                    })
            
            # Sort by gain
            gainers.sort(key=lambda x: x['price_change_24h'], reverse=True)
            return gainers[:limit]
    
    async def get_current_price(self, symbol: str) -> Optional[float]:
        """Get current price from cache"""
        price_data = await redis_client.cache_get(f"price_agg:{symbol}")
        return price_data['price'] if price_data else None
