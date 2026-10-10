"""Knowledge ingestion: validate -> extract -> chunk -> persist -> embed."""
import hashlib
import re
import unicodedata

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import ValidationFailedError
from app.db.models import DocumentStatus, KnowledgeChunk, KnowledgeDocument
from app.services.embeddings import Embedder

ALLOWED_EXTENSIONS = {".txt": "text", ".md": "markdown", ".markdown": "markdown"}
CHUNK_TARGET_CHARS = 1200
CHUNK_OVERLAP_CHARS = 200
MAX_CHUNKS_PER_DOC = 200


def detect_doc_type(filename: str) -> str:
    lower = filename.lower()
    for ext, kind in ALLOWED_EXTENSIONS.items():
        if lower.endswith(ext):
            return kind
    raise ValidationFailedError(
        f"Unsupported file type for {filename!r}; allowed: {sorted(ALLOWED_EXTENSIONS)}"
    )


def extract_text(data: bytes, doc_type: str, filename: str) -> str:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as e:
        raise ValidationFailedError(
            f"File {filename!r} is not valid UTF-8 text"
        ) from e
    # Normalize and strip control characters except whitespace
    text = unicodedata.normalize("NFC", text)
    text = "".join(ch for ch in text if ch == "\n" or ch == "\t" or not unicodedata.category(ch).startswith("C"))
    if not text.strip():
        raise ValidationFailedError(f"File {filename!r} contains no usable text")
    return text


def chunk_text(text: str) -> list[str]:
    """Deterministic paragraph-aware chunking with bounded size and overlap."""
    paragraphs = re.split(r"\n\s*\n", text)
    chunks: list[str] = []
    current = ""
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        candidate = f"{current}\n\n{para}".strip() if current else para
        if len(candidate) <= CHUNK_TARGET_CHARS:
            current = candidate
        else:
            if current:
                chunks.append(current)
            while len(para) > CHUNK_TARGET_CHARS:
                chunks.append(para[:CHUNK_TARGET_CHARS])
                para = para[CHUNK_TARGET_CHARS - CHUNK_OVERLAP_CHARS :]
            current = para
    if current:
        chunks.append(current)
    return chunks[:MAX_CHUNKS_PER_DOC]


def ingest_document(
    db: Session,
    settings: Settings,
    embedder: Embedder,
    title: str,
    filename: str,
    data: bytes,
    source_uri: str | None = None,
    created_by_id: str | None = None,
) -> KnowledgeDocument:
    if len(data) > settings.max_upload_bytes:
        raise ValidationFailedError(
            f"Upload exceeds maximum size of {settings.max_upload_bytes} bytes"
        )
    doc_type = detect_doc_type(filename)
    text = extract_text(data, doc_type, filename)
    checksum = hashlib.sha256(data).hexdigest()

    doc = KnowledgeDocument(
        title=title.strip() or filename,
        source_uri=source_uri,
        doc_type=doc_type,
        status=DocumentStatus.pending,
        checksum=checksum,
        created_by_id=created_by_id,
    )
    db.add(doc)
    db.flush()

    try:
        chunks = chunk_text(text)
        texts = [c for c in chunks]
        embeddings: list[list[float]] | None = None
        try:
            embeddings = embedder.embed(texts)
        except Exception as e:  # embedding failure must not lose the document
            embeddings = None
            doc.error = f"embedding_failed: {type(e).__name__}"
        for i, content in enumerate(chunks):
            db.add(
                KnowledgeChunk(
                    document_id=doc.id,
                    chunk_index=i,
                    content=content,
                    token_estimate=len(content) // 4,
                    embedding=embeddings[i] if embeddings else None,
                )
            )
        doc.status = DocumentStatus.ready
    except Exception as e:
        doc.status = DocumentStatus.failed
        doc.error = str(e)[:1000]
        raise
    return doc


def reprocess_document(
    db: Session, embedder: Embedder, doc: KnowledgeDocument
) -> KnowledgeDocument:
    """Re-embed existing chunks (e.g., after provider change)."""
    for chunk in doc.chunks:
        try:
            chunk.embedding = embedder.embed([chunk.content])[0]
        except Exception as e:
            doc.error = f"embedding_failed: {type(e).__name__}"
            return doc
    doc.error = None
    doc.status = DocumentStatus.ready
    return doc
