# Verification report

Every claim below was executed during development on this branch. Commands
are real; results are what the tool actually returned.

Environment: Ubuntu, Python 3.10.12, Docker 29.7.2 + Compose v5.4.0,
`pgvector/pgvector:pg16`, deterministic LLM provider (no `OPENAI_API_KEY`
available — live-model paths are marked accordingly).

## Results matrix

| Area | Command | Result | Status |
|---|---|---|---|
| Migrations on empty Postgres | `DATABASE_URL=... alembic upgrade head` (fresh `resolveflow_test` + fresh `pgdata` in compose) | `Running upgrade -> c5b257a7b624` — all 14 tables + `alembic_version` + `vector` ext | PASS |
| Downgrade/upgrade roundtrip | `alembic downgrade base && alembic upgrade head` | clean after enum-safe `DROP TYPE` fix | PASS |
| Unit + integration tests | `TEST_DATABASE_URL=... pytest tests/ -q` | `69 passed` | PASS |
| Lint | `ruff check app tests scripts migrations` | `All checks passed!` | PASS |
| Evaluation suite | `python scripts/evaluate.py --dataset evals/dataset.jsonl` | `32 passed / 0 failed / pass_rate 1.0, avg_latency 38.8ms, mode deterministic` → `evals/reports/latest.json` | PASS |
| E2E workflow (resolve) | ticket → run → worker | `completed/resolved`, 5 evidence rows, `resolve_ticket` executed, 9 audit events | PASS |
| E2E approval flow | refund ticket → run → pending → admin approve → worker resume | run `awaiting_approval` → `completed/resolved`, `send_response_and_resolve` executed exactly once | PASS |
| E2E approval reject | same, reject | ticket `escalated`, action `rejected`, never executed | PASS |
| Process restart between pause and decision | new `PostgresSaver` + `AgentDeps` instances before resume | resume succeeds, single execution | PASS (`test_restart_resumption`) |
| Docker Compose stack | `docker compose up --build` | db healthy → migrate applied → api `healthy` → worker up; `curl /health/ready` `{"status":"ok","db":"up"}`; ticket→run→resolved inside stack | PASS |
| OpenAPI | `GET /openapi.json` | generated; 24+ paths under `/api/v1` | PASS |
| Error contract | 401/403/404/409/413/422 probes | uniform `{"error":{...}}`, no stack traces | PASS |
| Secrets in tracked files | `git ls-files` scan + `.env` ignored | no credentials; `.env.example` placeholders only; no shipped passwords | PASS |

## Evaluation details

`evals/dataset.jsonl` — 32 labelled cases executed through the real
LangGraph graph + checkpointer, deterministic provider:

- Billing/shipping/technical happy paths (6), missing information (3),
  no-knowledge/out-of-domain (2), ambiguous (1), injection in ticket (2),
  injection inside knowledge doc (1), conflicting docs (1),
  sensitive refund/password/delete (3), approval granted (1),
  approval rejected (1), provider timeout (1), provider malformed output (1),
  duplicate/retry (1), explicit-escalation (1), near-empty/malformed
  input (3), post-injection normal ticket (1), misc coverage (3).
- Ground truth = dataset labels + deterministic safety assertions
  (never model self-evaluation).
- Latest report: `evals/reports/latest.json` — 32/32 pass.

Note: pass_rate measures **safety behaviour** (correct disposition, no
forbidden side effects), not answer quality — the deterministic provider
is a rules engine, not a model.

## Known defects found and fixed during verification

- Events recorded before `db.flush()` assigned UUIDs → `NotNullViolation`
  on `ticket_events.ticket_id`/`agent_runs.ticket_id` (3 call sites fixed).
- `ord` prefix in order-id regex misfired on "ordered" → missing-info
  detection skipped for shipping/refund.
- Junk tickets could resolve on stray lexical overlap → added
  content-word coverage check (≥30%) + insufficient-detail escalation.
- Eval approval path used a non-user `reviewer_id` → FK violation; fixed
  with a real synthetic reviewer.
- Eval session staleness post-resume → `db.expire_all()` before reading.
- Alembic downgrade left PG enum types → explicit `DROP TYPE` loop.

## Security limitations (verified scope)

- JWT HS256 shared-secret tokens; no revocation; 24h default expiry.
- Approver = `admin` only (smallest reasonable reviewer set).
- No brute-force rate limiting on `/auth/login` (size limits exist).
- Live OpenAI provider: implemented but **NOT VERIFIED** (no API key).
- Slack delivery: **NOT TESTED** (no credentials); signature verification
  is unit-tested; notifier raises on failure rather than faking success.
- `DeterministicEmbedder` is lexical-only; never reported as semantic.

## Remaining tasks (out of scope / next steps)

- Frontend (built separately in Antigravity + Stitch) against `/api/v1`.
- Real-model validation: set `OPENAI_API_KEY` + `EMBEDDING_PROVIDER=openai`,
  re-run `pytest` + `evaluate.py` and re-tune retrieval thresholds.
- Slack end-to-end test once `SLACK_BOT_TOKEN`/`SLACK_SIGNING_SECRET` exist.

## Final audit round (2026-10-10)

Independent re-verification after the final audit (see FINAL_AUDIT_REPORT.md
for the full requirements matrix and defect dispositions):

| Command | Result |
|---|---|
| `alembic upgrade head` on empty `resolveflow_fresh` | PASS — then `downgrade base` + re-upgrade clean |
| `.venv/bin/ruff check app tests scripts migrations` | PASS |
| `.venv/bin/python -m pytest tests/ -q` | **75 passed** (69 + 6 audit regressions) |
| `scripts/evaluate.py --dataset evals/dataset.jsonl` | 32/32 pass, deterministic mode, 36.7ms avg |
| Tracked-file secret scan | clean |

Defects fixed this round: needs_information reprocessing could not resolve
(P1), stale `running` runs never recovered (P2), approval could requeue after
ticket left `pending_approval` (P2), invalid status filters returned 500 (P3),
missing FTS/claim indexes (P3 — new migration `a1b2c3d4e5f6`).

New limitations documented: no login rate limiting; `Content-Length`-only
request-size cap; stale-run recovery window is `run_stale_seconds` (600s).
