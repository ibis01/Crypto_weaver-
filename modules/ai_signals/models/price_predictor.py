import numpy as np
import pandas as pd
from typing import Dict, Tuple, Optional
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers
import joblib
import pickle
from pathlib import Path
import logging
from datetime import datetime, timedelta

from core.database import get_db
from modules.market_data.models import PriceHistory

logger = logging.getLogger(__name__)

class LSTMPredictor:
    """LSTM neural network for price prediction"""
    
    def __init__(self, sequence_length: int = 60, prediction_horizon: int = 6):
        self.sequence_length = sequence_length
        self.prediction_horizon = prediction_horizon
        self.model = None
        self.scaler = None
        self.feature_columns = ['price', 'volume', 'high', 'low', 'spread']
        
    async def train_model(self, symbol: str, lookback_days: int = 90):
        """Train LSTM model on historical data"""
        # Load historical data
        X, y, scaler = await self._prepare_training_data(symbol, lookback_days)
        
        if len(X) < 100:
            logger.warning(f"Insufficient data for {symbol}: {len(X)} samples")
            return False
        
        # Build LSTM model
        self.model = self._build_lstm_model(input_shape=(self.sequence_length, len(self.feature_columns)))
        self.scaler = scaler
        
        # Train model
        history = self.model.fit(
            X, y,
            epochs=50,
            batch_size=32,
            validation_split=0.2,
            verbose=0,
            callbacks=[
                keras.callbacks.EarlyStopping(patience=10, restore_best_weights=True),
                keras.callbacks.ReduceLROnPlateau(factor=0.5, patience=5)
            ]
        )
        
        # Save model
        await self._save_model(symbol)
        
        logger.info(f"LSTM model trained for {symbol} with {len(X)} samples")
        return True
    
    def _build_lstm_model(self, input_shape: Tuple) -> keras.Model:
        """Build LSTM neural network architecture"""
        model = keras.Sequential([
            layers.LSTM(128, return_sequences=True, input_shape=input_shape,
                       dropout=0.2, recurrent_dropout=0.2),
            layers.LSTM(64, return_sequences=True, dropout=0.2, recurrent_dropout=0.2),
            layers.LSTM(32, dropout=0.2, recurrent_dropout=0.2),
            layers.Dense(32, activation='relu'),
            layers.Dropout(0.3),
            layers.Dense(16, activation='relu'),
            layers.Dense(self.prediction_horizon)  # Predict multiple steps ahead
        ])
        
        model.compile(
            optimizer=keras.optimizers.Adam(learning_rate=0.001),
            loss='mse',
            metrics=['mae', 'mape']
        )
        
        return model
    
    async def _prepare_training_data(self, symbol: str, lookback_days: int) -> Tuple:
        """Prepare training data from historical prices"""
        with get_db() as db:
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=lookback_days)
            
            # Query price history
            prices = db.query(
                PriceHistory.price,
                PriceHistory.volume,
                PriceHistory.high,
                PriceHistory.low,
                PriceHistory.spread,
                PriceHistory.timestamp
            ).filter(
                PriceHistory.symbol == symbol,
                PriceHistory.timestamp >= start_date,
                PriceHistory.timestamp <= end_date
            ).order_by(PriceHistory.timestamp.asc()).all()
            
            if not prices:
                return np.array([]), np.array([]), None
            
            # Convert to DataFrame
            df = pd.DataFrame(prices, columns=self.feature_columns + ['timestamp'])
            df.set_index('timestamp', inplace=True)
            
            # Handle missing values
            df = df.interpolate(method='linear').fillna(method='ffill').fillna(method='bfill')
            
            # Normalize data
            from sklearn.preprocessing import MinMaxScaler
            scaler = MinMaxScaler(feature_range=(0, 1))
            scaled_data = scaler.fit_transform(df[self.feature_columns])
            
            # Create sequences
            X, y = [], []
            for i in range(self.sequence_length, len(scaled_data) - self.prediction_horizon):
                X.append(scaled_data[i-self.sequence_length:i])
                y.append(scaled_data[i:i+self.prediction_horizon, 0])  # Predict price column
            
            return np.array(X), np.array(y), scaler
    
    async def predict(self, symbol: str, recent_data: np.ndarray) -> Dict:
        """Make price prediction using trained model"""
        if self.model is None:
            await self.load_model(symbol)
        
        if self.model is None or self.scaler is None:
            return {'error': 'Model not trained'}
        
        try:
            # Scale input data
            scaled_input = self.scaler.transform(recent_data)
            
            # Reshape for LSTM (batch_size, sequence_length, features)
            input_seq = scaled_input[-self.sequence_length:].reshape(1, self.sequence_length, -1)
            
            # Make prediction
            scaled_prediction = self.model.predict(input_seq, verbose=0)
            
            # Inverse transform to get actual prices
            # Create dummy array for inverse transform
            dummy_array = np.zeros((self.prediction_horizon, len(self.feature_columns)))
            dummy_array[:, 0] = scaled_prediction[0]  # Only price column predicted
            
            prediction = self.scaler.inverse_transform(dummy_array)[:, 0]
            
            # Calculate confidence based on prediction variance
            confidence = self._calculate_prediction_confidence(prediction)
            
            return {
                'predictions': prediction.tolist(),
                'horizon': self.prediction_horizon,
                'confidence': confidence,
                'model': 'lstm',
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Prediction failed: {e}")
            return {'error': str(e)}
    
    def _calculate_prediction_confidence(self, predictions: np.ndarray) -> float:
        """Calculate confidence score based on prediction pattern"""
        # Simple confidence based on prediction trend consistency
        diffs = np.diff(predictions)
        if len(diffs) > 0:
            # Check if predictions are monotonic (consistent direction)
            all_increasing = all(d > 0 for d in diffs)
            all_decreasing = all(d < 0 for d in diffs)
            
            if all_increasing or all_decreasing:
                return 0.8  # High confidence for clear trend
            else:
                # Calculate variance in prediction changes
                variance = np.var(diffs)
                return max(0.3, 1 - variance * 10)  # Lower variance = higher confidence
        return 0.5
    
    async def _save_model(self, symbol: str):
        """Save trained model to disk"""
        model_dir = Path(f"models/{symbol}")
        model_dir.mkdir(parents=True, exist_ok=True)
        
        # Save Keras model
        self.model.save(model_dir / "lstm_model.h5")
        
        # Save scaler
        with open(model_dir / "scaler.pkl", 'wb') as f:
            pickle.dump(self.scaler, f)
        
        # Save metadata
        metadata = {
            'symbol': symbol,
            'sequence_length': self.sequence_length,
            'prediction_horizon': self.prediction_horizon,
            'feature_columns': self.feature_columns,
            'trained_at': datetime.utcnow().isoformat()
        }
        
        with open(model_dir / "metadata.json", 'w') as f:
            import json
            json.dump(metadata, f)
    
    async def load_model(self, symbol: str) -> bool:
        """Load trained model from disk"""
        model_path = Path(f"models/{symbol}/lstm_model.h5")
        scaler_path = Path(f"models/{symbol}/scaler.pkl")
        
        if model_path.exists() and scaler_path.exists():
            try:
                self.model = keras.models.load_model(model_path)
                with open(scaler_path, 'rb') as f:
                    self.scaler = pickle.load(f)
                return True
            except Exception as e:
                logger.error(f"Failed to load model: {e}")
                return False
        return False

class GRUPredictor(LSTMPredictor):
    """GRU neural network for price prediction (faster training than LSTM)"""
    
    def _build_gru_model(self, input_shape: Tuple) -> keras.Model:
        """Build GRU neural network architecture"""
        model = keras.Sequential([
            layers.GRU(128, return_sequences=True, input_shape=input_shape,
                      dropout=0.2, recurrent_dropout=0.2),
            layers.GRU(64, return_sequences=True, dropout=0.2, recurrent_dropout=0.2),
            layers.GRU(32, dropout=0.2, recurrent_dropout=0.2),
            layers.Dense(32, activation='relu'),
            layers.Dropout(0.3),
            layers.Dense(16, activation='relu'),
            layers.Dense(self.prediction_horizon)
        ])
        
        model.compile(
            optimizer=keras.optimizers.Adam(learning_rate=0.001),
            loss='mse',
            metrics=['mae', 'mape']
        )
        
        return model
