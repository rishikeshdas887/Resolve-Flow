"""Action executor — the only place side effects happen.

Every action changes real persistent state inside the caller's transaction.
Execution is guarded by the ProposedAction row's status + a row lock so a
retry can never execute the same action twice.
"""
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, ForbiddenError
from app.db.models import (
    ActionStatus,
    AgentRun,
    ApprovalRequest,
    ApprovalStatus,
    PolicyDecision,
    ProposedAction,
    RunDisposition,
    RunStatus,
    Ticket,
    TicketStatus,
)
from app.services.audit import record_event
from app.services.tickets import transition_ticket

EXECUTABLE_ACTIONS = {
    "resolve_ticket",
    "send_response_and_resolve",
    "request_information",
    "add_tag",
    "assign_queue",
    "add_internal_note",
    "escalate_to_human",
}


def create_action(
    db: Session,
    run: AgentRun,
    ticket: Ticket,
    action_type: str,
    params: dict,
    policy_decision: str,
    policy_reasons: list[str],
    draft_response: str | None = None,
    cited_evidence_ids: list[str] | None = None,
) -> ProposedAction:
    action = ProposedAction(
        run_id=run.id,
        ticket_id=ticket.id,
        action_type=action_type,
        params=params,
        policy_decision=PolicyDecision(policy_decision),
        policy_reasons=policy_reasons,
        draft_response=draft_response,
        cited_evidence_ids=cited_evidence_ids or [],
    )
    db.add(action)
    db.flush()
    return action


def _lock_action(db: Session, action_id: str) -> ProposedAction:
    action = db.execute(
        select(ProposedAction).where(ProposedAction.id == action_id).with_for_update()
    ).scalar_one()
    return action


def execute_action(
    db: Session,
    action_id: str,
    actor_type: str = "system",
    actor_id: str | None = None,
) -> ProposedAction:
    """Execute a proposed action exactly once. Idempotent: if the action is
    already executed, returns the stored result without side effects."""
    action = _lock_action(db, action_id)
    if action.status == ActionStatus.executed:
        return action  # retry-safe: no duplicate side effects
    if action.status in (ActionStatus.rejected, ActionStatus.failed):
        raise ConflictError(
            f"Action {action_id} is {action.status.value} and cannot be executed"
        )
    if action.action_type not in EXECUTABLE_ACTIONS:
        action.status = ActionStatus.failed
        action.result = {"error": f"action type {action.action_type} is not executable"}
        raise ForbiddenError(f"Action type {action.action_type} is not executable")

    ticket = db.get(Ticket, action.ticket_id)
    if ticket is None:
        action.status = ActionStatus.failed
        action.result = {"error": "ticket missing"}
        raise ConflictError("Ticket for action no longer exists")

    try:
        result = _apply(db, ticket, action, actor_type, actor_id)
    except ConflictError:
        raise
    except Exception as e:
        action.status = ActionStatus.failed
        action.result = {"error": f"{type(e).__name__}: {e}"[:500]}
        record_event(
            db, ticket.id, "action_failed", {"action_type": action.action_type, "error": str(e)[:300]},
            run_id=action.run_id,
        )
        raise

    action.status = ActionStatus.executed
    action.result = result
    action.executed_at = datetime.now(timezone.utc)
    record_event(
        db, ticket.id, "action_executed",
        {"action_type": action.action_type, "result_summary": str(result)[:300]},
        run_id=action.run_id, actor_type=actor_type, actor_id=actor_id,
    )
    return action


