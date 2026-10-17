"""Windows daily-development launcher preflight coverage."""

import json
import os
import re
import shutil
import socket
import subprocess
import sys
import textwrap
import time
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import psutil
import pytest

SCRIPT = Path(__file__).resolve().parents[4] / "scripts" / "start-dev.ps1"
MODEL = "qwen3-embedding:0.6b"
DIGEST = "sha256:" + "b" * 64
ACCOUNT = "a" * 32


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
        "KNORA_EMBEDDING_PROVIDER",
        "KNORA_GENERATION_PROVIDER",
        "KNORA_EXPECTED_EMBEDDING_CONFIGURATION_ID",
        "KNORA_EMBEDDING_DIMENSION",
        "KNORA_CLOUDFLARE_ACCOUNT_ID",
        "KNORA_CLOUDFLARE_API_TOKEN",
        "KNORA_CLOUDFLARE_EMBEDDING_MODEL",
        "KNORA_CLOUDFLARE_GENERATION_MODEL",
        "KNORA_OLLAMA_GENERATION_MODEL",
        "KNORA_EXPECTED_GENERATION_MODEL_DIGEST",
    ):
        monkeypatch.delenv(key, raising=False)


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


@pytest.mark.skipif(os.name != "nt", reason="Windows-local launcher")
def test_daily_cloudflare_preflight_needs_no_ollama_and_pins_profile(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    template = (SCRIPT.parents[1] / ".env.example").read_text(encoding="utf-8")
    for name, value in {
        "KNORA_CLOUDFLARE_ACCOUNT_ID": ACCOUNT,
        "KNORA_CLOUDFLARE_API_TOKEN": "private-token",
        "KNORA_OBJECT_STORE_S3_ACCESS_KEY": "synthetic-access",
        "KNORA_OBJECT_STORE_S3_SECRET_KEY": "synthetic-secret",
        "SESSION_SECRET": "synthetic-session-secret",
        "KNORA_OTP_HMAC_KEY": "YWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWE=",
        "KC_SMTP_FROM": "synthetic@example.com",
        "KC_SMTP_USER": "synthetic@example.com",
        "KC_SMTP_PASSWORD": "synthetic-app-password",
    }.items():
        template = re.sub(rf"^{name}=.*$", f"{name}={value}", template, flags=re.MULTILINE)
    env_file.write_text(template, encoding="utf-8")
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
            "http://127.0.0.1:1",
            "-PythonExe",
            sys.executable,
        ],
        capture_output=True,
        text=True,
        timeout=25,
    )
    assert result.returncode == 0, result.stderr
    assert "PRECHECK_OK embedding-cloudflare-qwen3-06b-v1" in result.stdout
    assert "EMBEDDING_PROVIDER=cloudflare-workers-ai" in result.stdout
    assert "GENERATION_PROVIDER=cloudflare-workers-ai" in result.stdout
    assert "private-token" not in result.stdout + result.stderr


@pytest.mark.skipif(os.name != "nt", reason="Windows-local launcher")
@pytest.mark.parametrize("bad_setting", ["missing-token", "bad-model", "bad-profile"])
def test_daily_cloudflare_preflight_fails_closed_without_secret_leak(
    tmp_path: Path, bad_setting: str
) -> None:
    env_file = tmp_path / ".env"
    values = [f"KNORA_CLOUDFLARE_ACCOUNT_ID={ACCOUNT}"]
    if bad_setting != "missing-token":
        values.append("KNORA_CLOUDFLARE_API_TOKEN=private-token")
    if bad_setting == "bad-model":
        values.append("KNORA_CLOUDFLARE_GENERATION_MODEL=wrong-model")
    if bad_setting == "bad-profile":
        values.append("KNORA_CLOUDFLARE_EMBEDDING_CONFIGURATION_ID=wrong-profile")
    env_file.write_text("\n".join(values) + "\n")
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
            "http://127.0.0.1:1",
            "-PythonExe",
            sys.executable,
        ],
        capture_output=True,
        text=True,
        timeout=25,
    )
    assert result.returncode == 2
    assert "PROFILE_RESOLUTION_FAILED" in result.stderr
    assert "PRECHECK_OK" not in result.stdout
    assert "private-token" not in result.stdout + result.stderr


