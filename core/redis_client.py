
import redis
import json
from datetime import timedelta
from typing import Any, Optional, Union
import pickle
import zlib
import logging

from config.settings import settings

logger = logging.getLogger(__name__)

class RedisManager:
    """Enhanced Redis manager with compression and typed caching"""
    
    def __init__(self):
        redis_url = str(settings.REDIS_URL)
        password = settings.REDIS_PASSWORD.get_secret_value() if settings.REDIS_PASSWORD else None
        
        self.redis = redis.Redis.from_url(
            redis_url,
            password=password,
            decode_responses=False,  # Keep as bytes for compression
            socket_timeout=5,
            socket_keepalive=True,
            health_check_interval=30
        )
        
        # Test connection
        try:
            self.redis.ping()
            logger.info("Redis connection established")
        except redis.ConnectionError as e:
            logger.error(f"Redis connection failed: {e}")
            raise
    
    def _compress(self, data: Any) -> bytes:
        """Compress data using zlib"""
        pickled = pickle.dumps(data)
        compressed = zlib.compress(pickled)
        return compressed
    
    def _decompress(self, data: bytes) -> Any:
        """Decompress data"""
        decompressed = zlib.decompress(data)
        unpickled = pickle.loads(decompressed)
        return unpickled
    
    def cache_get(self, 
                  key: str, 
                  default: Any = None,
                  decompress: bool = True) -> Any:
        """Get cached value with optional decompression"""
        try:
            data = self.redis.get(key)
            if data is None:
                return default
            
            if decompress:
                return self._decompress(data)
            else:
                return data
        except Exception as e:
            logger.error(f"Cache get error for key {key}: {e}")
            return default
    
    def cache_set(self, 
                  key: str, 
                  value: Any,
                  expire: Optional[Union[int, timedelta]] = 300,
                  compress: bool = True) -> bool:
        """Set cache value with optional compression"""
        try:
            if compress:
                value = self._compress(value)
            
            if isinstance(expire, timedelta):
                expire = int(expire.total_seconds())
            
            self.redis.setex(key, expire, value)
            return True
        except Exception as e:
            logger.error(f"Cache set error for key {key}: {e}")
            return False
    
    def pubsub(self):
        """Get pubsub client for real-time messaging"""
        return self.redis.pubsub()
    
    def publish(self, channel: str, message: dict):
        """Publish message to channel"""
        self.redis.publish(channel, json.dumps(message))
    
    def rate_limit(self, key: str, limit: int, window: int = 60) -> bool:
        """Simple rate limiting using Redis"""
        current = self.redis.incr(key)
        if current == 1:
            self.redis.expire(key, window)
        
        return current <= limit

# Global Redis instance
redis_client = RedisManager()
