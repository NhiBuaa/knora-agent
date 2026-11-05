#!/usr/bin/env bash
set -e

echo "==> [Knora Render] Running database migrations with Alembic..."
alembic upgrade head

echo "==> [Knora Render] Starting background PDF Ingestion Worker..."
python -m knora.adapters.cli.worker &
PDF_WORKER_PID=$!

echo "==> [Knora Render] Starting background Conversation Worker..."
python scripts/run_conversation_worker.py &
CONV_WORKER_PID=$!

cleanup() {
    echo "==> [Knora Render] Termination signal received. Stopping worker processes..."
    kill -TERM "$UVICORN_PID" 2>/dev/null || true
    kill -TERM "$PDF_WORKER_PID" 2>/dev/null || true
    kill -TERM "$CONV_WORKER_PID" 2>/dev/null || true
    wait "$UVICORN_PID" 2>/dev/null || true
    wait "$PDF_WORKER_PID" 2>/dev/null || true
    wait "$CONV_WORKER_PID" 2>/dev/null || true
    exit 0
}

trap cleanup SIGINT SIGTERM

echo "==> [Knora Render] Starting Uvicorn API server on 0.0.0.0:${PORT:-8000}..."
uvicorn knora.main:app --host 0.0.0.0 --port "${PORT:-8000}" &
UVICORN_PID=$!

wait "$UVICORN_PID"
