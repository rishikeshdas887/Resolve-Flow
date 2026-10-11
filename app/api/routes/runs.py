from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import require_staff
from app.core.errors import NotFoundError
from app.db.models import AgentRun, KnowledgeDocument, ProposedAction, RunEvidence, User
from app.db.session import get_db
from app.schemas.runs import EvidenceOut, ProposalOut, RunOut

router = APIRouter(prefix="/runs", tags=["runs"])


def _get_run_or_404(db: Session, run_id: str) -> AgentRun:
    run = db.get(AgentRun, run_id)
    if run is None:
        raise NotFoundError("Run not found")
    return run


@router.get("/{run_id}", response_model=RunOut)
def get_run(
    run_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_staff),
) -> RunOut:
    return RunOut.model_validate(_get_run_or_404(db, run_id))


@router.get("/{run_id}/evidence", response_model=list[EvidenceOut])
def run_evidence(
    run_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_staff),
) -> list[EvidenceOut]:
    run = _get_run_or_404(db, run_id)
    rows = db.execute(
        select(RunEvidence, KnowledgeDocument.title)
        .join(KnowledgeDocument, RunEvidence.document_id == KnowledgeDocument.id)
        .where(RunEvidence.run_id == run.id)
        .order_by(RunEvidence.rank)
    ).all()
    return [
        EvidenceOut(
            id=ev.id, run_id=ev.run_id, chunk_id=ev.chunk_id,
            document_id=ev.document_id, rank=ev.rank, score=ev.score,
            excerpt=ev.excerpt, document_title=title,
        )
        for ev, title in rows
    ]


@router.get("/{run_id}/proposal", response_model=list[ProposalOut])
def run_proposal(
    run_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_staff),
) -> list[ProposalOut]:
    run = _get_run_or_404(db, run_id)
    actions = db.execute(
        select(ProposedAction)
        .where(ProposedAction.run_id == run.id)
        .order_by(ProposedAction.created_at)
    ).scalars().all()
    return [
        ProposalOut(
            action_id=a.id, run_id=a.run_id, ticket_id=a.ticket_id,
            action_type=a.action_type, params=a.params,
            policy_decision=a.policy_decision.value,
            policy_reasons=a.policy_reasons, status=a.status.value,
            result=a.result, draft_response=a.draft_response,
            cited_evidence_ids=a.cited_evidence_ids,
            created_at=a.created_at, executed_at=a.executed_at,
        )
        for a in actions
    ]
