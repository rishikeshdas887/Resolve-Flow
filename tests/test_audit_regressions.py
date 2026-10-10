"""Regression tests for defects found in the final audit."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.db.models import (
    ActionStatus,
    AgentRun,
    ApprovalRequest,
    ApprovalStatus,
    RunStatus,
    Ticket,
    TicketStatus,
)
from app.services.tickets import transition_ticket
from tests.conftest import create_ticket, ingest_doc, process_queued, start_run

REFUND_DOC = """# Refund Policy
Refunds are available within 30 days of purchase for digital orders. To request a
refund, reply to your order confirmation email with the order number.
"""

SHIPPING_DOC = """# Shipping Guide
Track your order with the tracking link sent when the order ships. Your package
delivery takes 1-2 business days. If the package arrived but is missing, report
the delivery as lost and we resend the order.
"""


def _pending_approval_ticket(client, agent_headers, db, settings, deps, checkpointer):
    ingest_doc(db, settings, content=REFUND_DOC)
    t = create_ticket(
        client, agent_headers, subject="Refund policy question",
        body="What is your refund policy for order RF-77889900?",
    )
    start_run(client, agent_headers, t["id"])
    process_queued(settings, deps, checkpointer)
    db.expire_all()
    approval = db.execute(
        select(ApprovalRequest).order_by(ApprovalRequest.created_at.desc())
    ).scalars().first()
    return t, approval


def test_reprocess_needs_information_can_resolve(
    client, agent_headers, db, settings, deps, checkpointer
):
    """Audit fix: a needs_information ticket reprocessed after the missing
    info is supplied must be able to reach resolved (was: invalid transition
    needs_information -> resolved killed the run)."""
    ingest_doc(db, settings, content=SHIPPING_DOC)
    t = create_ticket(
        client, agent_headers, subject="Where is my package?",
        body="I ordered something and it hasn't arrived yet, when will my delivery come?",
    )
    start_run(client, agent_headers, t["id"])
    process_queued(settings, deps, checkpointer)
    db.expire_all()
    assert db.get(Ticket, t["id"]).status == TicketStatus.needs_information

    # Customer supplies the order number (staff records it), then reprocess.
    resp = client.patch(
        f"/api/v1/tickets/{t['id']}",
        json={"body": "My order RF-12345678 hasn't arrived, when will my delivery come?"},
        headers=agent_headers,
    )
    assert resp.status_code == 200, resp.text
    start_run(client, agent_headers, t["id"])
    process_queued(settings, deps, checkpointer)
    db.expire_all()
    ticket = db.get(Ticket, t["id"])
    run = db.execute(
        select(AgentRun).where(AgentRun.ticket_id == t["id"]).order_by(AgentRun.queued_at.desc())
    ).scalars().first()
    assert run.status == RunStatus.completed and run.disposition == "resolved"
    assert ticket.status == TicketStatus.resolved


def test_stale_run_recovery_requeues_and_completes(
    client, agent_headers, db, settings, deps, checkpointer, sf
):
    """Audit fix: a run stuck 'running' (worker crash) is recovered."""
    from app.worker import recover_stale_runs

    ingest_doc(db, settings)
    t = create_ticket(client, agent_headers)
    run_body = start_run(client, agent_headers, t["id"])
    run = db.get(AgentRun, run_body["id"])
    run.status = RunStatus.running
    run.attempt = 1
    run.started_at = datetime.now(timezone.utc) - timedelta(seconds=3600)
    db.commit()

    assert recover_stale_runs(db, settings) == 1
    assert run.status == RunStatus.queued

    process_queued(settings, deps, checkpointer)
    db.expire_all()
    run = db.get(AgentRun, run.id)
    assert run.status == RunStatus.completed


def test_stale_run_at_max_attempts_fails_and_escalates(
    client, agent_headers, db, settings, deps, checkpointer
):
    from app.worker import recover_stale_runs

    t = create_ticket(client, agent_headers)
    run_body = start_run(client, agent_headers, t["id"])
    run = db.get(AgentRun, run_body["id"])
    run.status = RunStatus.running
    run.attempt = run.max_attempts
    run.started_at = datetime.now(timezone.utc) - timedelta(seconds=3600)
    db.commit()

    assert recover_stale_runs(db, settings) == 1
    db.expire_all()
    assert db.get(AgentRun, run.id).status == RunStatus.failed
    assert db.get(Ticket, t["id"]).status == TicketStatus.escalated


def test_approve_after_ticket_left_pending_rejected(
    client, agent_headers, admin_headers, db, settings, deps, checkpointer
):
    """Audit fix: approving after the ticket left pending_approval returns a
    clean 409 instead of requeuing a doomed resume."""
    t, approval = _pending_approval_ticket(client, agent_headers, db, settings, deps, checkpointer)
    assert approval is not None and approval.status == ApprovalStatus.pending

    ticket = db.get(Ticket, t["id"])
    transition_ticket(db, ticket, TicketStatus.escalated, reason="manual escalation")
    db.commit()

    resp = client.post(
        f"/api/v1/approvals/{approval.id}/approve", headers=admin_headers
    )
    assert resp.status_code == 409, resp.text
    # Nothing executed: action still pending_approval, ticket still escalated.
    db.expire_all()
    assert db.get(Ticket, t["id"]).status == TicketStatus.escalated


def test_double_decision_conflict(
    client, agent_headers, admin_headers, db, settings, deps, checkpointer
):
    _t, approval = _pending_approval_ticket(client, agent_headers, db, settings, deps, checkpointer)
    first = client.post(f"/api/v1/approvals/{approval.id}/approve", headers=admin_headers)
    assert first.status_code == 200, first.text
    second = client.post(f"/api/v1/approvals/{approval.id}/reject", headers=admin_headers)
    assert second.status_code == 409, second.text
    db.expire_all()
    assert db.get(ApprovalRequest, approval.id).status == ApprovalStatus.approved
    action_status = db.execute(
        select(ApprovalRequest.action_id).where(ApprovalRequest.id == approval.id)
    ).scalar_one()
    from app.db.models import ProposedAction

    assert db.get(ProposedAction, action_status).status == ActionStatus.pending_approval


def test_invalid_status_filters_return_4xx(client, agent_headers):
    """Audit fix: invalid enum filter values must not produce a 500."""
    resp = client.get("/api/v1/approvals?status=bogus", headers=agent_headers)
    assert resp.status_code == 409, resp.text
    resp = client.get("/api/v1/knowledge/documents?status=bogus", headers=agent_headers)
    assert resp.status_code == 409, resp.text
    resp = client.get("/api/v1/tickets?status=bogus", headers=agent_headers)
    assert resp.status_code == 409, resp.text
