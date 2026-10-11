"""Typed state for the agent workflow. Must stay JSON-serializable for checkpoints."""
from typing import TypedDict


class AgentState(TypedDict, total=False):
    ticket_id: str
    run_id: str
    subject: str
    body: str
    category: str | None
    priority: str | None
    missing_information: list[str]
    evidence: list[dict]  # {id, chunk_id, document_id, document_title, score, excerpt}
    draft: dict  # response_text, cited_evidence_ids, action_type, params, wants_resolution, flags
    validation: dict  # citations_valid, invalid_citations, issues
    policy: dict  # decision, disposition, reasons, terminal_action, supporting_actions
    approval_id: str | None
    approval_decision: str | None
    disposition: str | None
    error: str | None
