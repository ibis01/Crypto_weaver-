import logging
from typing import Dict, List, Optional
import asyncio
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters
)
from telegram import Update

from config.settings import settings
from core.logger import setup_logging
from core.exceptions import ModuleLoadError

# Import modules
from modules.auth import AuthModule
from modules.market_data import MarketDataModule
# Add other modules as they're built

class CryptoWeaverBot:
    """Main bot class with modular architecture"""
    
    def __init__(self):
        setup_logging()
        self.logger = logging.getLogger(__name__)
        
        # Module registry
        self.modules: Dict[str, Any] = {}
        self.handlers: List = []
        
        # Bot application
        self.application = Application.builder() \
            .token(settings.TELEGRAM_BOT_TOKEN.get_secret_value()) \
            .pool_timeout(30) \
            .connect_timeout(30) \
            .read_timeout(30) \
            .write_timeout(30) \
            .build()
    
    def register_module(self, module):
        """Register a feature module"""
        module_name = module.__class__.__name__
        
        try:
            # Initialize module
            module_instance = module(self)
            
            # Get module handlers
            module_handlers = module_instance.get_handlers()
            
            # Register handlers
            for handler in module_handlers:
                self.application.add_handler(handler)
            
            # Store module
            self.modules[module_name] = module_instance
            self.logger.info(f"Module '{module_name}' registered successfully")
            
        except Exception as e:
            raise ModuleLoadError(f"Failed to load module {module_name}: {e}")
    
    async def initialize(self):
        """Initialize all modules"""
        self.logger.info("Initializing CryptoWeaver Bot...")
        
        # Register modules
        modules_to_load = [
            AuthModule,
            MarketDataModule,
            # Add other modules here
        ]
        
        for module_class in modules_to_load:
            self.register_module(module_class)
        
        # Add error handler
        self.application.add_error_handler(self.error_handler)
        
        self.logger.info(f"Bot initialized with {len(self.modules)} modules")
    
    async def error_handler(self, update: object, context):
        """Global error handler"""
        self.logger.error(f"Update {update} caused error: {context.error}")
        
        # Notify user if it's a user-facing error
        if isinstance(update, Update) and update.effective_chat:
            await update.effective_chat.send_message(
                "⚠️ An error occurred. Our team has been notified."
            )
    
    async def start(self):
        """Start the bot"""
        await self.initialize()
        
        if settings.TELEGRAM_WEBHOOK_URL:
            # Webhook mode for production
            await self.application.start()
            await self.application.bot.set_webhook(
                settings.TELEGRAM_WEBHOOK_URL
            )
            self.logger.info("Bot started in webhook mode")
        else:
            # Polling mode for development
            await self.application.initialize()
            await self.application.start()
            await self.application.updater.start_polling(
                poll_interval=1.0,
                timeout=10,
                drop_pending_updates=True
            )
            self.logger.info("Bot started in polling mode")
        
        # Keep running
        await self.application.idle()
    
    async def stop(self):
        """Stop the bot gracefully"""
        self.logger.info("Stopping bot...")
        await self.application.stop()
        
        # Clean up modules
        for module in self.modules.values():
            if hasattr(module, 'cleanup'):
                await module.cleanup()

# Module Base Class
class BaseModule:
    """Base class for all feature modules"""
    
    def __init__(self, bot: CryptoWeaverBot):
        self.bot = bot
        self.logger = logging.getLogger(self.__class__.__name__)
        self.db = None  # Will be lazy-loaded
    
    def get_handlers(self) -> List:
        """Return list of handlers for this module"""
        raise NotImplementedError
    
    async def cleanup(self):
        """Cleanup resources when bot stops"""
        pass
