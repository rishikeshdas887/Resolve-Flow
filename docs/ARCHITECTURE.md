# ResolveFlow architecture

## Overview

Modular monolith. One FastAPI app, one Postgres database, one worker process.
The LLM **proposes** (classification, draft response, suggested action); the
application **decides** (deterministic risk policy, idempotent execution,
approval gating). Every decision and mutation is persisted.

```
HTTP client ──> FastAPI (/api/v1) ──> Postgres
                     │                    ▲
                     └─> agent_runs (queued)
worker (python -m app.worker) ──> claim run (FOR UPDATE SKIP LOCKED)
                     └─> LangGraph workflow (PostgresSaver checkpoints)
```

## Why these choices

- **Sync SQLAlchemy everywhere.** One coherent strategy: FastAPI executes sync
  dependencies/routes in a threadpool, the worker and scripts use plain
  sessions. Mixing async engines with sync LangGraph nodes would double the
  session-management surface for no benefit.
- **LangGraph + PostgresSaver for the agent.** The workflow is an explicit
  state machine; approval pause/resume is `interrupt()` + `Command(resume=...)`
  on a checkpoint stored in Postgres. A process restart between pause and
  decision resumes correctly (tested).
- **Durable worker over in-process tasks.** `POST /tickets/{id}/runs` only
  persists a queued run. The separate worker claims runs with
  `SELECT ... FOR UPDATE SKIP LOCKED`, so retries, restarts and multi-replica
  deployments never double-execute.
- **Deterministic policy outside the model.** `app/services/policy.py` is pure
  Python, has zero model access, and maps draft + validation + evidence to an
  allow/deny/require-approval decision with machine-readable reasons.

## Modules

| Path | Responsibility |
|---|---|
| `app/core/config.py` | Pydantic Settings, provider selection (`auto` → openai if `OPENAI_API_KEY` else deterministic), runtime validation |
| `app/core/security.py` | Argon2 password hashing, JWT issue/verify |
| `app/core/errors.py` | `AppError` hierarchy → uniform `{"error":{...}}` envelope; no stack traces |
| `app/core/deps.py` | `get_current_user`, `require_staff`, `require_admin`, `require_approver`, pagination |
| `app/db/models.py` | 14 tables: users, tickets, ticket_status_history, ticket_events, knowledge_documents, knowledge_chunks, agent_runs, run_evidence, proposed_actions, approval_requests, idempotency_records, eval_runs, eval_results, + PG enums |
| `app/api/routes/*` | Thin HTTP layer: auth, tickets, runs, knowledge, approvals, dashboard, evals, health |
| `app/services/tickets.py` | `ALLOWED_TRANSITIONS` state machine, `transition_ticket` (writes status history) |
| `app/services/knowledge.py` | Upload validation (ext/size/UTF-8), sha256 dedup, deterministic paragraph-aware chunking |
| `app/services/embeddings.py` | `DeterministicEmbedder` (hashing-trick, clearly labelled lexical-only) / `OpenAIEmbedder` |
| `app/services/retrieval.py` | pgvector cosine search → labelled `vector` results; Postgres FTS/ILIKE fallback → `lexical` |
| `app/services/llm.py` | Provider protocol; `DeterministicProvider` (offline/test) and `OpenAIProvider` (strict JSON-schema structured output, bounded retries). LLM output is always validated into pydantic models |
| `app/services/policy.py` | Deterministic risk policy + action allowlists (see below) |
| `app/services/actions.py` | `create_action`, `request_approval`, `decide_approval`, idempotent `execute_action` |
| `app/services/audit.py` | `record_event` — append-only audit trail with secret redaction |
| `app/services/metrics.py` | dashboard summary from persisted counts only |
| `app/services/evals.py` | dataset runner, deterministic assertions, fault injection provider |
| `app/agent/` | LangGraph StateGraph: state, deps, nodes, graph assembly |
| `app/worker.py` | claim loop, `_pending_decision` resume detection, retry/backoff, failure escalation |

## Agent workflow (LangGraph)

```
load_ticket → classify → retrieve_evidence → draft → validate_output
            → policy_gate ─┬─> execute            (allow)
                           ├─> approval_gate      (require_approval: persist
                           │    approval + interrupt(); resume executes the
                           │    action via idempotent execute_action)
                           └─> END                (deny with no actions needed)
```

Dispositions: `resolved`, `needs_information`, `pending_approval`,
`escalated`, `failed`.

- `validate_output` checks every `cited_evidence_ids` entry is an actual
  retrieved evidence ID — fabricated citations ⇒ escalate.
- `policy_gate` never trusts model-reported confidence; it re-evaluates
  evidence presence, citation validity, missing-information, action type
  allowlists, and category resolvability.

## Risk policy

- Auto-allowed (low risk, internal): `add_tag`, `assign_queue`,
  `add_internal_note`, `request_information`, plus `resolve_ticket` **only**
  when: draft requests resolution AND evidence exists AND citations are valid
  AND category ∈ {billing, technical, shipping, account, general} AND no
  missing information.
- Requires human approval: `send_response_and_resolve` (external-facing
  response + resolution).
- Always denied ⇒ escalate: `refund_payment`, `reset_credentials`,
  `modify_account`, `delete_data`, `grant_access`, `external_side_effect`,
  and any unknown action type. Injection flags and invalid citations also
  escalate.
- Model-suggested params are sanitized through a per-action allowlist so the
  model cannot smuggle extra side effects.

## Approvals

1. `approval_gate` persists the action (`pending_approval`) + `ApprovalRequest`
   (unique per action), transitions ticket → `pending_approval`, then
   `interrupt()`s — the LangGraph checkpoint freezes the exact state.
2. `POST /approvals/{id}/approve|reject` (admin only) records reviewer +
   timestamps. Reject → action `rejected`, run completes as `escalated`;
   approve → run requeues (`queued`, no retry delay).
3. Worker detects the approved approval (`_pending_decision`), resumes the
   checkpoint with `Command(resume={decision: approved})`, and the graph
   executes the persisted action through the row-locked, idempotent
   `execute_action` — exactly once even if the process restarts mid-flight.

## Idempotency & durability

- `POST /tickets`, `POST /tickets/{id}/runs`: `Idempotency-Key` header →
  `idempotency_records` (scope=resource+actor) + unique constraints on
  `tickets(created_by, idempotency_key)` and `agent_runs(ticket, idempotency_key)`.
- One active run per ticket (queued/running/awaiting_approval ⇒ 409).
- `execute_action` takes `SELECT ... FOR UPDATE`, short-circuits when already
  executed — retries never double side-effects.
- Worker claims are atomic (SKIP LOCKED); a crash mid-run leaves `running`
  which a reaper requeues after `stuck_run_minutes` (see worker).

## Security notes

- Passwords: argon2 (pwdlib recommended params). JWT: HS256, env-configured
  secret — startup refuses a dev-default secret outside dev/test.
- RBAC: `customer` < `support_agent` < `admin`; approvals restricted to
  `admin`; customers get 404 (not 403) on other users' tickets to avoid
  existence leaks.
- Uploads: extension/type/size/UTF-8 validation; request body size cap (2 MB).
- CORS: explicit origins only. Prompt-injection: retrieved content and ticket
  text are treated as untrusted data; injection markers in the deterministic
  provider escalate; the OpenAI provider instructs the model accordingly.
- Audit events redact keys containing secret/password/token/api_key and known
  credential-shaped strings.
