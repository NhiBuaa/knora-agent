"""Windows daily-development launcher preflight coverage."""

import json
import os
import shutil
import socket
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


@pytest.mark.skipif(os.name != "nt", reason="Windows-local launcher")
@pytest.mark.parametrize("parameter", ["ApiPort", "FrontendPort"])
def test_daily_launcher_rejects_occupied_port_before_starting_services(tmp_path, parameter):
    env_file = tmp_path / ".env"
    env_file.write_text("# isolated\n")
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = listener.getsockname()[1]
        with socket.socket() as unused:
            unused.bind(("127.0.0.1", 0))
            unused_port = unused.getsockname()[1]
        other_parameter = "FrontendPort" if parameter == "ApiPort" else "ApiPort"
        result = subprocess.run(
            [
                _powershell(),
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(SCRIPT),
                "-EnvFile",
                str(env_file),
                "-PythonExe",
                sys.executable,
                "-OllamaBaseUrl",
                "http://127.0.0.1:1",
                f"-{parameter}",
                str(port),
                f"-{other_parameter}",
                str(unused_port),
            ],
            capture_output=True,
            text=True,
            timeout=20,
        )
        assert result.returncode == 2
        assert f"PORT_IN_USE:{parameter}:{port}" in result.stderr
        assert "DEV_READY" not in result.stdout
        # The pre-existing listener belongs to another session and must remain intact.
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            pass


@pytest.fixture(autouse=True)
def isolate_generation_environment(monkeypatch):
    for key in (
        "KNORA_GENERATION_PROVIDER",
        "KNORA_OLLAMA_GENERATION_MODEL",
        "KNORA_EXPECTED_GENERATION_MODEL_DIGEST",
    ):
        monkeypatch.delenv(key, raising=False)


def test_daily_launcher_supervises_conversation_turn_worker() -> None:
    launcher = SCRIPT.read_text(encoding="utf-8")
    assert "scripts/run_conversation_worker.py" in launcher
    assert "if ($conversationWorker.HasExited)" in launcher
    assert "Stop-ProcessTree $conversationWorker" in launcher


def test_daily_dev_compose_reuses_dev_keycloak_without_e2e_faults() -> None:
    root = SCRIPT.parents[1]
    daily_environment = os.environ.copy()
    daily_environment.pop("KNORA_M5_E2E_FAULTS_ENABLED", None)
    for name in (
        "KNORA_KEYCLOAK_ISSUER",
        "KNORA_KEYCLOAK_AUDIENCE",
        "KNORA_KEYCLOAK_JWKS_URL",
    ):
        daily_environment.pop(name, None)
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
        env=daily_environment,
    )
    services = json.loads(result.stdout)["services"]
    assert "keycloak-dev" in services
    assert services["keycloak-dev"]["ports"][0]["published"] == "8180"
    assert services["api"]["environment"]["KNORA_M5_E2E_FAULTS_ENABLED"] == "false"
    assert Path(services["keycloak-dev"]["volumes"][0]["source"]) == (
        root / "test" / "fixtures" / "keycloak" / "dev-realm.json"
    )
    realm = json.loads((root / "test" / "fixtures" / "keycloak" / "dev-realm.json").read_text())
    assert realm["realm"] == "knora-dev"
    client = next(client for client in realm["clients"] if client["clientId"] == "knora-web")
    assert client["redirectUris"] == ["http://127.0.0.1:3000/api/auth/callback"]

    e2e_environment = {
        **daily_environment,
        "KNORA_M5_E2E_FAULTS_ENABLED": "true",
        "KNORA_CANONICAL_MINIO_ACCESS_KEY": "m5-e2e-minio-access",
        "KNORA_CANONICAL_MINIO_SECRET_KEY": "m5-e2e-minio-secret",
        "KNORA_KEYCLOAK_JWKS_CACHE_TTL_SECONDS": "1",
    }
    e2e = subprocess.run(
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
        env=e2e_environment,
    )
    e2e_services = json.loads(e2e.stdout)["services"]
    assert e2e_services["api"]["environment"]["KNORA_M5_E2E_FAULTS_ENABLED"] == "true"
    assert e2e_services["minio"]["environment"]["MINIO_ROOT_USER"] == "m5-e2e-minio-access"
    assert e2e_services["api"]["environment"]["KNORA_OBJECT_STORE_S3_SECRET_KEY"] == (
        "m5-e2e-minio-secret"
    )
    assert e2e_services["api"]["environment"]["KNORA_KEYCLOAK_ISSUER"] == (
        "http://127.0.0.1:8180/realms/knora-dev"
    )


