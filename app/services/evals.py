"""Evaluation runner: executes labelled dataset cases through the real
pipeline (same code path the worker uses) and records actual outcomes.

Never uses an LLM's self-evaluation as ground truth — expectations come from
the dataset labels and deterministic safety assertions.
"""
import json
import time
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.deps import AgentDeps
from app.agent.graph import run_workflow_once
from app.core.config import Settings
from app.db.models import (
    ActionStatus,
    AgentRun,
    ApprovalRequest,
    EvalResult,
    EvalRun,
    ProposedAction,
    RunDisposition,
    RunStatus,
    Ticket,
    TicketPriority,
)
from app.services.actions import decide_approval
from app.services.knowledge import ingest_document
from app.services.llm import (
    ClassificationResult,
    DraftResult,
    LLMMalformedOutputError,
    LLMTimeoutError,
)


class FaultyProvider:
    """Wraps a provider to simulate provider faults for eval cases."""

    def __init__(self, inner, mode: str):
        self._inner = inner
        self.name = f"{inner.name}-fault-{mode}"
        self._mode = mode

    def classify_ticket(self, subject: str, body: str) -> ClassificationResult:
        if self._mode == "timeout":
            raise LLMTimeoutError("simulated provider timeout")
        if self._mode == "malformed":
            raise LLMMalformedOutputError("simulated malformed model output")
        return self._inner.classify_ticket(subject, body)

    def draft_response(self, subject: str, body: str, category: str, evidence: list) -> DraftResult:
        if self._mode == "malformed":
            raise LLMMalformedOutputError("simulated malformed draft output")
        return self._inner.draft_response(subject, body, category, evidence)


def _execute_run(deps: AgentDeps, checkpointer, session_factory, run: AgentRun) -> tuple[dict, bool]:
    """Mirror of worker.process_run's graph invocation for eval use."""
    db = session_factory()
    try:
        approval = db.execute(
            select(ApprovalRequest).where(ApprovalRequest.run_id == run.id)
        ).scalar_one_or_none()
        resume = None
        if approval and approval.status.value == "approved":
            resume = {"decision": "approved", "reviewer_id": approval.reviewer_id}
        return run_workflow_once(
            deps, checkpointer, ticket_id=run.ticket_id, run_id=run.id,
            thread_id=run.langgraph_thread_id, resume_decision=resume,
        )
    finally:
        db.close()


def _run_case(
    case: dict,
    deps: AgentDeps,
    checkpointer,
    session_factory,
    settings: Settings,
) -> dict:
    """Execute one dataset case; returns actual observed outcomes."""
    actual: dict = {"disposition": None, "policy_decision": None, "action_types_executed": [],
                    "ticket_status": None, "run_status": None, "category": None}
    deps_local = deps
    if case.get("faulty_llm"):
        deps_local = AgentDeps(
            settings=deps.settings,
            session_factory=deps.session_factory,
            llm=FaultyProvider(deps.llm, case["faulty_llm"]),
            embedder=deps.embedder,
        )

    db = session_factory()
    try:
        for doc_spec in case.get("documents", []):
            ingest_document(
                db, settings, deps_local.embedder,
                title=doc_spec["title"], filename=doc_spec.get("filename", "doc.md"),
                data=doc_spec["content"].encode("utf-8"),
            )
        t = case["ticket"]
        ticket = Ticket(
            subject=t["subject"], body=t["body"],
            requester_email="eval@eval.local",
            priority=TicketPriority(t.get("priority", "medium")),
        )
        ticket.tags = ["eval"]
        db.add(ticket)
        run = AgentRun(
            ticket_id=ticket.id,
            langgraph_thread_id=f"eval-{uuid.uuid4()}",
            provider=deps_local.llm.name,
            max_attempts=settings.run_max_attempts,
        )
        db.add(run)
        db.commit()
        run_id, ticket_id = run.id, ticket.id
    finally:
        db.close()

    started = time.monotonic()
    try:
        final, interrupted = _execute_run(deps_local, checkpointer, session_factory, run)
    except Exception as e:
        interrupted = False
        final = {"disposition": "failed", "error": f"{type(e).__name__}: {e}"}
    latency_ms = int((time.monotonic() - started) * 1000)

    db = session_factory()
    try:
        run = db.get(AgentRun, run_id)
        ticket = db.get(Ticket, ticket_id)
        run.status = RunStatus.awaiting_approval if interrupted else (
            RunStatus.failed if final.get("disposition") == "failed" else RunStatus.completed
        )
        run.disposition = (
            RunDisposition.pending_approval if interrupted
            else RunDisposition(final.get("disposition", "failed"))
        )
        run.finished_at = None if interrupted else run.finished_at

        # Optional approval decision step.
        approval_action = case.get("approval")
        if interrupted and approval_action in ("approve", "reject"):
            approval = db.execute(
                select(ApprovalRequest).where(ApprovalRequest.run_id == run.id)
            ).scalar_one()
            decide_approval(
                db, approval, reviewer_id="eval-reviewer",
                approve=approval_action == "approve", note="eval decision",
            )
            db.commit()
            if approval_action == "approve":
                # Resume run as the worker would.
                run.status = RunStatus.running
                final2, interrupted2 = _execute_run(deps_local, checkpointer, session_factory, run)
                run.status = RunStatus.awaiting_approval if interrupted2 else RunStatus.completed
                run.disposition = (
                    RunDisposition.pending_approval if interrupted2
                    else RunDisposition(final2.get("disposition", "failed"))
                )
        db.commit()

        actions = db.execute(
            select(ProposedAction).where(ProposedAction.run_id == run.id)
        ).scalars().all()
        actual["disposition"] = run.disposition.value if run.disposition else None
        actual["run_status"] = run.status.value
        actual["ticket_status"] = ticket.status.value
        actual["category"] = ticket.category.value if ticket.category else None
        actual["action_types_executed"] = [
            a.action_type for a in actions if a.status == ActionStatus.executed
        ]
        actual["policy_decision"] = next(
            (a.policy_decision.value for a in actions
             if a.action_type in ("resolve_ticket", "send_response_and_resolve",
                                  "request_information", "escalate_to_human")),
            None,
        )
        actual["latency_ms"] = latency_ms
        actual["error"] = run.error
    finally:
        db.close()
    return actual


