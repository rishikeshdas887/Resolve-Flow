# AGENTS.md — guidance for AI agents working in this repo

## Project shape

Modular monolith, Python 3.10 (no `datetime.UTC` — use `timezone.utc`), sync
SQLAlchemy 2.x everywhere (FastAPI runs sync code in a threadpool — do not
"fix" this to async; it is deliberate and consistent).

```
app/
  core/       settings, security/JWT, logging (redaction), errors, deps (RBAC)
  db/         models.py (all 14 tables), session.py
  agent/      LangGraph state/graph/nodes + AgentDeps
  api/routes/ versioned routers under /api/v1
  services/   tickets, knowledge, retrieval, embeddings, llm, policy, actions,
              audit, metrics, evals — the business logic layer
  worker.py   durable run worker (SELECT ... FOR UPDATE SKIP LOCKED)
  integrations/slack.py
migrations/   alembic env + versions
tests/        pytest suite (needs TEST_DATABASE_URL on Postgres)
evals/        dataset.jsonl + knowledge/ + reports/
scripts/      create_user.py, seed.py, evaluate.py
```

## Invariants — do not break these

- **The model proposes, application code decides.** Never let an LLM decision
  bypass `app/services/policy.py`. Never add LLM-visible actions beyond the
  allowlists in `policy.py`/`actions.py` without a spec-level change.
- Every cited evidence ID must exist among retrieved IDs (`validate_output`
  node); fabricated citations → escalate. Never weaken this.
- `execute_action` is idempotent and row-locked; never remove the
  already-executed early return.
- Approval actions must never execute before approval; re-check status on
  resume. Never auto-execute anything in `DENIED_ACTIONS` or outside
  `EXECUTABLE_ACTIONS`.
- All ticket mutations emit `ticket_events` audit rows via `record_event`.
- No secrets in tracked files; `.env` stays gitignored; no hardcoded JWT secret.
- Ticket status transitions only through `transition_ticket` /
  `ALLOWED_TRANSITIONS`.
- UTC timestamps; enum values are stored as their Python values (native enums).

## Commands

- Lint: `ruff check app tests scripts migrations`
- Test: `TEST_DATABASE_URL=postgresql+psycopg://.../resolveflow_test pytest -q`
- Migrate: `DATABASE_URL=... alembic upgrade head`
- Worker: `DATABASE_URL=... python -m app.worker`
- Eval: `python scripts/evaluate.py --dataset evals/dataset.jsonl`

## Conventions

- Errors: raise `app.core.errors.*` subclasses; API handlers convert them to
  `{"error": {...}}` — don't hand-raise HTTPException for business errors.
- New tables need a migration (`alembic revision --autogenerate`) plus an
  entry in the downgrade `DROP TYPE` loop if you add a PG enum.
- Record decisions and WHY in `docs/` when making non-trivial changes.
