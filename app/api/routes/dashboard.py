from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import require_staff
from app.db.models import User
from app.db.session import get_db
from app.schemas.dashboard import DashboardSummary
from app.services.metrics import dashboard_summary

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary)
def summary(
    db: Session = Depends(get_db),
    user: User = Depends(require_staff),
) -> DashboardSummary:
    return dashboard_summary(db)
