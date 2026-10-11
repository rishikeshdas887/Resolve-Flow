#!/usr/bin/env bash
set -e

echo "[entrypoint] Running database migrations..."
alembic upgrade head || echo "[entrypoint] Warning: alembic upgrade failed or skipped."

echo "[entrypoint] Starting background agent worker..."
python -m app.worker &
WORKER_PID=$!

cleanup() {
    echo "[entrypoint] Stopping background worker (PID $WORKER_PID)..."
    kill -TERM "$WORKER_PID" 2>/dev/null || true
    wait "$WORKER_PID" 2>/dev/null || true
}
trap cleanup SIGTERM SIGINT

PORT="${PORT:-8000}"
echo "[entrypoint] Starting FastAPI web server on port $PORT..."
uvicorn app.main:app --host 0.0.0.0 --port "$PORT" &
API_PID=$!

wait -n "$API_PID" "$WORKER_PID" || true
cleanup
