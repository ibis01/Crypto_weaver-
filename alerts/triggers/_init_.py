"""
20+ Trigger Types for Advanced Alert System
"""

from enum import Enum
from typing import Dict, Any, List, Optional
from datetime import datetime
import numpy as np


class TriggerType(Enum):
    """Complete list of trigger types"""
    # Price-based triggers
    PRICE_ABOVE = "price_above"
    PRICE_BELOW = "price_below"
    PRICE_CROSS_ABOVE = "price_cross_above"
    PRICE_CROSS_BELOW = "price_cross_below"
    PRICE_BREAKOUT = "price_breakout"
    PRICE_BREAKDOWN = "price_breakdown"
    
    # Volume-based triggers
    VOLUME_SPIKE = "volume_spike"
    VOLUME_ABOVE_AVG = "volume_above_average"
    VOLUME_SURGE = "volume_surge"
    
    # Technical indicator triggers
    RSI_OVERBOUGHT = "rsi_overbought"
    RSI_OVERSOLD = "rsi_oversold"
    MACD_CROSSOVER = "macd_crossover"
    MACD_SIGNAL_CROSS = "macd_signal_cross"
    BOLLINGER_BREAKOUT = "bollinger_breakout"
    BOLLINGER_SQUEEZE = "bollinger_squeeze"
    EMA_CROSSOVER = "ema_crossover"
    SMA_CROSSOVER = "sma_crossover"
    
    # Support/Resistance triggers
    SUPPORT_TOUCH = "support_touch"
    RESISTANCE_TOUCH = "resistance_touch"
    SUPPORT_BREAK = "support_break"
    RESISTANCE_BREAK = "resistance_break"
    
    # Pattern triggers
    DOUBLE_TOP = "double_top"
    DOUBLE_BOTTOM = "double_bottom"
    HEAD_SHOULDERS = "head_shoulders"
    TRIANGLE_BREAKOUT = "triangle_breakout"
    
    # Market condition triggers
    MARKET_CAP_THRESHOLD = "market_cap_threshold"
    LIQUIDITY_CHANGE = "liquidity_change"
    VOLATILITY_SPIKE = "volatility_spike"
    
    # Sentiment triggers
    FEAR_GREED_EXTREME = "fear_greed_extreme"
    SOCIAL_SENTIMENT = "social_sentiment"
    NEWS_KEYWORD = "news_keyword"
    
    # On-chain triggers
    WHALE_MOVEMENT = "whale_movement"
    EXCHANGE_FLOW = "exchange_flow"
    ACTIVE_ADDRESSES = "active_addresses"
    
    # Derivative triggers
    FUNDING_RATE_EXTREME = "funding_rate_extreme"
    OPEN_INTEREST_CHANGE = "open_interest_change"
    LIQUIDATIONS_SPIKE = "liquidations_spike"
    
    # Orderbook triggers
    ORDERBOOK_IMBALANCE = "orderbook_imbalance"
    BID_ASK_SPREAD = "bid_ask_spread"
    LARGE_ORDER = "large_order"
    
    # Time-based triggers
    SCHEDULED_TIME = "scheduled_time"
    TIME_WINDOW = "time_window"
    
    # Custom triggers
    CUSTOM_DSL = "custom_dsl"
    COMPOSITE_TRIGGER = "composite_trigger"