@pytest.mark.skipif(os.name != "nt", reason="Windows-local launcher")
def test_daily_deterministic_pair_needs_no_ollama_or_cloudflare(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("# isolated\n")
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
            "-EmbeddingProvider",
            "deterministic-local",
            "-GenerationProvider",
            "deterministic-local",
            "-OllamaBaseUrl",
            "http://127.0.0.1:1",
            "-PythonExe",
            sys.executable,
        ],
        capture_output=True,
        text=True,
        timeout=25,
    )
    assert result.returncode == 0, result.stderr
    assert "PRECHECK_OK embedding-local-m1-v2" in result.stdout
    assert "EMBEDDING_PROVIDER=deterministic-local" in result.stdout
    assert "GENERATION_PROVIDER=deterministic-local" in result.stdout


@contextmanager
def _ollama_server(
    *, generation_digest: str | None = "c" * 64, generation_model: str = "qwen3:8b"
) -> Iterator[str]:
    class OllamaHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path != "/api/tags":
                self.send_error(404)
                return
            models = [{"name": MODEL, "digest": DIGEST}]
            if generation_digest is not None:
                models.append({"name": generation_model, "digest": generation_digest})
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
                "-EmbeddingProvider",
                "ollama",
                "-GenerationProvider",
                "ollama",
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
                "-EmbeddingProvider",
                "ollama",
                "-GenerationProvider",
                "ollama",
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
    env_file.write_text(
        "KNORA_EMBEDDING_PROVIDER=ollama\nKNORA_GENERATION_PROVIDER=deterministic-local\n"
    )
    environment = {
        k: v
        for k, v in os.environ.items()
        if k not in {"KNORA_GENERATION_PROVIDER", "KNORA_OLLAMA_GENERATION_MODEL"}
    }
    if process_provider:
        environment["KNORA_GENERATION_PROVIDER"] = process_provider
    environment["KNORA_EXPECTED_GENERATION_MODEL_DIGEST"] = "sha256:" + "d" * 64
    command = (
        "& $env:TEST_LAUNCHER -PreflightOnly -EmbeddingProvider ollama -EnvFile $env:TEST_ENV "
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
def test_daily_gpt_oss_selection_from_dotenv_pins_child_digest(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "KNORA_EMBEDDING_PROVIDER=ollama\nKNORA_GENERATION_PROVIDER=ollama\n"
        "KNORA_OLLAMA_GENERATION_MODEL=gpt-oss:20b\n"
    )
    child = tmp_path / "child.py"
    child.write_text(
        "import os\nfor key in ('KNORA_OLLAMA_GENERATION_MODEL', "
        "'KNORA_EXPECTED_GENERATION_MODEL_DIGEST'):\n    print(os.environ[key])\n"
    )
    environment = {key: value for key, value in os.environ.items() if not key.startswith("KNORA_")}
    command = (
        "& $env:TEST_LAUNCHER -PreflightOnly -EnvFile $env:TEST_ENV "
        "-OllamaBaseUrl $env:TEST_URL -PythonExe $env:TEST_PYTHON; "
        "if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; "
        "& $env:TEST_PYTHON $env:TEST_CHILD"
    )
    with _ollama_server(generation_model="gpt-oss:20b") as url:
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
    assert result.stdout.splitlines()[-2:] == ["gpt-oss:20b", "sha256:" + "c" * 64]


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
        "& $env:KNORA_TEST_SCRIPT -PreflightOnly -EmbeddingProvider ollama "
        "-GenerationProvider ollama -EnvFile $env:KNORA_TEST_ENV_FILE "
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
        "& $env:KNORA_TEST_SCRIPT -PreflightOnly -EmbeddingProvider ollama "
        "-GenerationProvider ollama -EnvFile $env:KNORA_TEST_ENV_FILE "
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


@pytest.fixture
def launcher_runtime(tmp_path: Path):
    """Real launcher/processes/console; replace only storage and service workloads."""
    root = tmp_path / "runtime space & directory"
    scripts = root / "scripts"
    scripts.mkdir(parents=True)
    shutil.copy2(SCRIPT, scripts / SCRIPT.name)
    native = SCRIPT.with_name("dev-process-job.cs")
    if native.exists():
        shutil.copy2(native, scripts / native.name)
    (root / "empty.env").write_text("# synthetic fixture\n")
    package = root / "backend/src/knora"
    for directory in (
        package,
        package / "infrastructure",
        package / "adapters",
        package / "adapters/cli",
    ):
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "__init__.py").touch()
    (package / "infrastructure/settings.py").write_text(
        "class Settings:\n    def __init__(self, **kwargs): pass\n"
    )
    (package / "bootstrap.py").write_text(
        "from types import SimpleNamespace as S\n"
        "def build_provider_selection(settings):\n"
        "    return S(embedding_configuration=S(id='embedding-local-m1-v2'))\n"
    )
    (root / "alembic.py").write_text("# No database side effects in this fixture.\n")
    service = textwrap.dedent("""
        import json, os, subprocess, sys, time, psutil
        from pathlib import Path
        from http.server import BaseHTTPRequestHandler, HTTPServer
        mode = sys.argv[1]
        Path(f'process-{os.getpid()}.json').write_text(json.dumps(
            {'pid': os.getpid(), 'created': psutil.Process().create_time()}))
        if mode == 'idle':
            while True: time.sleep(.1)
        if mode == 'frontend':
            child = subprocess.Popen([sys.executable, 'service.py', 'http', os.environ['PORT']])
            if os.environ.get('FIXTURE_FAILURE') == 'frontend': sys.exit(3)
            sys.exit(child.wait())
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.end_headers()
                self.wfile.write(json.dumps({'status': 'ok'}).encode())
            def log_message(self, *args): pass
        HTTPServer(('127.0.0.1', int(sys.argv[2])), Handler).serve_forever()
    """)
    (root / "service.py").write_text(service)
    (root / "uvicorn.py").write_text(
        "import subprocess, sys\n"
        "child = subprocess.Popen([sys.executable, 'service.py', 'http', "
        "sys.argv[sys.argv.index('--port') + 1]])\n"
        "sys.exit(child.wait())\n"
    )
    (package / "adapters/cli/worker.py").write_text(
        "import subprocess, sys, time\nfrom pathlib import Path\n"
        "if '--check-pdf-isolation' in sys.argv: sys.exit(0)\n"
        "child = subprocess.Popen([sys.executable, 'service.py', 'idle'])\n"
        "while not Path('restart-worker').exists(): time.sleep(.1)\n"
        "Path('restart-worker').unlink()\nsys.exit(75)\n"
    )
    (scripts / "run_conversation_worker.py").write_text(
        "import subprocess, sys\n"
        "sys.exit(subprocess.Popen([sys.executable, 'service.py', 'idle']).wait())\n"
    )
    (root / "npm.cmd").write_text(f'@echo off\n"{sys.executable}" service.py frontend\n')
    wrapper = root / "invoke.ps1"
    wrapper.write_text(
        "function docker { $global:LASTEXITCODE = 0; if ($args -contains 'exec') { '1' } }\n"
        "Add-Type -Path $env:FIXTURE_NATIVE\n"
        "Write-Output 'FIXTURE_NATIVE_READY'\n"
        "& $env:FIXTURE_LAUNCHER -NoBrowser -EnvFile $env:FIXTURE_ENV "
        "-PythonExe $env:FIXTURE_PYTHON -EmbeddingProvider deterministic-local "
        "-GenerationProvider deterministic-local -ApiPort $env:FIXTURE_API_PORT "
        "-FrontendPort $env:FIXTURE_FRONTEND_PORT\n"
    )
    return root, wrapper


