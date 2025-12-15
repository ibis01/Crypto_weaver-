import asyncio
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import numpy as np
from openai import AsyncOpenAI
import pandas as pd

from core.redis_client import redis_client
from config.settings import settings
from modules.market_data.aggregator import PriceAggregator
from modules.market_data.indicators import TechnicalIndicators

logger = logging.getLogger(__name__)

class AISignalService:
    """Core AI service for market analysis and signal generation"""
    
    def __init__(self):
        self.openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.price_aggregator = PriceAggregator()
        self.technical_indicators = TechnicalIndicators()
        
        # Model registry for different prediction tasks
        self.models = {
            'sentiment': self.analyze_sentiment_gpt4,
            'price_prediction': self.predict_price_lstm,
            'market_regime': self.detect_market_regime,
            'risk_assessment': self.assess_risk_gpt4,
            'pattern_recognition': self.recognize_patterns
        }
    
    async def generate_signal(self, symbol: str, timeframe: str = '1h') -> Dict:
        """Generate comprehensive AI trading signal"""
        # Check cache first
        cache_key = f"ai_signal:{symbol}:{timeframe}:{datetime.utcnow().hour}"
        cached = await redis_client.cache_get(cache_key)
        if cached:
            return cached
        
        # Gather all data for analysis
        analysis_data = await self._gather_analysis_data(symbol, timeframe)
        
        # Run all AI models in parallel
        tasks = [
            self.models['sentiment'](symbol, analysis_data),
            self.models['price_prediction'](symbol, timeframe, analysis_data),
            self.models['market_regime'](symbol, analysis_data),
            self.models['risk_assessment'](symbol, analysis_data),
            self.models['pattern_recognition'](symbol, analysis_data)
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Combine results into comprehensive signal
        signal = await self._synthesize_signal(symbol, results, analysis_data)
        
        # Cache signal
        await redis_client.cache_set(cache_key, signal, expire=300)  # 5 minutes
        
        return signal
    
    async def _gather_analysis_data(self, symbol: str, timeframe: str) -> Dict:
        """Gather all data needed for AI analysis"""
        # Get price data
        price_data = await self.price_aggregator.get_aggregated_price(symbol)
        
        # Get technical indicators
        indicators = await self.technical_indicators.calculate_all(symbol, timeframe)
        
        # Get market sentiment data
        sentiment = await self._get_market_sentiment(symbol)
        
        # Get order book data (simplified)
        order_book = await self._get_order_book_snapshot(symbol)
        
        # Get recent news/social data
        news_data = await self._get_recent_news(symbol)
        
        return {
            'symbol': symbol,
            'timeframe': timeframe,
            'timestamp': datetime.utcnow().isoformat(),
            'price_data': price_data,
            'technical_indicators': indicators,
            'sentiment': sentiment,
            'order_book': order_book,
            'news': news_data,
            'market_context': await self._get_market_context()
        }
    
    async def analyze_sentiment_gpt4(self, symbol: str, analysis_data: Dict) -> Dict:
        """Use GPT-4 for advanced market sentiment analysis"""
        try:
            # Prepare prompt with market data
            prompt = self._create_sentiment_prompt(symbol, analysis_data)
            
            response = await self.openai_client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=[
                    {
                        "role": "system",
                        "content": """You are a senior cryptocurrency trading analyst with 20 years of experience.
                        Analyze the market data provided and give a sentiment score from -100 (extremely bearish) 
                        to 100 (extremely bullish). Also provide confidence (0-1) and key factors influencing sentiment.
                        Format as JSON with: sentiment_score, confidence, factors, summary."""
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,
                max_tokens=500,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            return {
                'type': 'sentiment',
                'model': 'gpt-4',
                'data': result,
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"GPT-4 sentiment analysis failed: {e}")
            return {
                'type': 'sentiment',
                'model': 'fallback',
                'data': {
                    'sentiment_score': 0,
                    'confidence': 0.5,
                    'factors': ['Analysis unavailable'],
                    'summary': 'Sentiment analysis temporarily unavailable'
                }
            }
    
    def _create_sentiment_prompt(self, symbol: str, analysis_data: Dict) -> str:
        """Create detailed prompt for GPT-4 sentiment analysis"""
        price_data = analysis_data.get('price_data', {})
        indicators = analysis_data.get('technical_indicators', {})
        sentiment = analysis_data.get('sentiment', {})
        
        prompt = f"""
        Analyze {symbol} for trading sentiment.
        
        CURRENT MARKET DATA:
        - Price: ${price_data.get('price', 0):.2f}
        - 24h Change: {price_data.get('price_change_24h', 0):.2f}%
        - Volume: ${price_data.get('total_volume', 0):,.0f}
        - Market Confidence: {price_data.get('confidence', 0):.2f}
        
        TECHNICAL INDICATORS:
        - RSI: {indicators.get('rsi', {}).get('rsi', 50):.1f} ({indicators.get('rsi', {}).get('signal', 'neutral')})
        - MACD: {indicators.get('macd', {}).get('signal_type', 'neutral')}
        - Bollinger Bands: {indicators.get('bollinger', {}).get('signal', 'neutral')}
        - Overall Signal: {indicators.get('signals', {}).get('action', 'hold')} with {indicators.get('signals', {}).get('confidence', 0.5):.2f} confidence
        
        MARKET SENTIMENT:
        - Fear & Greed Index: {sentiment.get('fear_greed', 50)}
        - Social Sentiment: {sentiment.get('social', 50)}
        
        Based on this data, provide:
        1. Sentiment score (-100 to 100)
        2. Confidence in analysis (0-1)
        3. Top 3 factors driving sentiment
        4. Brief summary of market conditions
        """
        return prompt
    
    async def _get_market_sentiment(self, symbol: str) -> Dict:
        """Fetch market sentiment from various sources"""
        try:
            # Fetch from external APIs (simplified)
            # In production, integrate with: Alternative.me Fear & Greed, LunarCrush, Santiment
            
            # Mock data for now
            return {
                'fear_greed': np.random.randint(20, 80),
                'social': np.random.randint(30, 70),
                'weighted_sentiment': np.random.normal(0, 25),
                'sources': ['alternative', 'lunarcrush'],
                'timestamp': datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Sentiment fetch failed: {e}")
            return {'error': str(e)}
    
    async def _get_order_book_snapshot(self, symbol: str) -> Dict:
        """Get order book snapshot for analysis"""
        # In production, fetch from exchange WebSocket
        # Mock data for now
        return {
            'bids': [
                {'price': 50000 * 0.995, 'quantity': 10},
                {'price': 50000 * 0.99, 'quantity': 25},
                {'price': 50000 * 0.985, 'quantity': 50}
            ],
            'asks': [
                {'price': 50000 * 1.005, 'quantity': 12},
                {'price': 50000 * 1.01, 'quantity': 30},
                {'price': 50000 * 1.015, 'quantity': 45}
            ],
            'bid_ask_spread': 0.01,
            'order_book_imbalance': 0.05
        }
    
    async def _get_recent_news(self, symbol: str) -> List[Dict]:
        """Get recent news/articles about symbol"""
        # In production, integrate with: CryptoPanic, CoinTelegraph, etc.
        return [
            {
                'title': f'{symbol} shows strong momentum',
                'source': 'cryptopanic',
                'sentiment': 'positive',
                'timestamp': (datetime.utcnow() - timedelta(hours=2)).isoformat()
            }
        ]
    
    async def _get_market_context(self) -> Dict:
        """Get broader market context"""
        return {
            'btc_dominance': 52.5,
            'total_market_cap': 1.8e12,
            'market_cap_change_24h': 2.5,
            'top_gainers': ['SOL', 'AVAX', 'DOT'],
            'top_losers': ['XRP', 'ADA', 'DOGE']
      }
