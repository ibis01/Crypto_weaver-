"""
Alert Data Models
"""
from datetime import datetime
from typing import Dict, Any, List, Optional
from enum import Enum
from pydantic import BaseModel, Field, validator
import uuid


class AlertStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    TRIGGERED = "triggered"
    EXPIRED = "expired"
    DISABLED = "disabled"


class AlertPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class NotificationChannel(str, Enum):
    EMAIL = "email"
    SMS = "sms"
    WEBHOOK = "webhook"
    DISCORD = "discord"
    TELEGRAM = "telegram"
    SLACK = "slack"
    PUSH = "push"
    IN_APP = "in_app"


class AlertAction(str, Enum):
    NOTIFY_ONLY = "notify_only"
    PLACE_ORDER = "place_order"
    UPDATE_STRATEGY = "update_strategy"
    EXECUTE_SCRIPT = "execute_script"
    SEND_WEBHOOK = "send_webhook"


class Alert(BaseModel):
    """Main Alert Model"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    user_id: str
    symbol: str  # Trading pair, e.g., "BTC/USDT"
    
    # Trigger configuration
    trigger_type: str
    trigger_config: Dict[str, Any]
    
    # DSL expression (for custom triggers)
    dsl_expression: Optional[str] = None
    
    # Conditions
    conditions: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Actions
    actions: List[AlertAction] = Field(default_factory=lambda: [AlertAction.NOTIFY_ONLY])
    action_params: Dict[str, Any] = Field(default_factory=dict)
    
    # Notification settings
    notification_channels: List[NotificationChannel] = Field(default_factory=list)
    notification_recipients: List[str] = Field(default_factory=list)
    webhook_url: Optional[str] = None
    
    # Automation settings
    auto_trade: bool = False
    trade_strategy: Optional[str] = None
    position_size: Optional[float] = None  # Percentage of portfolio
    stop_loss: Optional[float] = None  # Percentage
    take_profit: Optional[float] = None  # Percentage
    
    # Risk management
    max_daily_triggers: int = 10
    cooldown_minutes: int = 5
    risk_score: Optional[float] = None
    
    # Status
    status: AlertStatus = AlertStatus.ACTIVE
    priority: AlertPriority = AlertPriority.MEDIUM
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_triggered: Optional[datetime] = None
    trigger_count: int = 0
    
    # Validity
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    is_recurring: bool = False
    recurrence_pattern: Optional[str] = None  # cron expression
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
    
    @validator('trigger_config')
    def validate_trigger_config(cls, v, values):
        """Validate trigger configuration"""
        trigger_type = values.get('trigger_type')
        
        # Add validation logic based on trigger type
        if trigger_type == 'price_above' and 'threshold' not in v:
            raise ValueError('Price above trigger requires threshold')
        
        return v
    
    def is_valid(self) -> bool:
        """Check if alert is currently valid"""
        now = datetime.utcnow()
        
        if self.status != AlertStatus.ACTIVE:
            return False
        
        if self.valid_from and now < self.valid_from:
            return False
        
        if self.valid_until and now > self.valid_until:
            return False
        
        if self.trigger_count >= self.max_daily_triggers:
            return False
        
        if self.last_triggered:
            cooldown_end = self.last_triggered.replace(
                minute=self.last_triggered.minute + self.cooldown_minutes
            )
            if now < cooldown_end:
                return False
        
        return True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert alert to dictionary"""
        return self.dict()


class AlertHistory(BaseModel):
    """Alert Trigger History"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    alert_id: str
    trigger_timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # Trigger context
    market_data: Dict[str, Any]
    trigger_config: Dict[str, Any]
    dsl_expression: Optional[str] = None
    
    # Actions taken
    actions_executed: List[str] = Field(default_factory=list)
    action_results: Dict[str, Any] = Field(default_factory=dict)
    
    # Status
    success: bool = True
    error_message: Optional[str] = None
    
    # Metadata
    processing_time_ms: Optional[float] = None


class AlertGroup(BaseModel):
    """Group of related alerts"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: Optional[str] = None
    alert_ids: List[str] = Field(default_factory=list)
    user_id: str
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Group settings
    group_conditions: Optional[Dict[str, Any]] = None
    group_actions: List[str] = Field(default_factory=list)
