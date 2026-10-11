# Implementation plan (as executed)

Phases followed during the build. Status reflects the final state of this
branch.

## Phase 1 — Foundation ✅
- Empty repo bootstrapped: `requirements.txt`/`requirements-dev.txt` (pinned),
  `pyproject.toml` (ruff config), `.env.example` (placeholders only),
  `.gitignore` (covers `.env`, venvs, caches, `evals/reports/*.json` kept).
- `app/core`: settings + env validation, security (argon2/JWT), logging with
  redaction, uniform error envelope, RBAC deps.

## Phase 2 — Data layer ✅
- `app/db/models.py`: 14 tables, PG enums, unique/check constraints, FKs,
  UTC timestamps, indexes on hot filters.
- Alembic: `migrations/env.py` reads `DATABASE_URL`; initial revision
  `c5b257a7b624` creates `vector` extension + all tables; downgrade drops
  enum types explicitly. Verified on an empty Postgres.

## Phase 3 — API surface ✅
- `/api/v1` versioned router; auth (login/me/user-admin), tickets CRUD-lite +
  filters + pagination, run start/status, events/status-history, evidence +
  proposal per run, knowledge documents, approvals, dashboard, evals, health.
- Idempotency-Key support, 2 MB request cap, object-level authorization
  (customer-scoped reads), uniform error schema.

## Phase 4 — Knowledge & retrieval ✅
- Text/Markdown ingestion with validation, checksum dedup, deterministic
  chunking, optional embeddings, ready/failed status.
- Retrieval: pgvector cosine (`vector` mode) → FTS/ILIKE fallback (`lexical`
  mode, clearly labelled — never presented as semantic search).

## Phase 5 — Agent workflow + safety ✅
- LangGraph StateGraph with the 8 implemented nodes and conditional routing;
  dispositions `resolved / needs_information / pending_approval / escalated /
  failed`.
- Evidence validation (citation existence), deterministic policy gate,
  approval pause via `interrupt()` + PostgresSaver resume.
- Exactly-once action execution with allowlist enforcement.

## Phase 6 — Worker + audit ✅
- Durable worker: SKIP LOCKED claim, retryable-error backoff, permanent-failure
  escalation, approved-approval resume path.
- Append-only `ticket_events` for every meaningful mutation.

## Phase 7 — Tests ✅
- `tests/` (69 tests): auth/RBAC, tickets API incl. idempotency + pagination,
  knowledge validation + chunking + retrieval, policy unit matrix, full
  workflow flows (resolve/no-evidence/injection/sensitive/missing-info/
  approval approve/reject/escalate), worker claim/retry/failure/restart
  resumption, error schema, CORS, size limits, Slack signature, state machine.

## Phase 8 — Evaluation ✅
- `evals/dataset.jsonl` (32 cases), `evals/knowledge/` corpus,
  `scripts/evaluate.py` → `evals/reports/latest.json`; admin-only
  `POST /api/v1/evals/runs` runs datasets through the API too.
- Results in `docs/VERIFICATION_REPORT.md`.

## Phase 9 — Packaging ✅
- `Dockerfile` (python:3.10-slim), `docker-compose.yml` (db/migrate/api/worker
  with healthchecks and dependency ordering).

## Phase 10 — Docs & review ✅
- README, AGENTS.md, this plan, ARCHITECTURE, FRONTEND_HANDOFF,
  ACCEPTANCE_CRITERIA, VERIFICATION_REPORT, KNOWN_LIMITATIONS.
- Adversarial review pass + secret scan before PR.

## Assumptions & decisions made

- Branch `devin/resolveflow-backend` (spec suggestion) since repo's `main` was
  empty; all work lands via PR.
- Python 3.10 target (VM-provided interpreter; Dockerfile matches).
- `LLM_PROVIDER=auto`: OpenAI when `OPENAI_API_KEY` set, else deterministic.
  No API key was available → all LLM-driven paths verified with the
  deterministic provider (labelled everywhere; never reported as real).
- Slack delivery not configured (no credentials) → integration code + unit
  tests only, documented as untested live.
- `admin` is the approver role (spec: "authorized reviewers" — admin is the
  smallest reasonable initial set; support agents cannot approve).
