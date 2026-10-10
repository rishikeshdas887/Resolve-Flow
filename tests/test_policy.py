"""Unit tests for the deterministic action/risk policy."""
from app.services.policy import DraftView, ValidationView, evaluate


def base_draft(**kw):
    d = {
        "action_type": "resolve_ticket",
        "params": {},
        "wants_resolution": True,
        "cited_evidence_ids": ["e1"],
        "flags": [],
    }
    d.update(kw)
    return DraftView(**d)


def ok_validation():
    return ValidationView(citations_valid=True)


def test_allows_resolution_when_all_checks_pass():
    out = evaluate(base_draft(), ok_validation(), ["e1"], [], "billing")
    assert out.decision == "allow" and out.disposition == "resolved"
    assert out.terminal_action == "resolve_ticket"


def test_denies_resolution_without_evidence():
    out = evaluate(base_draft(), ok_validation(), [], [], "billing")
    assert out.disposition == "escalated" and out.decision == "deny"


def test_denies_resolution_without_citations():
    out = evaluate(base_draft(cited_evidence_ids=[]), ok_validation(), ["e1"], [], "billing")
    assert out.disposition == "escalated"


def test_invalid_citations_escalate():
    v = ValidationView(citations_valid=False, invalid_citations=["bogus"])
    out = evaluate(base_draft(), v, ["e1"], [], "billing")
    assert out.decision == "deny" and out.disposition == "escalated"
    assert "citation_validation_failed" in out.reasons[0]


def test_missing_information_requests_info():
    out = evaluate(base_draft(), ok_validation(), ["e1"], ["order number"], "shipping")
    assert out.disposition == "needs_information" and out.decision == "allow"
    assert out.terminal_action == "request_information"


def test_sensitive_actions_denied_and_escalated():
    for t in ("refund_payment", "reset_credentials", "modify_account", "delete_data"):
        out = evaluate(base_draft(action_type=t), ok_validation(), ["e1"], [], "refund")
        assert out.decision == "deny" and out.disposition == "escalated", t


def test_unknown_action_denied():
    out = evaluate(base_draft(action_type="delete_everything"), ok_validation(), ["e1"], [], "general")
    assert out.decision == "deny" and out.disposition == "escalated"


def test_approval_required_action():
    out = evaluate(base_draft(action_type="send_response_and_resolve"), ok_validation(), ["e1"], [], "refund")
    assert out.decision == "require_approval" and out.disposition == "pending_approval"


def test_approval_action_needs_evidence():
    out = evaluate(base_draft(action_type="send_response_and_resolve"), ok_validation(), [], [], "refund")
    assert out.decision == "deny" and out.disposition == "escalated"


def test_injection_flag_escalates():
    out = evaluate(base_draft(flags=["injection_suspected"]), ok_validation(), ["e1"], [], "billing")
    assert out.decision == "deny" and out.disposition == "escalated"


def test_no_evidence_flag_escalates():
    out = evaluate(
        base_draft(action_type="escalate_to_human", flags=["no_evidence"]),
        ok_validation(), [], [], "general",
    )
    assert out.disposition == "escalated"


def test_model_cannot_override_policy_via_params():
    # Params are sanitized to an allowlist; injected params cannot expand it.
    d = base_draft(action_type="add_tag", params={"tag": "vip", "also_execute": "refund_payment"})
    out = evaluate(d, ok_validation(), ["e1"], [], "billing")
    for a in out.supporting_actions:
        assert set(a["params"].keys()) == {"tag"}


def test_resolution_blocked_for_refund_category():
    out = evaluate(base_draft(), ok_validation(), ["e1"], [], "refund")
    assert out.disposition == "escalated"  # refund is not auto-resolvable
