
#!/usr/bin/env python3
"""
CryptoWeaver AI - Main Entry Point
Web3 Trading Terminal with AI-powered signals
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

# Configure logging first
from core.logger import setup_logging
setup_logging()

logger = logging.getLogger(__name__)

async def main():
    """Main entry point for CryptoWeaver AI"""
    try:
        logger.info("🚀 Starting CryptoWeaver AI Trading Terminal...")
        logger.info(f"Python version: {sys.version}")
        
        # Import bot after logging is set up
        from crypto_weaver.bot import CryptoWeaverBot
        
        # Initialize and start the bot
        bot = CryptoWeaverBot()
        await bot.start()
        
    except KeyboardInterrupt:
        logger.info("Shutdown requested by user (Ctrl+C)")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)

def run():
    """Entry point for command line"""
    # Set up asyncio event loop for Windows compatibility
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    # Run the main async function
    asyncio.run(main())

if __name__ == "__main__":
    run()
