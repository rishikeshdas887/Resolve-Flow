"""Dependencies injected into the graph via closure (build-time DI)."""
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.services.embeddings import Embedder
from app.services.llm import LLMProvider


@dataclass
class AgentDeps:
    settings: Settings
    session_factory: Callable[[], Session]
    llm: LLMProvider
    embedder: Embedder

    @contextmanager
    def session(self):
        db = self.session_factory()
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
