"""Embedding providers.

`deterministic` is a hashing-trick embedder used for tests and offline demos.
It encodes lexical token overlap only — it is NOT a semantic model and results
must be described as such.
`openai` calls the configured OpenAI embedding model and is only used when
OPENAI_API_KEY is configured.
"""
import hashlib
import math
import re
from typing import Protocol

from app.core.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_TOKEN_RE = re.compile(r"[a-z0-9]+")


class Embedder(Protocol):
    name: str
    dim: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class DeterministicEmbedder:
    """Hashing-trick bag-of-words embedder (lexical overlap, not semantic)."""

    name = "deterministic-hashing"

    def __init__(self, dim: int = 256):
        self.dim = dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            vec = [0.0] * self.dim
            for token in _TOKEN_RE.findall(text.lower()):
                h = int.from_bytes(
                    hashlib.sha256(token.encode()).digest()[:4], "big"
                )
                vec[h % self.dim] += 1.0
            norm = math.sqrt(sum(x * x for x in vec)) or 1.0
            vectors.append([x / norm for x in vec])
        return vectors


class OpenAIEmbedder:
    name = "openai"

    def __init__(self, settings: Settings):
        from openai import OpenAI

        self._client = OpenAI(
            api_key=settings.openai_api_key, timeout=settings.openai_timeout_seconds
        )
        self._model = settings.openai_embedding_model
        self.dim = settings.embedding_dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        resp = self._client.embeddings.create(model=self._model, input=texts)
        return [list(d.embedding) for d in resp.data]


def get_embedder(settings: Settings) -> Embedder:
    provider = settings.effective_embedding_provider
    if provider == "openai":
        return OpenAIEmbedder(settings)
    if provider != "deterministic":
        logger.warning("unknown embedding provider %s; using deterministic", provider)
    return DeterministicEmbedder(dim=settings.embedding_dim)