@pytest.mark.skipif(os.name != "nt", reason="Windows-local E2E preparation")
def test_e2e_configuration_check_restores_caller_environment() -> None:
    root = SCRIPT.parents[1]
    script = root / "scripts" / "prepare-local-e2e.ps1"
    command = (
        "$env:KNORA_CANONICAL_MINIO_ACCESS_KEY = 'caller-access'; "
        "$env:KNORA_M5_E2E_FAULTS_ENABLED = 'false'; "
        "$env:KNORA_KEYCLOAK_ISSUER = 'http://127.0.0.1:9999/realms/custom'; "
        "& $env:E2E_PREPARE_SCRIPT -CheckConfigurationOnly; "
        "if ($env:KNORA_CANONICAL_MINIO_ACCESS_KEY -ne 'caller-access' -or "
        "$env:KNORA_M5_E2E_FAULTS_ENABLED -ne 'false' -or "
        "$env:KNORA_KEYCLOAK_ISSUER -ne 'http://127.0.0.1:9999/realms/custom') "
        "{ throw 'Environment leaked' }; "
        "Write-Output 'CALLER_ENV_RESTORED'"
    )
    result = subprocess.run(
        [_powershell(), "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "E2E_PREPARE_SCRIPT": str(script)},
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
    assert "E2E_ISSUER=http://127.0.0.1:8180/realms/knora-dev" in result.stdout
    assert "E2E_CONFIG_OK" in result.stdout
    assert "CALLER_ENV_RESTORED" in result.stdout


def _powershell() -> str:
    executable = shutil.which("powershell") or shutil.which("pwsh")
    if executable is None:
        pytest.skip("PowerShell is unavailable")
    return executable


@contextmanager
def _ollama_server(*, generation_digest: str | None = "c" * 64) -> Iterator[str]:
    class OllamaHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path != "/api/tags":
                self.send_error(404)
                return
            models = [{"name": MODEL, "digest": DIGEST}]
            if generation_digest is not None:
                models.append({"name": "qwen3:8b", "digest": generation_digest})
            self._respond({"models": models})

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
    assert "GENERATION_PROVIDER=ollama" in result.stdout
    assert "GENERATION_MODEL=qwen3:8b" in result.stdout
    assert "GENERATION_DIGEST=sha256:" + "c" * 64 in result.stdout
    assert "API_URL=http://127.0.0.1:8765" in result.stdout
    assert "OIDC_REDIRECT_URI=http://127.0.0.1:8766/api/auth/callback" in result.stdout
    assert "OIDC_ISSUER=http://127.0.0.1:8180/realms/knora-dev" in result.stdout


@pytest.mark.skipif(os.name != "nt", reason="Windows-local launcher")
@pytest.mark.parametrize("digest", [None, "invalid"])
def test_daily_real_generation_fails_closed_without_valid_model(tmp_path, digest):
    env_file = tmp_path / ".env"
    env_file.write_text("# isolated\n")
    environment = {k: v for k, v in os.environ.items() if not k.startswith("KNORA_GENERATION")}
    with _ollama_server(generation_digest=digest) as url:
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
            ],
            env=environment,
            capture_output=True,
            text=True,
            timeout=25,
        )
    assert result.returncode == 2
    assert "GENERATION_MODEL_UNAVAILABLE" in result.stderr


