from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import Pagination, require_approver, require_staff
from app.core.errors import ConflictError, NotFoundError
from app.db.models import AgentRun, ApprovalRequest, ApprovalStatus, RunStatus, Ticket, TicketStatus, User
from app.db.session import get_db
from app.schemas.approvals import ApprovalDecision, ApprovalOut
from app.schemas.common import Page, make_page
from app.services.actions import decide_approval

router = APIRouter(prefix="/approvals", tags=["approvals"])


def _approval_or_404(db: Session, approval_id: str) -> ApprovalRequest:
    ap = db.get(ApprovalRequest, approval_id)
    if ap is None:
        raise NotFoundError("Approval not found")
    return ap


def _enrich_approval_out(db: Session, a: ApprovalRequest) -> ApprovalOut:
    run = db.get(AgentRun, a.run_id)
    ticket = db.get(Ticket, a.ticket_id)
    run_status = run.status.value if run else None
    ticket_status = ticket.status.value if ticket else None
    stale_reason = None
    if a.status == ApprovalStatus.pending:
        if ticket is None or ticket.status != TicketStatus.pending_approval:
            stale_reason = f"Ticket is {ticket_status or 'missing'} (not pending approval)"
        elif run is None or run.status != RunStatus.awaiting_approval:
            stale_reason = f"Run is {run_status or 'missing'} (not awaiting approval)"
    is_actionable = a.status == ApprovalStatus.pending and stale_reason is None
    return ApprovalOut(
        id=a.id,
        ticket_id=a.ticket_id,
        run_id=a.run_id,
        action_id=a.action_id,
        reason=a.reason,
        status=a.status.value,
        reviewer_id=a.reviewer_id,
        decision_note=a.decision_note,
        decided_at=a.decided_at,
        created_at=a.created_at,
        run_status=run_status,
        ticket_status=ticket_status,
        is_actionable=is_actionable,
        stale_reason=stale_reason,
    )


@router.get("", response_model=Page[ApprovalOut])
def list_approvals(
    db: Session = Depends(get_db),
    user: User = Depends(require_staff),
    pagination: Pagination = Depends(),
    status_filter: str | None = Query(default=None, alias="status"),
) -> Page[ApprovalOut]:
    stmt = select(ApprovalRequest)
    if status_filter:
        try:
            stmt = stmt.where(ApprovalRequest.status == ApprovalStatus(status_filter))
        except ValueError as e:
            raise ConflictError(f"Unknown status filter: {status_filter}") from e
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = db.execute(
        stmt.order_by(ApprovalRequest.created_at.desc())
        .offset(pagination.offset).limit(pagination.size)
    ).scalars().all()
    return make_page(
        [_enrich_approval_out(db, a) for a in items],
        total, pagination.page, pagination.size,
    )


@router.get("/{approval_id}", response_model=ApprovalOut)
def get_approval(
    approval_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_staff),
) -> ApprovalOut:
    return _enrich_approval_out(db, _approval_or_404(db, approval_id))


@router.post("/{approval_id}/approve", response_model=ApprovalOut)
def approve(
    approval_id: str,
    body: ApprovalDecision | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_approver),
) -> ApprovalOut:
    ap = _approval_or_404(db, approval_id)
    decide_approval(db, ap, reviewer_id=user.id, approve=True, note=body.note if body else None)
    db.commit()
    return _enrich_approval_out(db, ap)


@router.post("/{approval_id}/reject", response_model=ApprovalOut)
def reject(
    approval_id: str,
    body: ApprovalDecision | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_approver),
) -> ApprovalOut:
    ap = _approval_or_404(db, approval_id)
    decide_approval(db, ap, reviewer_id=user.id, approve=False, note=body.note if body else None)
    db.commit()
    return _enrich_approval_out(db, ap)
