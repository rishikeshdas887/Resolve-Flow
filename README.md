# ResolveFlow — backend

Evidence-grounded autonomous customer-support operations backend. ResolveFlow
receives support tickets, classifies and prioritizes them, retrieves grounded
knowledge, drafts responses with evidence citations, applies a deterministic
risk policy outside the model, then resolves the ticket, asks for more
information, pauses for a human approval, or escalates — with a persisted audit
trail for every step.

The model proposes; application code decides. The frontend is out of scope of
this repository (it is built separately); this repo ships a stable, versioned
`/api/v1` HTTP API plus the OpenAPI contract at `/openapi.json`.

## Stack

- Python 3.10, FastAPI, Pydantic v2 / Pydantic Settings
- PostgreSQL 16 + pgvector, SQLAlchemy 2.x (sync), Alembic
- LangGraph (checkpointed via PostgresSaver) for the agent workflow and the
  resumable approval pause/resume
- LLM provider: OpenAI when `OPENAI_API_KEY` is set, otherwise a clearly
  labelled deterministic provider for tests/offline demos
- pytest + HTTPX (TestClient), Ruff
- Docker Compose for a repeatable local run

## Quick start (Docker Compose)

```bash
cp .env.example .env          # fill in JWT_SECRET etc.
docker compose up --build     # db -> migrate -> api + worker
```

Services:

- `db` — PostgreSQL 16 with pgvector (host port 55432)
- `migrate` — one-shot `alembic upgrade head`
- `api` — FastAPI on http://localhost:8000 (health: `/health/live`, `/health/ready`)
- `worker` — durable run worker (`python -m app.worker`) that claims queued
  runs, executes the LangGraph workflow, and resumes approved runs

## Quick start (local)

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env
# start Postgres with pgvector, e.g.:
docker run -d --name resolveflow-pg -p 55432:5432 \
  -e POSTGRES_USER=resolveflow -e POSTGRES_PASSWORD=localdev -e POSTGRES_DB=resolveflow \
  pgvector/pgvector:pg16
