import uuid

from fastapi import APIRouter, Depends, Header, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import Pagination, get_current_user, require_staff
from app.core.errors import ConflictError, NotFoundError
from app.db.models import (
    AgentRun,
    IdempotencyRecord,
    Role,
    RunStatus,
    Ticket,
    TicketCategory,
    TicketEvent,
    TicketPriority,
    TicketStatus,
    User,
)
from app.db.session import get_db
from app.schemas.common import Page, make_page
from app.schemas.events import EventOut
from app.schemas.runs import RunOut
from app.schemas.tickets import TicketCreate, TicketOut, TicketUpdate
from app.services.audit import record_event

router = APIRouter(prefix="/tickets", tags=["tickets"])

ACTIVE_RUN_STATUSES = {RunStatus.queued, RunStatus.running, RunStatus.awaiting_approval}


def _get_ticket_or_404(db: Session, ticket_id: str, user: User) -> Ticket:
    ticket = db.get(Ticket, ticket_id)
    if ticket is None:
        raise NotFoundError("Ticket not found")
    # Object-level authorization: customers may only see their own tickets.
    if user.role == Role.customer and ticket.created_by_id != user.id:
        raise NotFoundError("Ticket not found")
    return ticket


def _idempotent_replay(db: Session, scope: str, key: str | None, user_id: str):
    if not key:
        return None
    return db.execute(
        select(IdempotencyRecord).where(
            IdempotencyRecord.scope == scope, IdempotencyRecord.key == key
        )
    ).scalar_one_or_none()


def _store_idempotent(db: Session, scope: str, key: str | None, user_id: str, status_code: int, body: dict):
    if not key:
        return
    db.add(
        IdempotencyRecord(
            scope=scope, key=key, user_id=user_id,
            response_status=status_code, response_body=body,
        )
    )


@router.post("", response_model=TicketOut, status_code=status.HTTP_201_CREATED)
def create_ticket(
    body: TicketCreate,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TicketOut:
    scope = f"ticket:{user.id}"
    replay = _idempotent_replay(db, scope, idempotency_key, user.id)
    if replay is not None:
        return TicketOut.model_validate(replay.response_body)

    ticket = Ticket(
        subject=body.subject.strip(),
        body=body.body,
        requester_email=str(body.requester_email) if body.requester_email else None,
        created_by_id=user.id,
        idempotency_key=idempotency_key,
    )
    if body.priority:
        ticket.priority = TicketPriority(body.priority)
    db.add(ticket)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        existing = db.execute(
            select(Ticket).where(
                Ticket.created_by_id == user.id,
                Ticket.idempotency_key == idempotency_key,
            )
        ).scalar_one_or_none()
        if existing:
            return TicketOut.model_validate(existing)
        raise
    record_event(
        db, ticket.id, "ticket_received", {"subject": ticket.subject[:200]},
        actor_type="user", actor_id=user.id,
    )
    db.commit()
    out = TicketOut.model_validate(ticket)
    _store_idempotent(db, scope, idempotency_key, user.id, 201, out.model_dump(mode="json"))
    db.commit()
    return out


@router.get("", response_model=Page[TicketOut])
def list_tickets(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    pagination: Pagination = Depends(),
    status_filter: str | None = Query(default=None, alias="status"),
    category: str | None = Query(default=None),
    priority: str | None = Query(default=None),
    q: str | None = Query(default=None, max_length=200),
) -> Page[TicketOut]:
    stmt = select(Ticket)
    if user.role == Role.customer:
        stmt = stmt.where(Ticket.created_by_id == user.id)
    if status_filter:
        try:
            stmt = stmt.where(Ticket.status == TicketStatus(status_filter))
        except ValueError as e:
            raise ConflictError(f"Unknown status filter: {status_filter}") from e
    if category:
        try:
            stmt = stmt.where(Ticket.category == TicketCategory(category))
        except ValueError as e:
            raise ConflictError(f"Unknown category filter: {category}") from e
    if priority:
        try:
            stmt = stmt.where(Ticket.priority == TicketPriority(priority))
        except ValueError as e:
            raise ConflictError(f"Unknown priority filter: {priority}") from e
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Ticket.subject.ilike(like), Ticket.body.ilike(like)))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = db.execute(
        stmt.order_by(Ticket.created_at.desc())
        .offset(pagination.offset)
        .limit(pagination.size)
    ).scalars().all()
    return make_page(
        [TicketOut.model_validate(t) for t in items], total, pagination.page, pagination.size
    )


