from pydantic_settings import BaseSettings
from pydantic import PostgresDsn, RedisDsn, SecretStr
from typing import List, Optional
import os

class Settings(BaseSettings):
    # Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    
    # Telegram
    TELEGRAM_BOT_TOKEN: SecretStr
    TELEGRAM_WEBHOOK_URL: Optional[str] = None
    
    # Database
    DATABASE_URL: PostgresDsn = "postgresql://user:pass@localhost:5432/crypto_weaver"
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 30
    
    # Redis
    REDIS_URL: RedisDsn = "redis://localhost:6379/0"
    REDIS_PASSWORD: Optional[SecretStr] = None
    
    # JWT
    JWT_SECRET_KEY: SecretStr
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # API Keys (External Services)
    COINGECKO_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    BINANCE_API_KEY: Optional[str] = None
    BINANCE_API_SECRET: Optional[SecretStr] = None
    
    # Security
    RATE_LIMIT_PER_MINUTE: int = 100
    CORS_ORIGINS: List[str] = ["*"]
    
    # Feature Flags
    ENABLE_TRADING: bool = False
    ENABLE_AI_SIGNALS: bool = False
    PAPER_TRADING_ONLY: bool = True
    
    class Config:
        env_file = ".env"
        case_sensitive = True

# Global settings instance
settings = Settings()
