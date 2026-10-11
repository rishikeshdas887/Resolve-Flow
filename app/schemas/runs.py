from datetime import datetime

from pydantic import BaseModel, ConfigDict


class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    ticket_id: str
    status: str
    disposition: str | None
    provider: str | None
    attempt: int
    error: str | None
    queued_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    duration_ms: int | None


class EvidenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    run_id: str
    chunk_id: str
    document_id: str
    rank: int
    score: float
    excerpt: str
    document_title: str | None = None


class ProposalOut(BaseModel):
    """What the agent proposed and what deterministic policy decided."""

    action_id: str
    run_id: str
    ticket_id: str
    action_type: str
    params: dict
    policy_decision: str
    policy_reasons: list[str]
    status: str
    result: dict | None
    draft_response: str | None
    cited_evidence_ids: list[str] | None
    created_at: datetime
    executed_at: datetime | None
