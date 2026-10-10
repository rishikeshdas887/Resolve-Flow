# ResolveFlow — Final Engineering Audit Report

Date: 2026-10-10 · Branch: `devin/resolveflow-backend` · PR: #1
Scope: complete backend audit against `ResolveFlow_Devin_Autonomous_Backend_Prompt.md`,
security hardening, defect fixes, regression tests, release verification.

Statuses: **PASS** = verified working via test/reproducible procedure ·
**FAIL** = broken · **BLOCKED** = blocked by environment/credentials ·
**NOT IMPLEMENTED** = absent.

## Defects found and fixed in this audit

| Sev | Defect | Fix | Regression test |
|-----|--------|-----|-----------------|
| P1 | `load_ticket` only transitioned `new`→`processing`; reprocessing a `needs_information` ticket (the normal reply path) that reached resolution hit the invalid transition `needs_information`→`resolved` and killed the run with escalation | `app/agent/nodes.py` now transitions `{new, needs_information, escalated}`→`processing` | `test_reprocess_needs_information_can_resolve` |
| P2 | Runs stuck in `running` after a worker crash were never recovered, and `start_run` permanently refused new runs on that ticket | `app/worker.py` `recover_stale_runs()` requeues stale runs each poll (bounded by `max_attempts` → fails + escalates at cap); `run_stale_seconds` setting (600s) | `test_stale_run_recovery_requeues_and_completes`, `test_stale_run_at_max_attempts_fails_and_escalates` |
| P2 | `decide_approval` requeued a run on approve without revalidating ticket/run state → approving after the ticket left `pending_approval` produced a mid-resume conflict instead of a clean 409 | `app/services/actions.py` now requires ticket `pending_approval` + run `awaiting_approval` before requeue | `test_approve_after_ticket_left_pending_rejected` |
| P3 | Invalid `?status=` filter on `/approvals` and `/knowledge/documents` raised `ValueError` → HTTP 500 | Validated → `ConflictError` 409, matching `/tickets` | `test_invalid_status_filters_return_4xx` |
| P3 | Lexical FTS fallback and worker claim query lacked indexes | New migration `a1b2c3d4e5f6`: GIN `to_tsvector` index on `knowledge_chunks.content`, composite `(status, next_retry_at, queued_at)` on `agent_runs` | migration cycle verified (upgrade/downgrade/upgrade on empty DB) |
| P3 | Double-decision protection relied on E2E evidence only | — | `test_double_decision_conflict` |

## Requirements coverage matrix

