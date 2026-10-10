"""Shared test fixtures. Requires a PostgreSQL test database:
createdb resolveflow_test && DATABASE_URL=... alembic upgrade head
Default URL points at the docker-compose test db (port 55432).
"""
import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://resolveflow:localdev@localhost:55432/resolveflow_test",
)

os.environ["DATABASE_URL"] = TEST_DB_URL
os.environ["LLM_PROVIDER"] = "deterministic"
os.environ["EMBEDDING_PROVIDER"] = "deterministic"

from app.core.config import get_settings  # noqa: E402
from app.db.session import make_session_factory  # noqa: E402

get_settings.cache_clear()
session_factory = make_session_factory(TEST_DB_URL)

TABLES = [
    "ticket_events", "ticket_status_history", "run_evidence",
    "proposed_actions", "approval_requests", "agent_runs",
    "eval_results", "eval_runs", "idempotency_records",
    "knowledge_chunks", "knowledge_documents", "tickets", "users",
    "checkpoints", "checkpoint_blobs", "checkpoint_writes", "checkpoint_migrations",
]


@pytest.fixture(autouse=True)
def clean_db():
    db = session_factory()
    try:
        existing = {r[0] for r in db.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        )}
        targets = [t for t in TABLES if t in existing]
        if targets:
            db.execute(text("TRUNCATE TABLE " + ", ".join(f'"{t}"' for t in targets) + " CASCADE"))
        db.commit()
    finally:
        db.close()
    yield


@pytest.fixture()
def db():
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def settings():
    s = get_settings()
    s.llm_provider = "deterministic"
    s.embedding_provider = "deterministic"
    return s


@pytest.fixture()
def checkpointer():
    from langgraph.checkpoint.postgres import PostgresSaver

    from app.agent.graph import pg_conn_string

    with PostgresSaver.from_conn_string(pg_conn_string(TEST_DB_URL)) as cp:
        cp.setup()
        yield cp


@pytest.fixture()
def deps(settings, checkpointer):
    from app.agent.deps import AgentDeps
    from app.services.embeddings import get_embedder
    from app.services.llm import get_llm_provider

    return AgentDeps(
        settings=settings,
        session_factory=session_factory,
        llm=get_llm_provider(settings),
        embedder=get_embedder(settings),
    )


@pytest.fixture()
def client():
    from app.main import app

    return TestClient(app)


def make_user(db, email, role, password="Password123!"):
    from app.core.security import hash_password
    from app.db.models import Role, User

    u = User(
        id=str(uuid.uuid4()), email=email, full_name=email.split("@")[0],
        password_hash=hash_password(password), role=Role(role),
    )
    db.add(u)
    db.commit()
    return u


@pytest.fixture()
def admin_user(db):
    return make_user(db, "admin@example.com", "admin")


@pytest.fixture()
def agent_user(db):
    return make_user(db, "agent@example.com", "support_agent")


@pytest.fixture()
def customer_user(db):
    return make_user(db, "cust@example.com", "customer")


def login(client, email, password="Password123!"):
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def admin_headers(client, admin_user):
    return auth(login(client, admin_user.email))


@pytest.fixture()
def agent_headers(client, agent_user):
    return auth(login(client, agent_user.email))


@pytest.fixture()
def customer_headers(client, customer_user):
    return auth(login(client, customer_user.email))


def create_ticket(client, headers, subject="Help", body="I need help with my invoice billing receipt"):
    resp = client.post("/api/v1/tickets", json={"subject": subject, "body": body}, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


def start_run(client, headers, ticket_id):
    resp = client.post(f"/api/v1/tickets/{ticket_id}/runs", headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


def ingest_doc(db, settings, title="Doc", filename="doc.md", content="billing invoice receipt payment info"):
    from app.services.embeddings import get_embedder
    from app.services.knowledge import ingest_document

    doc = ingest_document(
        db, settings, get_embedder(settings), title=title, filename=filename,
        data=content.encode("utf-8"),
    )
    db.commit()
    return doc


def process_queued(settings, deps, checkpointer, session_factory=session_factory):
    """Claim and process the next queued run synchronously (worker path)."""
    from app.worker import claim_next_run, process_run

    db = session_factory()
    try:
        run = claim_next_run(db)
    finally:
        db.close()
    if run is None:
        return None
    return process_run(run.id, session_factory, checkpointer, settings, deps)


@pytest.fixture()
def sf():
    return session_factory
