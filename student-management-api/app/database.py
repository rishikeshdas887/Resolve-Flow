"""SQLite engine, session configuration, and the database dependency.

The default database file lives next to this package (``student-management-api/students.db``)
so its location never depends on the directory the server was started from. Set the
``STUDENT_DATABASE_URL`` environment variable to point at a different database.
(A dedicated name is used so a generic ``DATABASE_URL`` exported for another
project can never redirect this app.)
"""

import os
from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DATABASE_URL = f"sqlite:///{BASE_DIR / 'students.db'}"

DATABASE_URL = os.environ.get("STUDENT_DATABASE_URL", DEFAULT_DATABASE_URL)

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def init_db() -> None:
    """Create tables that do not exist yet. Never drops or resets data."""
    # Import models so they are registered on Base.metadata before create_all.
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)


def get_db() -> Iterator[Session]:
    """FastAPI dependency yielding a session that is always closed.

    Tests override this dependency with a session bound to a temporary
    database, so no test ever touches the development database file.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