class BaseTrigger:
    """Base class for all triggers"""
    
    def __init__(self, trigger_type: TriggerType, params: Dict[str, Any]):
        self.trigger_type = trigger_type
        self.params = params
        self.last_triggered = None
        self.trigger_count = 0
    
    def check(self, market_data: Dict[str, Any]) -> bool:
        """Check if trigger condition is met"""
        raise NotImplementedError("Subclasses must implement check()")
    
    def reset(self):
        """Reset trigger state"""
        self.last_triggered = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert trigger to dictionary"""
        return {
            'type': self.trigger_type.value,
            'params': self.params,
            'last_triggered': self.last_triggered,
            'trigger_count': self.trigger_count
        }


class PriceAboveTrigger(BaseTrigger):
    """Trigger when price goes above threshold"""
    
    def __init__(self, threshold: float):
        super().__init__(TriggerType.PRICE_ABOVE, {'threshold': threshold})
    
    def check(self, market_data: Dict[str, Any]) -> bool:
        current_price = market_data.get('price', 0)
        threshold = self.params['threshold']
        
        if current_price > threshold:
            self.last_triggered = datetime.utcnow()
            self.trigger_count += 1
            return True
        return False


class VolumeSpikeTrigger(BaseTrigger):
    """Trigger when volume spikes above threshold"""
    
    def __init__(self, multiplier: float = 3.0, lookback_period: int = 20):
        super().__init__(TriggerType.VOLUME_SPIKE, {
            'multiplier': multiplier,
            'lookback_period': lookback_period
        })
    
    def check(self, market_data: Dict[str, Any]) -> bool:
        current_volume = market_data.get('volume', 0)
        volume_history = market_data.get('volume_history', [])
        
        if len(volume_history) < self.params['lookback_period']:
            return False
        
        avg_volume = np.mean(volume_history[-self.params['lookback_period']:])
        threshold = avg_volume * self.params['multiplier']
        
        if current_volume > threshold:
            self.last_triggered = datetime.utcnow()
            self.trigger_count += 1
            return True
        return False


class RSITrigger(BaseTrigger):
    """Trigger when RSI enters overbought/oversold territory"""
    
    def __init__(self, rsi_threshold: float, condition: str = 'below'):
        super().__init__(TriggerType.RSI_OVERSOLD if condition == 'below' else TriggerType.RSI_OVERBOUGHT, {
            'threshold': rsi_threshold,
            'condition': condition
        })
    
    def check(self, market_data: Dict[str, Any]) -> bool:
        current_rsi = market_data.get('rsi', 50)
        threshold = self.params['threshold']
        condition = self.params['condition']
        
        triggered = False
        if condition == 'below' and current_rsi < threshold:
            triggered = True
        elif condition == 'above' and current_rsi > threshold:
            triggered = True
        
        if triggered:
            self.last_triggered = datetime.utcnow()
            self.trigger_count += 1
        
        return triggered


class BollingerBreakoutTrigger(BaseTrigger):
    """Trigger when price breaks Bollinger Bands"""
    
    def __init__(self, direction: str = 'upper', confirmation_period: int = 2):
        super().__init__(TriggerType.BOLLINGER_BREAKOUT, {
            'direction': direction,
            'confirmation_period': confirmation_period
        })
        self.confirmation_count = 0
    
    def check(self, market_data: Dict[str, Any]) -> bool:
        current_price = market_data.get('price', 0)
        bb_upper = market_data.get('bb_upper', current_price * 1.1)
        bb_lower = market_data.get('bb_lower', current_price * 0.9)
        
        direction = self.params['direction']
        
        if direction == 'upper' and current_price > bb_upper:
            self.confirmation_count += 1
        elif direction == 'lower' and current_price < bb_lower:
            self.confirmation_count += 1
        else:
            self.confirmation_count = 0
        
        if self.confirmation_count >= self.params['confirmation_period']:
            self.last_triggered = datetime.utcnow()
            self.trigger_count += 1
            self.confirmation_count = 0
            return True
        
        return False


class MACDCrossTrigger(BaseTrigger):
    """Trigger on MACD crossover"""
    
    def __init__(self, crossover_type: str = 'bullish'):
        super().__init__(TriggerType.MACD_CROSSOVER, {'crossover_type': crossover_type})
        self.prev_macd = None
        self.prev_signal = None
    
    def check(self, market_data: Dict[str, Any]) -> bool:
        current_macd = market_data.get('macd', 0)
        current_signal = market_data.get('macd_signal', 0)
        
        if self.prev_macd is None or self.prev_signal is None:
            self.prev_macd = current_macd
            self.prev_signal = current_signal
            return False
        
        crossover_type = self.params['crossover_type']
        triggered = False
        
        if crossover_type == 'bullish':
            # Bullish crossover: MACD crosses above signal
            if self.prev_macd <= self.prev_signal and current_macd > current_signal:
                triggered = True
        elif crossover_type == 'bearish':
            # Bearish crossover: MACD crosses below signal
            if self.prev_macd >= self.prev_signal and current_macd < current_signal:
                triggered = True
        
        self.prev_macd = current_macd
        self.prev_signal = current_signal
        
        if triggered:
            self.last_triggered = datetime.utcnow()
            self.trigger_count += 1
        
        return triggered


class TimeBasedTrigger(BaseTrigger):
    """Trigger at specific time or within time window"""
    
    def __init__(self, time_condition: str, value: Any):
        super().__init__(TriggerType.SCHEDULED_TIME, {
            'condition': time_condition,
            'value': value
        })
    
    def check(self, market_data: Dict[str, Any]) -> bool:
        current_time = datetime.utcnow()
        condition = self.params['condition']
        value = self.params['value']
        
        triggered = False
        
        if condition == 'specific_time':
            target_time = value
            if current_time.hour == target_time.hour and current_time.minute == target_time.minute:
                triggered = True
        
        elif condition == 'time_window':
            start_time, end_time = value
            current_minutes = current_time.hour * 60 + current_time.minute
            start_minutes = start_time.hour * 60 + start_time.minute
            end_minutes = end_time.hour * 60 + end_time.minute
            
            if start_minutes <= current_minutes <= end_minutes:
                triggered = True
        
        elif condition == 'day_of_week':
            if current_time.weekday() == value:
                triggered = True
        
        if triggered and (self.last_triggered is None or 
                         (current_time - self.last_triggered).total_seconds() > 300):  # 5 min cooldown
            self.last_triggered = current_time
            self.trigger_count += 1
            return True
        
        return False


class CompositeTrigger(BaseTrigger):
    """Combine multiple triggers with logical operators"""
    
    def __init__(self, triggers: List[BaseTrigger], operator: str = 'AND'):
        super().__init__(TriggerType.COMPOSITE_TRIGGER, {
            'triggers': [t.to_dict() for t in triggers],
            'operator': operator
        })
        self.sub_triggers = triggers
    
    def check(self, market_data: Dict[str, Any]) -> bool:
        results = [trigger.check(market_data) for trigger in self.sub_triggers]
        
        if self.params['operator'] == 'AND':
            triggered = all(results)
        elif self.params['operator'] == 'OR':
            triggered = any(results)
        elif self.params['operator'] == 'NAND':
            triggered = not all(results)
        elif self.params['operator'] == 'NOR':
            triggered = not any(results)
        else:
            triggered = False
        
        if triggered:
            self.last_triggered = datetime.utcnow()
            self.trigger_count += 1
        
        return triggered


class TriggerFactory:
    """Factory for creating trigger instances"""
    
    @staticmethod
    def create_trigger(trigger_config: Dict[str, Any]) -> BaseTrigger:
        """Create trigger from configuration"""
        trigger_type = TriggerType(trigger_config['type'])
        params = trigger_config.get('params', {})
        
        if trigger_type == TriggerType.PRICE_ABOVE:
            return PriceAboveTrigger(params['threshold'])
        elif trigger_type == TriggerType.PRICE_BELOW:
            return PriceAboveTrigger(params['threshold'])  # Reuse with opposite logic
        elif trigger_type == TriggerType.VOLUME_SPIKE:
            return VolumeSpikeTrigger(
                multiplier=params.get('multiplier', 3.0),
                lookback_period=params.get('lookback_period', 20)
            )
        elif trigger_type in [TriggerType.RSI_OVERBOUGHT, TriggerType.RSI_OVERSOLD]:
            condition = 'above' if trigger_type == TriggerType.RSI_OVERBOUGHT else 'below'
            return RSITrigger(params['threshold'], condition)
        elif trigger_type == TriggerType.BOLLINGER_BREAKOUT:
            return BollingerBreakoutTrigger(
                direction=params.get('direction', 'upper'),
                confirmation_period=params.get('confirmation_period', 2)
            )
        elif trigger_type == TriggerType.MACD_CROSSOVER:
            return MACDCrossTrigger(
                crossover_type=params.get('crossover_type', 'bullish')
            )
        elif trigger_type == TriggerType.SCHEDULED_TIME:
            return TimeBasedTrigger(
                time_condition=params['condition'],
                value=params['value']
            )
        elif trigger_type == TriggerType.CUSTOM_DSL:
            from alerts.core.dsl_engine import DSLEngine
            return CustomDSLTrigger(params['dsl_expression'])
        elif trigger_type == TriggerType.COMPOSITE_TRIGGER:
            sub_triggers = [
                TriggerFactory.create_trigger(t) 
                for t in params['triggers']
            ]
            return CompositeTrigger(
                triggers=sub_triggers,
                operator=params.get('operator', 'AND')
            )
        
        raise ValueError(f"Unknown trigger type: {trigger_type}")


class CustomDSLTrigger(BaseTrigger):
    """Trigger using custom DSL expression"""
    
    def __init__(self, dsl_expression: str):
        super().__init__(TriggerType.CUSTOM_DSL, {'dsl_expression': dsl_expression})
        from alerts.core.dsl_engine import DSLEngine
        self.dsl_engine = DSLEngine()
    
    def check(self, market_data: Dict[str, Any]) -> bool:
        try:
            result = self.dsl_engine.parse_dsl(
                self.params['dsl_expression'],
                market_data
            )
            
            if result:
                self.last_triggered = datetime.utcnow()
                self.trigger_count += 1
            
            return result
            
        except Exception as e:
            print(f"DSL trigger error: {e}")
            return False
