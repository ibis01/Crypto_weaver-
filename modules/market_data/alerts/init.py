import asyncio
import json
import logging
from typing import Dict, List, Optional, Callable
from datetime import datetime, timedelta
from enum import Enum
import re

from core.database import get_db
from core.redis_client import redis_client
from modules.market_data.models import Alert, AlertTrigger

logger = logging.getLogger(__name__)

class AlertType(Enum):
    """Types of alerts supported"""
    PRICE_ABOVE = "price_above"
    PRICE_BELOW = "price_below"
    PRICE_CHANGE = "price_change"
    VOLUME_SPIKE = "volume_spike"
    RSI_OVERBOUGHT = "rsi_overbought"
    RSI_OVERSOLD = "rsi_oversold"
    MACD_CROSSOVER = "macd_crossover"
    SUPPORT_BREAK = "support_break"
    RESISTANCE_BREAK = "resistance_break"
    PATTERN_FORMATION = "pattern_formation"

class AlertManager:
    """Manage and trigger alerts for users"""
    
    def __init__(self):
        self.active_alerts = {}
        self.alert_handlers = {
            AlertType.PRICE_ABOVE: self.check_price_above,
            AlertType.PRICE_BELOW: self.check_price_below,
            AlertType.PRICE_CHANGE: self.check_price_change,
            AlertType.VOLUME_SPIKE: self.check_volume_spike,
            AlertType.RSI_OVERBOUGHT: self.check_rsi,
            AlertType.RSI_OVERSOLD: self.check_rsi,
            AlertType.MACD_CROSSOVER: self.check_macd,
            AlertType.SUPPORT_BREAK: self.check_support_resistance,
            AlertType.RESISTANCE_BREAK: self.check_support_resistance
        }
    
    async def create_alert(self, user_id: int, alert_data: Dict) -> Alert:
        """Create a new alert for user"""
        with get_db() as db:
            alert = Alert(
                user_id=user_id,
                symbol=alert_data['symbol'],
                alert_type=alert_data['type'],
                condition=alert_data['condition'],
                value=float(alert_data['value']),
                is_active=True,
                created_at=datetime.utcnow(),
                last_triggered=None
            )
            db.add(alert)
            db.commit()
            db.refresh(alert)
            
            # Add to active alerts cache
            alert_key = f"alert:{user_id}:{alert.id}"
            await redis_client.cache_set(alert_key, alert_data, expire=86400)  # 24h
            
            logger.info(f"Alert created: {alert.id} for user {user_id}")
            return alert
    
    async def check_all_alerts(self, symbol: str, price_data: Dict):
        """Check all alerts for a symbol"""
        # Get active alerts for this symbol
        alert_pattern = f"alert:*:{symbol}"
        # Note: Redis doesn't support wildcard search directly
        # In production, use Redis sets or sorted sets
        
        # For now, check database
        with get_db() as db:
            active_alerts = db.query(Alert).filter(
                Alert.symbol == symbol,
                Alert.is_active == True
            ).all()
            
            for alert in active_alerts:
                await self.check_single_alert(alert, price_data)
    
    async def check_single_alert(self, alert: Alert, price_data: Dict):
        """Check if a single alert should trigger"""
        handler = self.alert_handlers.get(AlertType(alert.alert_type))
        if handler:
            should_trigger = await handler(alert, price_data)
            
            if should_trigger:
                await self.trigger_alert(alert, price_data)
    
    async def check_price_above(self, alert: Alert, price_data: Dict) -> bool:
        """Check if price is above threshold"""
        current_price = price_data.get('price', 0)
        return current_price >= alert.value
    
    async def check_price_below(self, alert: Alert, price_data: Dict) -> bool:
        """Check if price is below threshold"""
        current_price = price_data.get('price', 0)
        return current_price <= alert.value
    
    async def check_price_change(self, alert: Alert, price_data: Dict) -> bool:
        """Check if price changed by percentage in time window"""
        # Get price from specified time ago
        time_window = timedelta(minutes=int(alert.condition.get('minutes', 60)))
        
        with get_db() as db:
            past_time = datetime.utcnow() - time_window
            past_price = db.query(PriceHistory.price).filter(
                PriceHistory.symbol == alert.symbol,
                PriceHistory.timestamp >= past_time
            ).order_by(PriceHistory.timestamp.asc()).first()
            
            if past_price:
                change_percent = ((price_data['price'] - past_price[0]) / past_price[0]) * 100
                return abs(change_percent) >= alert.value
            
            return False
    
    async def check_volume_spike(self, alert: Alert, price_data: Dict) -> bool:
        """Check for volume spike compared to average"""
        current_volume = price_data.get('volume', 0)
        
        with get_db() as db:
            # Calculate average volume over last 24 hours
            twenty_four_hours_ago = datetime.utcnow() - timedelta(hours=24)
            avg_volume = db.query(db.func.avg(PriceHistory.volume)).filter(
                PriceHistory.symbol == alert.symbol,
                PriceHistory.timestamp >= twenty_four_hours_ago
            ).scalar()
            
            if avg_volume and avg_volume > 0:
                volume_ratio = current_volume / avg_volume
                return volume_ratio >= alert.value  # alert.value is the multiplier threshold
            
            return False
    
    async def check_rsi(self, alert: Alert, price_data: Dict) -> bool:
        """Check RSI conditions"""
        from modules.market_data.indicators import TechnicalIndicators
        
        indicators = TechnicalIndicators()
        rsi_data = await indicators.calculate_rsi(
            await indicators.get_historical_data(alert.symbol, '1h')
        )
        
        if not rsi_data:
            return False
        
        rsi_value = rsi_data.get('rsi', 50)
        
        if alert.alert_type == AlertType.RSI_OVERBOUGHT.value:
            return rsi_value >= alert.value  # Typically 70
        elif alert.alert_type == AlertType.RSI_OVERSOLD.value:
            return rsi_value <= alert.value  # Typically 30
        
        return False
    
    async def trigger_alert(self, alert: Alert, price_data: Dict):
        """Trigger an alert and notify user"""
        # Update alert in database
        with get_db() as db:
            alert.last_triggered = datetime.utcnow()
            alert.trigger_count = (alert.trigger_count or 0) + 1
            
            # Create alert trigger record
            trigger = AlertTrigger(
                alert_id=alert.id,
                triggered_value=price_data['price'],
                triggered_at=datetime.utcnow(),
                metadata=json.dumps(price_data)
            )
            db.add(trigger)
            db.commit()
        
        # Prepare notification message
        message = self.format_alert_message(alert, price_data)
        
        # Send notification via Telegram
        await self.send_telegram_notification(alert.user_id, message)
        
        # Also send to Redis for real-time WebSocket updates
        await redis_client.publish(
            f"alerts:{alert.user_id}",
            {
                'alert_id': alert.id,
                'symbol': alert.symbol,
                'type': alert.alert_type,
                'message': message,
                'price': price_data['price'],
                'timestamp': datetime.utcnow().isoformat()
            }
        )
        
        logger.info(f"Alert triggered: {alert.id} for user {alert.user_id}")
    
    def format_alert_message(self, alert: Alert, price_data: Dict) -> str:
        """Format alert message for Telegram"""
        symbol = alert.symbol
        current_price = price_data['price']
        alert_type = alert.alert_type
        condition_value = alert.value
        
        messages = {
            'price_above': f"🚨 {symbol} is above ${condition_value:,.2f}\nCurrent: ${current_price:,.2f}",
            'price_below': f"🚨 {symbol} is below ${condition_value:,.2f}\nCurrent: ${current_price:,.2f}",
            'price_change': f"📈 {symbol} changed by {condition_value}%\nCurrent: ${current_price:,.2f}",
            'volume_spike': f"📊 {symbol} volume spike! {condition_value}x average\nCurrent: ${current_price:,.2f}",
            'rsi_overbought': f"⚠️ {symbol} RSI overbought ({condition_value}+)\nCurrent: ${current_price:,.2f}",
            'rsi_oversold': f"⚠️ {symbol} RSI oversold ({condition_value}-)\nCurrent: ${current_price:,.2f}",
            'macd_crossover': f"↗️ {symbol} MACD {condition_value} crossover\nCurrent: ${current_price:,.2f}"
        }
        
        return messages.get(alert_type, f"Alert triggered for {symbol}: ${current_price:,.2f}")
    
    async def send_telegram_notification(self, user_id: int, message: str):
        """Send alert notification via Telegram"""
        # Get user's Telegram chat ID
        with get_db() as db:
            from modules.auth.models import User
            user = db.query(User).filter(User.id == user_id).first()
            
            if user and user.telegram_id:
                # In production, use bot instance to send message
                # This is a placeholder - actual implementation depends on your bot setup
                logger.info(f"Would send Telegram alert to {user.telegram_id}: {message}")
                
                # For now, publish to Redis for bot to pick up
                await redis_client.publish(
                    "telegram_notifications",
                    {
                        'chat_id': user.telegram_id,
                        'message': message,
                        'type': 'alert'
                    }
                )