def _unused_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait_until(predicate, timeout: float = 20) -> None:
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() >= deadline:
            pytest.fail("Timed out waiting for launcher fixture")
        time.sleep(0.05)


def _console_ctrl_c(pid: int) -> None:
    # Attach only to a fresh, dedicated hidden console; never broadcast to the test host.
    subprocess.run(
        [
            sys.executable,
            "-c",
            textwrap.dedent("""
            import ctypes, sys, time
            kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            kernel.FreeConsole()
            if not kernel.AttachConsole(int(sys.argv[1])):
                raise ctypes.WinError(ctypes.get_last_error())
            kernel.SetConsoleCtrlHandler(None, True)
            if not kernel.GenerateConsoleCtrlEvent(0, 0):
                raise ctypes.WinError(ctypes.get_last_error())
            time.sleep(.2)
            kernel.FreeConsole()
        """),
            str(pid),
        ],
        check=True,
        timeout=10,
    )


@pytest.mark.skipif(os.name != "nt", reason="Windows launcher process ownership")
@pytest.mark.parametrize("shell", ["powershell", "pwsh"])
@pytest.mark.parametrize("scenario", ["ctrl-c", "exited-root", "startup-failure", "worker-restart"])
def test_launcher_cleans_owned_descendants(launcher_runtime, shell: str, scenario: str):
    executable = shutil.which(shell)
    if executable is None:
        pytest.skip(f"{shell} is unavailable")
    root, wrapper = launcher_runtime
    api_port, frontend_port = _unused_port(), _unused_port()
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("KNORA_", "KEYCLOAK_", "SESSION_"))
    }
    environment.update(
        PATH=f"{root};{environment['PATH']}",
        TEMP=str(root),
        TMP=str(root),
        FIXTURE_LAUNCHER=str(root / "scripts/start-dev.ps1"),
        FIXTURE_NATIVE=str(root / "scripts/dev-process-job.cs"),
        FIXTURE_ENV=str(root / "empty.env"),
        FIXTURE_PYTHON=sys.executable,
        FIXTURE_API_PORT=str(api_port),
        FIXTURE_FRONTEND_PORT=str(frontend_port),
        SESSION_SECRET="synthetic-session-secret-000000000000",
        KNORA_CANONICAL_MINIO_ACCESS_KEY="synthetic-access",
        KNORA_CANONICAL_MINIO_SECRET_KEY="synthetic-secret",
        FIXTURE_FAILURE="frontend" if scenario == "startup-failure" else "",
    )
    startup = subprocess.STARTUPINFO()
    startup.dwFlags = subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = 0
    known: set[psutil.Process] = set()
    # An unrelated process with the same executable must survive every cleanup.
    outsider = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(120)"],
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    launcher = None
    try:
        log_path = root / "launcher.log"
        with log_path.open("w") as output:
            launcher = subprocess.Popen(
                [executable, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(wrapper)],
                cwd=root,
                env=environment,
                stdout=output,
                stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NEW_CONSOLE,
                startupinfo=startup,
            )
        owner = psutil.Process(launcher.pid)

        def observe():
            if launcher.poll() is None:
                with suppress(psutil.NoSuchProcess):
                    known.update(owner.children(recursive=True))
            return log_path.read_text(errors="replace")

        # Match native-job tests' compile bound; runtime readiness and cleanup keep their bounds.
        _wait_until(lambda: "FIXTURE_NATIVE_READY" in observe(), timeout=40)
        if scenario == "startup-failure":
            _wait_until(lambda: observe() and launcher.poll() is not None)
            assert "DEV_RUNTIME_FAILED" in observe()
        else:
            try:
                _wait_until(lambda: "DEV_READY" in observe())
            except pytest.fail.Exception:
                service_logs = "\n".join(
                    f"{path.name}:\n{path.read_text(errors='replace')[-4000:]}"
                    for path in sorted((root / "knora-dev-runtime").glob("*.log"))
                )
                pytest.fail(
                    f"Launcher readiness timeout; exit={launcher.poll()}\n"
                    f"{observe()}\n{service_logs}",
                    pytrace=False,
                )
            if scenario == "exited-root":
                frontend_pid = int(re.search(r"FRONTEND_PID=(\d+)", observe())[1])
                frontend_root = next(process for process in known if process.pid == frontend_pid)
                frontend_root.kill()
                frontend_root.wait(5)
            if scenario == "worker-restart":
                (root / "restart-worker").touch()
                _wait_until(lambda: "[worker] ready generation 2" in observe())
            if launcher.poll() is None:
                _console_ctrl_c(launcher.pid)
            launcher.wait(15)
        assert outsider.poll() is None
        for marker in root.glob("process-*.json"):
            identity = json.loads(marker.read_text())
            with suppress(psutil.NoSuchProcess):
                process = psutil.Process(identity["pid"])
                if process.create_time() == identity["created"]:
                    known.add(process)
        assert "DEV_STOPPED" in observe()
        # Console hosts can outlive their launcher briefly while attachments close.
        _, remaining = psutil.wait_procs(list(known), timeout=10)
        assert not remaining, f"Owned processes survived cleanup: {remaining}\n{observe()}"
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", api_port))
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", frontend_port))
    finally:
        if launcher is not None and launcher.poll() is None:
            known.update(psutil.Process(launcher.pid).children(recursive=True))
            launcher.kill()
            launcher.wait(10)
        # psutil identities retain creation time, protecting against recycled PIDs.
        for process in known:
            with suppress(psutil.NoSuchProcess):
                process.kill()
        psutil.wait_procs(list(known), timeout=10)
        outsider.kill()
        outsider.wait(10)


