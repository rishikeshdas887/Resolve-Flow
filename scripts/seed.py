"""Seed synthetic demo knowledge documents and (optionally) demo users.

Demo users are only created when SEED_*_PASSWORD env vars are explicitly set —
no predictable default password is ever used.

Usage: python scripts/seed.py
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.models import KnowledgeDocument, Role, User
from app.db.session import make_session_factory
from app.services.embeddings import get_embedder
from app.services.knowledge import ingest_document

KNOWLEDGE_DIR = Path(__file__).resolve().parents[1] / "knowledge_samples"


def seed_knowledge(db, settings) -> int:
    embedder = get_embedder(settings)
    created = 0
    for path in sorted(KNOWLEDGE_DIR.glob("*.md")):
        checksum_source = path.read_bytes()
        import hashlib

        checksum = hashlib.sha256(checksum_source).hexdigest()
        existing = db.execute(
            select(KnowledgeDocument).where(KnowledgeDocument.checksum == checksum)
        ).scalar_one_or_none()
        if existing:
            print(f"skip (already ingested): {path.name}")
            continue
        doc = ingest_document(
            db, settings, embedder,
            title=path.stem.replace("_", " ").title(),
            filename=path.name, data=checksum_source,
            source_uri=f"seed://{path.name}",
        )
        print(f"ingested: {path.name} -> {doc.id} ({doc.status.value})")
        created += 1
    db.commit()
    return created


def seed_users(db) -> int:
    created = 0
    for email_env, pw_env, role, name in (
        ("SEED_ADMIN_EMAIL", "SEED_ADMIN_PASSWORD", Role.admin, "Demo Admin"),
        ("SEED_AGENT_EMAIL", "SEED_AGENT_PASSWORD", Role.support_agent, "Demo Agent"),
    ):
        email = os.environ.get(email_env)
        password = os.environ.get(pw_env)
        if not email:
            continue
        if not password:
            print(f"{email_env} set but {pw_env} missing — skipping user {email}")
            continue
        existing = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if existing:
            print(f"user exists: {email}")
            continue
        db.add(
            User(
                email=email, full_name=name,
                password_hash=hash_password(password), role=role,
            )
        )
        print(f"created {role.value} user {email}")
        created += 1
    db.commit()
    return created


def main() -> int:
    settings = get_settings()
    session_factory = make_session_factory(settings.database_url)
    db = session_factory()
    try:
        docs = seed_knowledge(db, settings)
        users = seed_users(db)
        print(f"seed complete: {docs} documents ingested, {users} users created")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