| # | Requirement | Implementation | Verification | Status |
|---|-------------|----------------|--------------|--------|
| A | Repo config & reproducible setup | `requirements*.txt` (pinned), `pyproject.toml`, `.env.example`, `scripts/create_user.py`+`seed.py` | fresh clone → venv → pytest | PASS |
| B | DB schema, migrations, persistence | `app/db/models.py` (13 models), `migrations/versions/` (2 revisions), FK+unique constraints, `PostgresSaver` checkpoints | `alembic upgrade head`/`downgrade base`/re-upgrade on `resolveflow_fresh` empty DB — clean cycle | PASS |
| C | Auth & RBAC | Argon2 (`pwdlib`), HS256 JWT w/ exp, `require_staff/admin/approver`, customer<agent<admin | `test_auth.py` (9): login, bad pw, missing/invalid token, inactive, role gates, no password in responses | PASS |
| D | Ticket CRUD, filters, pagination, transitions | `app/api/routes/tickets.py`, `ALLOWED_TRANSITIONS` state machine, `TicketStatusHistory`, Idempotency-Key replay + unique-constraint race fallback | `test_tickets_api.py` (12) + `test_create_ticket_validation` | PASS |
| E | Knowledge ingestion & retrieval | text/md only, UTF-8+control sanitize, bounded upload (`file.read(max+1)`), sha256 dedupe, chunking (1200/200, ≤200 chunks), pgvector cosine → FTS → ILIKE fallback | `test_knowledge.py` (9): ext/empty/utf8/oversize rejects, deterministic chunking, retrieval sources | PASS |
| F | LangGraph orchestration | `StateGraph` 8 nodes, PostgresSaver, `interrupt()`/`Command(resume=)`, LLM error taxonomy (retryable vs permanent) | `test_agent_flow.py` incl. `test_restart_resumption` (fresh checkpointer, resume works) | PASS |
| G | Evidence-grounded generation | drafts cite stored `RunEvidence` only; citation validation vs retrieved set; score≥0.15 + ≥30% word coverage; fabricated refs → escalate | `test_fabricated_citation_rejected`, eval C14/C15/C16 | PASS |
| H | Deterministic risk/action policy | `policy.evaluate()` ordered rules; model proposes only; deny list for sensitive ops; approval-required set; auto-allow set | `test_policy.py` (13) | PASS |
| I | Human approvals & resumption | `ApprovalRequest` unique per action, row-locked `decide_approval`, reject→never-executes, approve→requeue+checkpoint resume | `test_approval_pause_and_resume`, `test_double_decision_conflict`, new stale-state guard test | PASS |
| J | Idempotency & duplicate execution | `IdempotencyRecord`, unique constraint on ProposedAction per run, `execute_action` row-lock + early-return on `executed`, idempotent run-start | `test_idempotent_*` (3) | PASS |
| K | Audit events & history | `TicketEvent` append-only, redaction filter, status history; events for run_started/classified/evidence_retrieved/policy_decision/approval_*/action_executed/run_* | asserted in `test_resolved_flow` + `/events` endpoint test | PASS |
| L | Eval dataset & runner | `evals/dataset.jsonl` (32 labelled cases), `scripts/evaluate.py`, `EvalRun`/`EvalResult` persisted, failed cases listed, exit≠0 on failure | `evaluate.py` → 32/32 pass, 36.7ms avg, mode=deterministic | PASS |
| M | API docs & OpenAPI accuracy | FastAPI schemas on all routes, `HTTPBearer` → `/docs` Authorize works, consistent `{"error":{code,message,details}}` | `openapi.json` regenerated post-fix; routes vs `FRONTEND_HANDOFF.md` verified | PASS |
| N | Docker config & startup | `Dockerfile`, `docker-compose.yml` (db/migrate/api/worker), healthchecks, `.env` gitignored | `docker compose up --build` verified live end-to-end (prior phase) | PASS |
| O | Observability & health | `/health/live`, `/health/ready` (SELECT 1), JSON logs w/ correlation_id + RedactingFilter | hit live in compose stack + tests | PASS |
| P | Security & dependency review | see §3 below; pinned deps; no committed secrets (tracked-file scan) | `test_security_misc.py` (11) + this audit | PASS* |
| Q | Frontend handoff docs | `docs/FRONTEND_HANDOFF.md` — routes, enums, error contract, flows | reviewed vs live routes; updated where needed | PASS |
| R | Functional & integration tests | `tests/` — 75 tests | `pytest tests/ -q` → 75 passed | PASS |

\* No P0 security defects found. P2/P3 findings fixed above. External pentest
not claimed.

## Security audit findings & disposition

| Area | Finding | Disposition |
|------|---------|-------------|
| Missing auth/endpoint authz | none — all routes behind `require_*` deps | verified via 401/403 tests |
| Object-level authz (BOLA) | customers see only own tickets (`_get_ticket_or_404`); staff endpoints role-gated | `test_customer_sees_only_own_tickets` |
| Cross-user private data | ticket events/status-history are staff-only | test-tagged |
| Unauthorized approval/execution | approver=admin only; `execute_action` not reachable via API at all (worker-only) | `test_agent_cannot_approve`, `test_double_decision_conflict` |
| Sensitive info in responses | `password_hash` never serialized; status-history omits actor_id | `test_password_not_in_user_response` |
| Secrets in git/logs | tracked-file scan: none; dev defaults refused outside dev/test (`validate_runtime`); log RedactingFilter | verified |
| Uploads | ext allowlist {.txt,.md,.markdown}, UTF-8 + control-char strip, 1 MiB bound (`read(max+1)`), sha256 dedupe | `test_upload_*` |
| SQL injection | all queries parameterized (ORM/`text().params()`); `ilike` values bound | code review |
| Prompt injection | injection markers in ticket AND knowledge docs → flag→escalate; docs never override policy | eval C13–C16, `test_injection_*` |
| Request/upload size | global 2 MB `Content-Length` cap → 413; per-field pydantic bounds | `test_size_bound` |
| Unbounded LLM calls/retries | `max_retries` bounded in provider; `run_max_attempts` in worker; node retryable-only requeue | `test_retryable_llm_error_requeues` |
| Missing timeouts | OpenAI provider timeout configured; requests bounded | code review |
| CORS | explicit origin list + credentials; no `*` | code review |
| Races / duplicate actions | `FOR UPDATE SKIP LOCKED` claim; row-locked action status guard; unique constraints; double-decide → 409 | `test_second_active_run_conflict`, new regressions |
| Invalid transitions | central `ALLOWED_TRANSITIONS` + history rows; invalid → 409 | P1 fix + `test_invalid_transition_409` |
| Error leakage | AppError envelope; unhandled → 500 w/ correlation_id, no stack | code review |
| **Stale running runs** | **fixed** — `recover_stale_runs` | new tests |
| Login brute force | **no rate limit** — documented limitation | KNOWN_LIMITATIONS |
| Chunked-body bypass of size middleware | `Content-Length`-only check; per-endpoint bounds still apply | documented |