export DATABASE_URL=postgresql+psycopg://resolveflow:localdev@localhost:55432/resolveflow
alembic upgrade head
python scripts/seed.py                                   # sample knowledge docs
python scripts/create_user.py --email admin@example.com --password '<your-strong-password>' --role admin
uvicorn app.main:app --port 8000 &
python -m app.worker                                     # run worker (separate process)
```

## API tour

All endpoints except `/health/*` live under `/api/v1` and require a
`Authorization: Bearer <jwt>` from `POST /api/v1/auth/login`.

| Area | Endpoints |
|---|---|
| Auth | `POST /auth/login`, `GET /auth/me`, `POST /auth/users` (admin) |
| Tickets | `POST/GET /tickets`, `GET/PATCH /tickets/{id}`, `GET /tickets/{id}/events`, `GET /tickets/{id}/status-history` |
| Runs | `POST /tickets/{id}/runs`, `GET /tickets/{id}/runs`, `GET /runs/{id}`, `GET /runs/{id}/evidence`, `GET /runs/{id}/proposal` |
| Knowledge | `POST/GET /knowledge/documents`, `GET /knowledge/documents/{id}` `/chunks`, `POST /{id}/reprocess`, `DELETE /{id}` (admin) |
| Approvals | `GET /approvals`, `GET /approvals/{id}`, `POST /approvals/{id}/approve` `/reject` (admin) |
| Dashboard | `GET /dashboard/summary` (staff) |
| Eval | `POST /evals/runs`, `GET /evals/runs`, `GET /evals/runs/{id}` (admin) |
| Health | `GET /health/live`, `GET /health/ready` |

Typical flow:

```bash
TOKEN=$(curl -s localhost:8000/api/v1/auth/login -H 'content-type: application/json' \
  -d '{"email":"admin@example.com","password":"<password>"}' | jq -r .access_token)
curl -s localhost:8000/api/v1/tickets -H "authorization: Bearer $TOKEN" \
  -H 'content-type: application/json' -H 'Idempotency-Key: req-1' \
  -d '{"subject":"Where is my invoice?","body":"Need the March billing receipt."}'
curl -s -X POST localhost:8000/api/v1/tickets/<ticket_id>/runs -H "authorization: Bearer $TOKEN"
# worker claims the run -> poll:
curl -s localhost:8000/api/v1/runs/<run_id> -H "authorization: Bearer $TOKEN"
```

- `Idempotency-Key` header makes `POST /tickets` and `POST /tickets/{id}/runs`
  replay-safe (same key + same request returns the stored result; same key +
  different body returns 409).
- Roles: `customer` (own tickets only), `support_agent` (tickets, knowledge,
  dashboard), `admin` (all of the above plus user management, approvals,
  evals, document deletion). Approval decisions require `admin`.
- Errors are always `{"error": {"code", "message", "details", "correlation_id"}}`;
  internal stack traces are never returned.

## Tests

```bash
createdb resolveflow_test   # or a second postgres container
DATABASE_URL=postgresql+psycopg://.../resolveflow_test alembic upgrade head
TEST_DATABASE_URL=postgresql+psycopg://.../resolveflow_test pytest -q
```

## Evaluation

```bash
python scripts/evaluate.py --dataset evals/dataset.jsonl --out evals/reports/latest.json
```

Runs the labelled deterministic provider against ~32 designed cases
(no-evidence, injection, sensitive actions, approval accept/reject, provider
faults, duplicate retries, ...) and writes an honest report with per-case
results. See `docs/VERIFICATION_REPORT.md` for the latest real numbers.

## CI

`.github/workflows/ci.yml` runs on every pull request and push to `main`,
against a disposable `pgvector/pgvector:pg16` service:

1. `ruff check app tests scripts migrations`
2. `alembic upgrade head` from an empty database
3. `alembic downgrade base` + re-upgrade (migration reversibility)
4. `pytest tests/ -q`
5. `scripts/evaluate.py --dataset evals/dataset.jsonl` (deterministic mode —
   no OpenAI or Slack credentials required)

## Verified results (latest run)

- `pytest tests/ -q` — **76 passed** (including worker regression test)
- `ruff check` — clean (all rules passed)
- `evaluate.py` — **32/32** eval cases pass (deterministic provider, 100% case match across two independent runs)
- `frontend/scripts/verify_browser_workflows.js` — **11/11 browser workflows PASS** (Puppeteer + Google Chrome, independently verified twice)
- `oxlint` & `tsc -b && vite build` — clean (0 errors, built in ~960ms)
- `alembic upgrade head` from empty DB — clean; downgrade + re-upgrade clean
- `docker compose up --build` — end-to-end stack verified (ticket → run → evidence → approval → resolve, restart-resumed)

Credentials-dependent paths (live OpenAI provider, Slack delivery) are
implemented but **not verified** — see `docs/KNOWN_LIMITATIONS.md`.

## Frontend & Demo Deployment

The complete React 19 + TypeScript + Vite operations frontend (Google Stitch-inspired design) is located in `frontend/` and deployed to Vercel:

- **Public Production Frontend URL**: [https://frontend-three-bice-94.vercel.app](https://frontend-three-bice-94.vercel.app)
- **Live Production Backend API**: [https://resolve-flow-yrux.onrender.com](https://resolve-flow-yrux.onrender.com)
  - API Health: [https://resolve-flow-yrux.onrender.com/health/ready](https://resolve-flow-yrux.onrender.com/health/ready)
  - Interactive OpenAPI Swagger: [https://resolve-flow-yrux.onrender.com/docs](https://resolve-flow-yrux.onrender.com/docs)
- **Demo Accounts**:
  - Administrator: `admin@example.com` / `AdminPass123!`
  - Support Agent: `agent@example.com` / `AgentPass123!`
- **Local Dev Server**: `cd frontend && npm run dev` (http://localhost:5173)
- **Automated Browser E2E Suite**: `cd frontend && npm run test:e2e`

## Docs

- `docs/LOCAL_REVERIFICATION_REPORT.md` — full two-round verification and browser evidence report
- `docs/ARCHITECTURE.md` — modules, data model, workflow, safety design
- `docs/FRONTEND_HANDOFF.md` — API contract notes for the Antigravity+Stitch frontend
- `docs/ACCEPTANCE_CRITERIA.md` — definition of done, marked
- `docs/VERIFICATION_REPORT.md` — backend verification results
- `docs/KNOWN_LIMITATIONS.md` — honest limitations

## Slack (optional)

`app/integrations/slack.py` contains signature verification (HMAC, 5-min
tolerance) and a notifier. Live Slack delivery was **not tested** (no
credentials); signature verification is unit-tested. See
`docs/KNOWN_LIMITATIONS.md`.
