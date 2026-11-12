from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
GIT_BASH = Path(os.environ.get("PROGRAMFILES", "C:/Program Files")) / "Git/bin/bash.exe"
BASH = str(GIT_BASH) if os.name == "nt" and GIT_BASH.is_file() else shutil.which("bash")

HARNESS = r"""
set -m
wait_for_start() {
    for expected in "$@"; do
        until grep -qx "$expected:started" "$EVENTS" 2>/dev/null; do sleep 0.01; done
    done
}
run_child() {
    local role=$1
    trap 'printf "%s:stopped\n" "$role" >> "$EVENTS"; exit 0' TERM
    printf '%s\n' "$BASHPID" >> "$CHILD_PIDS"
    if [[ "$role" == "pdf" && "$SPAWN_EXTRACTOR" == "1" ]]; then
        run_child extractor &
    fi
    printf '%s:started\n' "$role" >> "$EVENTS"
    if [[ "$role" == "$FAIL_ROLE" ]]; then
        wait_for_start pdf conversation
        if [[ "$DELAY_API_START" != "1" ]]; then wait_for_start api; fi
        if [[ "$SPAWN_EXTRACTOR" == "1" ]]; then wait_for_start extractor; fi
        printf '%s:exited\n' "$role" >> "$EVENTS"
        return "$FAIL_CODE"
    fi
    while true; do sleep 0.05; done
}
alembic() { return "$MIGRATION_CODE"; }
python() {
    if [[ "$1" == "-m" ]]; then run_child pdf; else run_child conversation; fi
}
uvicorn() { run_child api; }
echo() {
    if [[ "$SEND_EARLY_TERM" == "1" && "$*" == *"Starting background Conversation"* ]]; then
        wait_for_start pdf
        if [[ "$SPAWN_EXTRACTOR" == "1" ]]; then wait_for_start extractor; fi
        kill -TERM "$BASHPID"
    fi
    if [[ "$DELAY_API_START" == "1" && "$*" == *"Starting Uvicorn"* ]]; then
        while kill -0 "$PDF_WORKER_PID" 2>/dev/null; do sleep 0.01; done
    fi
    builtin echo "$@"
}
parent=$BASHPID
(sleep 5
 printf 'watchdog:fired\n' >> "$EVENTS"
 if [[ -f "$CHILD_PIDS" ]]; then
     while read -r pid; do kill -TERM -- "-$pid" 2>/dev/null || true; done < "$CHILD_PIDS"
 fi
 kill -TERM "$parent" 2>/dev/null || true) &
if [[ "$SEND_TERM" == "1" ]]; then
    (wait_for_start pdf conversation api; kill -TERM "$parent") &
fi
source "$1"
"""


@pytest.mark.parametrize("role", ["pdf", "conversation", "api"])
@pytest.mark.parametrize("exit_code", [0, 7])
def test_render_exits_and_stops_other_processes_when_one_child_exits(tmp_path, role, exit_code):
    result, events = run_startup(tmp_path, fail_role=role, fail_code=exit_code)
    assert result.returncode == (exit_code or 1), result.stdout + result.stderr
    for other in {"pdf", "conversation", "api"} - {role}:
        assert f"{other}:stopped" in events


@pytest.mark.parametrize("exit_code", [0, 7])
def test_render_detects_worker_that_exited_before_supervision_started(tmp_path, exit_code):
    result, events = run_startup(
        tmp_path, fail_role="pdf", fail_code=exit_code, delay_api_start=True
    )
    assert result.returncode == (exit_code or 1), result.stdout + result.stderr
    assert "conversation:stopped" in events
    if "api:started" in events:
        assert "api:stopped" in events


def test_render_does_not_start_processes_after_migration_failure(tmp_path):
    result, events = run_startup(tmp_path, migration_code=17)
    assert result.returncode == 17
    assert events == []


def test_render_stops_all_processes_on_termination(tmp_path):
    result, events = run_startup(tmp_path, send_term=True)
    assert result.returncode == 0, result.stdout + result.stderr
    for role in ("pdf", "conversation", "api"):
        assert f"{role}:stopped" in events


def test_render_stops_worker_when_terminated_during_startup(tmp_path):
    result, events = run_startup(tmp_path, send_early_term=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "pdf:stopped" in events
    assert "conversation:started" not in events
    assert "api:started" not in events


def test_render_stops_pdf_extractor_when_another_process_exits(tmp_path):
    result, events = run_startup(tmp_path, fail_role="api", fail_code=7, spawn_extractor=True)
    assert result.returncode == 7, result.stdout + result.stderr
    assert "pdf:stopped" in events
    assert "extractor:stopped" in events


def run_startup(
    tmp_path,
    *,
    fail_role="",
    fail_code=0,
    migration_code=0,
    send_term=False,
    delay_api_start=False,
    send_early_term=False,
    spawn_extractor=False,
):
    assert BASH, "Bash is required to verify the Render startup script"
    events = tmp_path / "events.txt"
    environment = {
        **os.environ,
        "EVENTS": events.as_posix(),
        "FAIL_ROLE": fail_role,
        "FAIL_CODE": str(fail_code),
        "MIGRATION_CODE": str(migration_code),
        "SEND_TERM": "1" if send_term else "0",
        "DELAY_API_START": "1" if delay_api_start else "0",
        "SEND_EARLY_TERM": "1" if send_early_term else "0",
        "SPAWN_EXTRACTOR": "1" if spawn_extractor else "0",
        "CHILD_PIDS": (tmp_path / "child-pids.txt").as_posix(),
    }
    result = subprocess.run(
        [
            BASH,
            "--noprofile",
            "--norc",
            "-c",
            HARNESS,
            "render-startup-test",
            "scripts/start-render.sh",
        ],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=8,
        check=False,
    )
    recorded = events.read_text().splitlines() if events.exists() else []
    assert "watchdog:fired" not in recorded, result.stdout + result.stderr
    return result, recorded
