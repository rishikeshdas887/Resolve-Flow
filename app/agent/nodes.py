"""Workflow nodes. Each node is a small function with one responsibility;
all side effects go through services and are committed per-node so a crash
never leaves silently inconsistent state."""
from langgraph.types import interrupt

from app.agent.deps import AgentDeps
from app.agent.state import AgentState
from app.db.models import RunEvidence, Ticket, TicketStatus
from app.services import policy as policy_mod
from app.services.actions import (
    create_action,
    execute_action,
    request_approval,
)
from app.services.audit import record_event
from app.services.retrieval import retrieve
from app.services.tickets import set_classification, transition_ticket


def make_nodes(deps: AgentDeps):
    def load_ticket(state: AgentState) -> dict:
        with deps.session() as db:
            ticket = db.get(Ticket, state["ticket_id"])
            if ticket is None:
                return {"error": "ticket_not_found", "disposition": "failed"}
            subject = (ticket.subject or "").strip()
            body = (ticket.body or "").strip()
            if not subject or not body:
                record_event(db, ticket.id, "malformed_input", {}, run_id=state["run_id"])
                transition_ticket(
                    db, ticket, TicketStatus.escalated, reason="malformed input"
                )
                return {
                    "subject": subject,
                    "body": body,
                    "disposition": "escalated",
                    "error": "malformed_input",
                    "policy": {
                        "decision": "deny",
                        "disposition": "escalated",
                        "reasons": ["malformed_input"],
                        "terminal_action": "escalate_to_human",
                        "supporting_actions": [],
                    },
                }
            # A run moves the ticket to processing regardless of which open
            # state it started from — otherwise e.g. a needs_information ticket
            # that is reprocessed after the customer replies can never reach
            # resolved (needs_information -> resolved is an invalid transition).
            if ticket.status in (
                TicketStatus.new,
                TicketStatus.needs_information,
                TicketStatus.escalated,
            ):
                transition_ticket(db, ticket, TicketStatus.processing, reason="run started", actor_id=None)
            record_event(db, ticket.id, "run_started", {"run_id": state["run_id"]}, run_id=state["run_id"])
            return {"subject": subject, "body": body}

    def classify(state: AgentState) -> dict:
        if state.get("disposition"):
            return {}
        result = deps.llm.classify_ticket(state["subject"], state["body"])
        with deps.session() as db:
            ticket = db.get(Ticket, state["ticket_id"])
            if ticket is not None:
                set_classification(ticket, result.category, result.priority)
                record_event(
                    db, ticket.id, "classified",
                    {
                        "category": result.category,
                        "priority": result.priority,
                        "missing_information": result.missing_information,
                    },
                    run_id=state["run_id"],
                )
        return {
            "category": result.category,
            "priority": result.priority,
            "missing_information": result.missing_information,
        }

    def retrieve_evidence(state: AgentState) -> dict:
        if state.get("disposition"):
            return {}
        query = f"{state['subject']}\n{state['body']}"
        from sqlalchemy import select as _select

        with deps.session() as db:
            ticket = db.get(Ticket, state["ticket_id"])
            # Retry-safe: if evidence was already persisted for this run, reuse it.
            existing = db.execute(
                _select(RunEvidence).where(RunEvidence.run_id == state["run_id"])
            ).scalars().all()
            if existing:
                return {
                    "evidence": [
                        {
                            "id": ev.chunk_id,
                            "chunk_id": ev.chunk_id,
                            "document_id": ev.document_id,
                            "document_title": "",
                            "score": ev.score,
                            "excerpt": ev.excerpt,
                            "retrieval_mode": "vector",
                        }
                        for ev in sorted(existing, key=lambda e: e.rank)
                    ]
                }
            chunks = retrieve(db, deps.settings, deps.embedder, query)
            evidence = []
            for c in chunks:
                db.add(
                    RunEvidence(
                        run_id=state["run_id"],
                        chunk_id=c.chunk_id,
                        document_id=c.document_id,
                        rank=c.rank,
                        score=c.score,
                        excerpt=c.excerpt,
                    )
                )
                evidence.append(
                    {
                        "id": c.chunk_id,
                        "chunk_id": c.chunk_id,
                        "document_id": c.document_id,
                        "document_title": c.document_title,
                        "score": c.score,
                        "excerpt": c.excerpt,
                        "retrieval_mode": c.retrieval_mode,
                    }
                )
            if ticket is not None:
                record_event(
                    db, ticket.id, "evidence_retrieved",
                    {"count": len(evidence), "top_score": evidence[0]["score"] if evidence else None,
                     "retrieval_mode": evidence[0]["retrieval_mode"] if evidence else None},
                    run_id=state["run_id"],
                )
        return {"evidence": evidence}

    def draft(state: AgentState) -> dict:
        if state.get("disposition"):
            return {}
        result = deps.llm.draft_response(
            state["subject"], state["body"], state.get("category") or "general", state.get("evidence", [])
        )
        return {
            "draft": {
                "response_text": result.response_text,
                "cited_evidence_ids": result.cited_evidence_ids,
                "action_type": result.proposed_action.action_type,
                "params": result.proposed_action.params,
                "wants_resolution": result.wants_resolution,
                "flags": result.flags,
            }
        }

    def validate_output(state: AgentState) -> dict:
        if state.get("disposition"):
            return {}
        draft = state.get("draft", {})
        evidence_ids = {e["id"] for e in state.get("evidence", [])}
        cited = [str(c) for c in draft.get("cited_evidence_ids", [])]
        invalid = [c for c in cited if c not in evidence_ids]
        issues = []
        if not draft.get("response_text"):
            issues.append("empty_response_text")
        if not draft.get("action_type"):
            issues.append("missing_action_type")
        return {
            "validation": {
                "citations_valid": not invalid,
                "invalid_citations": invalid,
                "issues": issues,
            }
        }

    def policy_gate(state: AgentState) -> dict:
        if state.get("disposition"):
            return {}
        draft = state["draft"]
        validation = state["validation"]
        outcome = policy_mod.evaluate(
            draft=policy_mod.DraftView(
                action_type=draft["action_type"],
                params=draft.get("params", {}),
                wants_resolution=draft.get("wants_resolution", False),
                cited_evidence_ids=draft.get("cited_evidence_ids", []),
                flags=draft.get("flags", []),
            ),
            validation=policy_mod.ValidationView(
                citations_valid=validation["citations_valid"],
                invalid_citations=validation["invalid_citations"],
                issues=validation["issues"],
            ),
            evidence_ids=[e["id"] for e in state.get("evidence", [])],
            missing_information=state.get("missing_information", []),
            category=state.get("category"),
        )
        policy = {
            "decision": outcome.decision,
            "disposition": outcome.disposition,
            "reasons": outcome.reasons,
            "terminal_action": outcome.terminal_action,
            "supporting_actions": outcome.supporting_actions,
        }
        with deps.session() as db:
            ticket = db.get(Ticket, state["ticket_id"])
            if ticket is not None:
                record_event(
                    db, ticket.id, "policy_decision",
                    {"decision": outcome.decision, "disposition": outcome.disposition,
                     "reasons": outcome.reasons},
                    run_id=state["run_id"],
                )
        return {"policy": policy}

    def _persist_actions(state: AgentState, db) -> tuple[list, object]:
        """Create ProposedAction rows for supporting + terminal actions.

        Idempotent: on resume/retry it reuses the already-persisted actions
        for this run instead of creating duplicates."""
        from sqlalchemy import select

        from app.db.models import AgentRun, ProposedAction

        policy = state["policy"]
        draft = state["draft"]
        run = db.get(AgentRun, state["run_id"])
        ticket = db.get(Ticket, state["ticket_id"])

        existing = db.execute(
            select(ProposedAction).where(ProposedAction.run_id == state["run_id"])
        ).scalars().all()
        by_type = {a.action_type: a for a in existing}

        supporting_ids = []
        for spec in policy.get("supporting_actions", []):
            a = by_type.get(spec["action_type"]) or create_action(
                db, run, ticket, spec["action_type"], spec["params"],
                "allow", ["auto_allowed_supporting_action"],
            )
            supporting_ids.append(a.id)

        terminal = by_type.get(policy["terminal_action"]) or create_action(
            db, run, ticket,
            policy["terminal_action"],
            draft.get("params", {}),
            policy["decision"],
            policy["reasons"],
            draft_response=draft.get("response_text"),
            cited_evidence_ids=draft.get("cited_evidence_ids", []),
        )
        return supporting_ids, terminal

    def execute(state: AgentState) -> dict:
        """Executes allowed terminal + supporting actions (deny -> escalate)."""
        if state.get("disposition"):
            return {}
        policy = state["policy"]
        if policy["decision"] == "require_approval":
            return {}
        with deps.session() as db:
            supporting_ids, terminal = _persist_actions(state, db)
            for aid in supporting_ids:
                execute_action(db, aid)
            execute_action(db, terminal.id)
            disposition = policy["disposition"]
            record_event(
                db, state["ticket_id"], "run_finished",
                {"disposition": disposition}, run_id=state["run_id"],
            )
        return {"disposition": disposition}

    def approval_gate(state: AgentState) -> dict:
        """Pause for a human decision. Idempotent across resumes: the approval
        row is created once; interrupt() returns the reviewer decision on resume."""
        if state.get("disposition"):
            return {}
        policy = state["policy"]
        from app.db.models import AgentRun

        with deps.session() as db:
            run = db.get(AgentRun, state["run_id"])
            ticket = db.get(Ticket, state["ticket_id"])
            supporting_ids, terminal = _persist_actions(state, db)
            for aid in supporting_ids:
                execute_action(db, aid)
            approval = request_approval(
                db, terminal, run, ticket, "; ".join(policy["reasons"]) or "approval required"
            )
            approval_id = approval.id
            transition_ticket(db, ticket, TicketStatus.pending_approval, reason="approval required")

        decision = interrupt({"approval_id": approval_id, "action": "review_required"})
        # --- resumed path (approved only; rejections complete the run in the API) ---
        dec = (decision or {}).get("decision", "rejected")
        reviewer_id = (decision or {}).get("reviewer_id")
        if dec != "approved":
            return {"disposition": "escalated", "approval_id": approval_id,
                    "approval_decision": dec}
        with deps.session() as db:
            action_id = _action_id_for_approval(db, approval_id)
            execute_action(db, action_id, actor_type="user", actor_id=reviewer_id)
            record_event(
                db, state["ticket_id"], "run_finished",
                {"disposition": "resolved"}, run_id=state["run_id"],
            )
        return {"disposition": "resolved", "approval_id": approval_id, "approval_decision": dec}

    return {
        "load_ticket": load_ticket,
        "classify": classify,
        "retrieve_evidence": retrieve_evidence,
        "draft": draft,
        "validate_output": validate_output,
        "policy_gate": policy_gate,
        "execute": execute,
        "approval_gate": approval_gate,
    }


def _action_id_for_approval(db, approval_id: str) -> str:
    from app.db.models import ApprovalRequest

    ap = db.get(ApprovalRequest, approval_id)
    return ap.action_id
