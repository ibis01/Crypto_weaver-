
import hashlib
from datetime import datetime, timedelta
from typing import Optional
import jwt
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from core.database import get_db
from core.redis_client import redis_client
from modules.auth.models import User, UserSession
from config.settings import settings

class AuthHandlers:
    """Authentication command handlers"""
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user = update.effective_user
        
        with get_db() as db:
            # Check if user exists
            db_user = db.query(User).filter(
                User.telegram_id == str(user.id)
            ).first()
            
            if not db_user:
                # Create new user
                db_user = User(
                    telegram_id=str(user.id),
                    username=user.username,
                    first_name=user.first_name,
                    last_name=user.last_name,
                    language_code=user.language_code
                )
                db.add(db_user)
                db.commit()
                db.refresh(db_user)
            
            # Create JWT token
            token = self._create_jwt_token(db_user)
            
            # Store session
            session = UserSession(
                user_id=db_user.id,
                token=token,
                expires_at=datetime.utcnow() + timedelta(days=7)
            )
            db.add(session)
            db.commit()
        
        # Welcome message with inline keyboard
        keyboard = [
            [
                InlineKeyboardButton("📊 Market Data", callback_data="market_data"),
                InlineKeyboardButton("💰 Portfolio", callback_data="portfolio")
            ],
            [
                InlineKeyboardButton("🤖 AI Signals", callback_data="ai_signals"),
                InlineKeyboardButton("👥 Social", callback_data="social")
            ],
            [
                InlineKeyboardButton("⚙️ Settings", callback_data="settings")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        welcome_text = f"""
🚀 **Welcome to CryptoWeaver AI, {user.first_name}!**

✨ **Your Web3 Trading Terminal** ✨

📍 **Quick Start:**
1. Connect your wallet → /connect
2. View markets → /markets
3. Get AI signals → /signals
4. Paper trade → /trade

📈 **Features:**
• Real-time multi-exchange trading
• AI-powered market predictions
• Portfolio tracking across chains
• Social trading & leaderboards
• NFT & DeFi integration

Use the buttons below or type /help for commands.
        """
        
        await update.message.reply_text(
            welcome_text,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    
    def _create_jwt_token(self, user) -> str:
        """Create JWT token for user"""
        payload = {
            "user_id": user.id,
            "telegram_id": user.telegram_id,
            "exp": datetime.utcnow() + timedelta(days=7)
        }
        
        token = jwt.encode(
            payload,
            settings.JWT_SECRET_KEY.get_secret_value(),
            algorithm=settings.JWT_ALGORITHM
        )
        
        # Cache user data
        redis_client.cache_set(
            f"user:{user.id}",
            {
                "id": user.id,
                "telegram_id": user.telegram_id,
                "username": user.username
            },
            expire=timedelta(days=1)
        )
        
        return token
    
    async def login(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /login command"""
        # Implementation for web login flow
        pass
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline keyboard callbacks"""
        query = update.callback_query
        await query.answer()
        
        # Route callback to appropriate handler
        callback_data = query.data
        
        if callback_data == "market_data":
            await self._show_market_data(query)
        elif callback_data == "portfolio":
            await self._show_portfolio(query)
        # Add more callback handlers
