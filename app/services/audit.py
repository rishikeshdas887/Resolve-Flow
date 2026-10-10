"""Append-only audit events for tickets. Details must be pre-sanitized."""
from sqlalchemy.orm import Session

from app.core.logging import redact
from app.db.models import TicketEvent


def _sanitize_detail(detail: dict) -> dict:
    out = {}
    for k, v in detail.items():
        key_lower = k.lower()
        if any(s in key_lower for s in ("secret", "password", "token", "api_key", "authorization")):
            out[k] = "[REDACTED]"
        elif isinstance(v, str):
            out[k] = redact(v[:2000])
        else:
            out[k] = v
    return out


def record_event(
    db: Session,
    ticket_id: str,
    event_type: str,
    detail: dict | None = None,
    run_id: str | None = None,
    actor_type: str = "system",
    actor_id: str | None = None,
) -> TicketEvent:
    ev = TicketEvent(
        ticket_id=ticket_id,
        run_id=run_id,
        actor_type=actor_type,
        actor_id=actor_id,
        event_type=event_type,
        detail=_sanitize_detail(detail or {}),
    )
    db.add(ev)
    return ev
