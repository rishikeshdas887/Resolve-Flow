from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class TicketCreate(BaseModel):
    subject: str = Field(min_length=1, max_length=500)
    body: str = Field(min_length=1, max_length=20_000)
    requester_email: EmailStr | None = None
    priority: str | None = Field(default=None, pattern="^(low|medium|high|urgent)$")


class TicketUpdate(BaseModel):
    """Only safe, manually editable fields. Status changes flow through runs/approvals."""

    subject: str | None = Field(default=None, min_length=1, max_length=500)
    body: str | None = Field(default=None, min_length=1, max_length=20_000)
    priority: str | None = Field(default=None, pattern="^(low|medium|high|urgent)$")
    assigned_queue: str | None = Field(default=None, max_length=100)


class TicketOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    subject: str
    body: str
    requester_email: str | None
    status: str
    category: str | None
    priority: str
    assigned_queue: str | None
    created_by_id: str | None
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None