@pytest.mark.skipif(os.name != "nt", reason="Windows-local launcher")
@pytest.mark.parametrize(
    ("parameter", "process_provider", "expected"),
    [
        ("-GenerationProvider ollama", "deterministic-local", "ollama"),
        ("", "ollama", "ollama"),
        ("", None, "deterministic-local"),
    ],
)
def test_daily_generation_selection_and_child_environment(
    tmp_path, parameter, process_provider, expected
):
    env_file = tmp_path / ".env"
    env_file.write_text("KNORA_GENERATION_PROVIDER=deterministic-local\n")
    environment = {
        k: v
        for k, v in os.environ.items()
        if k not in {"KNORA_GENERATION_PROVIDER", "KNORA_OLLAMA_GENERATION_MODEL"}
    }
    if process_provider:
        environment["KNORA_GENERATION_PROVIDER"] = process_provider
    environment["KNORA_EXPECTED_GENERATION_MODEL_DIGEST"] = "sha256:" + "d" * 64
    command = (
        "& $env:TEST_LAUNCHER -PreflightOnly -EnvFile $env:TEST_ENV "
        f"-OllamaBaseUrl $env:TEST_URL -PythonExe $env:TEST_PYTHON {parameter}; "
        "if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; "
        "& $env:TEST_PYTHON $env:TEST_CHILD"
    )
    child = tmp_path / "child.py"
    child.write_text(
        "import os\nfor key in ('KNORA_GENERATION_PROVIDER', "
        "'KNORA_OLLAMA_GENERATION_MODEL', 'KNORA_EXPECTED_GENERATION_MODEL_DIGEST'):\n"
        "    print(os.environ.get(key, 'unset'))\n"
    )
    with _ollama_server(generation_digest="c" * 64 if expected == "ollama" else None) as url:
        result = subprocess.run(
            [_powershell(), "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
            capture_output=True,
            text=True,
            timeout=25,
            env={
                **environment,
                "TEST_LAUNCHER": str(SCRIPT),
                "TEST_ENV": str(env_file),
                "TEST_URL": url,
                "TEST_PYTHON": sys.executable,
                "TEST_CHILD": str(child),
            },
        )
    assert result.returncode == 0, result.stderr
    digest = "sha256:" + "c" * 64 if expected == "ollama" else "unset"
    assert result.stdout.splitlines()[-3:] == [expected, "qwen3:8b", digest]


@pytest.mark.skipif(os.name != "nt", reason="Windows-local launcher")
def test_dev_launcher_respects_explicit_oidc_environment(tmp_path: Path) -> None:
    issuer = "http://127.0.0.1:8181/realms/custom"
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                f"KEYCLOAK_ISSUER={issuer}",
                f"KNORA_KEYCLOAK_ISSUER={issuer}",
                f"KEYCLOAK_AUTHORIZATION_URL={issuer}/protocol/openid-connect/custom-auth",
                f"KNORA_KEYCLOAK_JWKS_URL={issuer}/protocol/openid-connect/custom-certs",
                "KEYCLOAK_CLIENT_ID=custom-web",
                "KEYCLOAK_AUDIENCE=custom-web",
                "KNORA_KEYCLOAK_AUDIENCE=custom-web",
                "KEYCLOAK_CLIENT_SECRET=local-secret",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    script = (
        "& $env:KNORA_TEST_SCRIPT -PreflightOnly -EnvFile $env:KNORA_TEST_ENV_FILE "
        "-OllamaBaseUrl $env:KNORA_TEST_OLLAMA -PythonExe $env:KNORA_TEST_PYTHON; "
        '"AUTH_URL=$env:KEYCLOAK_AUTHORIZATION_URL"; '
        '"BACKEND_JWKS=$env:KNORA_KEYCLOAK_JWKS_URL"; '
        '"CLIENT_ID=$env:KEYCLOAK_CLIENT_ID"; '
        '"CLIENT_AUDIENCE=$env:KEYCLOAK_AUDIENCE"; '
        '"CLIENT_SECRET_SET=$([bool]$env:KEYCLOAK_CLIENT_SECRET)"'
    )
    clean_env = os.environ.copy()
    for key in (
        "KEYCLOAK_ISSUER",
        "KNORA_KEYCLOAK_ISSUER",
        "KEYCLOAK_AUTHORIZATION_URL",
        "KNORA_KEYCLOAK_JWKS_URL",
        "KEYCLOAK_CLIENT_ID",
        "KEYCLOAK_AUDIENCE",
        "KNORA_KEYCLOAK_AUDIENCE",
        "KEYCLOAK_CLIENT_SECRET",
    ):
        clean_env.pop(key, None)
    with _ollama_server() as url:
        result = subprocess.run(
            [_powershell(), "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            capture_output=True,
            text=True,
            check=False,
            timeout=25,
            env={
                **clean_env,
                "KNORA_TEST_SCRIPT": str(SCRIPT),
                "KNORA_TEST_ENV_FILE": str(env_file),
                "KNORA_TEST_OLLAMA": url,
                "KNORA_TEST_PYTHON": sys.executable,
            },
        )
    assert result.returncode == 0, result.stderr
    assert f"OIDC_ISSUER={issuer}" in result.stdout
    assert f"AUTH_URL={issuer}/protocol/openid-connect/custom-auth" in result.stdout
    assert f"BACKEND_JWKS={issuer}/protocol/openid-connect/custom-certs" in result.stdout
    assert "CLIENT_ID=custom-web" in result.stdout
    assert "CLIENT_AUDIENCE=custom-web" in result.stdout
    assert "CLIENT_SECRET_SET=True" in result.stdout


@pytest.mark.skipif(os.name != "nt", reason="Windows-local launcher")
def test_dev_launcher_rejects_mismatched_frontend_and_backend_issuers(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "KEYCLOAK_ISSUER=http://127.0.0.1:8181/realms/one\n"
        "KNORA_KEYCLOAK_ISSUER=http://127.0.0.1:8181/realms/two\n",
        encoding="utf-8",
    )
    clean_env = os.environ.copy()
    clean_env.pop("KEYCLOAK_ISSUER", None)
    clean_env.pop("KNORA_KEYCLOAK_ISSUER", None)
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
            "-PythonExe",
            sys.executable,
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
        env=clean_env,
    )
    assert result.returncode == 2
    assert "OIDC_ISSUER_MISMATCH" in result.stderr


@pytest.mark.skipif(os.name != "nt", reason="Windows-local launcher")
def test_dev_launcher_imports_dotenv_over_empty_process_value(tmp_path: Path) -> None:
    issuer = "http://127.0.0.1:8181/realms/custom"
    env_file = tmp_path / ".env"
    env_file.write_text(f"KEYCLOAK_ISSUER={issuer}\n", encoding="utf-8")
    command = (
        "$env:KEYCLOAK_ISSUER = ''; "
        "& $env:KNORA_TEST_SCRIPT -PreflightOnly -EnvFile $env:KNORA_TEST_ENV_FILE "
        "-OllamaBaseUrl $env:KNORA_TEST_OLLAMA -PythonExe $env:KNORA_TEST_PYTHON"
    )
    clean_env = os.environ.copy()
    clean_env.pop("KNORA_KEYCLOAK_ISSUER", None)
    with _ollama_server() as url:
        result = subprocess.run(
            [_powershell(), "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
            capture_output=True,
            text=True,
            check=False,
            timeout=25,
            env={
                **clean_env,
                "KNORA_TEST_SCRIPT": str(SCRIPT),
                "KNORA_TEST_ENV_FILE": str(env_file),
                "KNORA_TEST_OLLAMA": url,
                "KNORA_TEST_PYTHON": sys.executable,
            },
        )
    assert result.returncode == 0, result.stderr
    assert f"OIDC_ISSUER={issuer}" in result.stdout
