"""Windows daily-development launcher preflight coverage."""

import json
import os
import shutil
import subprocess
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import pytest

SCRIPT = Path(__file__).resolve().parents[4] / "scripts" / "start-dev.ps1"
MODEL = "qwen3-embedding:0.6b"
DIGEST = "sha256:" + "b" * 64


def test_daily_dev_compose_reuses_dev_keycloak_without_e2e_faults() -> None:
    root = SCRIPT.parents[1]
    result = subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            str(root / "docker-compose.yml"),
            "-f",
            str(root / "docker-compose.dev.yml"),
            "config",
            "--format",
            "json",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    services = json.loads(result.stdout)["services"]
    assert "keycloak-dev" in services
    assert services["keycloak-dev"]["ports"][0]["published"] == "8180"
    assert "KNORA_M5_E2E_FAULTS_ENABLED" not in services["api"]["environment"]
    assert Path(services["keycloak-dev"]["volumes"][0]["source"]) == (
        root / "test" / "fixtures" / "keycloak" / "dev-realm.json"
    )
    realm = json.loads((root / "test" / "fixtures" / "keycloak" / "dev-realm.json").read_text())
    assert realm["realm"] == "knora-dev"
    client = next(client for client in realm["clients"] if client["clientId"] == "knora-web")
    assert client["redirectUris"] == ["http://127.0.0.1:3000/api/auth/callback"]

    e2e = subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            str(root / "docker-compose.yml"),
            "-f",
            str(root / "docker-compose.dev.yml"),
            "-f",
            str(root / "docker-compose.m5-e2e.yml"),
            "config",
            "--format",
            "json",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    e2e_services = json.loads(e2e.stdout)["services"]
    assert e2e_services["api"]["environment"]["KNORA_M5_E2E_FAULTS_ENABLED"] == "true"
    assert e2e_services["api"]["environment"]["KNORA_KEYCLOAK_ISSUER"] == (
        "http://127.0.0.1:8180/realms/knora-dev"
    )


def _powershell() -> str:
    executable = shutil.which("powershell") or shutil.which("pwsh")
    if executable is None:
        pytest.skip("PowerShell is unavailable")
    return executable


@contextmanager
def _ollama_server() -> Iterator[str]:
    class OllamaHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path != "/api/tags":
                self.send_error(404)
                return
            self._respond({"models": [{"name": MODEL, "digest": DIGEST}]})

        def do_POST(self) -> None:
            if self.path == "/api/show":
                self._respond({"details": {"family": "qwen3", "quantization_level": "Q8_0"}})
            elif self.path == "/api/embed":
                self._respond({"model": MODEL, "embeddings": [[0.5] * 1024]})
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
def test_dev_launcher_preflight_uses_real_profile_and_pdf_safety(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "KEYCLOAK_REDIRECT_URI=http://127.0.0.1:3000/api/auth/callback\n",
        encoding="utf-8",
    )

    with _ollama_server() as url:
        result = subprocess.run(
            [
                _powershell(),
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(SCRIPT),
                "-PreflightOnly",
                "-EnvFile",
                str(env_file),
                "-OllamaBaseUrl",
                url,
                "-PythonExe",
                sys.executable,
                "-ApiPort",
                "8765",
                "-FrontendPort",
                "8766",
            ],
            capture_output=True,
            text=True,
            timeout=25,
            check=False,
        )

    assert result.returncode == 0, result.stderr
    assert "PRECHECK_OK" in result.stdout
    assert "API_URL=http://127.0.0.1:8765" in result.stdout
    assert "OIDC_REDIRECT_URI=http://127.0.0.1:8766/api/auth/callback" in result.stdout
    assert "OIDC_ISSUER=http://127.0.0.1:8180/realms/knora-dev" in result.stdout
