from fastapi import APIRouter

from app.api.routes import (
    approvals,
    auth,
    dashboard,
    evals,
    health,
    knowledge,
    runs,
    tickets,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router, prefix="/api/v1")
api_router.include_router(tickets.router, prefix="/api/v1")
api_router.include_router(runs.router, prefix="/api/v1")
api_router.include_router(knowledge.router, prefix="/api/v1")
api_router.include_router(approvals.router, prefix="/api/v1")
api_router.include_router(dashboard.router, prefix="/api/v1")
api_router.include_router(evals.router, prefix="/api/v1")
