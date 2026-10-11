"""Durable run worker.

Claims queued agent_runs rows with SELECT ... FOR UPDATE SKIP LOCKED (safe
under multiple concurrent workers), executes the LangGraph workflow, persists
outcome, and retries transient failures with bounded attempts + backoff.

Approval resume: when an approval is granted, the API requeues the run; the
worker detects the persisted LangGraph checkpoint interrupt and resumes the
graph with the reviewer decision.
"""
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from langgraph.checkpoint.postgres import PostgresSaver
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.deps import AgentDeps
from app.agent.graph import pg_conn_string, run_workflow_once
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.db.models import (
    AgentRun,
    ApprovalRequest,
    ApprovalStatus,
    RunDisposition,
    RunStatus,
    Ticket,
    TicketStatus,
)
from app.db.session import make_session_factory
from app.services.audit import record_event
from app.services.embeddings import get_embedder
from app.services.llm import LLMError, get_llm_provider
from app.services.tickets import transition_ticket

logger = get_logger(__name__)

TERMINAL_DISPOSITIONS = {
    "resolved": RunDisposition.resolved,
    "needs_information": RunDisposition.needs_information,
    "pending_approval": RunDisposition.pending_approval,
    "escalated": RunDisposition.escalated,
    "failed": RunDisposition.failed,
}


def claim_next_run(db: Session) -> AgentRun | None:
    stmt = (
        select(AgentRun)
        .where(AgentRun.status == RunStatus.queued)
        .where(
            (AgentRun.next_retry_at.is_(None))
            | (AgentRun.next_retry_at <= datetime.now(timezone.utc))
        )
        .order_by(AgentRun.queued_at)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    run = db.execute(stmt).scalar_one_or_none()
    if run:
        run.status = RunStatus.running
        run.attempt += 1
        run.started_at = datetime.now(timezone.utc)
        db.commit()
    return run


def recover_stale_runs(db: Session, settings) -> int:
    """Requeue runs stuck in 'running' (e.g. after a worker crash mid-run).

    Node side effects are idempotent, so re-executing the graph on the same
    thread is safe. Runs past max_attempts are failed and their ticket
    escalated — never left silently stuck."""
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=settings.run_stale_seconds)
    stale = db.execute(
        select(AgentRun)
        .where(AgentRun.status == RunStatus.running)
        .where(AgentRun.started_at < cutoff)
        .with_for_update(skip_locked=True)
    ).scalars().all()
    for run in stale:
        ticket = db.get(Ticket, run.ticket_id)
        if run.attempt >= run.max_attempts:
            run.status = RunStatus.failed
            run.disposition = RunDisposition.failed
            run.error = "exceeded max attempts (stale run recovery)"
            run.finished_at = datetime.now(timezone.utc)
            if ticket is not None:
                try:
                    transition_ticket(
                        db, ticket, TicketStatus.escalated,
                        reason="agent run exceeded max attempts",
                    )
                except Exception:
                    logger.exception("could not escalate ticket %s", ticket.id)
        else:
            run.status = RunStatus.queued
            run.next_retry_at = datetime.now(timezone.utc)
            run.error = f"recovered stale run after attempt {run.attempt}"
            if ticket is not None:
                record_event(
                    db, ticket.id, "run_recovered",
                    {"attempt": run.attempt}, run_id=run.id,
                )
    if stale:
        db.commit()
    return len(stale)


def _pending_decision(db: Session, run: AgentRun) -> dict | None:
    """If this run is resuming after approval, return the decision payload."""
    approval = db.execute(
        select(ApprovalRequest).where(ApprovalRequest.run_id == run.id)
    ).scalar_one_or_none()
    if approval and approval.status == ApprovalStatus.approved:
        return {"decision": "approved", "reviewer_id": approval.reviewer_id}
    if approval and approval.status == ApprovalStatus.rejected:
        return {"decision": "rejected", "reviewer_id": approval.reviewer_id}
    return None


