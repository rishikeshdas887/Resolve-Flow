"""Dashboard metrics computed from persistent records — never hardcoded."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    AgentRun,
    ApprovalRequest,
    ApprovalStatus,
    KnowledgeChunk,
    KnowledgeDocument,
    RunStatus,
    Ticket,
    TicketStatus,
)
from app.schemas.dashboard import DashboardSummary


def _count_by(db: Session, column) -> dict[str, int]:
    rows = db.execute(select(column, func.count()).group_by(column)).all()
    return {(k.value if hasattr(k, "value") else str(k)): v for k, v in rows}


def dashboard_summary(db: Session) -> DashboardSummary:
    tickets_total = db.scalar(select(func.count(Ticket.id))) or 0
    by_status = _count_by(db, Ticket.status)
    by_priority = _count_by(db, Ticket.priority)
    by_category = _count_by(db, Ticket.category)
    open_tickets = db.scalar(
        select(func.count(Ticket.id)).where(
            Ticket.status.notin_([TicketStatus.resolved])
        )
    ) or 0
    resolved = by_status.get(TicketStatus.resolved.value, 0)

    runs_total = db.scalar(select(func.count(AgentRun.id))) or 0
    runs_by_status = _count_by(db, AgentRun.status)
    day_ago = datetime.now(timezone.utc) - timedelta(hours=24)
    runs_24h = db.scalar(
        select(func.count(AgentRun.id)).where(
            AgentRun.status == RunStatus.completed,
            AgentRun.finished_at >= day_ago,
        )
    ) or 0
    avg_dur = db.scalar(
        select(func.avg(AgentRun.duration_ms)).where(AgentRun.duration_ms.isnot(None))
    )
    pending_approvals = db.scalar(
        select(func.count(ApprovalRequest.id)).where(
            ApprovalRequest.status == ApprovalStatus.pending
        )
    ) or 0
    docs = db.scalar(select(func.count(KnowledgeDocument.id))) or 0
    chunks = db.scalar(select(func.count(KnowledgeChunk.id))) or 0

    return DashboardSummary(
        tickets_total=tickets_total,
        tickets_by_status=by_status,
        tickets_by_priority=by_priority,
        tickets_by_category=by_category,
        open_tickets=open_tickets,
        runs_total=runs_total,
        runs_by_status=runs_by_status,
        runs_completed_24h=runs_24h,
        avg_run_duration_ms=round(float(avg_dur), 1) if avg_dur is not None else None,
        pending_approvals=pending_approvals,
        resolved_tickets=resolved,
        resolution_rate=round(resolved / tickets_total, 4) if tickets_total else None,
        knowledge_documents=docs,
        knowledge_chunks=chunks,
    )
