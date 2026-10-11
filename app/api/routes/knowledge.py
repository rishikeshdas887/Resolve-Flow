from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.deps import Pagination, require_admin, require_staff
from app.core.errors import ConflictError, NotFoundError, ValidationFailedError
from app.db.models import DocumentStatus, KnowledgeChunk, KnowledgeDocument, User
from app.db.session import get_db
from app.schemas.common import Page, make_page
from app.schemas.knowledge import ChunkOut, DocumentDetail, DocumentOut
from app.services.embeddings import get_embedder
from app.services.knowledge import ingest_document, reprocess_document

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


def _doc_or_404(db: Session, doc_id: str) -> KnowledgeDocument:
    doc = db.get(KnowledgeDocument, doc_id)
    if doc is None:
        raise NotFoundError("Document not found")
    return doc


@router.post(
    "/documents", response_model=DocumentOut, status_code=status.HTTP_201_CREATED
)
async def upload_document(
    file: UploadFile = File(...),
    title: str | None = Query(default=None, max_length=500),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(require_staff),
) -> DocumentOut:
    filename = file.filename or "upload.txt"
    data = await file.read(settings.max_upload_bytes + 1)
    if not data:
        raise ValidationFailedError("Uploaded file is empty")
    doc = ingest_document(
        db, settings, get_embedder(settings),
        title=title or filename, filename=filename, data=data,
        created_by_id=user.id,
    )
    db.commit()
    return DocumentOut.model_validate(doc)


@router.get("/documents", response_model=Page[DocumentOut])
def list_documents(
    db: Session = Depends(get_db),
    user: User = Depends(require_staff),
    pagination: Pagination = Depends(),
    status_filter: str | None = Query(default=None, alias="status"),
) -> Page[DocumentOut]:
    stmt = select(KnowledgeDocument)
    if status_filter:
        try:
            stmt = stmt.where(KnowledgeDocument.status == DocumentStatus(status_filter))
        except ValueError as e:
            raise ConflictError(f"Unknown status filter: {status_filter}") from e
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = db.execute(
        stmt.order_by(KnowledgeDocument.created_at.desc())
        .offset(pagination.offset).limit(pagination.size)
    ).scalars().all()
    return make_page(
        [DocumentOut.model_validate(d) for d in items],
        total, pagination.page, pagination.size,
    )


@router.get("/documents/{doc_id}", response_model=DocumentDetail)
def get_document(
    doc_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_staff),
) -> DocumentDetail:
    doc = _doc_or_404(db, doc_id)
    out = DocumentDetail.model_validate(doc)
    out.chunk_count = db.scalar(
        select(func.count(KnowledgeChunk.id)).where(KnowledgeChunk.document_id == doc.id)
    ) or 0
    return out


@router.get("/documents/{doc_id}/chunks", response_model=list[ChunkOut])
def get_document_chunks(
    doc_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_staff),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[ChunkOut]:
    doc = _doc_or_404(db, doc_id)
    chunks = db.execute(
        select(KnowledgeChunk)
        .where(KnowledgeChunk.document_id == doc.id)
        .order_by(KnowledgeChunk.chunk_index)
        .limit(limit)
    ).scalars().all()
    return [
        ChunkOut(
            id=c.id, chunk_index=c.chunk_index, content=c.content,
            token_estimate=c.token_estimate, has_embedding=c.embedding is not None,
        )
        for c in chunks
    ]


@router.post("/documents/{doc_id}/reprocess", response_model=DocumentOut)
def reprocess(
    doc_id: str,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(require_staff),
) -> DocumentOut:
    doc = _doc_or_404(db, doc_id)
    reprocess_document(db, get_embedder(settings), doc)
    db.commit()
    return DocumentOut.model_validate(doc)


@router.delete("/documents/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    doc_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
) -> None:
    doc = _doc_or_404(db, doc_id)
    db.delete(doc)
    db.commit()
