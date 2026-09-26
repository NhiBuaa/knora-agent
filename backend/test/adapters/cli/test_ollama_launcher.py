"""The Windows launcher checks the real host preconditions before touching Compose."""

import json
import os
import shutil
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import pytest

SCRIPT = Path(__file__).resolve().parents[4] / "scripts" / "start-ollama-demo.ps1"
MODEL = "qwen3-embedding:0.6b"
DIGEST = "sha256:" + "a" * 64


def _powershell() -> str:
    executable = shutil.which("powershell") or shutil.which("pwsh")
    if executable is None:
        pytest.skip("PowerShell is unavailable")
    return executable


def _launch(
    url: str, api_port: int = 8000, existing_storage: bool = False
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment.pop("KNORA_EXPECTED_EMBEDDING_CONFIGURATION_ID", None)
    arguments = [
            _powershell(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(SCRIPT),
            "-PreflightOnly",
            "-OllamaBaseUrl",
            url,
            "-PythonExe",
            sys.executable,
            "-ApiPort",
            str(api_port),
        ]
    if existing_storage:
        arguments.append("-UseExistingStorage")
    return subprocess.run(
        arguments,
        env=environment,
        capture_output=True,
        text=True,
        timeout=25,
        check=False,
    )


@pytest.mark.skipif(os.name != "nt", reason="Windows-local launcher")
@pytest.mark.parametrize(
    ("model_available", "dimensions", "expected_error"),
    [(True, 1024, None), (False, 1024, "MODEL_UNAVAILABLE"), (True, 1023, "DIMENSION_MISMATCH")],
)
def test_launcher_preflight_checks_model_and_dimension(
    model_available: bool, dimensions: int, expected_error: str | None
) -> None:
    class OllamaHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path != "/api/tags":
                self.send_error(404)
                return
            models = [{"name": MODEL, "digest": DIGEST}] if model_available else []
            self._respond({"models": models})

        def do_POST(self) -> None:
            if self.path == "/api/show":
                self._respond({"details": {"family": "qwen3", "quantization_level": "Q8_0"}})
            elif self.path == "/api/embed":
                self._respond({"model": MODEL, "embeddings": [[0.5] * dimensions]})
            else:
                self.send_error(404)

        def _respond(self, payload: dict) -> None:
            content = json.dumps(payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        def log_message(self, *_args) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), OllamaHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        result = _launch(f"http://127.0.0.1:{server.server_port}", api_port=8765)
        existing_result = (
            _launch(f"http://127.0.0.1:{server.server_port}", existing_storage=True)
            if expected_error is None
            else None
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    assert (result.returncode == 0) is (expected_error is None), result.stderr
    if expected_error is None:
        assert "PRECHECK_OK" in result.stdout
        assert "API_URL=http://127.0.0.1:8765" in result.stdout
        assert existing_result is not None
        assert existing_result.returncode != 0
        assert "EXISTING_STORAGE_CONFIG_REQUIRED" in existing_result.stderr
    else:
        assert expected_error in result.stderr
