
import numpy as np
import pandas as pd
import pandas_ta as ta
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import logging

from core.database import get_db
from modules.market_data.models import PriceHistory

logger = logging.getLogger(__name__)

class TechnicalIndicators:
    """Calculate technical indicators for trading signals"""
    
    def __init__(self):
        self.indicators = {
            'sma': self.calculate_sma,
            'ema': self.calculate_ema,
            'rsi': self.calculate_rsi,
            'macd': self.calculate_macd,
            'bollinger': self.calculate_bollinger_bands,
            'stochastic': self.calculate_stochastic,
            'atr': self.calculate_atr,
            'obv': self.calculate_obv,
            'ichimoku': self.calculate_ichimoku,
            'vwap': self.calculate_vwap
        }
    
    async def calculate_all(self, symbol: str, period: str = '1h') -> Dict:
        """Calculate all indicators for a symbol"""
        # Get historical data
        df = await self.get_historical_data(symbol, period)
        
        if df.empty or len(df) < 50:
            return {}
        
        results = {}
        
        for name, func in self.indicators.items():
            try:
                results[name] = await func(df)
            except Exception as e:
                logger.error(f"Error calculating {name} for {symbol}: {e}")
                results[name] = None
        
        # Generate trading signals
        results['signals'] = await self.generate_signals(results)
        
        return results
    
    async def get_historical_data(self, symbol: str, period: str) -> pd.DataFrame:
        """Get historical price data from database"""
        with get_db() as db:
            # Determine time range based on period
            if period == '1m':
                hours = 24
            elif period == '5m':
                hours = 72
            elif period == '1h':
                hours = 720  # 30 days
            elif period == '1d':
                hours = 8760  # 1 year
            else:
                hours = 720
            
            start_time = datetime.utcnow() - timedelta(hours=hours)
            
            # Query price history
            prices = db.query(
                PriceHistory.timestamp,
                PriceHistory.price,
                PriceHistory.volume,
                PriceHistory.high,
                PriceHistory.low
            ).filter(
                PriceHistory.symbol == symbol,
                PriceHistory.timestamp >= start_time
            ).order_by(PriceHistory.timestamp.asc()).all()
            
            if not prices:
                return pd.DataFrame()
            
            # Convert to DataFrame
            df = pd.DataFrame(prices, columns=['timestamp', 'close', 'volume', 'high', 'low'])
            df.set_index('timestamp', inplace=True)
            
            # Resample based on period
            if period == '1m':
                df = df.resample('1min').agg({
                    'close': 'last',
                    'volume': 'sum',
                    'high': 'max',
                    'low': 'min'
                })
            elif period == '5m':
                df = df.resample('5min').agg({
                    'close': 'last',
                    'volume': 'sum',
                    'high': 'max',
                    'low': 'min'
                })
            elif period == '1h':
                df = df.resample('1H').agg({
                    'close': 'last',
                    'volume': 'sum',
                    'high': 'max',
                    'low': 'min'
                })
            
            df.dropna(inplace=True)
            return df
    
    async def calculate_sma(self, df: pd.DataFrame, periods: List[int] = None) -> Dict:
        """Calculate Simple Moving Average"""
        if periods is None:
            periods = [20, 50, 200]
        
        result = {}
        for period in periods:
            if len(df) >= period:
                result[f'sma_{period}'] = float(df['close'].rolling(window=period).mean().iloc[-1])
        
        # Generate signal
        if 'sma_20' in result and 'sma_50' in result:
            if result['sma_20'] > result['sma_50']:
                result['signal'] = 'bullish_crossover'
            else:
                result['signal'] = 'bearish_crossover'
        
        return result
    
    async def calculate_ema(self, df: pd.DataFrame, periods: List[int] = None) -> Dict:
        """Calculate Exponential Moving Average"""
        if periods is None:
            periods = [12, 26]
        
        result = {}
        for period in periods:
            if len(df) >= period:
                result[f'ema_{period}'] = float(df['close'].ewm(span=period, adjust=False).mean().iloc[-1])
        
        # EMA crossover signal
        if 'ema_12' in result and 'ema_26' in result:
            result['signal'] = 'bullish' if result['ema_12'] > result['ema_26'] else 'bearish'
        
        return result
    
    async def calculate_rsi(self, df: pd.DataFrame, period: int = 14) -> Dict:
        """Calculate Relative Strength Index"""
        if len(df) < period + 1:
            return {}
        
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        current_rsi = float(rsi.iloc[-1])
        
        return {
            'rsi': current_rsi,
            'signal': self._get_rsi_signal(current_rsi)
        }
    
    def _get_rsi_signal(self, rsi: float) -> str:
        """Get trading signal from RSI value"""
        if rsi >= 70:
            return 'overbought'
        elif rsi <= 30:
            return 'oversold'
        elif rsi > 50:
            return 'bullish'
        else:
            return 'bearish'
    
    async def calculate_macd(self, df: pd.DataFrame) -> Dict:
        """Calculate MACD indicator"""
        if len(df) < 26:
            return {}
        
        exp1 = df['close'].ewm(span=12, adjust=False).mean()
        exp2 = df['close'].ewm(span=26, adjust=False).mean()
        macd = exp1 - exp2
        signal = macd.ewm(span=9, adjust=False).mean()
        histogram = macd - signal
        
        return {
            'macd': float(macd.iloc[-1]),
            'signal': float(signal.iloc[-1]),
            'histogram': float(histogram.iloc[-1]),
            'signal_type': 'bullish' if macd.iloc[-1] > signal.iloc[-1] else 'bearish'
        }
    
    async def calculate_bollinger_bands(self, df: pd.DataFrame, period: int = 20, std: int = 2) -> Dict:
        """Calculate Bollinger Bands"""
        if len(df) < period:
            return {}
        
        sma = df['close'].rolling(window=period).mean()
        rolling_std = df['close'].rolling(window=period).std()
        
        upper_band = sma + (rolling_std * std)
        lower_band = sma - (rolling_std * std)
        
        current_price = float(df['close'].iloc[-1])
        current_upper = float(upper_band.iloc[-1])
        current_lower = float(lower_band.iloc[-1])
        current_sma = float(sma.iloc[-1])
        
        # Calculate %B (position within bands)
        percent_b = (current_price - current_lower) / (current_upper - current_lower)
        
        return {
            'upper_band': current_upper,
            'lower_band': current_lower,
            'middle_band': current_sma,
            'percent_b': float(percent_b),
            'band_width': float((current_upper - current_lower) / current_sma * 100),
            'signal': self._get_bollinger_signal(current_price, current_upper, current_lower)
        }
    
    def _get_bollinger_signal(self, price: float, upper: float, lower: float) -> str:
        """Get signal from Bollinger Bands"""
        if price >= upper:
            return 'overbought'
        elif price <= lower:
            return 'oversold'
        else:
            return 'neutral'
    
    async def generate_signals(self, indicators: Dict) -> List[Dict]:
        """Generate trading signals from all indicators"""
        signals = []
        
        # RSI signal
        if 'rsi' in indicators and indicators['rsi']:
            rsi_data = indicators['rsi']
            if rsi_data.get('signal') in ['overbought', 'oversold']:
                signals.append({
                    'type': 'rsi',
                    'strength': 'strong' if abs(rsi_data['rsi'] - 50) > 20 else 'weak',
                    'action': 'sell' if rsi_data['signal'] == 'overbought' else 'buy',
                    'confidence': 0.8
                })
        
        # MACD signal
        if 'macd' in indicators and indicators['macd']:
            macd_data = indicators['macd']
            if macd_data.get('signal_type'):
                signals.append({
                    'type': 'macd',
                    'action': macd_data['signal_type'],
                    'strength': 'strong' if abs(macd_data['histogram']) > 1 else 'weak',
                    'confidence': 0.7
                })
        
        # Bollinger Bands signal
        if 'bollinger' in indicators and indicators['bollinger']:
            bb_data = indicators['bollinger']
            if bb_data.get('signal') in ['overbought', 'oversold']:
                signals.append({
                    'type': 'bollinger',
                    'action': 'sell' if bb_data['signal'] == 'overbought' else 'buy',
                    'strength': 'strong',
                    'confidence': 0.75
                })
        
        # Combine signals for final recommendation
        if signals:
            buy_signals = [s for s in signals if s['action'] == 'buy']
            sell_signals = [s for s in signals if s['action'] == 'sell']
            
            if len(buy_signals) > len(sell_signals):
                final_action = 'buy'
                confidence = sum(s['confidence'] for s in buy_signals) / len(buy_signals)
            elif len(sell_signals) > len(buy_signals):
                final_action = 'sell'
                confidence = sum(s['confidence'] for s in sell_signals) / len(sell_signals)
            else:
                final_action = 'hold'
                confidence = 0.5
            
            return {
                'action': final_action,
                'confidence': confidence,
                'signals': signals,
                'timestamp': datetime.utcnow().isoformat()
            }
        
        return {'action': 'hold', 'confidence': 0.5, 'signals': []}
