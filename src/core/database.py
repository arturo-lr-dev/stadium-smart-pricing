"""
Database configuration and session management.

This module provides database engine, session factory, and connection management
for the Smart Pricing system.
"""

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import Pool

from src.core.config import get_settings
from src.core.logging import get_logger

logger = get_logger(__name__)

# Declarative Base for SQLAlchemy models
Base = declarative_base()

# Global engine and session factory
_engine: Engine | None = None
_SessionLocal: sessionmaker | None = None


def get_database_url() -> str:
    """
    Construct database URL from settings.

    Returns:
        Database connection URL
    """
    settings = get_settings()
    return (
        f"postgresql://{settings.database.user}:{settings.database.password}"
        f"@{settings.database.host}:{settings.database.port}/{settings.database.name}"
    )


def create_db_engine() -> Engine:
    """
    Create and configure SQLAlchemy engine.

    Returns:
        Configured SQLAlchemy engine
    """
    settings = get_settings()
    database_url = get_database_url()

    engine = create_engine(
        database_url,
        pool_size=settings.database.pool_size,
        max_overflow=settings.database.max_overflow,
        pool_pre_ping=True,  # Verify connections before using
        pool_recycle=3600,   # Recycle connections after 1 hour
        echo=settings.database.echo,  # Log SQL statements if enabled
    )

    # Log connection pool events
    @event.listens_for(Pool, "connect")
    def receive_connect(dbapi_conn, connection_record):
        logger.debug("Database connection established")

    @event.listens_for(Pool, "checkout")
    def receive_checkout(dbapi_conn, connection_record, connection_proxy):
        logger.debug("Connection checked out from pool")

    logger.info(
        f"Database engine created: {settings.database.host}:{settings.database.port}/{settings.database.name}"
    )

    return engine


def get_engine() -> Engine:
    """
    Get or create the global database engine.

    Returns:
        SQLAlchemy engine instance
    """
    global _engine

    if _engine is None:
        _engine = create_db_engine()

    return _engine


def get_session_factory() -> sessionmaker:
    """
    Get or create the global session factory.

    Returns:
        SQLAlchemy sessionmaker
    """
    global _SessionLocal

    if _SessionLocal is None:
        engine = get_engine()
        _SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=engine,
        )
        logger.info("Session factory created")

    return _SessionLocal


def get_db_session() -> Session:
    """
    Create a new database session.

    This function should be used with dependency injection in FastAPI.

    Returns:
        SQLAlchemy Session instance
    """
    SessionLocal = get_session_factory()
    return SessionLocal()


@contextmanager
def get_db() -> Generator[Session, None, None]:
    """
    Context manager for database sessions.

    Provides automatic session cleanup and rollback on exceptions.

    Usage:
        with get_db() as db:
            # Use db session
            result = db.query(Model).all()

    Yields:
        Database session
    """
    db = get_db_session()
    try:
        yield db
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Database session error: {e}")
        raise
    finally:
        db.close()


def create_all_tables() -> None:
    """
    Create all tables defined in SQLAlchemy models.

    This should be used for initial setup or testing.
    In production, use Alembic migrations instead.
    """
    engine = get_engine()
    logger.info("Creating all database tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created successfully")


def drop_all_tables() -> None:
    """
    Drop all tables defined in SQLAlchemy models.

    WARNING: This will delete all data. Use with caution!
    """
    engine = get_engine()
    logger.warning("Dropping all database tables...")
    Base.metadata.drop_all(bind=engine)
    logger.warning("Database tables dropped")


def check_database_connection() -> bool:
    """
    Check if database connection is working.

    Returns:
        True if connection is successful, False otherwise
    """
    try:
        engine = get_engine()
        with engine.connect() as connection:
            connection.execute("SELECT 1")
        logger.info("Database connection check: OK")
        return True
    except Exception as e:
        logger.error(f"Database connection check failed: {e}")
        return False


def close_database_connection() -> None:
    """
    Close database engine and cleanup connections.

    Should be called on application shutdown.
    """
    global _engine, _SessionLocal

    if _engine is not None:
        _engine.dispose()
        _engine = None
        _SessionLocal = None
        logger.info("Database connections closed")