@router.get("/{ticket_id}", response_model=TicketOut)
def get_ticket(
    ticket_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TicketOut:
    ticket = _get_ticket_or_404(db, ticket_id, user)
    return TicketOut.model_validate(ticket)


@router.patch("/{ticket_id}", response_model=TicketOut)
def update_ticket(
    ticket_id: str,
    body: TicketUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_staff),
) -> TicketOut:
    ticket = _get_ticket_or_404(db, ticket_id, user)
    data = body.model_dump(exclude_unset=True)
    if "subject" in data and data["subject"] is not None:
        ticket.subject = data["subject"].strip()
    if "body" in data and data["body"] is not None:
        ticket.body = data["body"]
    if "priority" in data and data["priority"] is not None:
        ticket.priority = TicketPriority(data["priority"])
    if "assigned_queue" in data:
        ticket.assigned_queue = data["assigned_queue"]
    record_event(db, ticket.id, "ticket_updated", {"fields": sorted(data.keys())}, actor_type="user", actor_id=user.id)
    db.commit()
    return TicketOut.model_validate(ticket)


@router.get("/{ticket_id}/events", response_model=Page[EventOut])
def ticket_events(
    ticket_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_staff),
    pagination: Pagination = Depends(),
) -> Page[EventOut]:
    ticket = _get_ticket_or_404(db, ticket_id, user)
    stmt = select(TicketEvent).where(TicketEvent.ticket_id == ticket.id)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = db.execute(
        stmt.order_by(TicketEvent.created_at.asc())
        .offset(pagination.offset)
        .limit(pagination.size)
    ).scalars().all()
    return make_page(
        [EventOut.model_validate(e) for e in items], total, pagination.page, pagination.size
    )


@router.post(
    "/{ticket_id}/runs", response_model=RunOut, status_code=status.HTTP_201_CREATED
)
def start_run(
    ticket_id: str,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    user: User = Depends(require_staff),
) -> RunOut:
    ticket = _get_ticket_or_404(db, ticket_id, user)
    if idempotency_key:
        existing = db.execute(
            select(AgentRun).where(
                AgentRun.ticket_id == ticket.id,
                AgentRun.idempotency_key == idempotency_key,
            )
        ).scalar_one_or_none()
        if existing:
            return RunOut.model_validate(existing)
    active = db.execute(
        select(AgentRun).where(
            AgentRun.ticket_id == ticket.id,
            AgentRun.status.in_(list(ACTIVE_RUN_STATUSES)),
        )
    ).scalar_one_or_none()
    if active:
        raise ConflictError(
            f"Ticket already has an active run ({active.id}, status {active.status.value})"
        )
    if ticket.status == TicketStatus.resolved:
        raise ConflictError("Ticket is already resolved; reopen via a new ticket update first")
    run = AgentRun(
        ticket_id=ticket.id,
        langgraph_thread_id=f"run-{uuid.uuid4()}",
        idempotency_key=idempotency_key,
        max_attempts=get_settings().run_max_attempts,
        provider=get_settings().effective_llm_provider,
    )
    db.add(run)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        existing = db.execute(
            select(AgentRun).where(
                AgentRun.ticket_id == ticket.id,
                AgentRun.idempotency_key == idempotency_key,
            )
        ).scalar_one_or_none()
        if existing:
            return RunOut.model_validate(existing)
        raise
    record_event(db, ticket.id, "run_queued", {"run_id": run.id}, run_id=run.id, actor_type="user", actor_id=user.id)
    db.commit()
    return RunOut.model_validate(run)


@router.get("/{ticket_id}/runs", response_model=Page[RunOut])
def list_runs(
    ticket_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_staff),
    pagination: Pagination = Depends(),
) -> Page[RunOut]:
    ticket = _get_ticket_or_404(db, ticket_id, user)
    stmt = select(AgentRun).where(AgentRun.ticket_id == ticket.id)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = db.execute(
        stmt.order_by(AgentRun.queued_at.desc())
        .offset(pagination.offset)
        .limit(pagination.size)
    ).scalars().all()
    return make_page(
        [RunOut.model_validate(r) for r in items], total, pagination.page, pagination.size
    )


@router.get("/{ticket_id}/status-history")
def status_history(
    ticket_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_staff),
) -> dict:
    from app.db.models import TicketStatusHistory

    ticket = _get_ticket_or_404(db, ticket_id, user)
    items = db.execute(
        select(TicketStatusHistory)
        .where(TicketStatusHistory.ticket_id == ticket.id)
        .order_by(TicketStatusHistory.created_at.asc())
    ).scalars().all()
    return {
        "items": [
            {
                "from_status": h.from_status,
                "to_status": h.to_status,
                "reason": h.reason,
                "actor_type": h.actor_type,
                "created_at": h.created_at.isoformat(),
            }
            for h in items
        ]
    }
