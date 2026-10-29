"""
Database engine and session management supporting SQLite and PostgreSQL via SQLAlchemy.
"""
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.config import settings
from app.models.db_models import Base
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Configure connect_args for SQLite
connect_args = {}
if settings.database_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Create all tables in the database."""
    logger.info("Initializing database tables on %s", settings.database_url)
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables initialized successfully")
    except Exception as exc:
        logger.error("Failed to initialize database tables: %s", exc)
        raise


def get_db_session() -> Generator[Session, None, None]:
    """FastAPI dependency for yielding database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def close_db():
    """Dispose of engine connections on shutdown."""
    engine.dispose()
    logger.info("Database engine disposed")

