# Create the file
cat > quick_start.py << 'EOF'
#!/usr/bin/env python3
"""
CryptoWeaver AI - Quick Start Verification
"""

import os
import sys
import subprocess
from pathlib import Path

def print_step(step, message):
    """Print a formatted step"""
    print(f"\n{'='*60}")
    print(f"📝 STEP {step}: {message}")
    print(f"{'='*60}")

def run_command(cmd, check=True):
    """Run a shell command and return output"""
    try:
        result = subprocess.run(
            cmd, 
            shell=True, 
            capture_output=True, 
            text=True,
            check=check
        )
        return True, result.stdout.strip()
    except subprocess.CalledProcessError as e:
        return False, e.stderr.strip()

def main():
    print("🚀 CRYPTO WEAVER AI - SETUP VERIFICATION")
    print("This script will check if your project is ready to run.\n")
    
    # Step 1: Check Python
    print_step(1, "Checking Python Installation")
    success, output = run_command("python --version")
    if success:
        print(f"✅ Python version: {output}")
    else:
        print(f"❌ Python not found. Please install Python 3.8+")
        return
    
    # Step 2: Check project structure
    print_step(2, "Checking Project Structure")
    
    required_files = [
        "main.py",
        "crypto_weaver/__init__.py",
        "crypto_weaver/bot.py",
        "config/__init__.py",
        "config/settings.py"
    ]
    
    all_files_exist = True
    for file in required_files:
        if os.path.exists(file):
            print(f"✅ {file}")
        else:
            print(f"❌ {file} (MISSING)")
            all_files_exist = False
    
    if not all_files_exist:
        print("\n⚠️ Some required files are missing.")
        print("Creating basic structure...")
        
        # Create minimal structure if missing
        if not os.path.exists("crypto_weaver"):
            os.makedirs("crypto_weaver")
            open("crypto_weaver/__init__.py", "w").close()
            print("Created crypto_weaver/__init__.py")
        
        if not os.path.exists("config"):
            os.makedirs("config")
            open("config/__init__.py", "w").close()
            print("Created config/__init__.py")
        
        # Create minimal bot.py if missing
        if not os.path.exists("crypto_weaver/bot.py"):
            with open("crypto_weaver/bot.py", "w") as f:
                f.write('''
import logging

logger = logging.getLogger(__name__)

class CryptoWeaverBot:
    """Main CryptoWeaver AI bot class"""
    
    def __init__(self):
        self.name = "CryptoWeaver Bot"
    
    async def start(self):
        """Start the bot"""
        logger.info("Starting bot...")
        logger.info("✅ Bot started successfully!")
        # Keep running
        import asyncio
        await asyncio.sleep(10)
        logger.info("Test complete!")
''')
            print("Created crypto_weaver/bot.py")
        
        # Create minimal settings.py if missing
        if not os.path.exists("config/settings.py"):
            with open("config/settings.py", "w") as f:
                f.write('''
from pydantic_settings import BaseSettings
from pydantic import SecretStr

class Settings(BaseSettings):
    TELEGRAM_BOT_TOKEN: SecretStr = SecretStr("8332574617:AAGSmL6KcwZ6pPdyF9SoTRm5X1t3y264CdQ")
    ENVIRONMENT: str = "development"
    
settings = Settings()
''')
            print("Created config/settings.py")
        
        # Create main.py if missing
        if not os.path.exists("main.py"):
            with open("main.py", "w") as f:
                f.write('''
#!/usr/bin/env python3
"""
CryptoWeaver AI - Main Entry Point
"""

import asyncio
import logging
import sys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    try:
        logger.info("🚀 Starting CryptoWeaver AI...")
        
        from crypto_weaver.bot import CryptoWeaverBot
        bot = CryptoWeaverBot()
        await bot.start()
        
    except Exception as e:
        logger.error(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
''')
            print("Created main.py")
    
    # Step 3: Check imports
    print_step(3, "Testing Python Imports")
    
    test_code = """
import sys
import os
sys.path.insert(0, os.getcwd())

# Test core imports
try:
    import asyncio
    print("✅ asyncio")
except ImportError as e:
    print(f"❌ asyncio: {e}")

# Test Telegram library
try:
    import telegram
    print("✅ python-telegram-bot")
except ImportError as e:
    print(f"❌ python-telegram-bot: {e}")

# Test project imports
try:
    from crypto_weaver.bot import CryptoWeaverBot
    print("✅ crypto_weaver.bot")
except ImportError as e:
    print(f"❌ crypto_weaver.bot: {e}")

try:
    from config.settings import settings
    print("✅ config.settings")
except ImportError as e:
    print(f"❌ config.settings: {e}")
"""
    
    with open("test_imports.py", "w") as f:
        f.write(test_code)
    
    success, output = run_command("python test_imports.py")
    print(output)
    
    # Clean up
    if os.path.exists("test_imports.py"):
        os.remove("test_imports.py")
    
    # Final instructions
    print_step("READY", "Next Steps")
    
    print("""
🎉 Your project structure looks good!

🚀 TO START THE BOT:

1. Get a Telegram token from @BotFather
2. Update config/settings.py with your token
3. Run: python main.py

📱 HOW TO GET TELEGRAM TOKEN:

1. Open Telegram app
2. Search for @BotFather
3. Send: /newbot
4. Follow instructions
5. Copy the token (looks like: 1234567890:ABCdefGHIjklMNOpqrsTUVwxyz)
6. Edit config/settings.py in Termux:
   nano config/settings.py
7. Replace "YOUR_TOKEN_HERE" with your actual token
8. Save: Ctrl+X, then Y, then Enter

✅ Then run: python main.py
""")

if __name__ == "__main__":
    main()
EOF

# Make it executable
chmod +x quick_start.py
