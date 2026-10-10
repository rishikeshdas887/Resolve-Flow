# Acceptance criteria (definition of done)

Marked against the implemented system. PASS = verified with a real command or
test; FAIL/BLOCKED/NOT IMPLEMENTED stated honestly.

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | Empty DB initializes from migrations | PASS | `alembic upgrade head` on fresh `resolveflow_test` (14 app tables + alembic_version); `test suite creates its schema this way` |
| 2 | Auth'd ticket API with RBAC + filters | PASS | `tests/test_tickets_api.py`, `tests/test_auth.py` (customer scoping, staff-only PATCH/dashboard, agent-only user-admin denial) |
| 3 | Knowledge ingest validates type/size/UTF-8, deterministic chunking | PASS | `tests/test_knowledge.py` (bad ext, empty, non-UTF-8, oversize all 422; `chunk_text` deterministic) |
| 4 | Retrieval returns source doc/chunk IDs + excerpts; lexical fallback is labelled | PASS | `retrieve()` → `RetrievedChunk{document_id, chunk_id, excerpt, retrieval_mode: vector|lexical}`; `test_retrieval_returns_sources` |
| 5 | Evidence grounding: every cited ID must exist | PASS | `validate_output` node + `test_invalid_citations_escalate` (fabricated IDs → escalate) |
| 6 | No auto-resolve on absent/irrelevant/contradictory evidence | PASS | `test_no_evidence_escalates`; policy rules 2–3,6; provider relevance threshold |
| 7 | Model cannot execute actions; deterministic policy gate | PASS | `app/services/policy.py` + `tests/test_policy.py` matrix (denied/unknown/params-sanitized) |
| 8 | Only allowlisted low-risk actions auto-execute | PASS | `AUTO_ALLOWED_ACTIONS`/`APPROVAL_REQUIRED_ACTIONS`/`DENIED_ACTIONS`; `test_denied_action_cannot_execute` |
| 9 | Never auto-execute refunds/credential/account changes | PASS | `DENIED_ACTIONS` + `test_sensitive_request_not_auto_executed` + `test_sensitive_actions_denied_and_escalated` |
| 10 | Real approval workflow: pending persists, action cannot execute pre-approval, reviewer-restricted, reject prevents forever, approve revalidates+executes once, survives restart | PASS | `test_approval_pause_and_resume`, `test_approval_rejection_never_executes`, `test_agent_cannot_approve`, `test_restart_resumption` (fresh checkpointer+deps between pause and decision) |
| 11 | Append-only audit trail with actor + reason | PASS | `record_event` on every mutation; `ticket_events` asserted in `test_resolved_flow` |
| 12 | Durability: POST persists run, worker claims from DB | PASS | `agent_runs` table + `claim_next_run` (SKIP LOCKED); `test_claim_only_queued` |
| 13 | Idempotent retries: duplicate POST or re-execution causes no duplicate side effects | PASS | `test_idempotent_ticket_create`, `test_idempotent_run_start`, `test_execute_action_idempotent` |
| 14 | Liveness + readiness probes | PASS | `/health/live`, `/health/ready` (real `SELECT 1`, 503 when down) — `test_health_endpoints` |
| 15 | OpenAPI contract generated + versioned paths | PASS | `/openapi.json` — `test_openapi_has_versioned_paths` |
| 16 | Eval suite runs real cases, reports honest results | PASS | `python scripts/evaluate.py` → `evals/reports/latest.json` (32 cases; results in VERIFICATION_REPORT) |
| 17 | No secrets/passwords committed; config via env | PASS | `grep -rniE 'secret|password|token' --include='*.py' app/ | only parameter names; .env gitignored; seed users need explicit env passwords |
| 18 | Docker Compose repeatable local run | PASS | `docker compose config` validated; services: db/migrate/api/worker with healthchecks (see VERIFICATION_REPORT for runtime verification) |
| 19 | Reviewed diff, no stack traces to clients, consistent error schema | PASS | `test_error_shape_consistent`, `test_no_stack_trace_on_404`; request-size 413 test |

## Explicitly marked

- **Slack live delivery**: BLOCKED (no credentials) — signature verification tested; notifier raises on failure; documented in KNOWN_LIMITATIONS.
- **Live OpenAI path**: NOT VERIFIED (no API key) — code exists behind
  `LLM_PROVIDER=auto`; deterministic provider covers all tested behaviour.
