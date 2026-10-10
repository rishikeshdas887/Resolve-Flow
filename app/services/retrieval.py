"""Evidence retrieval: pgvector cosine search with honest lexical fallback."""
from dataclasses import dataclass

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.logging import get_logger
from app.db.models import DocumentStatus, KnowledgeChunk, KnowledgeDocument
from app.services.embeddings import Embedder

logger = get_logger(__name__)


@dataclass
class RetrievedChunk:
    chunk_id: str
    document_id: str
    document_title: str
    rank: int
    score: float
    excerpt: str
    retrieval_mode: str  # "vector" | "lexical"


def _excerpt(content: str, limit: int = 500) -> str:
    return content[:limit]


def retrieve(
    db: Session,
    settings: Settings,
    embedder: Embedder,
    query: str,
    top_k: int | None = None,
) -> list[RetrievedChunk]:
    """Return the most relevant chunks for a query.

    Tries pgvector cosine similarity first; falls back to Postgres full-text
    lexical search when embeddings are unavailable (e.g. provider failure or
    documents ingested without embeddings). The retrieval mode is returned on
    each result and logged so callers never misrepresent lexical as semantic.
    """
    top_k = top_k or settings.retrieval_top_k
    top_k = min(top_k, settings.retrieval_max_chunks)

    chunks: list[RetrievedChunk] = []
    try:
        chunks = _vector_search(db, settings, embedder, query, top_k)
    except Exception as e:
        logger.warning("vector search failed (%s); falling back to lexical", e)

    if not chunks:
        chunks = _lexical_search(db, query, top_k)
    return chunks


def _vector_search(
    db: Session, settings: Settings, embedder: Embedder, query: str, top_k: int
) -> list[RetrievedChunk]:
    query_vec = embedder.embed([query])[0]
    distance = KnowledgeChunk.embedding.cosine_distance(query_vec)
    stmt = (
        select(KnowledgeChunk, KnowledgeDocument, distance.label("distance"))
        .join(KnowledgeDocument, KnowledgeChunk.document_id == KnowledgeDocument.id)
        .where(KnowledgeChunk.embedding.isnot(None))
        .where(KnowledgeDocument.status == DocumentStatus.ready)
        .order_by(distance)
        .limit(top_k)
    )
    results = []
    for rank, (chunk, doc, dist) in enumerate(db.execute(stmt).all(), start=1):
        score = max(0.0, 1.0 - float(dist))
        if score < settings.retrieval_min_score:
            continue
        results.append(
            RetrievedChunk(
                chunk_id=chunk.id,
                document_id=doc.id,
                document_title=doc.title,
                rank=rank,
                score=round(score, 4),
                excerpt=_excerpt(chunk.content),
                retrieval_mode="vector",
            )
        )
    return results


def _lexical_search(db: Session, query: str, top_k: int) -> list[RetrievedChunk]:
    ts_query = func.plainto_tsquery("english", query)
    rank_col = func.ts_rank(
        func.to_tsvector("english", KnowledgeChunk.content), ts_query
    )
    stmt = (
        select(KnowledgeChunk, KnowledgeDocument, rank_col.label("score"))
        .join(KnowledgeDocument, KnowledgeChunk.document_id == KnowledgeDocument.id)
        .where(KnowledgeDocument.status == DocumentStatus.ready)
        .where(func.to_tsvector("english", KnowledgeChunk.content).op("@@")(ts_query))
        .order_by(rank_col.desc())
        .limit(top_k)
    )
    results = [
        RetrievedChunk(
            chunk_id=chunk.id,
            document_id=doc.id,
            document_title=doc.title,
            rank=rank,
            score=round(float(score), 4),
            excerpt=_excerpt(chunk.content),
            retrieval_mode="lexical",
        )
        for rank, (chunk, doc, score) in enumerate(db.execute(stmt).all(), start=1)
    ]
    if results:
        return results
    # ILIKE fallback for short queries that FTS tokenizes away
    pattern = f"%{query[:200].strip()}%"
    if len(pattern) < 4:
        return []
    stmt = (
        select(KnowledgeChunk, KnowledgeDocument)
        .join(KnowledgeDocument, KnowledgeChunk.document_id == KnowledgeDocument.id)
        .where(KnowledgeDocument.status == DocumentStatus.ready)
        .where(KnowledgeChunk.content.ilike(text(":pat")))
        .params(pat=pattern)
        .limit(top_k)
    )
    return [
        RetrievedChunk(
            chunk_id=chunk.id,
            document_id=doc.id,
            document_title=doc.title,
            rank=rank,
            score=0.01,
            excerpt=_excerpt(chunk.content),
            retrieval_mode="lexical",
        )
        for rank, (chunk, doc) in enumerate(db.execute(stmt).all(), start=1)
    ]
