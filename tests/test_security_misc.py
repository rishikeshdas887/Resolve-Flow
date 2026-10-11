"""Cross-cutting: error schema, state machine, CORS, size limits, Slack signature."""
import hashlib
import hmac
import time

from app.db.models import TicketStatus
from app.integrations.slack import verify_slack_signature
from app.services.tickets import ALLOWED_TRANSITIONS, transition_ticket
from tests.conftest import auth, create_ticket


def test_error_shape_consistent(client):
    for r in (
        client.get("/api/v1/tickets"),
        client.get("/api/v1/nope", headers=auth("x")),
        client.post("/api/v1/auth/login", json={"email": "bad"}),
    ):
        assert "error" in r.json()
        assert "code" in r.json()["error"]


def test_no_stack_trace_on_404(client, agent_headers):
    r = client.get("/api/v1/tickets/missing", headers=agent_headers)
    assert "Traceback" not in r.text


def test_state_machine_transitions():
    for s in TicketStatus:
        assert s in ALLOWED_TRANSITIONS
    assert TicketStatus.resolved not in ALLOWED_TRANSITIONS[TicketStatus.new]


def test_invalid_transition_rejected(db, client, agent_headers):
    import pytest

    from app.core.errors import ConflictError

    t = create_ticket(client, agent_headers)
    from app.db.models import Ticket
    ticket = db.get(Ticket, t["id"])
    with pytest.raises(ConflictError):
        transition_ticket(db, ticket, TicketStatus.resolved)  # new -> resolved not allowed


def test_cors_preflight(client):
    r = client.options(
        "/api/v1/tickets",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST"},
    )
    assert r.headers.get("access-control-allow-origin")


def test_request_size_limit(client, agent_headers):
    r = client.post("/api/v1/tickets", content=b"x" * (3 * 1024 * 1024),
                    headers={**agent_headers, "Content-Type": "application/json"})
    assert r.status_code == 413


def test_slack_signature_verify():
    secret = "testsecret"
    ts = str(int(time.time()))
    body = b'{"type":"url_verification"}'
    base = f"v0:{ts}:{body.decode()}".encode()
    sig = "v0=" + hmac.new(secret.encode(), base, hashlib.sha256).hexdigest()
    assert verify_slack_signature(secret, ts, body, sig)
    assert not verify_slack_signature(secret, ts, body, "v0=deadbeef")
    assert not verify_slack_signature(secret, str(int(time.time()) - 10000), body, sig)


def test_dashboard_counts(client, agent_headers):
    create_ticket(client, agent_headers)
    r = client.get("/api/v1/dashboard/summary", headers=agent_headers)
    assert r.status_code == 200
    assert r.json()["tickets_total"] >= 1


def test_health_endpoints(client):
    assert client.get("/health/live").status_code == 200
    assert client.get("/health/ready").status_code == 200


def test_openapi_has_versioned_paths(client):
    spec = client.get("/openapi.json").json()
    paths = list(spec["paths"].keys())
    assert any(p.startswith("/api/v1/tickets") for p in paths)
    assert any(p.startswith("/api/v1/approvals") for p in paths)
    assert "title" in spec["info"]
