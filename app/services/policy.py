"""Deterministic action/risk policy.

The model may PROPOSE; this module DECIDES. No LLM output (including
confidence) is used as an authorization signal.
"""
from dataclasses import dataclass, field

# --- Action registry ---------------------------------------------------------
# Low-risk actions the policy may auto-execute.
AUTO_ALLOWED_ACTIONS = {"add_tag", "assign_queue", "add_internal_note", "request_information"}
# Terminal action that can auto-execute ONLY when every eligibility check passes.
RESOLVE_ACTION = "resolve_ticket"
# Allowed to exist but ALWAYS requires an authorized human decision first.
APPROVAL_REQUIRED_ACTIONS = {"send_response_and_resolve"}
# Never executed by the agent in this prototype — escalates to a human instead.
DENIED_ACTIONS = {
    "refund_payment",
    "reset_credentials",
    "modify_account",
    "delete_data",
    "grant_access",
    "external_side_effect",
}
# Terminal (non-execution) disposition action.
ESCALATE_ACTION = "escalate_to_human"

KNOWN_ACTIONS = (
    AUTO_ALLOWED_ACTIONS
    | {RESOLVE_ACTION, ESCALATE_ACTION}
    | APPROVAL_REQUIRED_ACTIONS
    | DENIED_ACTIONS
)

ALLOWED_TAGS = {"billing", "technical", "account", "shipping", "refund", "vip", "duplicate", "docs-gap"}
ALLOWED_QUEUES = {"general", "billing", "technical", "tier2", "escalations"}
# Categories that may be auto-resolved when all other eligibility checks pass.
RESOLVABLE_CATEGORIES = {"billing", "technical", "shipping", "account", "general"}


@dataclass
class DraftView:
    action_type: str
    params: dict
    wants_resolution: bool
    cited_evidence_ids: list[str]
    flags: list[str]


@dataclass
class ValidationView:
    citations_valid: bool
    invalid_citations: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)


@dataclass
class PolicyOutcome:
    decision: str  # allow | require_approval | deny
    disposition: str  # resolved | needs_information | pending_approval | escalated
    reasons: list[str]
    terminal_action: str  # resolve_ticket | send_response_and_resolve | request_information | escalate_to_human
    supporting_actions: list[dict] = field(default_factory=list)


def _sanitize_params(action_type: str, params: dict) -> dict:
    """Bound params; strip anything not needed. Retrieved/uploaded text is
    untrusted and can never expand this allowlist."""
    if action_type == "add_tag":
        return {"tag": str(params.get("tag", ""))[:50]}
    if action_type == "assign_queue":
        return {"queue": str(params.get("queue", ""))[:50]}
    if action_type in ("add_internal_note", "request_information"):
        return {"note": str(params.get("note", params.get("question", "")))[:2000]}
    return {}


def evaluate(
    draft: DraftView,
    validation: ValidationView,
    evidence_ids: list[str],
    missing_information: list[str],
    category: str | None,
) -> PolicyOutcome:
    """Apply the deterministic policy. Order matters — first match wins."""
    reasons: list[str] = []
    supporting: list[dict] = []

    # Supporting (non-terminal) low-risk proposals execute alongside the
    # terminal decision if their params pass the allowlist.
    action_type = draft.action_type
    if action_type in AUTO_ALLOWED_ACTIONS:
        supporting.append({"action_type": action_type, "params": _sanitize_params(action_type, draft.params)})
        action_type = RESOLVE_ACTION if draft.wants_resolution else "add_internal_note"

    # 1. Prompt-injection flag → escalate, never act on injected content.
    if "injection_suspected" in draft.flags:
        return PolicyOutcome("deny", "escalated", ["prompt_injection_suspected"], ESCALATE_ACTION)

    # 2. Fabricated/invalid citations → cannot trust the draft → escalate.
    if not validation.citations_valid:
        return PolicyOutcome(
            "deny",
            "escalated",
            ["citation_validation_failed", f"invalid: {validation.invalid_citations}"],
            ESCALATE_ACTION,
        )

    # 3. Other structural validation issues → conservative escalation.
    if validation.issues:
        return PolicyOutcome(
            "deny", "escalated", [f"output_validation_failed: {i}" for i in validation.issues],
            ESCALATE_ACTION,
        )

    # 4. Missing required information → ask the customer (auto-allowed).
    if missing_information:
        return PolicyOutcome(
            "allow",
            "needs_information",
            [f"missing_information: {m}" for m in missing_information],
            "request_information",
            supporting,
        )

    # 5. Denied/sensitive proposal → never auto-executed → escalate.
    if action_type in DENIED_ACTIONS or action_type not in KNOWN_ACTIONS:
        reason = "sensitive_action_proposed" if action_type in DENIED_ACTIONS else "unsupported_action_proposed"
        return PolicyOutcome("deny", "escalated", [reason, action_type], ESCALATE_ACTION)

    # 6. Model asked for a human → escalate with reasons.
    if action_type == ESCALATE_ACTION or "no_evidence" in draft.flags:
        reasons = ["agent_requested_escalation"]
        if "no_evidence" in draft.flags:
            reasons.append("no_evidence_retrieved")
        return PolicyOutcome("deny", "escalated", reasons, ESCALATE_ACTION)

    # 7. Approval-gated action (external side effect + resolution).
    if action_type in APPROVAL_REQUIRED_ACTIONS:
        if not evidence_ids:
            return PolicyOutcome("deny", "escalated", ["no_evidence_for_resolution"], ESCALATE_ACTION)
        return PolicyOutcome(
            "require_approval",
            "pending_approval",
            ["action_requires_human_approval", action_type],
            action_type,
            supporting,
        )

    # 8. Resolution — allowed only when every eligibility check passes.
    if action_type == RESOLVE_ACTION:
        blockers: list[str] = []
        if not draft.wants_resolution:
            blockers.append("model_did_not_propose_resolution")
        if not evidence_ids:
            blockers.append("no_evidence_retrieved")
        if not draft.cited_evidence_ids:
            blockers.append("no_cited_evidence")
        if category and category not in RESOLVABLE_CATEGORIES:
            blockers.append(f"category_{category}_not_auto_resolvable")
        if blockers:
            return PolicyOutcome("deny", "escalated", blockers, ESCALATE_ACTION)
        return PolicyOutcome("allow", "resolved", ["all_eligibility_checks_passed"], RESOLVE_ACTION, supporting)

    # Unreachable for known actions, but stay conservative.
    return PolicyOutcome("deny", "escalated", ["unhandled_action_type"], ESCALATE_ACTION)
