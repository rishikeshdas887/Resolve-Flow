# Frontend handoff

ResolveFlow exposes a versioned JSON API at `/api/v1`. OpenAPI:
`GET /openapi.json` (Swagger UI at `/docs`). All responses are JSON; all
errors share one envelope — build your error handling around it once.

## Auth

```http
POST /api/v1/auth/login        {email, password} -> {access_token, token_type, user}
GET  /api/v1/auth/me           Authorization: Bearer <jwt>
```

Roles: `customer` (own tickets only), `support_agent`, `admin` (approvals,
users, evals, deletes). Check `user.role` from `/auth/me` to gate UI.

## Core objects

**Ticket**
```json
{"id","subject","body","requester_email","status","priority","category",
 "assigned_queue","tags":[...],"created_by_id","assigned_to_id",
 "created_at","updated_at","resolved_at"}
```
- `status`: `new | processing | needs_information | pending_approval |
  resolved | escalated`
- `priority`: `low | medium | high | urgent`
- `category`: `billing | shipping | refund | technical | account | general |
  security | other` (set by the agent; initially `null`)
- `tags`: string list (set by agent actions)

**AgentRun**
```json
{"id","ticket_id","status","disposition","provider","attempt","max_attempts",
 "queued_at","started_at","finished_at","duration_ms","error","summary"}
```
- `status`: `queued | running | awaiting_approval | completed | failed`
- `disposition`: `resolved | needs_information | pending_approval |
  escalated | failed` (null while in flight)

**Evidence item** (`GET /runs/{id}/evidence`)
```json
{"id","chunk_id","document_id","document_title","score","excerpt","retrieval_mode"}
```
`retrieval_mode` is `"vector"` or `"lexical"` — render it; the lexical mode is
keyword search, not semantic.

**Proposal** (`GET /runs/{id}/proposal`) — array of proposed actions:
```json
[{"id","action_type","params","status","policy_decision","policy_reasons",
  "draft_response","cited_evidence_ids","result","executed_at","is_terminal"}]
```
`policy_decision`: `allow | deny | require_approval`.
`status`: `proposed | pending_approval | executed | rejected | failed`.

**ApprovalRequest**
```json
{"id","run_id","action_id","status","reason","reviewer_id","decision_note",
 "created_at","decided_at"}
```
`status`: `pending | approved | rejected`.

**TicketEvent** (audit, `GET /tickets/{id}/events`)
```json
{"id","event_type","detail","actor_type","actor_id","run_id","created_at"}
```

## Key flows

### Create ticket → process → poll
```http
POST /api/v1/tickets                    (Idempotency-Key recommended)
POST /api/v1/tickets/{id}/runs          -> 201 {run}  (409 if one already active)
GET  /api/v1/runs/{id}                  -> poll until status completed/failed
GET  /api/v1/runs/{id}/evidence         -> grounded sources
GET  /api/v1/runs/{id}/proposal         -> draft + actions + policy reasons
GET  /api/v1/tickets/{id}/events        -> audit timeline
```
Runs are processed asynchronously by the worker — always poll; there is no
synchronous processing endpoint.

### Approvals (admin UI)
```http
GET  /api/v1/approvals?status=pending
GET  /api/v1/approvals/{id}             -> includes embedded action + draft
POST /api/v1/approvals/{id}/approve     {note?}
POST /api/v1/approvals/{id}/reject      {note?}
```
After approval the worker resumes the run; the ticket lands `resolved` and the
response is recorded as a `response_posted` ticket event (the proposal's
`draft_response` is the text that was "sent").

### Knowledge management
```http
POST /api/v1/knowledge/documents        multipart file (.txt/.md/.markdown, <=1MB)
GET  /api/v1/knowledge/documents        list (+status ready/failed)
GET  /api/v1/knowledge/documents/{id}
GET  /api/v1/knowledge/documents/{id}/chunks
POST /api/v1/knowledge/documents/{id}/reprocess
DELETE /api/v1/knowledge/documents/{id} (admin)
```

### Dashboard
```http
GET /api/v1/dashboard/summary (staff)
```
`{tickets_total, tickets_by_status, tickets_by_priority, tickets_by_category,
open_tickets, resolved_tickets, runs_total, runs_by_status,
runs_completed_24h, avg_run_duration_ms, pending_approvals,
documents_total, chunks_total}`

## Conventions to rely on

- **Idempotency**: send `Idempotency-Key: <uuid>` on ticket/run creation —
  safe retry semantics are server-enforced.
- **Pagination**: `?page=&size=` (size ≤ 100) → `{items, total, page, size, pages}`.
- **Filtering**: `/tickets?status=&category=&priority=&q=` (q matches
  subject/body substring).
- **Errors**: `{"error":{"code","message","details","correlation_id"}}` —
  codes: `unauthorized, forbidden, not_found, conflict, validation_failed,
  unprocessable, rate_limited, internal`.
- **Tickets a customer can't see return 404**, not 403 — treat both as "gone".
- **Never expect synchronous AI output**: `POST /tickets/{id}/runs` returns
  `queued` immediately.
- PATCH on tickets accepts only `subject, body, priority, assigned_queue`;
  status transitions are system-owned.
- Timestamps are ISO-8601 UTC (`...Z`-style offset).
- CORS: the deploy env sets explicit origins; local dev default allows
  `http://localhost:3000`.
