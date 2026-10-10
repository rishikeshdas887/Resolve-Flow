from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import Pagination, require_approver, require_staff
from app.core.errors import NotFoundError
from app.db.models import ApprovalRequest, ApprovalStatus, User
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


@router.get("", response_model=Page[ApprovalOut])
def list_approvals(
    db: Session = Depends(get_db),
    user: User = Depends(require_staff),
    pagination: Pagination = Depends(),
    status_filter: str | None = Query(default=None, alias="status"),
) -> Page[ApprovalOut]:
    stmt = select(ApprovalRequest)
    if status_filter:
        stmt = stmt.where(ApprovalRequest.status == ApprovalStatus(status_filter))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = db.execute(
        stmt.order_by(ApprovalRequest.created_at.desc())
        .offset(pagination.offset).limit(pagination.size)
    ).scalars().all()
    return make_page(
        [ApprovalOut.model_validate(a) for a in items],
        total, pagination.page, pagination.size,
    )


@router.get("/{approval_id}", response_model=ApprovalOut)
def get_approval(
    approval_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_staff),
) -> ApprovalOut:
    return ApprovalOut.model_validate(_approval_or_404(db, approval_id))


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
    return ApprovalOut.model_validate(ap)


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
    return ApprovalOut.model_validate(ap)
