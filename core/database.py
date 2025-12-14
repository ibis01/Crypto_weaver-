from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session
from contextlib import contextmanager
from typing import Generator
import logging

from config.settings import settings

logger = logging.getLogger(__name__)

# Create engine with connection pooling
engine = create_engine(
    str(settings.DATABASE_URL),
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_pre_ping=True,  # Verify connections before using
    echo=settings.DEBUG   # SQL logging in debug mode
)

# Session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Thread-safe session
ScopedSession = scoped_session(SessionLocal)

Base = declarative_base()

@contextmanager
def get_db() -> Generator:
    """Dependency for FastAPI or context manager for sessions"""
    db = ScopedSession()
    try:
        yield db
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Database session error: {e}")
        raise
    finally:
        ScopedSession.remove()

def init_db():
    """Initialize database tables"""
    Base.metadata.create_all(bind=engine)
    logger.info("Database initialized")
