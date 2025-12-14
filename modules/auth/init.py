
from typing import List
from telegram.ext import CommandHandler, CallbackQueryHandler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from .handlers import AuthHandlers
from core.database import get_db
from core.redis_client import redis_client

class AuthModule:
    """Authentication and user management module"""
    
    def __init__(self, bot):
        self.bot = bot
        self.handlers = AuthHandlers()
    
    def get_handlers(self):
        return [
            CommandHandler("start", self.handlers.start),
            CommandHandler("login", self.handlers.login),
            CommandHandler("profile", self.handlers.profile),
            CommandHandler("logout", self.handlers.logout),
            CallbackQueryHandler(self.handlers.handle_callback, pattern="^auth_")
        ]
