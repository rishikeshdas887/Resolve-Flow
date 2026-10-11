"""retrieval + worker-claim indexes

Revision ID: a1b2c3d4e5f6
Revises: c5b257a7b624
Create Date: 2026-10-10 20:30:00.000000

"""
from alembic import op

revision = 'a1b2c3d4e5f6'
down_revision = 'c5b257a7b624'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # GIN index backing the lexical full-text fallback in services/retrieval.py
    op.execute(
        "CREATE INDEX ix_chunks_fts ON knowledge_chunks "
        "USING gin (to_tsvector('english', content))"
    )
    # Composite index for the worker claim query:
    # status = 'queued' AND (next_retry_at IS NULL OR next_retry_at <= now)
    op.execute(
        "CREATE INDEX ix_runs_claim ON agent_runs (status, next_retry_at, queued_at)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_runs_claim")
    op.execute("DROP INDEX IF EXISTS ix_chunks_fts")
