"""Synchronous SQLAlchemy engine/session.

One coherent sync strategy: the whole app uses sync SQLAlchemy. FastAPI runs
sync route functions and dependencies in its threadpool, so requests remain
non-blocking without mixing sync/async ORM patterns.
"""
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()

engine = create_engine(settings.database_url, pool_pre_ping=True, pool_size=5, max_overflow=5)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def make_session_factory(url: str) -> sessionmaker:
    """Independent session factory (used by the worker / tests / eval script)."""
    eng = create_engine(url, pool_pre_ping=True)
    return sessionmaker(bind=eng, autoflush=False, expire_on_commit=False)
