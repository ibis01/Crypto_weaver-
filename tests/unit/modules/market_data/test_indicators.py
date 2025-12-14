import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from modules.market_data.indicators import TechnicalIndicators

def test_rsi_calculation():
    """Test RSI calculation"""
    indicators = TechnicalIndicators()
    
    # Create test data: prices going up (should give high RSI)
    dates = pd.date_range('2024-01-01', periods=15, freq='D')
    prices = [100 + i * 2 for i in range(15)]  # Increasing prices
    df = pd.DataFrame({
        'close': prices,
        'volume': [1000] * 15,
        'high': [p + 1 for p in prices],
        'low': [p - 1 for p in prices]
    }, index=dates)
    
    rsi_result = asyncio.run(indicators.calculate_rsi(df))
    
    assert 'rsi' in rsi_result
    assert 50 <= rsi_result['rsi'] <= 100  # Rising prices -> RSI > 50
    assert rsi_result['signal'] in ['bullish', 'overbought']

def test_macd_signal():
    """Test MACD signal generation"""
    indicators = TechnicalIndicators()
    
    # Create test data with clear trend
    dates = pd.date_range('2024-01-01', periods=100, freq='H')
    
    # Create uptrend
    trend = np.linspace(100, 200, 100)
    noise = np.random.normal(0, 5, 100)
    prices = trend + noise
    
    df = pd.DataFrame({
        'close': prices,
        'volume': np.random.randint(1000, 5000, 100),
        'high': prices + 2,
        'low': prices - 2
    }, index=dates)
    
    macd_result = asyncio.run(indicators.calculate_macd(df))
    
    assert 'macd' in macd_result
    assert 'signal' in macd_result
    assert 'histogram' in macd_result
    # In uptrend, MACD should be positive
    assert macd_result['signal_type'] == 'bullish'

def test_bollinger_bands():
    """Test Bollinger Bands calculation"""
    indicators = TechnicalIndicators()
    
    # Create data with volatility
    np.random.seed(42)
    dates = pd.date_range('2024-01-01', periods=50, freq='H')
    prices = 100 + np.random.randn(50) * 10  # Volatile prices
    
    df = pd.DataFrame({
        'close': prices,
        'volume': [1000] * 50,
        'high': prices + 1,
        'low': prices - 1
    }, index=dates)
    
    bb_result = asyncio.run(indicators.calculate_bollinger_bands(df))
    
    assert 'upper_band' in bb_result
    assert 'lower_band' in bb_result
    assert 'middle_band' in bb_result
    assert 0 <= bb_result['percent_b'] <= 1  # %B should be between 0 and 1
    assert bb_result['band_width'] > 0
