from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.api.router import api_router
from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging

settings = get_settings()
settings.validate_runtime()
configure_logging()

MAX_BODY_BYTES = 2 * 1024 * 1024  # bounded request size


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        length = request.headers.get("content-length")
        if length and int(length) > MAX_BODY_BYTES:
            return JSONResponse(
                status_code=413,
                content={"error": {"code": "payload_too_large", "message": "Request body too large", "details": {}}},
            )
        return await call_next(request)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure LangGraph checkpoint tables exist so the API/worker share state.
    try:
        from langgraph.checkpoint.postgres import PostgresSaver

        from app.agent.graph import pg_conn_string

        with PostgresSaver.from_conn_string(pg_conn_string(settings.database_url)) as cp:
            cp.setup()
    except Exception as e:  # readiness endpoint reports DB health separately
        import logging

        logging.getLogger(__name__).warning("checkpoint setup skipped: %s", e)
    yield


app = FastAPI(
    title="ResolveFlow API",
    version="0.1.0",
    description="Evidence-grounded autonomous customer-support operations backend",
    lifespan=lifespan,
)
app.add_middleware(RequestSizeLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
)
register_error_handlers(app)
app.include_router(api_router)
