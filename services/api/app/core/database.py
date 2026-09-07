from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from app.core.config import settings

# SQLAlchemy engine: the connection pool to PostgreSQL.
# pool_pre_ping ensures stale connections are detected and replaced.
engine = create_engine(settings.database_url, pool_pre_ping=True)

# SessionLocal: one factory for creating DB sessions.
# Each request gets its own session (see get_db below).
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base: every ORM model will inherit from this so SQLAlchemy
# knows how to map Python classes to database tables.
Base = declarative_base()


def get_db():
    """FastAPI dependency: opens one DB session per request, closes it after."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
