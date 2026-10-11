"""LangGraph workflow assembly and run helpers."""
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from app.agent.deps import AgentDeps
from app.agent.nodes import make_nodes
from app.agent.state import AgentState
from app.core.logging import get_logger

logger = get_logger(__name__)


def _route_after_policy(state: AgentState):
    if state.get("disposition"):
        return END
    decision = (state.get("policy") or {}).get("decision")
    if decision == "require_approval":
        return "approval_gate"
    return "execute"


def build_graph(deps: AgentDeps, checkpointer=None):
    builder = StateGraph(AgentState)
    for name, fn in make_nodes(deps).items():
        builder.add_node(name, fn)
    builder.add_edge(START, "load_ticket")
    builder.add_edge("load_ticket", "classify")
    builder.add_edge("classify", "retrieve_evidence")
    builder.add_edge("retrieve_evidence", "draft")
    builder.add_edge("draft", "validate_output")
    builder.add_edge("validate_output", "policy_gate")
    builder.add_conditional_edges(
        "policy_gate",
        _route_after_policy,
        {"execute": "execute", "approval_gate": "approval_gate", END: END},
    )
    builder.add_edge("execute", END)
    builder.add_edge("approval_gate", END)
    return builder.compile(checkpointer=checkpointer)


def pg_conn_string(sqlalchemy_url: str) -> str:
    """Convert a SQLAlchemy psycopg URL to a plain libpq/psycopg conn string."""
    return sqlalchemy_url.replace("+psycopg", "")


def run_workflow_once(
    deps: AgentDeps,
    checkpointer,
    ticket_id: str,
    run_id: str,
    thread_id: str,
    resume_decision: dict | None = None,
) -> tuple[AgentState, bool]:
    """Invoke the graph for a run. Returns (state, interrupted).

    With resume_decision set, resumes the pending interrupt via a Command
    instead of starting fresh."""
    graph = build_graph(deps, checkpointer=checkpointer)
    config = {"configurable": {"thread_id": thread_id}}
    if resume_decision is not None:
        result = graph.invoke(Command(resume=resume_decision), config)
    else:
        result = graph.invoke(
            {"ticket_id": ticket_id, "run_id": run_id}, config
        )
    snapshot = graph.get_state(config)
    interrupted = bool(getattr(snapshot, "next", None))
    return result, interrupted
