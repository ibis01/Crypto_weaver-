"""
Trigger Manager for handling multiple triggers
"""
from typing import Dict, List, Any, Optional
from datetime import datetime
import asyncio
from . import TriggerFactory, BaseTrigger, TriggerType


class TriggerManager:
    """Manager for all alert triggers"""
    
    def __init__(self):
        self.triggers: Dict[str, BaseTrigger] = {}
        self.trigger_history: List[Dict] = []
        self.max_history_size = 1000
        
    def add_trigger(self, trigger_id: str, trigger_config: Dict[str, Any]) -> BaseTrigger:
        """Add a new trigger"""
        trigger = TriggerFactory.create_trigger(trigger_config)
        self.triggers[trigger_id] = trigger
        return trigger
    
    def remove_trigger(self, trigger_id: str) -> bool:
        """Remove a trigger"""
        if trigger_id in self.triggers:
            del self.triggers[trigger_id]
            return True
        return False
    
    def check_triggers(self, market_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Check all triggers against market data"""
        triggered = []
        
        for trigger_id, trigger in self.triggers.items():
            try:
                if trigger.check(market_data):
                    trigger_info = {
                        'trigger_id': trigger_id,
                        'trigger_type': trigger.trigger_type.value,
                        'params': trigger.params,
                        'timestamp': datetime.utcnow().isoformat(),
                        'market_data_snapshot': {
                            'price': market_data.get('price'),
                            'volume': market_data.get('volume'),
                            'symbol': market_data.get('symbol', 'unknown')
                        }
                    }
                    triggered.append(trigger_info)
                    
                    # Add to history
                    self.trigger_history.append(trigger_info)
                    if len(self.trigger_history) > self.max_history_size:
                        self.trigger_history = self.trigger_history[-self.max_history_size:]
                    
            except Exception as e:
                print(f"Error checking trigger {trigger_id}: {e}")
                continue
        
        return triggered
    
    def get_trigger_stats(self) -> Dict[str, Any]:
        """Get statistics about triggers"""
        stats = {
            'total_triggers': len(self.triggers),
            'trigger_counts': {},
            'recent_triggers': self.trigger_history[-10:] if self.trigger_history else [],
            'trigger_types': {}
        }
        
        for trigger_id, trigger in self.triggers.items():
            trigger_type = trigger.trigger_type.value
            stats['trigger_counts'][trigger_id] = trigger.trigger_count
            
            if trigger_type not in stats['trigger_types']:
                stats['trigger_types'][trigger_type] = 0
            stats['trigger_types'][trigger_type] += 1
        
        return stats
    
    def reset_trigger(self, trigger_id: str) -> bool:
        """Reset trigger state"""
        if trigger_id in self.triggers:
            self.triggers[trigger_id].reset()
            return True
        return False
    
    def get_supported_trigger_types(self) -> List[Dict[str, Any]]:
        """Get list of all supported trigger types with descriptions"""
        return [
            {
                'type': trigger_type.value,
                'name': trigger_type.name.replace('_', ' ').title(),
                'description': self._get_trigger_description(trigger_type),
                'params_schema': self._get_params_schema(trigger_type)
            }
            for trigger_type in TriggerType
        ]
    
    def _get_trigger_description(self, trigger_type: TriggerType) -> str:
        """Get description for trigger type"""
        descriptions = {
            TriggerType.PRICE_ABOVE: "Trigger when price goes above threshold",
            TriggerType.PRICE_BELOW: "Trigger when price goes below threshold",
            TriggerType.VOLUME_SPIKE: "Trigger when volume spikes above average",
            TriggerType.RSI_OVERBOUGHT: "Trigger when RSI enters overbought territory (>70)",
            TriggerType.RSI_OVERSOLD: "Trigger when RSI enters oversold territory (<30)",
            TriggerType.MACD_CROSSOVER: "Trigger on MACD line crossover",
            TriggerType.BOLLINGER_BREAKOUT: "Trigger when price breaks Bollinger Bands",
            TriggerType.CUSTOM_DSL: "Custom trigger using DSL expression language",
            TriggerType.COMPOSITE_TRIGGER: "Combine multiple triggers with logical operators",
        }
        return descriptions.get(trigger_type, "No description available")
    
    def _get_params_schema(self, trigger_type: TriggerType) -> Dict[str, Any]:
        """Get parameter schema for trigger type"""
        schemas = {
            TriggerType.PRICE_ABOVE: {
                'threshold': {'type': 'number', 'required': True, 'description': 'Price threshold'}
            },
            TriggerType.VOLUME_SPIKE: {
                'multiplier': {'type': 'number', 'required': True, 'default': 3.0, 'description': 'Volume multiplier'},
                'lookback_period': {'type': 'integer', 'required': True, 'default': 20, 'description': 'Lookback period for average'}
            },
            TriggerType.RSI_OVERBOUGHT: {
                'threshold': {'type': 'number', 'required': True, 'default': 70, 'description': 'RSI threshold'}
            },
            TriggerType.CUSTOM_DSL: {
                'dsl_expression': {'type': 'string', 'required': True, 'description': 'DSL expression to evaluate'}
            }
        }
        return schemas.get(trigger_type, {})
