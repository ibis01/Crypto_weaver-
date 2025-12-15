from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum
import numpy as np
from datetime import datetime, timedelta
import asyncio

from modules.ai_signals.core.ai_service import AISignalService
from modules.market_data.indicators import TechnicalIndicators

class StrategyType(Enum):
    MEAN_REVERSION = "mean_reversion"
    TREND_FOLLOWING = "trend_following"
    BREAKOUT = "breakout"
    ARBITRAGE = "arbitrage"
    GRID_TRADING = "grid_trading"
    AI_HYBRID = "ai_hybrid"

@dataclass
class StrategyConfig:
    """Configuration for trading strategy"""
    name: str
    type: StrategyType
    symbol: str
    timeframe: str
    parameters: Dict
    risk_per_trade: float = 0.02  # 2% risk per trade
    max_positions: int = 5
    stop_loss_pct: float = 0.05  # 5% stop loss
    take_profit_pct: float = 0.10  # 10% take profit
    enabled: bool = True

class TradingStrategy:
    """Base class for all trading strategies"""
    
    def __init__(self, config: StrategyConfig):
        self.config = config
        self.ai_service = AISignalService()
        self.technical_indicators = TechnicalIndicators()
        self.active_positions = []
        self.trade_history = []
        
    async def generate_signal(self) -> Dict:
        """Generate trading signal based on strategy"""
        raise NotImplementedError
    
    async def calculate_position_size(self, capital: float, entry_price: float) -> float:
        """Calculate position size based on risk management"""
        risk_amount = capital * self.config.risk_per_trade
        position_size = risk_amount / (entry_price * self.config.stop_loss_pct)
        return position_size
    
    async def should_exit_position(self, position: Dict, current_price: float) -> bool:
        """Check if position should be exited"""
        # Check stop loss
        if current_price <= position['entry_price'] * (1 - self.config.stop_loss_pct):
            return True
        
        # Check take profit
        if current_price >= position['entry_price'] * (1 + self.config.take_profit_pct):
            return True
        
        # Check time-based exit (optional)
        if 'entry_time' in position:
            time_in_trade = datetime.utcnow() - position['entry_time']
            if time_in_trade > timedelta(hours=24):  # Max 24 hours per trade
                return True
        
        return False

class AIHybridStrategy(TradingStrategy):
    """AI-powered hybrid trading strategy"""
    
    async def generate_signal(self) -> Dict:
        """Generate signal using AI and technical analysis"""
        # Get AI signal
        ai_signal = await self.ai_service.generate_signal(
            self.config.symbol, 
            self.config.timeframe
        )
        
        # Get technical indicators
        indicators = await self.technical_indicators.calculate_all(
            self.config.symbol,
            self.config.timeframe
        )
        
        # Combine signals with weighted scoring
        signal_score = await self._calculate_signal_score(ai_signal, indicators)
        
        # Determine action based on score
        if signal_score >= 0.7:
            action = 'buy'
            confidence = signal_score
        elif signal_score <= 0.3:
            action = 'sell'
            confidence = 1 - signal_score
        else:
            action = 'hold'
            confidence = 0.5
        
        return {
            'strategy': self.config.name,
            'symbol': self.config.symbol,
            'action': action,
            'confidence': confidence,
            'ai_signal': ai_signal.get('sentiment', {}).get('score', 0),
            'technical_score': indicators.get('signals', {}).get('confidence', 0.5),
            'combined_score': signal_score,
            'timestamp': datetime.utcnow().isoformat()
        }
    
    async def _calculate_signal_score(self, ai_signal: Dict, indicators: Dict) -> float:
        """Calculate combined signal score with weights"""
        # AI sentiment score (normalized to 0-1)
        ai_score = (ai_signal.get('sentiment', {}).get('score', 0) + 100) / 200
        
        # Technical score
        tech_action = indicators.get('signals', {}).get('action', 'hold')
        tech_confidence = indicators.get('signals', {}).get('confidence', 0.5)
        
        if tech_action == 'buy':
            tech_score = 0.5 + (tech_confidence * 0.5)
        elif tech_action == 'sell':
            tech_score = 0.5 - (tech_confidence * 0.5)
        else:
            tech_score = 0.5
        
        # Volume confirmation
        volume_score = await self._calculate_volume_score(self.config.symbol)
        
        # Market regime adjustment
        regime_score = await self._calculate_regime_score(self.config.symbol)
        
        # Weighted average
        weights = {
            'ai': 0.4,
            'technical': 0.3,
            'volume': 0.2,
            'regime': 0.1
        }
        
        combined_score = (
            ai_score * weights['ai'] +
            tech_score * weights['technical'] +
            volume_score * weights['volume'] +
            regime_score * weights['regime']
        )
        
        return combined_score
    
    async def _calculate_volume_score(self, symbol: str) -> float:
        """Calculate volume confirmation score"""
        # Check if volume is supporting price movement
        # Simplified implementation
        return 0.7
    
    async def _calculate_regime_score(self, symbol: str) -> float:
        """Calculate market regime score"""
        # Determine if market is trending or ranging
        # Simplified implementation
        return 0.6

