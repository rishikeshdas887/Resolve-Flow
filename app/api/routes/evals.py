from pathlib import Path

from fastapi import APIRouter, Depends, status
from langgraph.checkpoint.postgres import PostgresSaver
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agent.deps import AgentDeps
from app.agent.graph import pg_conn_string
from app.core.config import Settings, get_settings
from app.core.deps import Pagination, require_admin, require_staff
from app.core.errors import NotFoundError
from app.db.models import EvalResult, EvalRun, User
from app.db.session import get_db, make_session_factory
from app.schemas.common import Page, make_page
from app.schemas.evals import EvalResultOut, EvalRunOut, EvalRunRequest
from app.services.embeddings import get_embedder
from app.services.evals import run_dataset
from app.services.llm import get_llm_provider

router = APIRouter(prefix="/evals", tags=["evals"])

DATASET_DIR = Path(__file__).resolve().parents[3] / "evals"


def _dataset_path(name: str) -> Path:
    safe = Path(name).name
    for candidate in (DATASET_DIR / safe, DATASET_DIR / f"{safe}.jsonl"):
        if candidate.exists():
            return candidate
    default = DATASET_DIR / "dataset.jsonl"
    if name == "default" and default.exists():
        return default
    raise NotFoundError(f"Eval dataset {name!r} not found")


@router.post("/runs", response_model=EvalRunOut, status_code=status.HTTP_201_CREATED)
def trigger_eval(
    body: EvalRunRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(require_admin),
) -> EvalRunOut:
    dataset = _dataset_path(body.dataset)
    session_factory = make_session_factory(settings.database_url)
    deps = AgentDeps(
        settings=settings,
        session_factory=session_factory,
        llm=get_llm_provider(settings),
        embedder=get_embedder(settings),
    )
    with PostgresSaver.from_conn_string(pg_conn_string(settings.database_url)) as cp:
        cp.setup()
        eval_run = run_dataset(dataset, settings, session_factory, cp, deps, db)
    return EvalRunOut.model_validate(eval_run)


@router.get("/runs", response_model=Page[EvalRunOut])
def list_eval_runs(
    db: Session = Depends(get_db),
    user: User = Depends(require_staff),
    pagination: Pagination = Depends(),
) -> Page[EvalRunOut]:
    stmt = select(EvalRun).order_by(EvalRun.started_at.desc())
    total = db.scalar(select(func.count(EvalRun.id))) or 0
    items = db.execute(stmt.offset(pagination.offset).limit(pagination.size)).scalars().all()
    return make_page(
        [EvalRunOut.model_validate(r) for r in items],
        total, pagination.page, pagination.size,
    )


@router.get("/runs/{run_id}", response_model=EvalRunOut)
def get_eval_run(
    run_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_staff),
) -> EvalRunOut:
    eval_run = db.get(EvalRun, run_id)
    if eval_run is None:
        raise NotFoundError("Eval run not found")
    results = db.execute(
        select(EvalResult).where(EvalResult.eval_run_id == eval_run.id)
        .order_by(EvalResult.created_at)
    ).scalars().all()
    out = EvalRunOut.model_validate(eval_run)
    out.results = [EvalResultOut.model_validate(r) for r in results]
    return out