## 20-scenario workflow verification

Scenarios 1–20 verified by `test_agent_flow.py` + evals + E2E recording
(`rec-55ad2f8a`, prior phase): resolved-with-evidence (1,2,9), fabricated/
invalid citations rejected (3), no-evidence & contradictory → escalate
(4,5), malformed model output → escalate ticket (6), provider timeout →
run fails cleanly, ticket escalates, state intact (7), injection → escalate
(8), approval pending blocked (10), approve/reject by admin (11,12),
rejected never executes (13), non-admin approve → 403 (14), idempotent
retries/no dup actions (15,16), restart-survival + resume correctness
(17,18 — verified live with kill+restart), escalated ≠ resolved (19),
audit completeness (20). New this audit: stale-run recovery, stale-approval
409, needs_information→resolved path, invalid filter 4xx.

## DB & worker reliability

- Migrations from empty DB: `alembic upgrade head` on `resolveflow_fresh` ✓,
  downgrade+upgrade cycle clean ✓, chain extended (2 revisions).
- Persistence: all state in Postgres incl. LangGraph checkpoints; restart
  resumption proven (test + live kill/restart).
- Transactions: all side effects in `deps.session()` (commit-on-exit,
  rollback-on-error); claim uses `SKIP LOCKED`; decisions row-locked.
- No destructive resets; test suite uses isolated `resolveflow_test`.
- Stale runs: recovered (new). Failed runs: escalate ticket unless
  `pending_approval` (approval still decides).

## Tests actually run

```
alembic upgrade head / downgrade base / upgrade head   (resolveflow_fresh)  PASS
.venv/bin/ruff check app tests scripts migrations                          PASS
.venv/bin/python -m pytest tests/ -q                                       75 passed
.venv/bin/python scripts/evaluate.py --dataset evals/dataset.jsonl         32/32 (deterministic, 36.7ms)
git tracked-file secret scan                                               clean
docker compose up --build (prior phase)                                    PASS — not re-run this audit
```

Deterministic-provider tests = 75 unit/integration + 32 evals.
Real-provider (OpenAI) tests: **0 — BLOCKED** (`OPENAI_API_KEY` not set);
Slack delivery: **BLOCKED** (no credentials). Neither claimed as verified.

## Known limitations / remaining manual actions

- JWT HS256 shared-secret, no revocation; 24 h expiry. Approver=admin only.
- No `/auth/login` rate limiting; no audit-event retention job; checkpoint
  tables grow unbounded (documented).
- Deterministic embedder is lexical (non-semantic) — by design for dev/eval.
- `Content-Length`-based size cap doesn't cover chunked bodies (per-endpoint
  pydantic/read bounds still apply).
- Manual actions before production: set `OPENAI_API_KEY`+`EMBEDDING_PROVIDER=openai`
  and re-run suite/evals; provision Slack creds and test delivery; create real
  admin via `scripts/create_user.py`; rotate all dev secrets.

## Verdict

All P0/P1 issues found were fixed; required P2 fixes are in. The backend is
**ready for frontend integration** — the versioned `/api/v1` contract and
OpenAPI document are accurate and exercised. It is not claimed production-ready:
OpenAI/Slack paths remain credential-blocked, and operational hardening
(rate limiting, retention) is future work listed above.
