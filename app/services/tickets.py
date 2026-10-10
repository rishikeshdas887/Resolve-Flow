"""Ticket state machine — the single source of truth for valid transitions."""
from sqlalchemy.orm import Session

from app.core.errors import ConflictError
from app.db.models import (
    Ticket,
    TicketCategory,
    TicketPriority,
    TicketStatus,
    TicketStatusHistory,
)

# Valid status transitions. Anything not listed is rejected centrally.
ALLOWED_TRANSITIONS: dict[TicketStatus, set[TicketStatus]] = {
    TicketStatus.new: {TicketStatus.processing, TicketStatus.escalated},
    TicketStatus.processing: {
        TicketStatus.resolved,
        TicketStatus.needs_information,
        TicketStatus.pending_approval,
        TicketStatus.escalated,
        TicketStatus.new,  # run failed and was requeued/failed -> back to new
    },
    TicketStatus.pending_approval: {
        TicketStatus.processing,  # resumed after decision
        TicketStatus.resolved,
        TicketStatus.escalated,
        TicketStatus.needs_information,
    },
    TicketStatus.needs_information: {TicketStatus.processing, TicketStatus.escalated},
    TicketStatus.escalated: {TicketStatus.processing, TicketStatus.resolved},
    TicketStatus.resolved: {TicketStatus.processing},  # reopen -> new run
}


def transition_ticket(
    db: Session,
    ticket: Ticket,
    to_status: TicketStatus,
    reason: str | None = None,
    actor_type: str = "system",
    actor_id: str | None = None,
) -> None:
    """Transition a ticket with validation + status-history record.

    Caller is responsible for committing the surrounding transaction.
    """
    current = ticket.status
    if current == to_status:
        return
    if to_status not in ALLOWED_TRANSITIONS.get(current, set()):
        raise ConflictError(
            f"Invalid ticket status transition: {current.value} -> {to_status.value}",
            {"ticket_id": ticket.id, "from": current.value, "to": to_status.value},
        )
    db.add(
        TicketStatusHistory(
            ticket_id=ticket.id,
            from_status=current.value,
            to_status=to_status.value,
            reason=reason,
            actor_type=actor_type,
            actor_id=actor_id,
        )
    )
    ticket.status = to_status
    if to_status == TicketStatus.resolved:
        from datetime import datetime, timezone

        ticket.resolved_at = datetime.now(timezone.utc)


def set_classification(
    ticket: Ticket, category: str | None, priority: str | None
) -> None:
    if category:
        ticket.category = TicketCategory(category)
    if priority:
        ticket.priority = TicketPriority(priority)
