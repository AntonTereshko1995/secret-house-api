from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from config import settings
import db.models  # noqa: F401 — registers all ORM models with SQLAlchemy metadata

engine = create_engine(settings.database_url, echo=settings.debug)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a DB session."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