def _run_job_script(tmp_path: Path, shell: str, statements: str, **environment):
    executable = shutil.which(shell)
    if executable is None:
        pytest.skip(f"{shell} is unavailable")
    script = tmp_path / "job.ps1"
    script.write_text(
        "$ErrorActionPreference = 'Stop'\n"
        "Add-Type -Path $env:FIXTURE_NATIVE\n"
        "$job = [Knora.Dev.ProcessJob]::new()\n"
        "$other = [Knora.Dev.ProcessJob]::new()\n"
        "try {\n" + statements + "\n} finally { $job.Dispose(); $other.Dispose() }\n"
    )
    return subprocess.run(
        [executable, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)],
        capture_output=True,
        text=True,
        timeout=40,
        cwd=SCRIPT.parents[1],
        env={
            **os.environ,
            "FIXTURE_NATIVE": str(SCRIPT.with_name("dev-process-job.cs")),
            "FIXTURE_PYTHON": sys.executable,
            "FIXTURE_DIRECTORY": str(tmp_path),
            **environment,
        },
    )


@pytest.mark.skipif(os.name != "nt", reason="Windows launcher process ownership")
@pytest.mark.parametrize("shell", ["powershell", "pwsh"])
def test_process_job_cleanup_is_repeatable_and_preserves_other_invocation(tmp_path, shell):
    result = _run_job_script(
        tmp_path,
        shell,
        """
        $dir = $env:FIXTURE_DIRECTORY
        $live = $other.Start($env:FIXTURE_PYTHON, @('-c', 'import time; time.sleep(60)'),
            $dir, "$dir/other.out", "$dir/other.err")
        $owned = $job.Start($env:FIXTURE_PYTHON, @('-c', 'import time; time.sleep(60)'),
            $dir, "$dir/owned.out", "$dir/owned.err")
        try {
            $job.Start("$dir/missing.exe", @(), $dir, "$dir/fail.out", "$dir/fail.err")
            throw 'Missing executable was accepted'
        } catch {
            if ($_.Exception.Message -notlike '*DEV_PROCESS_JOB_FAILED:CREATE_PROCESS:*') { throw }
        }
        $job.Dispose()
        $job.Dispose()
        if ($live.HasExited) { throw 'Other invocation was stopped' }
        $job = [Knora.Dev.ProcessJob]::new()
        $replacement = $job.Start($env:FIXTURE_PYTHON, @('-c', 'print("new invocation")'),
            $dir, "$dir/new.out", "$dir/new.err")
        if (-not $replacement.WaitForExit(5000) -or $replacement.ExitCode -ne 0) {
            throw 'New invocation failed'
        }
        'JOB_INVOCATIONS_OK'
    """,
    )
    assert result.returncode == 0, result.stderr
    assert "JOB_INVOCATIONS_OK" in result.stdout


