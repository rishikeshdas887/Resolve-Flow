from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    source_uri: str | None
    doc_type: str
    status: str
    checksum: str
    error: str | None
    created_at: datetime


class ChunkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    chunk_index: int
    content: str
    token_estimate: int
    has_embedding: bool = False


class DocumentDetail(DocumentOut):
    chunk_count: int = 0