def process_run(
    run_id: str,
    session_factory,
    checkpointer,
    settings,
    deps: AgentDeps,
) -> AgentRun:
    """Process a single claimed run. Separable from the claim loop so tests
    can call it synchronously."""
    db: Session = session_factory()
    try:
        run = db.get(AgentRun, run_id)
        if run is None:
            raise RuntimeError(f"run {run_id} disappeared")
        resume = _pending_decision(db, run)
        ticket = db.get(Ticket, run.ticket_id)
        try:
            final, interrupted = run_workflow_once(
                deps,
                checkpointer,
                ticket_id=run.ticket_id,
                run_id=run.id,
                thread_id=run.langgraph_thread_id,
                resume_decision=resume,
            )
        except Exception as e:
            _handle_failure(db, run, ticket, e, settings)
            db.commit()
            return run

        if interrupted:
            # Paused on a persisted interrupt (approval required).
            run.status = RunStatus.awaiting_approval
            run.disposition = RunDisposition.pending_approval
            run.error = None
            db.commit()
            return run

        disposition = final.get("disposition") or "failed"
        run.disposition = TERMINAL_DISPOSITIONS.get(disposition, RunDisposition.failed)
        run.error = final.get("error")
        run.finished_at = datetime.now(timezone.utc)
        run.duration_ms = int(
            (run.finished_at - run.started_at).total_seconds() * 1000
        ) if run.started_at else None
        run.status = RunStatus.completed
        db.commit()
        return run
    finally:
        db.close()


def _handle_failure(db: Session, run: AgentRun, ticket: Ticket | None, exc: Exception, settings) -> None:
    retryable = isinstance(exc, LLMError) and exc.retryable
    if run.attempt < run.max_attempts and retryable:
        run.status = RunStatus.queued
        run.next_retry_at = datetime.now(timezone.utc) + timedelta(
            seconds=settings.run_retry_backoff_seconds * run.attempt
        )
        run.error = f"retryable failure attempt {run.attempt}: {type(exc).__name__}"
    else:
        run.status = RunStatus.failed
        run.disposition = RunDisposition.failed
        run.error = f"{type(exc).__name__}: {exc}"[:1000]
        run.finished_at = datetime.now(timezone.utc)
        if ticket is not None and ticket.status in (
            TicketStatus.processing,
            TicketStatus.new,
            TicketStatus.needs_information,
        ):
            try:
                transition_ticket(
                    db, ticket, TicketStatus.escalated, reason="agent run failed"
                )
            except Exception:
                logger.exception("could not escalate ticket %s after run failure", ticket.id)
        if ticket is not None:
            record_event(
                db, ticket.id, "run_failed", {"error": run.error[:500]}, run_id=run.id
            )
    logger.error("run %s failed: %s", run.id, run.error)


@contextmanager
def make_deps(settings=None):
    settings = settings or get_settings()
    configure_logging()
    session_factory = make_session_factory(settings.database_url)
    deps = AgentDeps(
        settings=settings,
        session_factory=session_factory,
        llm=get_llm_provider(settings),
        embedder=get_embedder(settings),
    )
    yield deps, session_factory


def run_worker(poll_seconds: float | None = None, max_runs: int | None = None) -> int:
    settings = get_settings()
    settings.validate_runtime()
    poll = poll_seconds or settings.worker_poll_seconds
    processed = 0
    with make_deps(settings) as (deps, session_factory):
        with PostgresSaver.from_conn_string(pg_conn_string(settings.database_url)) as checkpointer:
            checkpointer.setup()
            logger.info("worker started provider=%s", deps.llm.name)
            while True:
                db = session_factory()
                try:
                    recover_stale_runs(db, settings)
                    run = claim_next_run(db)
                finally:
                    db.close()
                if run is None:
                    if max_runs is not None and processed >= max_runs:
                        break
                    time.sleep(poll)
                    continue
                process_run(run.id, session_factory, checkpointer, settings, deps)
                processed += 1
                if max_runs is not None and processed >= max_runs:
                    break
    return processed


if __name__ == "__main__":
    runs = run_worker()
    sys.exit(0 if runs >= 0 else 1)
