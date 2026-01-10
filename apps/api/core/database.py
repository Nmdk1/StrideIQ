"""
Database connection management with connection pooling.

This module provides a production-ready database connection pool
that can handle high concurrency and scale horizontally.
"""
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from core.config import settings
import logging

logger = logging.getLogger(__name__)

# Build database URL
DATABASE_URL = (
    f"postgresql://{settings.POSTGRES_USER}:"
    f"{settings.POSTGRES_PASSWORD}@"
    f"{settings.POSTGRES_HOST}:"
    f"{settings.POSTGRES_PORT}/"
    f"{settings.POSTGRES_DB}"
)

# Create engine with connection pooling
engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=settings.DB_POOL_SIZE,  # Number of connections to maintain
    max_overflow=settings.DB_MAX_OVERFLOW,  # Additional connections beyond pool_size
    pool_timeout=settings.DB_POOL_TIMEOUT,  # Seconds to wait for connection
    pool_recycle=settings.DB_POOL_RECYCLE,  # Recycle connections after this many seconds
    pool_pre_ping=True,  # Verify connections before using
    echo=settings.DEBUG,  # Log SQL queries in debug mode
)

# Session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,  # Prevent lazy loading issues
)

Base = declarative_base()


# Connection pool event listeners for monitoring
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    """Set connection-level settings."""
    logger.debug("New database connection established")


@event.listens_for(engine, "checkout")
def receive_checkout(dbapi_conn, connection_record, connection_proxy):
    """Log when connection is checked out from pool."""
    logger.debug("Connection checked out from pool")


@event.listens_for(engine, "checkin")
def receive_checkin(dbapi_conn, connection_record):
    """Log when connection is returned to pool."""
    logger.debug("Connection returned to pool")


def get_db() -> Session:
    """
    Dependency for FastAPI to get database session.
    
    This function ensures:
    - Connection is properly acquired from pool
    - Connection is returned to pool after request
    - Transactions are properly managed
    - Connection health is verified with retry logic
    """
    db = None
    max_retries = 3
    retry_delay = 0.1  # 100ms initial delay
    
    for attempt in range(max_retries):
        try:
            db = SessionLocal()
            # Verify connection is alive
            db.execute(text("SELECT 1"))
            break
        except Exception as e:
            if db:
                db.close()
            if attempt == max_retries - 1:
                logger.error(f"Failed to establish database connection after {max_retries} attempts: {e}")
                raise
            logger.warning(f"Database connection attempt {attempt + 1} failed, retrying...")
            import time
            time.sleep(retry_delay * (2 ** attempt))  # Exponential backoff
    
    try:
        yield db
        db.commit()
    except Exception as e:
        db.rollback()
        # Only log actual database errors, not HTTP exceptions
        from fastapi import HTTPException
        if not isinstance(e, HTTPException):
            logger.error(f"Database transaction error: {e}")
        raise
    finally:
        if db:
            db.close()


def get_db_sync() -> Session:
    """
    Synchronous database session getter for use in scripts and background tasks.
    
    Note: This does NOT auto-commit or auto-rollback.
    Caller must manage transactions explicitly.
    """
    return SessionLocal()


def check_db_connection() -> bool:
    """
    Check if database connection is healthy.
    
    Returns:
        True if connection is healthy, False otherwise
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"Database connection check failed: {e}")
        return False

