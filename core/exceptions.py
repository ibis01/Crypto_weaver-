"""
Custom exceptions for CryptoWeaver AI
"""

class CryptoWeaverError(Exception):
    """Base exception for CryptoWeaver AI"""
    pass

class ModuleLoadError(CryptoWeaverError):
    """Failed to load a module"""
    pass

class DatabaseError(CryptoWeaverError):
    """Database related errors"""
    pass

class ExchangeError(CryptoWeaverError):
    """Exchange API errors"""
    pass

class TradingError(CryptoWeaverError):
    """Trading related errors"""
    pass

class WalletError(CryptoWeaverError):
    """Wallet related errors"""
    pass

class AIError(CryptoWeaverError):
    """AI/ML related errors"""
    pass

class ValidationError(CryptoWeaverError):
    """Data validation errors"""
    pass

class RateLimitError(CryptoWeaverError):
    """Rate limiting errors"""
    pass
