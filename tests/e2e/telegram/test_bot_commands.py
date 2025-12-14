import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from telegram import Update, Message, Chat, User as TelegramUser
from telegram.ext import ContextTypes

@pytest.mark.asyncio
async def test_start_command():
    """Test /start command flow"""
    from modules.auth.handlers import AuthHandlers
    handlers = AuthHandlers()
    
    # Mock update
    mock_update = AsyncMock(spec=Update)
    mock_message = AsyncMock(spec=Message)
    mock_chat = AsyncMock(spec=Chat)
    mock_user = AsyncMock(spec=TelegramUser)
    
    mock_user.id = 123456
    mock_user.username = "testuser"
    mock_user.first_name = "Test"
    mock_user.last_name = "User"
    mock_user.language_code = "en"
    
    mock_chat.id = 123456
    mock_message.chat = mock_chat
    mock_message.from_user = mock_user
    mock_update.message = mock_message
    
    # Mock context
    mock_context = AsyncMock(spec=ContextTypes.DEFAULT_TYPE)
    
    # Mock database session
    with patch('modules.auth.handlers.get_db') as mock_get_db:
        mock_db = AsyncMock()
        mock_get_db.return_value.__enter__.return_value = mock_db
        
        # Mock user query (no existing user)
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        await handlers.start(mock_update, mock_context)
        
        # Verify user was created
        assert mock_db.add.called
        assert mock_db.commit.called
        
        # Verify reply was sent
        assert mock_message.reply_text.called
        
        # Check reply contains welcome message
        args, kwargs = mock_message.reply_text.call_args
        assert "Welcome to CryptoWeaver AI" in args[0]
        assert "reply_markup" in kwargs  # Should have inline keyboard

@pytest.mark.asyncio
async def test_market_data_command():
    """Test /price command with real data"""
    from modules.market_data.handlers import MarketDataHandlers
    handlers = MarketDataHandlers()
    
    mock_update = AsyncMock(spec=Update)
    mock_message = AsyncMock(spec=Message)
    mock_context = AsyncMock(spec=ContextTypes.DEFAULT_TYPE)
    
    mock_message.text = "/price BTC"
    mock_update.message = mock_message
    
    # Mock price aggregator
    with patch('modules.market_data.handlers.PriceAggregator') as MockAggregator:
        mock_aggregator = AsyncMock()
        mock_aggregator.get_aggregated_price.return_value = {
            'symbol': 'BTC-USDT',
            'price': 50000.50,
            'spread_percent': 0.5,
            'exchange_count': 3,
            'confidence': 0.9
        }
        MockAggregator.return_value = mock_aggregator
        
        await handlers.get_price(mock_update, mock_context)
        
        # Verify price was fetched
        assert mock_aggregator.get_aggregated_price.called
        
        # Verify reply contains price
        args, kwargs = mock_message.reply_text.call_args
        assert "BTC-USDT" in args[0]
        assert "50000.50" in args[0]
