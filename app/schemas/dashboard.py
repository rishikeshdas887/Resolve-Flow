from pydantic import BaseModel


class DashboardSummary(BaseModel):
    tickets_total: int
    tickets_by_status: dict[str, int]
    tickets_by_priority: dict[str, int]
    tickets_by_category: dict[str, int]
    open_tickets: int
    runs_total: int
    runs_by_status: dict[str, int]
    runs_completed_24h: int
    avg_run_duration_ms: float | None
    pending_approvals: int
    resolved_tickets: int
    resolution_rate: float | None
    knowledge_documents: int
    knowledge_chunks: int
