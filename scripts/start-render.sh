#!/usr/bin/env bash
set -e
set -m

PDF_WORKER_PID=""
CONV_WORKER_PID=""
UVICORN_PID=""

cleanup() {
    trap '' SIGINT SIGTERM
    echo "==> [Knora Render] Stopping service processes..."
    # Include jobs spawned just before their PID assignment and descendants of dead workers.
    for PID in $PDF_WORKER_PID $CONV_WORKER_PID $UVICORN_PID $(jobs -p); do
        kill -TERM -- "-$PID" 2>/dev/null || true
    done
    wait 2>/dev/null || true
}

trap cleanup EXIT
trap 'exit 0' SIGINT SIGTERM

echo "==> [Knora Render] Running database migrations with Alembic..."
alembic upgrade head

echo "==> [Knora Render] Starting background PDF Ingestion Worker..."
python -m knora.adapters.cli.worker &
PDF_WORKER_PID=$!

echo "==> [Knora Render] Starting background Conversation Worker..."
python scripts/run_conversation_worker.py &
CONV_WORKER_PID=$!

echo "==> [Knora Render] Starting Uvicorn API server on 0.0.0.0:${PORT:-8000}..."
uvicorn knora.main:app --host 0.0.0.0 --port "${PORT:-8000}" &
UVICORN_PID=$!

STATUS=0
# Bash before 5.3 can omit already-terminated jobs from wait -n.
while true; do
    for PID in "$PDF_WORKER_PID" "$CONV_WORKER_PID" "$UVICORN_PID"; do
        if ! kill -0 "$PID" 2>/dev/null; then
            wait "$PID" || STATUS=$?
            echo "==> [Knora Render] Required process exited unexpectedly (status $STATUS)."
            if [ "$STATUS" -eq 0 ]; then
                STATUS=1
            fi
            exit "$STATUS"
        fi
    done
    sleep 1
done
