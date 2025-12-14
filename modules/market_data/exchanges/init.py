
import asyncio
import json
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Callable
import aiohttp
from datetime import datetime
import hashlib

from core.redis_client import redis_client
from config.settings import settings

logger = logging.getLogger(__name__)

class ExchangeAdapter(ABC):
    """Abstract base class for all exchange adapters"""
    
    def __init__(self, name: str, base_url: str, websocket_url: str):
        self.name = name
        self.base_url = base_url
        self.websocket_url = websocket_url
        self.session: Optional[aiohttp.ClientSession] = None
        self.ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self.subscribers: Dict[str, List[Callable]] = {}
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 10
        self.reconnect_delay = 1
    
    @abstractmethod
    async def connect_websocket(self):
        """Establish WebSocket connection"""
        pass
    
    @abstractmethod
    async def subscribe(self, symbols: List[str]):
        """Subscribe to symbol updates"""
        pass
    
    @abstractmethod
    def normalize_symbol(self, symbol: str) -> str:
        """Normalize symbol to standard format (BTC-USDT)"""
        pass
    
    async def start(self):
        """Start WebSocket connection with reconnection logic"""
        while self.reconnect_attempts < self.max_reconnect_attempts:
            try:
                await self.connect_websocket()
                self.reconnect_attempts = 0
                logger.info(f"{self.name} WebSocket connected successfully")
                await self.listen()
            except Exception as e:
                self.reconnect_attempts += 1
                delay = self.reconnect_delay * (2 ** self.reconnect_attempts)
                logger.error(f"{self.name} connection failed: {e}. Reconnecting in {delay}s...")
                await asyncio.sleep(min(delay, 60))
        
        logger.error(f"{self.name} max reconnection attempts reached")
    
    async def listen(self):
        """Listen for WebSocket messages"""
        async for msg in self.ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                await self.handle_message(msg.data)
            elif msg.type == aiohttp.WSMsgType.ERROR:
                break
            elif msg.type == aiohttp.WSMsgType.CLOSED:
                break
    
    async def handle_message(self, data: str):
        """Process incoming WebSocket message"""
        raise NotImplementedError
    
    def add_subscriber(self, symbol: str, callback: Callable):
        """Add callback for symbol updates"""
        if symbol not in self.subscribers:
            self.subscribers[symbol] = []
        self.subscribers[symbol].append(callback)
    
    async def broadcast(self, symbol: str, data: Dict):
        """Broadcast update to all subscribers"""
        if symbol in self.subscribers:
            for callback in self.subscribers[symbol]:
                try:
                    await callback(symbol, data)
                except Exception as e:
                    logger.error(f"Error in subscriber callback: {e}")
