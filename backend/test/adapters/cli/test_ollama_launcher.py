"""The Windows launcher checks host preconditions and persistent local dotenv behavior."""

import json
import os
import shutil
import subprocess
import sys
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from typing import Iterator

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
    url: str | None,
    *,
    api_port: int = 8000,
    existing_storage: bool = False,
    database_url: str | None = None,
    object_store_endpoint: str | None = None,
    env_file: Path | None = None,
    environment_overrides: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment.pop("KNORA_EXPECTED_EMBEDDING_CONFIGURATION_ID", None)
    environment.pop("KNORA_DATABASE_URL", None)
    environment.pop("KNORA_OLLAMA_BASE_URL", None)
    if database_url is not None:
        environment["KNORA_DATABASE_URL"] = database_url
    if environment_overrides:
        environment.update(environment_overrides)

    arguments = [
        _powershell(),
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(SCRIPT),
        "-PreflightOnly",
        "-PythonExe",
        sys.executable,
        "-ApiPort",
        str(api_port),
    ]
    if url is not None:
        arguments.extend(["-OllamaBaseUrl", url])
    if env_file is not None:
        arguments.extend(["-EnvFile", str(env_file)])
    if existing_storage:
        arguments.append("-UseExistingStorage")
    if object_store_endpoint is not None:
        arguments.extend(["-ObjectStoreEndpoint", object_store_endpoint])

    return subprocess.run(
        arguments,
        env=environment,
        capture_output=True,
        text=True,
        timeout=25,
        check=False,
    )


@contextmanager
def _ollama_server(
    *, model_available: bool = True, dimensions: int = 1024
) -> Iterator[str]:
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
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


@pytest.mark.skipif(os.name != "nt", reason="Windows-local launcher")
@pytest.mark.parametrize(
    ("model_available", "dimensions", "expected_error"),
    [(True, 1024, None), (False, 1024, "MODEL_UNAVAILABLE"), (True, 1023, "DIMENSION_MISMATCH")],
)
def test_launcher_preflight_checks_model_and_dimension(
    tmp_path: Path,
    model_available: bool,
    dimensions: int,
    expected_error: str | None,
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("# isolated launcher test\n", encoding="utf-8")

    with _ollama_server(model_available=model_available, dimensions=dimensions) as url:
        result = _launch(url, api_port=8765, env_file=env_file)
        existing_result = (
            _launch(url, existing_storage=True, env_file=env_file)
            if expected_error is None
            else None
        )

    assert (result.returncode == 0) is (expected_error is None), result.stderr
    if expected_error is None:
        assert "PRECHECK_OK" in result.stdout
        assert "API_URL=http://127.0.0.1:8765" in result.stdout
        assert existing_result is not None
        assert existing_result.returncode != 0
        assert "EXISTING_STORAGE_CONFIG_REQUIRED" in existing_result.stderr
    else:
        assert expected_error in result.stderr


@pytest.mark.skipif(os.name != "nt", reason="Windows-local launcher")
def test_launcher_loads_persistent_dotenv_and_preserves_equals(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    with _ollama_server() as url:
        env_file.write_text(
            "\n".join(
                [
                    f"KNORA_OLLAMA_BASE_URL={url}",
                    "KNORA_DATABASE_URL=postgresql+psycopg://knora:knora@localhost:5432/demo?application_name=a=b",
                ]
            ),
            encoding="utf-8",
        )
        result = _launch(
            None,
            existing_storage=True,
            object_store_endpoint="http://127.0.0.1:9000",
            env_file=env_file,
        )

    assert result.returncode == 0, result.stderr
    assert "PRECHECK_OK" in result.stdout


@pytest.mark.skipif(os.name != "nt", reason="Windows-local launcher")
def test_process_environment_overrides_dotenv(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("KNORA_OLLAMA_BASE_URL=http://127.0.0.1:9\n", encoding="utf-8")

    with _ollama_server() as url:
        result = _launch(
            None,
            env_file=env_file,
            environment_overrides={"KNORA_OLLAMA_BASE_URL": url},
        )

    assert result.returncode == 0, result.stderr
    assert "PRECHECK_OK" in result.stdout


@pytest.mark.skipif(os.name != "nt", reason="Windows-local launcher")
def test_launcher_rejects_malformed_dotenv_without_echoing_content(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    secret_marker = "do-not-print-this-secret"
    env_file.write_text(f"BROKEN {secret_marker}\n", encoding="utf-8")

    result = _launch("http://127.0.0.1:9", env_file=env_file)

    assert result.returncode != 0
    assert "INVALID_DOTENV_ENTRY:1" in result.stderr
    assert secret_marker not in result.stdout
    assert secret_marker not in result.stderr
