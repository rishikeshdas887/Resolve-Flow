from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ApprovalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    ticket_id: str
    run_id: str
    action_id: str
    reason: str
    status: str
    reviewer_id: str | None
    decision_note: str | None
    decided_at: datetime | None
    created_at: datetime
    run_status: str | None = None
    ticket_status: str | None = None
    is_actionable: bool = True
    stale_reason: str | None = None


class ApprovalDecision(BaseModel):
    note: str | None = Field(default=None, max_length=2000)
