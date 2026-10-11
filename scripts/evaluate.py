"""Run the ResolveFlow evaluation dataset against a real database.

Usage:
  DATABASE_URL=postgresql+psycopg://... python scripts/evaluate.py \
      [--dataset evals/dataset.jsonl] [--provider deterministic|openai] \
      [--out evals/reports/latest.json]

Prints real, measured results — never fabricated.
"""
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langgraph.checkpoint.postgres import PostgresSaver
from sqlalchemy import select

from app.agent.deps import AgentDeps
from app.agent.graph import pg_conn_string
from app.core.config import get_settings
from app.db.models import EvalResult
from app.db.session import make_session_factory
from app.services.embeddings import get_embedder
from app.services.evals import run_dataset
from app.services.llm import get_llm_provider


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="evals/dataset.jsonl")
    parser.add_argument("--provider", default=None, help="override LLM_PROVIDER")
    parser.add_argument("--out", default="evals/reports/latest.json")
    args = parser.parse_args()

    settings = get_settings()
    if args.provider:
        settings.llm_provider = args.provider
    db_url = os.environ.get("EVAL_DATABASE_URL") or settings.database_url
    session_factory = make_session_factory(db_url)

    deps = AgentDeps(
        settings=settings,
        session_factory=session_factory,
        llm=get_llm_provider(settings),
        embedder=get_embedder(settings),
    )
    print(f"eval provider={deps.llm.name} dataset={args.dataset}")

    db = session_factory()
    try:
        with PostgresSaver.from_conn_string(pg_conn_string(db_url)) as cp:
            cp.setup()
            eval_run = run_dataset(
                Path(args.dataset), settings, session_factory, cp, deps, db
            )
        results = db.execute(
            select(EvalResult).where(EvalResult.eval_run_id == eval_run.id)
        ).scalars().all()
        report = {
            "eval_run_id": eval_run.id,
            "summary": eval_run.summary,
            "cases": [
                {
                    "case_id": r.case_id,
                    "passed": r.passed,
                    "detail": r.detail,
                    "actual": r.actual,
                    "latency_ms": r.latency_ms,
                }
                for r in results
            ],
        }
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2, default=str))
        print(json.dumps(eval_run.summary, indent=2))
        failures = [r.case_id for r in results if not r.passed]
        if failures:
            print(f"FAILED cases: {failures}")
        print(f"report written to {out_path}")
        return 0 if not failures else 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