@pytest.mark.skipif(os.name != "nt", reason="Windows native argv and log redirection")
@pytest.mark.parametrize("shell", ["powershell", "pwsh"])
def test_process_job_preserves_arguments_and_separate_standard_streams(tmp_path, shell):
    arguments = ["space & value", 'embedded"quote', "trailing\\", ""]
    result = _run_job_script(
        tmp_path,
        shell,
        """
        $dir = $env:FIXTURE_DIRECTORY
        $arguments = [string[]](ConvertFrom-Json $env:FIXTURE_ARGUMENTS)
        $code = 'import json,sys; print(json.dumps(sys.argv[1:])); print("stderr", file=sys.stderr)'
        $child = $job.Start($env:FIXTURE_PYTHON,
            (@('-c', $code) + $arguments),
            $dir, "$dir/out.log", "$dir/err.log")
        if (-not $child.WaitForExit(5000) -or $child.ExitCode -ne 0) { throw 'Child failed' }
    """,
        FIXTURE_ARGUMENTS=json.dumps(arguments),
    )
    assert result.returncode == 0, result.stderr
    assert json.loads((tmp_path / "out.log").read_text()) == arguments
    assert (tmp_path / "err.log").read_text().strip() == "stderr"


@pytest.mark.skipif(os.name != "nt", reason="Windows nested PDF memory Job")
@pytest.mark.parametrize("shell", ["powershell", "pwsh"])
def test_process_job_retains_pdf_child_memory_enforcement(tmp_path, shell):
    result = _run_job_script(
        tmp_path,
        shell,
        """
        $dir = $env:FIXTURE_DIRECTORY
        $child = $job.Start($env:FIXTURE_PYTHON,
            @('-m', 'knora.adapters.cli.worker', '--check-pdf-isolation'),
            (Get-Location).Path, "$dir/pdf.out", "$dir/pdf.err")
        if (-not $child.WaitForExit(30000) -or $child.ExitCode -ne 0) {
            throw 'Nested PDF memory enforcement failed'
        }
    """,
    )
    assert result.returncode == 0, result.stderr + (tmp_path / "pdf.err").read_text()
