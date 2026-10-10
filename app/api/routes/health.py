from fastapi import APIRouter
from sqlalchemy import text

from app.db.session import engine

router = APIRouter(tags=["health"])


@router.get("/health/live")
def liveness() -> dict:
    return {"status": "ok"}


@router.get("/health/ready")
def readiness() -> dict:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=503, content={"status": "unavailable", "db": "down"})
    return {"status": "ok", "db": "up"}
