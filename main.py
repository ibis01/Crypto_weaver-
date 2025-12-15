#!/usr/bin/env python3
"""
CryptoWeaver AI - Main Entry Point
Web3 Trading Terminal with AI-powered signals

Run this file to start the bot:
$ python main.py
"""

import asyncio
import logging
import sys
import os
from pathlib import Path

# Add the project root to Python path so imports work
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Try to import our custom logger, fall back to basic if needed
try:
    from crypto_weaver.core.logger import setup_logging
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("Using custom logging configuration")
except ImportError:
    # Fallback to basic logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    logger = logging.getLogger(__name__)
    logger.info("Using basic logging (custom logger not found)")

async def main():
    """Main async entry point for the bot"""
    try:
        logger.info("🚀 Starting CryptoWeaver AI Trading Terminal...")
        logger.info(f"Project root: {project_root}")
        logger.info(f"Python: {sys.version}")
        
        # Check for Telegram token
        from config.settings import settings
        
        if settings.TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN_HERE" or not settings.TELEGRAM_BOT_TOKEN:
            logger.error("❌ TELEGRAM_BOT_TOKEN not set in config/settings.py!")
            logger.info("""
            To get a token:
            1. Open Telegram and search for @BotFather
            2. Send /newbot command
            3. Choose a name for your bot
            4. Copy the token (looks like: 1234567890:ABCdefGHIjklMNOpqrsTUVwxyz)
            5. Update config/settings.py with your token
            """)
            return
        
        # Import and start the bot
        try:
            from crypto_weaver.bot import CryptoWeaverBot
            logger.info("✅ Bot module imported successfully")
            
            bot = CryptoWeaverBot()
            logger.info("✅ Bot instance created")
            
            await bot.start()
            logger.info("✅ Bot started successfully")
            
        except ImportError as e:
            logger.error(f"❌ Failed to import bot module: {e}")
            logger.info("""
            Common fixes:
            1. Make sure crypto_weaver/bot.py exists
            2. Check that bot.py contains 'class CryptoWeaverBot'
            3. Verify the class name is spelled correctly
            """)
            
            # Try to create a minimal bot for testing
            await start_minimal_bot()
            
    except KeyboardInterrupt:
        logger.info("👋 Shutdown requested by user (Ctrl+C)")
    except Exception as e:
        logger.error(f"💥 Fatal error: {e}", exc_info=True)
        return 1
    
    return 0

async def start_minimal_bot():
    """Start a minimal bot if main bot fails (for testing)"""
    logger.info("🔄 Attempting to start minimal test bot...")
    
    try:
        from telegram.ext import Application, CommandHandler
        from config.settings import settings
        
        # Create a simple bot
        app = Application.builder().token(settings.TELEGRAM_BOT_TOKEN.get_secret_value()).build()
        
        # Add basic commands
        async def start(update, context):
            await update.message.reply_text("✅ CryptoWeaver AI is working!\n\nSend /help for commands")
        
        async def help_cmd(update, context):
            await update.message.reply_text(
                "🤖 CryptoWeaver AI Help\n\n"
                "Available commands:\n"
                "/start - Start the bot\n"
                "/help - Show this message\n"
                "/test - Test connection\n"
                "\n🚀 Your bot framework is working!"
            )
        
        async def test(update, context):
            await update.message.reply_text("✅ Bot is online and responding!")
        
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("help", help_cmd))
        app.add_handler(CommandHandler("test", test))
        
        # Start the bot
        await app.initialize()
        await app.start()
        await app.updater.start_polling()
        
        logger.info("✅ Minimal bot is running! Press Ctrl+C to stop")
        logger.info("📱 Open Telegram and search for your bot to test commands")
        
        # Keep running until interrupted
        await asyncio.Event().wait()
        
    except Exception as e:
        logger.error(f"❌ Minimal bot also failed: {e}")
        logger.info("""
        🔧 Debugging steps:
        1. Check your Telegram token in config/settings.py
        2. Run: pip install python-telegram-bot
        3. Check internet connection
        4. Try: python -c "import telegram; print('Telegram lib OK')"
        """)

def run():
    """Entry point for command line execution"""
    # Windows compatibility
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    # Run the async main function
    return asyncio.run(main())

if __name__ == "__main__":
    sys.exit(run())
