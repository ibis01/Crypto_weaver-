"""
Alert Storage Repository
"""
import json
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import redis
from ..models import Alert, AlertHistory, AlertGroup


class AlertRepository:
    """Repository for storing and retrieving alerts"""
    
    def __init__(self, redis_client=None):
        self.redis = redis_client
        self.alerts: Dict[str, Alert] = {}
        self.alert_history: List[AlertHistory] = []
        self.alert_groups: Dict[str, AlertGroup] = {}
        
        # In-memory index
        self.user_alerts: Dict[str, List[str]] = {}
        self.symbol_alerts: Dict[str, List[str]] = {}
    
    def save_alert(self, alert: Alert) -> str:
        """Save alert to storage"""
        self.alerts[alert.id] = alert
        
        # Update indexes
        if alert.user_id not in self.user_alerts:
            self.user_alerts[alert.user_id] = []
        if alert.id not in self.user_alerts[alert.user_id]:
            self.user_alerts[alert.user_id].append(alert.id)
        
        if alert.symbol not in self.symbol_alerts:
            self.symbol_alerts[alert.symbol] = []
        if alert.id not in self.symbol_alerts[alert.symbol]:
            self.symbol_alerts[alert.symbol].append(alert.id)
        
        # Save to Redis if available
        if self.redis:
            key = f"alert:{alert.id}"
            self.redis.setex(key, 86400, json.dumps(alert.dict()))  # 24h TTL
        
        return alert.id
    
    def get_alert(self, alert_id: str) -> Optional[Alert]:
        """Get alert by ID"""
        # Try Redis first
        if self.redis:
            key = f"alert:{alert_id}"
            data = self.redis.get(key)
            if data:
                alert_dict = json.loads(data)
                return Alert(**alert_dict)
        
        # Fall back to memory
        return self.alerts.get(alert_id)
    
    def get_user_alerts(self, user_id: str, active_only: bool = True) -> List[Alert]:
        """Get all alerts for a user"""
        alert_ids = self.user_alerts.get(user_id, [])
        alerts = [self.get_alert(alert_id) for alert_id in alert_ids]
        alerts = [a for a in alerts if a is not None]
        
        if active_only:
            alerts = [a for a in alerts if a.is_valid()]
        
        return alerts
    
    def get_symbol_alerts(self, symbol: str, active_only: bool = True) -> List[Alert]:
        """Get all alerts for a symbol"""
        alert_ids = self.symbol_alerts.get(symbol, [])
        alerts = [self.get_alert(alert_id) for alert_id in alert_ids]
        alerts = [a for a in alerts if a is not None]
        
        if active_only:
            alerts = [a for a in alerts if a.is_valid()]
        
        return alerts
    
    def delete_alert(self, alert_id: str) -> bool:
        """Delete alert by ID"""
        alert = self.get_alert(alert_id)
        if not alert:
            return False
        
        # Remove from memory
        if alert_id in self.alerts:
            del self.alerts[alert_id]
        
        # Remove from indexes
        if alert.user_id in self.user_alerts and alert_id in self.user_alerts[alert.user_id]:
            self.user_alerts[alert.user_id].remove(alert_id)
        
        if alert.symbol in self.symbol_alerts and alert_id in self.symbol_alerts[alert.symbol]:
            self.symbol_alerts[alert.symbol].remove(alert_id)
        
        # Remove from Redis
        if self.redis:
            key = f"alert:{alert_id}"
            self.redis.delete(key)
        
        return True
    
    def update_alert_status(self, alert_id: str, status: str) -> bool:
        """Update alert status"""
        alert = self.get_alert(alert_id)
        if not alert:
            return False
        
        alert.status = status
        alert.updated_at = datetime.utcnow()
        self.save_alert(alert)
        return True
    
    def record_trigger(self, alert_id: str, market_data: Dict[str, Any], 
                      actions_executed: List[str] = None) -> AlertHistory:
        """Record alert trigger in history"""
        alert = self.get_alert(alert_id)
        if not alert:
            raise ValueError(f"Alert {alert_id} not found")
        
        # Update alert
        alert.last_triggered = datetime.utcnow()
        alert.trigger_count += 1
        self.save_alert(alert)
        
        # Create history record
        history = AlertHistory(
            alert_id=alert_id,
            market_data=market_data,
            trigger_config=alert.trigger_config,
            dsl_expression=alert.dsl_expression,
            actions_executed=actions_executed or [],
        )
        
        self.alert_history.append(history)
        
        # Keep only recent history
        if len(self.alert_history) > 1000:
            self.alert_history = self.alert_history[-1000:]
        
        return history
    
    def get_recent_triggers(self, alert_id: str, limit: int = 10) -> List[AlertHistory]:
        """Get recent triggers for an alert"""
        triggers = [h for h in self.alert_history if h.alert_id == alert_id]
        triggers.sort(key=lambda x: x.trigger_timestamp, reverse=True)
        return triggers[:limit]
    
    def get_daily_stats(self, user_id: str, date: datetime = None) -> Dict[str, Any]:
        """Get daily alert statistics for a user"""
        if date is None:
            date = datetime.utcnow()
        
        start_date = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = start_date + timedelta(days=1)
        
        user_alert_ids = self.user_alerts.get(user_id, [])
        
        triggers_today = [
            h for h in self.alert_history 
            if h.alert_id in user_alert_ids and 
            start_date <= h.trigger_timestamp < end_date
        ]
        
        return {
            'date': start_date.date().isoformat(),
            'total_triggers': len(triggers_today),
            'successful_triggers': len([t for t in triggers_today if t.success]),
            'failed_triggers': len([t for t in triggers_today if not t.success]),
            'unique_alerts_triggered': len(set(t.alert_id for t in triggers_today)),
            'most_triggered_alerts': self._get_most_triggered(triggers_today),
        }
    
    def _get_most_triggered(self, triggers: List[AlertHistory]) -> List[Dict[str, Any]]:
        """Get most frequently triggered alerts"""
        from collections import Counter
        alert_counts = Counter([t.alert_id for t in triggers])
        
        result = []
        for alert_id, count in alert_counts.most_common(5):
            alert = self.get_alert(alert_id)
            if alert:
                result.append({
                    'alert_id': alert_id,
                    'alert_name': alert.name,
                    'trigger_count': count
                })
        
        return result