def evaluate_case(case: dict, actual: dict) -> tuple[bool, str]:
    """Deterministic assertions for one case."""
    expect = case.get("expect", {})
    failures = []
    if "disposition" in expect and actual.get("disposition") != expect["disposition"]:
        failures.append(f"disposition: expected {expect['disposition']} got {actual.get('disposition')}")
    if "category" in expect and actual.get("category") != expect["category"]:
        failures.append(f"category: expected {expect['category']} got {actual.get('category')}")
    if "ticket_status" in expect and actual.get("ticket_status") != expect["ticket_status"]:
        failures.append(f"ticket_status: expected {expect['ticket_status']} got {actual.get('ticket_status')}")
    for prohibited in expect.get("prohibited_actions", []):
        if prohibited in (actual.get("action_types_executed") or []):
            failures.append(f"prohibited action executed: {prohibited}")
    if expect.get("requires_no_escalation") and actual.get("disposition") == "escalated":
        failures.append("unexpected escalation")
    if expect.get("not_resolved") and actual.get("ticket_status") == "resolved":
        failures.append("ticket must not be resolved")
    return (not failures), "; ".join(failures)


def run_dataset(
    dataset_path: Path,
    settings: Settings,
    session_factory,
    checkpointer,
    deps: AgentDeps,
    db: Session,
) -> EvalRun:
    cases = []
    with open(dataset_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                cases.append(json.loads(line))

    # Ingest the shared eval corpus once (deduplicated by checksum).
    import hashlib as _hashlib

    from app.db.models import KnowledgeDocument

    corpus_dir = dataset_path.parent / "knowledge"
    if corpus_dir.is_dir():
        for path in sorted(corpus_dir.glob("*.md")):
            data = path.read_bytes()
            checksum = _hashlib.sha256(data).hexdigest()
            exists = db.execute(
                select(KnowledgeDocument).where(KnowledgeDocument.checksum == checksum)
            ).scalar_one_or_none()
            if not exists:
                ingest_document(
                    db, settings, deps.embedder, title=path.stem,
                    filename=path.name, data=data,
                )
        db.commit()

    eval_run = EvalRun(
        dataset_name=dataset_path.name,
        provider=deps.llm.name,
        status="running",
    )
    db.add(eval_run)
    db.commit()

    passed_count = 0
    for case in cases:
        try:
            actual = _run_case(case, deps, checkpointer, session_factory, settings)
        except Exception as e:
            actual = {"disposition": "failed", "error": f"{type(e).__name__}: {e}"}
        ok, detail = evaluate_case(case, actual)
        if ok:
            passed_count += 1
        db.add(
            EvalResult(
                eval_run_id=eval_run.id,
                case_id=case["case_id"],
                passed=ok,
                expected=case.get("expect", {}),
                actual=actual,
                detail=detail or None,
                latency_ms=actual.get("latency_ms"),
            )
        )
        db.commit()

    total = len(cases)
    summary = {
        "dataset_size": total,
        "passed": passed_count,
        "failed": total - passed_count,
        "pass_rate": round(passed_count / total, 4) if total else None,
        "provider": deps.llm.name,
        "mode": "deterministic" if deps.llm.name == "deterministic" else "live-model",
        "avg_latency_ms": None,
    }
    latencies = [
        r.latency_ms for r in db.execute(
            select(EvalResult).where(EvalResult.eval_run_id == eval_run.id)
        ).scalars().all() if r.latency_ms
    ]
    if latencies:
        summary["avg_latency_ms"] = round(sum(latencies) / len(latencies), 1)
    eval_run.summary = summary
    eval_run.status = "completed"
    from datetime import datetime, timezone

    eval_run.finished_at = datetime.now(timezone.utc)
    db.commit()
    return eval_run
