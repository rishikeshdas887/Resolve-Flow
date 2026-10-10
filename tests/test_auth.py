from tests.conftest import auth, login


def test_login_success_and_me(client, admin_user):
    token = login(client, admin_user.email)
    me = client.get("/api/v1/auth/me", headers=auth(token))
    assert me.status_code == 200
    assert me.json()["email"] == admin_user.email
    assert me.json()["role"] == "admin"


def test_login_wrong_password(client, admin_user):
    r = client.post("/api/v1/auth/login", json={"email": admin_user.email, "password": "wrong"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthorized"


def test_login_unknown_email(client):
    r = client.post("/api/v1/auth/login", json={"email": "nobody@example.com", "password": "x"})
    assert r.status_code == 401


def test_missing_token(client):
    r = client.get("/api/v1/tickets")
    assert r.status_code == 401


def test_invalid_token(client):
    r = client.get("/api/v1/tickets", headers=auth("not-a-jwt"))
    assert r.status_code == 401


def test_inactive_user_rejected(client, db, agent_user):
    token = login(client, agent_user.email)
    agent_user.is_active = False
    db.commit()
    r = client.get("/api/v1/auth/me", headers=auth(token))
    assert r.status_code == 401


def test_admin_can_create_user(client, admin_headers, db):
    r = client.post(
        "/api/v1/auth/users",
        json={"email": "new@example.com", "full_name": "New", "password": "Password123!", "role": "customer"},
        headers=admin_headers,
    )
    assert r.status_code == 201
    assert r.json()["role"] == "customer"


def test_agent_cannot_create_user(client, agent_headers):
    r = client.post(
        "/api/v1/auth/users",
        json={"email": "x@example.com", "full_name": "X", "password": "Password123!", "role": "admin"},
        headers=agent_headers,
    )
    assert r.status_code == 403


def test_password_not_in_user_response(client, admin_headers):
    r = client.get("/api/v1/auth/me", headers=admin_headers)
    assert "password" not in r.text.lower() and "hash" not in r.text.lower()
