"""Worker claiming, retry and restart-resumption tests."""

import pytest
from sqlalchemy import select

from app.db.models import AgentRun, ApprovalRequest, Ticket
from app.services.llm import LLMTimeoutError
from tests.conftest import (
    create_ticket,
    ingest_doc,
    process_queued,
    session_factory,
    start_run,
)


def test_claim_only_queued(sf, client, agent_headers, settings, db):
    t = create_ticket(client, agent_headers)
    run = start_run(client, agent_headers, t["id"])
    from app.worker import claim_next_run

    s = session_factory()
    claimed = claim_next_run(s)
    assert claimed.id == run["id"]
    # claimed -> running, not reclaimable
    assert claim_next_run(s) is None
    s.close()


def test_execute_action_idempotent(db, client, agent_headers):
    t = create_ticket(client, agent_headers)
    run = start_run(client, agent_headers, t["id"])
    ticket = db.get(Ticket, t["id"])
    run_obj = db.get(AgentRun, run["id"])
    from app.services.actions import create_action, execute_action

    action = create_action(db, run=run_obj, ticket=ticket, action_type="add_tag",
                           params={"tag": "auto-tagged"}, policy_decision="allow", policy_reasons=["test"])
    db.commit()
    first = execute_action(db, action.id)
    db.commit()
    second = execute_action(db, action.id)  # retry -> returns stored result
    db.commit()
    assert first.status == second.status == "executed"
    assert db.get(Ticket, t["id"]).tags == ["auto-tagged"]


def test_denied_action_cannot_execute(db, client, agent_headers):
    t = create_ticket(client, agent_headers)
    run = start_run(client, agent_headers, t["id"])
    ticket = db.get(Ticket, t["id"])
    run_obj = db.get(AgentRun, run["id"])
    from app.core.errors import ForbiddenError
    from app.services.actions import create_action, execute_action

    action = create_action(db, run=run_obj, ticket=ticket, action_type="refund_payment",
                           params={}, policy_decision="deny", policy_reasons=["test"])
    db.commit()
    with pytest.raises(ForbiddenError):
        execute_action(db, action.id)


def test_retryable_llm_error_requeues(sf, client, agent_headers, settings, checkpointer):
    class Flaky:
        name = "flaky"
        def classify_ticket(self, *a, **k):
            raise LLMTimeoutError("timeout")
        def draft_response(self, **k):
            raise LLMTimeoutError("timeout")

    from app.agent.deps import AgentDeps
    from app.services.embeddings import get_embedder

    deps = AgentDeps(settings=settings, session_factory=session_factory,
                     llm=Flaky(), embedder=get_embedder(settings))
    t = create_ticket(client, agent_headers)
    run = start_run(client, agent_headers, t["id"])
    r = process_queued(settings, deps, checkpointer)
    db = session_factory()
    r = db.get(AgentRun, run["id"])
    # retryable failure -> requeued (or failed after max attempts)
    assert r.status in ("queued", "failed")
    assert r.attempt >= 1
    db.close()


def test_permanent_failure_escalates(sf, client, agent_headers, settings, checkpointer):
    class Broken:
        name = "broken"
        def classify_ticket(self, *a, **k):
            raise ValueError("deterministic boom")
        def draft_response(self, **k):
            raise ValueError("deterministic boom")

    from app.agent.deps import AgentDeps
    from app.services.embeddings import get_embedder

    deps = AgentDeps(settings=settings, session_factory=session_factory,
                     llm=Broken(), embedder=get_embedder(settings))
    t = create_ticket(client, agent_headers)
    run = start_run(client, agent_headers, t["id"])
    process_queued(settings, deps, checkpointer)
    db = session_factory()
    r = db.get(AgentRun, run["id"])
    ticket = db.get(Ticket, t["id"])
    assert r.status == "failed"
    assert ticket.status == "escalated"
    db.close()


def test_restart_resumption(sf, client, agent_headers, admin_headers, db, settings, checkpointer):
    """Pause -> NEW checkpointer + graph instances (process restart) -> approve -> resume works."""
    ingest_doc(db, settings, title="refund", filename="r.md",
               content="Refunds are available within 30 days of purchase for digital orders. "
                       "To request a refund, reply to your order confirmation email with the order "
                       "number. The finance team reviews every request manually; approved refunds "
                       "are paid in 5-10 days.")
    t = create_ticket(
        client, agent_headers, subject="Refund policy question",
        body="What is your refund policy for order RF-12345678? Bought 10 days ago.",
    )
    start_run(client, agent_headers, t["id"])
    process_queued(settings, deps_for(settings), checkpointer)
    db.expire_all()
    run = db.execute(select(AgentRun).where(AgentRun.ticket_id == t["id"])).scalars().first()
    ap = db.execute(select(ApprovalRequest).where(ApprovalRequest.run_id == run.id)).scalars().one()
    assert run.status == "awaiting_approval"

    # Simulate process restart: brand-new checkpointer + deps
    from langgraph.checkpoint.postgres import PostgresSaver

    from app.agent.deps import AgentDeps
    from app.agent.graph import pg_conn_string
    from app.services.embeddings import get_embedder
    from app.services.llm import get_llm_provider

    client.post(f"/api/v1/approvals/{ap.id}/approve", json={}, headers=admin_headers)
    with PostgresSaver.from_conn_string(pg_conn_string(settings.database_url)) as cp2:
        cp2.setup()
        deps2 = AgentDeps(settings=settings, session_factory=session_factory,
                          llm=get_llm_provider(settings), embedder=get_embedder(settings))
        run2 = process_queued(settings, deps2, cp2)
        assert run2.status == "completed"
    db.expire_all()
    assert db.get(Ticket, t["id"]).status == "resolved"
    # exactly once: still exactly one executed send_response_and_resolve
    from app.db.models import ProposedAction

    acts = db.execute(
        select(ProposedAction).where(
            ProposedAction.run_id == run.id,
            ProposedAction.action_type == "send_response_and_resolve",
        )
    ).scalars().all()
    assert len(acts) == 1 and acts[0].status == "executed"


def deps_for(settings):
    from app.agent.deps import AgentDeps
    from app.services.embeddings import get_embedder
    from app.services.llm import get_llm_provider
    return AgentDeps(settings=settings, session_factory=session_factory,
                     llm=get_llm_provider(settings), embedder=get_embedder(settings))


def test_worker_ignores_eval_runs(sf, client, agent_headers, settings, db):
    """Worker claim and stale recovery must ignore in-process evaluation runs (eval-*)."""
    from datetime import datetime, timedelta, timezone

    from app.db.models import AgentRun, RunStatus
    from app.worker import claim_next_run, recover_stale_runs

    t = create_ticket(client, agent_headers)
    s = session_factory()
    eval_run = AgentRun(
        ticket_id=t["id"],
        status=RunStatus.queued,
        langgraph_thread_id="eval-test-thread-isolation",
        provider="deterministic",
    )
    s.add(eval_run)
    s.commit()

    # Worker claim should skip queued runs belonging to eval runner
    assert claim_next_run(s) is None

    # Stale run recovery should skip eval runs that are running
    eval_run.status = RunStatus.running
    eval_run.started_at = datetime.now(timezone.utc) - timedelta(seconds=settings.run_stale_seconds + 60)
    s.commit()

    recovered = recover_stale_runs(s, settings)
    assert recovered == 0
    s.close()