def _apply(
    db: Session, ticket: Ticket, action: ProposedAction, actor_type: str, actor_id: str | None
) -> dict:
    t = action.action_type
    if t == "resolve_ticket":
        transition_ticket(
            db, ticket, TicketStatus.resolved, reason="agent resolution",
            actor_type=actor_type, actor_id=actor_id,
        )
        if action.draft_response:
            record_event(
                db, ticket.id, "response_posted",
                {"response": action.draft_response[:2000]}, run_id=action.run_id,
            )
        return {"resolved": True}
    if t == "send_response_and_resolve":
        if not action.draft_response:
            raise ConflictError("send_response_and_resolve requires a draft response")
        record_event(
            db, ticket.id, "response_posted", {"response": action.draft_response[:2000]},
            run_id=action.run_id, actor_type=actor_type, actor_id=actor_id,
        )
        transition_ticket(
            db, ticket, TicketStatus.resolved,
            reason="response sent after approval", actor_type=actor_type, actor_id=actor_id,
        )
        return {"response_posted": True, "resolved": True}
    if t == "request_information":
        note = str(action.params.get("note") or action.draft_response or "Additional information is required.")
        transition_ticket(
            db, ticket, TicketStatus.needs_information,
            reason="agent requested information", actor_type=actor_type, actor_id=actor_id,
        )
        record_event(db, ticket.id, "information_requested", {"request": note[:2000]}, run_id=action.run_id)
        return {"information_requested": True}
    if t == "add_tag":
        tag = str(action.params.get("tag", "")).strip()
        tags = list(ticket.tags or [])
        if tag and tag not in tags:
            tags.append(tag)
            ticket.tags = tags
        record_event(db, ticket.id, "tag_added", {"tag": tag}, run_id=action.run_id)
        return {"tags": tags}
    if t == "assign_queue":
        queue = str(action.params.get("queue", "")).strip()
        ticket.assigned_queue = queue
        record_event(db, ticket.id, "queue_assigned", {"queue": queue}, run_id=action.run_id)
        return {"assigned_queue": queue}
    if t == "add_internal_note":
        note = str(action.params.get("note") or action.draft_response or "")
        record_event(
            db, ticket.id, "internal_note", {"note": note[:2000]},
            run_id=action.run_id, actor_type=actor_type, actor_id=actor_id,
        )
        return {"note_recorded": True}
    if t == "escalate_to_human":
        reason = "; ".join(action.policy_reasons) or "escalated"
        transition_ticket(
            db, ticket, TicketStatus.escalated, reason=reason[:500],
            actor_type=actor_type, actor_id=actor_id,
        )
        record_event(
            db, ticket.id, "escalated",
            {"reason": reason[:1000], "cited_evidence_ids": action.cited_evidence_ids or []},
            run_id=action.run_id,
        )
        return {"escalated": True, "reason": reason}
    raise ForbiddenError(f"Unknown action {t}")


def request_approval(
    db: Session,
    action: ProposedAction,
    run: AgentRun,
    ticket: Ticket,
    reason: str,
) -> ApprovalRequest:
    """Persist a pending approval for the action; guarantee nothing executed."""
    existing = db.execute(
        select(ApprovalRequest).where(ApprovalRequest.action_id == action.id)
    ).scalar_one_or_none()
    if existing:
        return existing
    if action.status == ActionStatus.executed:
        raise ConflictError("Action already executed; cannot request approval")
    action.status = ActionStatus.pending_approval
    approval = ApprovalRequest(
        ticket_id=ticket.id, run_id=run.id, action_id=action.id, reason=reason[:2000]
    )
    db.add(approval)
    record_event(
        db, ticket.id, "approval_requested", {"approval_reason": reason[:500]},
        run_id=run.id,
    )
    db.flush()
    return approval


def decide_approval(
    db: Session,
    approval: ApprovalRequest,
    reviewer_id: str,
    approve: bool,
    note: str | None,
) -> ApprovalRequest:
    """Record a reviewer decision. Execution happens on run resume, not here."""
    approval = db.execute(
        select(ApprovalRequest).where(ApprovalRequest.id == approval.id).with_for_update()
    ).scalar_one()
    if approval.status != ApprovalStatus.pending:
        raise ConflictError(f"Approval {approval.id} already {approval.status.value}")
    approval.status = ApprovalStatus.approved if approve else ApprovalStatus.rejected
    approval.reviewer_id = reviewer_id
    approval.decision_note = note
    approval.decided_at = datetime.now(timezone.utc)

    action = _lock_action(db, approval.action_id)
    run = db.get(AgentRun, approval.run_id)
    ticket = db.get(Ticket, approval.ticket_id)
    if not approve:
        action.status = ActionStatus.rejected
        if run and run.status == RunStatus.awaiting_approval:
            run.status = RunStatus.completed
            run.disposition = RunDisposition.escalated
            run.finished_at = datetime.now(timezone.utc)
        if ticket and ticket.status == TicketStatus.pending_approval:
            transition_ticket(
                db, ticket, TicketStatus.escalated, reason="approval rejected",
                actor_type="user", actor_id=reviewer_id,
            )
        record_event(
            db, approval.ticket_id, "approval_rejected", {"note": (note or "")[:500]},
            run_id=approval.run_id, actor_type="user", actor_id=reviewer_id,
        )
    else:
        # Revalidate state before allowing resume: the ticket must still be
        # awaiting this decision and the run must still be paused on it.
        if ticket is None or ticket.status != TicketStatus.pending_approval:
            raise ConflictError("Ticket is no longer awaiting this approval")
        if run is None or run.status != RunStatus.awaiting_approval:
            raise ConflictError("Run is no longer awaiting approval")
        record_event(
            db, approval.ticket_id, "approval_granted", {"note": (note or "")[:500]},
            run_id=approval.run_id, actor_type="user", actor_id=reviewer_id,
        )
        # Requeue the run so the worker resumes it from the LangGraph checkpoint.
        run.status = RunStatus.queued
        run.next_retry_at = None
    return approval
