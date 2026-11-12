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
run_child() {
    role=$1
    trap 'printf "%s:stopped\n" "$role" >> "$EVENTS"; exit 0' TERM
    printf '%s:started\n' "$role" >> "$EVENTS"
    if [[ "$role" == "$FAIL_ROLE" ]]; then
        sleep 0.2
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
    if [[ "$DELAY_API_START" == "1" && "$*" == *"Starting Uvicorn"* ]]; then
        sleep 0.4
    fi
    builtin echo "$@"
}
parent=$BASHPID
(sleep 3; kill -TERM "$parent" 2>/dev/null || true) &
if [[ "$SEND_TERM" == "1" ]]; then
    (sleep 0.4; kill -TERM "$parent") &
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


def run_startup(
    tmp_path, *, fail_role="", fail_code=0, migration_code=0, send_term=False, delay_api_start=False
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
        timeout=5,
        check=False,
    )
    return result, events.read_text().splitlines() if events.exists() else []
