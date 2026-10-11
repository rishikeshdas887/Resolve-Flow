from tests.conftest import create_ticket, start_run


def test_create_and_get_ticket(client, agent_headers):
    t = create_ticket(client, agent_headers)
    got = client.get(f"/api/v1/tickets/{t['id']}", headers=agent_headers)
    assert got.status_code == 200
    assert got.json()["subject"] == "Help"
    assert got.json()["status"] == "new"


def test_create_ticket_validation(client, agent_headers):
    r = client.post("/api/v1/tickets", json={"subject": "", "body": "x"}, headers=agent_headers)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_failed"


def test_list_pagination_and_filters(client, agent_headers):
    for i in range(25):
        create_ticket(client, agent_headers, subject=f"t{i}", body=f"body{i}")
    page1 = client.get("/api/v1/tickets?page=1&size=10", headers=agent_headers).json()
    assert page1["total"] == 25 and len(page1["items"]) == 10 and page1["pages"] == 3
    page3 = client.get("/api/v1/tickets?page=3&size=10", headers=agent_headers).json()
    assert len(page3["items"]) == 5
    f = client.get("/api/v1/tickets?status=new", headers=agent_headers).json()
    assert f["total"] == 25
    f = client.get("/api/v1/tickets?status=resolved", headers=agent_headers).json()
    assert f["total"] == 0
    f = client.get("/api/v1/tickets?q=t1", headers=agent_headers).json()
    assert f["total"] >= 1


def test_size_bound(client, agent_headers):
    r = client.get("/api/v1/tickets?size=500", headers=agent_headers)
    assert r.status_code == 422


def test_customer_sees_only_own_tickets(client, agent_headers, customer_headers, customer_user, agent_user):
    own = create_ticket(client, customer_headers, subject="mine")
    other = create_ticket(client, agent_headers, subject="not mine")
    mine = client.get("/api/v1/tickets", headers=customer_headers).json()
    ids = [t["id"] for t in mine["items"]]
    assert own["id"] in ids and other["id"] not in ids
    # object-level: customer cannot fetch someone else's ticket (404, no existence leak)
    assert client.get(f"/api/v1/tickets/{other['id']}", headers=customer_headers).status_code == 404


def test_customer_cannot_use_staff_endpoints(client, customer_headers):
    assert client.get("/api/v1/dashboard/summary", headers=customer_headers).status_code == 403
    assert client.get("/api/v1/approvals", headers=customer_headers).status_code == 403


def test_idempotent_ticket_create(client, agent_headers):
    body = {"subject": "dup", "body": "same request"}
    r1 = client.post("/api/v1/tickets", json=body, headers={**agent_headers, "Idempotency-Key": "k1"})
    r2 = client.post("/api/v1/tickets", json=body, headers={**agent_headers, "Idempotency-Key": "k1"})
    assert r1.status_code == 201 and r2.status_code == 201
    assert r1.json()["id"] == r2.json()["id"]


def test_idempotent_run_start(client, agent_headers):
    t = create_ticket(client, agent_headers)
    h = {**agent_headers, "Idempotency-Key": "run-1"}
    r1 = client.post(f"/api/v1/tickets/{t['id']}/runs", headers=h)
    r2 = client.post(f"/api/v1/tickets/{t['id']}/runs", headers=h)
    assert r1.json()["id"] == r2.json()["id"]


def test_second_active_run_conflict(client, agent_headers):
    t = create_ticket(client, agent_headers)
    start_run(client, agent_headers, t["id"])
    r = client.post(f"/api/v1/tickets/{t['id']}/runs", headers=agent_headers)
    assert r.status_code == 409


def test_patch_safe_fields(client, agent_headers):
    t = create_ticket(client, agent_headers)
    r = client.patch(
        f"/api/v1/tickets/{t['id']}",
        json={"priority": "high", "assigned_queue": "billing"}, headers=agent_headers,
    )
    assert r.status_code == 200
    assert r.json()["priority"] == "high" and r.json()["assigned_queue"] == "billing"
    r = client.patch(f"/api/v1/tickets/{t['id']}", json={"status": "resolved"}, headers=agent_headers)
    assert r.json()["status"] != "resolved" or r.status_code == 422  # status is not client-writable


def test_events_endpoint_reflects_changes(client, agent_headers):
    t = create_ticket(client, agent_headers)
    ev = client.get(f"/api/v1/tickets/{t['id']}/events", headers=agent_headers).json()
    assert any(e["event_type"] == "ticket_received" for e in ev["items"])


def test_ticket_not_found(client, agent_headers):
    r = client.get("/api/v1/tickets/nonexistent", headers=agent_headers)
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"
