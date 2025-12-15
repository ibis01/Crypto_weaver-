import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
import numpy as np
from datetime import datetime

from modules.ai_signals.core.ai_service import AISignalService
from modules.ai_signals.models.price_predictor import LSTMPredictor
from modules.ai_signals.backtesting.engine import BacktestingEngine
from modules.ai_signals.strategies import AIHybridStrategy, StrategyConfig, StrategyType

@pytest.mark.asyncio
async def test_ai_signal_generation():
    """Test AI signal generation"""
    service = AISignalService()
    
    # Mock dependencies
    with patch('modules.ai_signals.core.ai_service.PriceAggregator') as MockAggregator, \
         patch('modules.ai_signals.core.ai_service.TechnicalIndicators') as MockIndicators, \
         patch('modules.ai_signals.core.ai_service.AsyncOpenAI') as MockOpenAI:
        
        # Setup mocks
        mock_aggregator = AsyncMock()
        mock_aggregator.get_aggregated_price.return_value = {
            'price': 50000,
            'price_change_24h': 2.5,
            'total_volume': 1000000,
            'confidence': 0.9
        }
        
        mock_indicators = AsyncMock()
        mock_indicators.calculate_all.return_value = {
            'rsi': {'rsi': 65, 'signal': 'bullish'},
            'macd': {'signal_type': 'bullish'},
            'bollinger': {'signal': 'neutral'},
            'signals': {'action': 'buy', 'confidence': 0.7}
        }
        
        mock_openai = AsyncMock()
        mock_completion = MagicMock()
        mock_completion.choices[0].message.content = json.dumps({
            'sentiment_score': 75,
            'confidence': 0.8,
            'factors': ['Positive momentum', 'Strong volume'],
            'summary': 'Bullish sentiment'
        })
        mock_openai.chat.completions.create.return_value = mock_completion
        
        # Inject mocks
        service.price_aggregator = mock_aggregator
        service.technical_indicators = mock_indicators
        service.openai_client = mock_openai
        
        # Generate signal
        signal = await service.generate_signal('BTC-USDT', '1h')
        
        assert signal is not None
        assert 'sentiment' in signal
        assert 'prediction' in signal
        assert 'risk_assessment' in signal
        assert signal['symbol'] == 'BTC-USDT'

@pytest.mark.asyncio
async def test_lstm_prediction():
    """Test LSTM price prediction"""
    predictor = LSTMPredictor(sequence_length=10, prediction_horizon=3)
    
    # Mock model and scaler
    predictor.model = MagicMock()
    predictor.model.predict.return_value = np.array([[0.6, 0.65, 0.7]])
    
    predictor.scaler = MagicMock()
    predictor.scaler.transform.return_value = np.random.randn(20, 5)
    
    # Create dummy recent data
    recent_data = np.random.randn(20, 5)
    
    prediction = await predictor.predict('BTC-USDT', recent_data)
    
    assert 'predictions' in prediction
    assert 'confidence' in prediction
    assert len(prediction['predictions']) == 3
    assert 0 <= prediction['confidence'] <= 1

@pytest.mark.asyncio
async def test_backtesting_engine():
    """Test backtesting engine"""
    engine = BacktestingEngine(initial_capital=10000)
    
    # Create mock historical data
    dates = pd.date_range('2024-01-01', periods=100, freq='H')
    historical_data = pd.DataFrame({
        'close': [50000 + i * 10 for i in range(100)],
        'volume': [1000] * 100,
        'high': [50100 + i * 10 for i in range(100)],
        'low': [49900 + i * 10 for i in range(100)]
    }, index=dates)
    
    # Mock signal generator (always buy)
    async def mock_signal_generator(data):
        return {'action': 'buy', 'confidence': 0.7}
    
    # Run backtest
    with patch.object(engine, '_load_historical_data', 
                     return_value=historical_data):
        results = await engine.backtest_signal_strategy(
            symbol='BTC-USDT',
            signal_generator=mock_signal_generator,
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 5),
            timeframe='1h'
        )
        
        assert 'performance' in results
        assert 'trades' in results
        assert 'equity_curve' in results

def test_ai_hybrid_strategy():
    """Test AI hybrid strategy"""
    config = StrategyConfig(
        name='AI_Hybrid_BTC',
        type=StrategyType.AI_HYBRID,
        symbol='BTC-USDT',
        timeframe='1h',
        parameters={'weights': {'ai': 0.4, 'technical': 0.3}},
        risk_per_trade=0.02
    )
    
    strategy = AIHybridStrategy(config)
    
    # Test position size calculation
    position_size = asyncio.run(strategy.calculate_position_size(10000, 50000))
    assert position_size > 0
    
    # Test exit conditions
    position = {'entry_price': 50000, 'entry_time': datetime.utcnow()}
    
    # Should not exit at same price
    assert not asyncio.run(strategy.should_exit_position(position, 50000))
    
    # Should exit at stop loss
    assert asyncio.run(strategy.should_exit_position(position, 47500))  # 5% below
    
    # Should exit at take profit
    assert asyncio.run(strategy.should_exit_position(position, 55000))  # 10% above

# Performance test for ML models
@pytest.mark.performance
@pytest.mark.asyncio
async def test_ml_model_performance():
    """Test ML model inference performance"""
    predictor = LSTMPredictor()
    
    # Load or create test model
    # Create dummy input
    batch_size = 100
    sequence_length = 60
    features = 5
    
    dummy_input = np.random.randn(batch_size, sequence_length, features)
    
    # Time inference
    import time
    
    start_time = time.time()
    
    # Mock prediction for performance test
    with patch.object(predictor, 'model'):
        predictor.model = MagicMock()
        predictor.model.predict.return_value = np.random.randn(batch_size, 3)
        
        for i in range(100):  # 100 predictions
            await predictor.predict('BTC-USDT', dummy_input[i % 10])
    
    end_time = time.time()
    
    avg_inference_time = (end_time - start_time) / 100 * 1000  # ms per prediction
    
    print(f"\n🤖 ML Model Performance:")
    print(f"Average inference time: {avg_inference_time:.1f}ms")
    
    assert avg_inference_time < 50  # Should be under 50ms