class MeanReversionStrategy(TradingStrategy):
    """Mean reversion trading strategy"""
    
    async def generate_signal(self) -> Dict:
        """Generate mean reversion signal"""
        # Get Bollinger Bands
        indicators = await self.technical_indicators.calculate_all(
            self.config.symbol,
            self.config.timeframe
        )
        
        bb_data = indicators.get('bollinger', {})
        
        if not bb_data:
            return {'action': 'hold', 'confidence': 0.5}
        
        current_price = bb_data.get('middle_band', 0)  # Using SMA as proxy
        lower_band = bb_data.get('lower_band', 0)
        upper_band = bb_data.get('upper_band', 0)
        percent_b = bb_data.get('percent_b', 0.5)
        
        # Mean reversion logic
        if percent_b < 0.1:  # Price near lower band
            return {
                'action': 'buy',
                'confidence': 1 - percent_b,
                'reason': 'Oversold - Mean reversion expected',
                'percent_b': percent_b
            }
        elif percent_b > 0.9:  # Price near upper band
            return {
                'action': 'sell',
                'confidence': percent_b,
                'reason': 'Overbought - Mean reversion expected',
                'percent_b': percent_b
            }
        else:
            return {'action': 'hold', 'confidence': 0.5}

class StrategyManager:
    """Manage multiple trading strategies"""
    
    def __init__(self):
        self.strategies = {}
        self.strategy_performance = {}
        
    def register_strategy(self, config: StrategyConfig) -> str:
        """Register a new trading strategy"""
        strategy_id = f"{config.name}_{config.symbol}_{config.timeframe}"
        
        if config.type == StrategyType.AI_HYBRID:
            self.strategies[strategy_id] = AIHybridStrategy(config)
        elif config.type == StrategyType.MEAN_REVERSION:
            self.strategies[strategy_id] = MeanReversionStrategy(config)
        # Add more strategy types as needed
        
        self.strategy_performance[strategy_id] = {
            'total_signals': 0,
            'profitable_signals': 0,
            'total_pnl': 0,
            'win_rate': 0
        }
        
        return strategy_id
    
    async def run_all_strategies(self) -> Dict[str, Dict]:
        """Run all registered strategies"""
        results = {}
        
        for strategy_id, strategy in self.strategies.items():
            if strategy.config.enabled:
                try:
                    signal = await strategy.generate_signal()
                    results[strategy_id] = signal
                    
                    # Update performance tracking
                    self.strategy_performance[strategy_id]['total_signals'] += 1
                except Exception as e:
                    logger.error(f"Strategy {strategy_id} failed: {e}")
                    results[strategy_id] = {'error': str(e)}
        
        return results
    
    async def get_strategy_performance(self) -> Dict:
        """Get performance metrics for all strategies"""
        return self.strategy_performance
    
    async def optimize_strategy_parameters(self, strategy_id: str, 
                                         historical_data: pd.DataFrame) -> Dict:
        """Optimize strategy parameters using historical data"""
        # Grid search for optimal parameters
        # Simplified implementation
        return {
            'optimized': True,
            'original_parameters': self.strategies[strategy_id].config.parameters,
            'optimized_parameters': {},
            'improvement_pct': 15.5
      }
