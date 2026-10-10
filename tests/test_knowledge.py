import io

from tests.conftest import ingest_doc


def test_upload_markdown_document(client, agent_headers, db):
    content = b"# Policy\nBilling invoices are emailed monthly with receipt details."
    r = client.post(
        "/api/v1/knowledge/documents",
        files={"file": ("policy.md", io.BytesIO(content), "text/markdown")},
        headers=agent_headers,
    )
    assert r.status_code == 201, r.text
    doc = r.json()
    assert doc["status"] == "ready"
    detail = client.get(f"/api/v1/knowledge/documents/{doc['id']}", headers=agent_headers).json()
    assert detail["chunk_count"] >= 1
    chunks = client.get(f"/api/v1/knowledge/documents/{doc['id']}/chunks", headers=agent_headers).json()
    assert chunks[0]["has_embedding"] is True


def test_upload_rejects_bad_extension(client, agent_headers):
    r = client.post(
        "/api/v1/knowledge/documents",
        files={"file": ("evil.exe", io.BytesIO(b"MZ..."), "application/octet-stream")},
        headers=agent_headers,
    )
    assert r.status_code == 422


def test_upload_rejects_empty(client, agent_headers):
    r = client.post(
        "/api/v1/knowledge/documents",
        files={"file": ("empty.txt", io.BytesIO(b""), "text/plain")},
        headers=agent_headers,
    )
    assert r.status_code == 422


def test_upload_rejects_non_utf8(client, agent_headers):
    r = client.post(
        "/api/v1/knowledge/documents",
        files={"file": ("bad.txt", io.BytesIO(b"\xff\xfe\x00\x01binary"), "text/plain")},
        headers=agent_headers,
    )
    assert r.status_code == 422


def test_upload_oversize(client, agent_headers, settings):
    big = b"x" * (settings.max_upload_bytes + 10)
    r = client.post(
        "/api/v1/knowledge/documents",
        files={"file": ("big.txt", io.BytesIO(big), "text/plain")},
        headers=agent_headers,
    )
    assert r.status_code == 422


def test_chunking_is_deterministic(db, settings):
    from app.services.knowledge import chunk_text

    text = ("para one about billing invoices and payment receipts.\n\n" * 60)
    c1 = chunk_text(text)
    c2 = chunk_text(text)
    assert c1 == c2 and len(c1) > 1


def test_retrieval_returns_sources(db, settings, deps):
    doc = ingest_doc(
        db, settings, title="Billing FAQ",
        content="invoices are emailed on the 1st of each month with receipts for payment",
    )
    from app.services.retrieval import retrieve

    chunks = retrieve(db, settings, deps.embedder, "where is my invoice receipt")
    assert chunks
    assert chunks[0].document_id == doc.id
    assert chunks[0].chunk_id
    assert chunks[0].excerpt
    assert chunks[0].retrieval_mode in ("vector", "lexical")


def test_retrieval_empty_when_no_docs(db, settings, deps):
    from app.services.retrieval import retrieve

    assert retrieve(db, settings, deps.embedder, "anything") == []


def test_delete_document_admin_only(client, admin_headers, agent_headers, db, settings):
    doc = ingest_doc(db, settings)
    assert client.delete(f"/api/v1/knowledge/documents/{doc.id}", headers=agent_headers).status_code == 403
    assert client.delete(f"/api/v1/knowledge/documents/{doc.id}", headers=admin_headers).status_code == 204
