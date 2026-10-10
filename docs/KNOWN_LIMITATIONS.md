# Known limitations

Honest inventory — everything here is real, not hedged.

## Provider / model quality

- **No `OPENAI_API_KEY` was available during development.** Every LLM-facing
  path (classification, drafting, injection sensitivity, structured output)
  is exercised through the labelled **deterministic provider**, which is a
  keyword/rules engine — not a language model. Deterministic results are
  never presented as real LLM results. The `OpenAIProvider` implements
  strict JSON-schema structured output, bounded retry, and error mapping but
  is **untested against the live API**. Verified: provider selection logic,
  error taxonomy, malformed-output handling (via fault injection).
- The deterministic provider's "understanding" is shallow: e.g. nuanced
  paraphrases, non-English tickets, or subtle intents will classify poorly.
  The system fails safe (escalates) rather than hallucinating, but expect
  conservative behaviour offline.
- `DeterministicEmbedder` is a hashing-trick bag-of-words vectorizer used so
  the vector pipeline exercises end-to-end offline. It is **lexical
  overlap, not semantic similarity**; production use requires
  `EMBEDDING_PROVIDER=openai` (or another real model). Retrieval relevance
  thresholds in the deterministic provider were calibrated to this embedder
  and may need re-tuning with real embeddings.

## Slack

- Signature verification (`verify_slack_signature`) is unit-tested.
- `SlackNotifier` raises on failure by design; **live delivery was not
  tested** — no credentials provided. No simulated success is reported.

## Scale / ops

- Single worker process is fine at low volume; horizontal scale works (SKIP
  LOCKED claims) but there's no supervisor/metrics/alerting on the worker
  beyond logging.
- No rate limiting middleware (request size limit exists; auth brute-force is
  not throttled — add e.g. slowapi at the edge before public exposure).
- No ticket-comment thread / customer reply channel; `needs_information`
  dispositions have no inbound "customer answered" webhook.
- Approval decisions are `admin`-only; there is no separate reviewer role or
  multi-approver policy.
- Full-text search indexes on tickets are simple ILIKE; multilingual/typo
  tolerance is limited.
- Checkpoints accumulate in the `checkpoints` tables — no retention job.
- Eval cases exercise the deterministic provider; they validate safety
  behaviour (policy, approval, citations), not answer quality.

## Security boundaries

- JWT is a shared-secret token (HS256) — no refresh/revocation list; token
  expiry (default 24h) is the mitigation. `JWT_SECRET` is required in
  non-dev environments (startup refuses the dev default).
- `.env.example` contains no secrets; seed users exist **only** when
  `SEED_*_PASSWORD` env vars are explicitly provided — there is no shipped
  default password.
- Customer→staff object isolation is enforced at query level; a future
  multi-tenant split would need row-level security.
- Audit events redact common secret patterns but are not a substitute for
  never logging secrets.

## Deferred / not implemented

- PDF ingestion (spec allowed skipping if unreliable — text/Markdown only).
- Multi-turn conversational runs (one run per ticket processing cycle; new
  customer input = new ticket update + new run).
- Real-time push (SSE/websockets); the contract is poll-based by design.
