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
@pytest.mark.parametrize("shell", ["powershell", "pwsh"])
@pytest.mark.parametrize("parameter", ["ApiPort", "FrontendPort"])
def test_daily_launcher_rejects_occupied_port_before_starting_services(tmp_path, parameter, shell):
    executable = shutil.which(shell)
    if executable is None:
        pytest.skip(f"{shell} is unavailable")
    env_file = tmp_path / ".env"
    env_file.write_text("# isolated\n")
    wrapper = tmp_path / "invoke.ps1"
    wrapper.write_text(
        "param([string]$EnvFile, [string]$PythonExe, [string]$OllamaBaseUrl, "
        "[int]$ApiPort, [int]$FrontendPort)\n"
        # Port safety must work even when the NetTCPIP/CIM provider is unavailable.
        "function Get-NetTCPConnection { throw 'CIM_QUERY_UNAVAILABLE' }\n"
        "& $env:KNORA_TEST_SCRIPT @PSBoundParameters\n"
        "exit $LASTEXITCODE\n"
    )
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
                executable,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(wrapper),
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
            env={**os.environ, "KNORA_TEST_SCRIPT": str(SCRIPT)},
        )
        assert result.returncode == 2, result.stderr
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


@pytest.mark.skipif(os.name != "nt", reason="Windows-local launcher")
@pytest.mark.parametrize("shell", ["powershell", "pwsh"])
@pytest.mark.parametrize("occupied", [True, False])
@pytest.mark.parametrize(
    "ownership",
    [
        "owned",
        "foreign-project",
        "foreign-service",
        "foreign-directory",
        "stopped-foreign-directory",
        "foreign-minio-directory",
        "wrong-port",
        "wildcard-binding",
        "missing-labels",
        "inspect-failed",
        "docker-unavailable",
        "no-container",
        "orphan-volume",
        "stopped-owned-postgres",
        "unverified-volume",
        "wrong-label-volume",
    ],
)
def test_daily_launcher_checks_postgres_ownership_before_side_effects(
    tmp_path, shell, occupied, ownership
):
    executable = shutil.which(shell)
    if executable is None:
        pytest.skip(f"{shell} is unavailable")
    env_file = tmp_path / ".env"
    env_file.write_text("# isolated\n")
    calls_file = tmp_path / "docker-calls.txt"
    wrapper = tmp_path / "invoke.ps1"
    wrapper.write_text(
        textwrap.dedent("""
        param([string]$EnvFile, [int]$PostgresPort, [int]$ApiPort, [int]$FrontendPort)
        Set-StrictMode -Version Latest
        function Get-NetTCPConnection { throw 'CIM_QUERY_UNAVAILABLE' }
        function docker {
          Add-Content -LiteralPath $env:KNORA_TEST_CALLS -Value ($args -join ' ')
          if ($args[0] -eq 'ps') {
            if ($env:KNORA_TEST_OWNERSHIP -eq 'docker-unavailable') { throw 'unavailable' }
            $global:LASTEXITCODE = 0
            if ($env:KNORA_TEST_OWNERSHIP -eq 'stopped-foreign-directory' -and
                $args -notcontains '-a') { return }
            if ($env:KNORA_TEST_OWNERSHIP -notin @('no-container', 'orphan-volume')) {
              'synthetic-container'
            }
          } elseif ($args[0] -eq 'volume') {
            $global:LASTEXITCODE = 0
            if ($env:KNORA_TEST_OWNERSHIP -eq 'docker-unavailable') { throw 'unavailable' }
            if ($env:KNORA_TEST_VOLUMES) {
              $vols = (ConvertFrom-Json -InputObject $env:KNORA_TEST_VOLUMES)
              if ($args[1] -eq 'ls') {
                if (($args -join ' ') -like '*label=com.docker.compose.project=*') {
                  foreach ($v in $vols) {
                    if ($v.PSObject.Properties['labels'] -and $v.labels -and
                        $v.labels.PSObject.Properties['com.docker.compose.project'] -and
                        $v.labels.'com.docker.compose.project' -eq 'knora-dev') {
                      if ($v.PSObject.Properties['name']) { $v.name }
                    }
                  }
                } else {
                  foreach ($v in $vols) {
                    if ($v.PSObject.Properties['name']) { $v.name }
                  }
                }
              } elseif ($args[1] -eq 'inspect') {
                if ($env:KNORA_TEST_OWNERSHIP -eq 'inspect-failed') {
                  $global:LASTEXITCODE = 1
                  return
                }
                $targetName = $args[2]
                $found = $null
                foreach ($v in $vols) {
                  if ($v.PSObject.Properties['name'] -and $v.name -eq $targetName) { $found = $v }
                }
                if (-not $found) { $global:LASTEXITCODE = 1; return }
                if ($args[-1] -like '*Labels*') {
                  if ($found.PSObject.Properties['labels'] -and $found.labels) {
                    $found.labels | ConvertTo-Json -Compress
                  } else {
                    '{}'
                  }
                } else {
                  if ($found.PSObject.Properties['name']) { $found.name }
                }
              }
            }
          } elseif ($args[0] -eq 'inspect') {
            $global:LASTEXITCODE = 0
            if ($env:KNORA_TEST_OWNERSHIP -eq 'inspect-failed') { $global:LASTEXITCODE = 1 }
            $data = $env:KNORA_TEST_CONTAINER | ConvertFrom-Json
            if ($args[-1] -like '*Config.Labels*') {
              if ($data.PSObject.Properties['labels'] -and $data.labels) {
                $data.labels | ConvertTo-Json -Compress
              } else {
                '{}'
              }
            }
            elseif ($args[-1] -like '*Mounts*') {
              if ($data.PSObject.Properties['mounts'] -and $data.mounts) {
                $data.mounts | ConvertTo-Json -Depth 5 -Compress
              } else {
                '[]'
              }
            }
            elseif ($args[-1] -like '*State*') {
              if ($data.PSObject.Properties['state'] -and $data.state) {
                $data.state | ConvertTo-Json -Compress
              } else {
                '{"Running":true}'
              }
            }
            else {
              if ($data.PSObject.Properties['ports'] -and $data.ports) {
                $data.ports | ConvertTo-Json -Depth 5 -Compress
              } else {
                '{}'
              }
            }
          } else { throw 'COMPOSE_MUTATION_ATTEMPTED' }
        }
        & $env:KNORA_TEST_SCRIPT @PSBoundParameters -EmbeddingProvider invalid
        exit $LASTEXITCODE
        """).strip()
        + "\n"
    )
    with socket.socket() as listener, socket.socket() as unused_api, socket.socket() as unused_ui:
        listener.bind(("127.0.0.1", 0))
        if occupied:
            listener.listen()
        unused_api.bind(("127.0.0.1", 0))
        unused_ui.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
        labels = {
            "com.docker.compose.project": "knora-dev",
            "com.docker.compose.service": "postgres",
            "com.docker.compose.project.working_dir": str(SCRIPT.parents[1]),
        }
        for variant, key, value in (
            ("foreign-project", "project", "another-session"),
            ("foreign-service", "service", "minio"),
            ("foreign-directory", "project.working_dir", str(tmp_path)),
            ("stopped-foreign-directory", "project.working_dir", str(tmp_path)),
            ("foreign-minio-directory", "project.working_dir", str(tmp_path)),
        ):
            if ownership == variant:
                labels[f"com.docker.compose.{key}"] = value
        if ownership == "foreign-minio-directory":
            labels["com.docker.compose.service"] = "minio"

        volumes = []
        if ownership == "orphan-volume":
            volumes = [
                {
                    "name": "knora-dev_knora_postgres_data",
                    "labels": {
                        "com.docker.compose.project": "knora-dev",
                        "com.docker.compose.volume": "knora_postgres_data",
                    },
                }
            ]
        elif ownership == "unverified-volume":
            volumes = [
                {
                    "name": "knora-dev_knora_postgres_data",
                    "labels": {
                        "com.docker.compose.project": "knora-dev",
                        "com.docker.compose.volume": "knora_postgres_data",
                    },
                },
                {
                    "name": "knora-dev_knora_minio_data",
                    "labels": {
                        "com.docker.compose.project": "knora-dev",
                        "com.docker.compose.volume": "knora_minio_data",
                    },
                },
            ]
        elif ownership == "wrong-label-volume":
            volumes = [
                {
                    "name": "knora-dev_knora_postgres_data",
                    "labels": {
                        "com.docker.compose.project": "another-session",
                        "com.docker.compose.volume": "knora_postgres_data",
                    },
                }
            ]
        elif ownership == "owned":
            volumes = [
                {
                    "name": "knora-dev_knora_postgres_data",
                    "labels": {
                        "com.docker.compose.project": "knora-dev",
                        "com.docker.compose.volume": "knora_postgres_data",
                    },
                }
            ]

        container_mounts = []
        if ownership in {"owned", "unverified-volume", "stopped-owned-postgres"}:
            container_mounts = [
                {
                    "Type": "volume",
                    "Name": "knora-dev_knora_postgres_data",
                    "Destination": "/var/lib/postgresql/data",
                }
            ]

        is_running = ownership != "stopped-owned-postgres"
        container = {
            "labels": {} if ownership == "missing-labels" else labels,
            "state": {"Running": is_running},
            "mounts": container_mounts,
            "ports": {
                "5432/tcp": [
                    {
                        "HostIp": "0.0.0.0" if ownership == "wildcard-binding" else "127.0.0.1",
                        "HostPort": str(port + 1 if ownership == "wrong-port" else port),
                    }
                ]
            },
        }
        result = subprocess.run(
            [
                executable,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(wrapper),
                "-EnvFile",
                str(env_file),
                "-PostgresPort",
                str(port),
                "-ApiPort",
                str(unused_api.getsockname()[1]),
                "-FrontendPort",
                str(unused_ui.getsockname()[1]),
            ],
            env={
                **os.environ,
                "KNORA_TEST_SCRIPT": str(SCRIPT),
                "KNORA_TEST_CALLS": str(calls_file),
                "KNORA_TEST_OWNERSHIP": ownership,
                "KNORA_TEST_CONTAINER": json.dumps(container),
                "KNORA_TEST_VOLUMES": json.dumps(volumes),
            },
            capture_output=True,
            text=True,
            timeout=20,
        )
        assert result.returncode == 2, result.stderr
        reusable = (
            ownership == "owned"
            or (not occupied and ownership == "stopped-owned-postgres")
            or (
                not occupied
                and ownership
                in {"foreign-service", "wrong-port", "wildcard-binding", "no-container"}
            )
        )
        if reusable:
            # The guard allows reuse and reaches the next validation, not service startup.
            assert "INVALID_EMBEDDING_PROVIDER" in result.stderr
        else:
            if occupied:
                assert f"PORT_IN_USE:PostgresPort:{port}" in result.stderr
                assert "-PostgresPort" in result.stderr
            else:
                assert "COMPOSE_PROJECT_OWNERSHIP_UNVERIFIED:knora-dev" in result.stderr
        calls = calls_file.read_text(encoding="utf-8-sig").splitlines()
        assert all(call.startswith(("ps ", "inspect ", "volume ")) for call in calls)
        assert "COMPOSE_MUTATION_ATTEMPTED" not in result.stderr
        if occupied:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                pass


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
@pytest.mark.parametrize("shell", ["powershell", "pwsh"])
@pytest.mark.parametrize(
    "launcher,python_available",
    [("start-dev.ps1", False), ("start-dev.ps1", True), ("start-ollama-demo.ps1", False)],
)
def test_launcher_platform_check_supports_inherited_strict_mode(
    tmp_path, shell, launcher, python_available
):
    executable = shutil.which(shell)
    if executable is None:
        pytest.skip(f"{shell} is unavailable")
    env_file = tmp_path / ".env"
    env_file.write_text("# isolated\n")
    command = (
        "$ErrorActionPreference = 'Stop'; Set-StrictMode -Version 3.0; "
        "& $env:TEST_LAUNCHER -PreflightOnly -EnvFile $env:TEST_ENV_FILE "
        "-PythonExe $env:TEST_PYTHON"
    )
    if launcher == "start-dev.ps1":
        command += " -EmbeddingProvider deterministic-local -GenerationProvider deterministic-local"
    command += "; exit $LASTEXITCODE"
    result = subprocess.run(
        [executable, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
        env={
            **os.environ,
            "TEST_LAUNCHER": str(SCRIPT.parent / launcher),
            "TEST_ENV_FILE": str(env_file),
            "TEST_PYTHON": sys.executable
            if python_available
            else str(tmp_path / "missing-python.exe"),
        },
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == (0 if python_available else 2), result.stderr
    if python_available:
        assert "PRECHECK_OK embedding-local-m1-v2" in result.stdout
    else:
        assert "PYTHON_RUNTIME_UNAVAILABLE" in result.stderr


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
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length > 0:
                self.rfile.read(content_length)
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
        "& $env:FIXTURE_LAUNCHER -NoBrowser -EnvFile $env:FIXTURE_ENV "
        "-PythonExe $env:FIXTURE_PYTHON -EmbeddingProvider deterministic-local "
        "-GenerationProvider deterministic-local -ApiPort $env:FIXTURE_API_PORT "
        "-FrontendPort $env:FIXTURE_FRONTEND_PORT -PostgresPort $env:FIXTURE_POSTGRES_PORT\n"
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
        FIXTURE_ENV=str(root / "empty.env"),
        FIXTURE_PYTHON=sys.executable,
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
        with socket.socket() as postgres_reservation:
            postgres_reservation.bind(("127.0.0.1", 0))
            postgres_port = postgres_reservation.getsockname()[1]
            api_port, frontend_port = _unused_port(), _unused_port()
            environment.update(
                FIXTURE_API_PORT=str(api_port),
                FIXTURE_FRONTEND_PORT=str(frontend_port),
                FIXTURE_POSTGRES_PORT=str(postgres_port),
            )
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

            def observe(p=launcher, o=owner):
                if p.poll() is None:
                    with suppress(psutil.NoSuchProcess):
                        known.update(o.children(recursive=True))
                return log_path.read_text(errors="replace")

            if scenario == "startup-failure":
                _wait_until(lambda p=launcher: observe(p) and p.poll() is not None)
                assert "DEV_RUNTIME_FAILED" in observe(launcher)
                lock_file = root / "knora-dev-reservation-knora-dev.lock"
                assert not lock_file.exists(), (
                    "Reservation lock must be released on clean startup failure"
                )
                res_check = subprocess.run(
                    [
                        executable,
                        "-NoProfile",
                        "-ExecutionPolicy",
                        "Bypass",
                        "-File",
                        str(wrapper),
                        "-PreflightOnly",
                    ],
                    cwd=root,
                    env=environment,
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                assert "DEV_PROJECT_RESERVED" not in res_check.stderr
            else:
                _wait_until(
                    lambda p=launcher: "DEV_READY" in observe(p),
                    timeout=20,
                )
                if scenario == "exited-root":
                    frontend_pid = int(re.search(r"FRONTEND_PID=(\d+)", observe(launcher))[1])
                    frontend_root = next(
                        process for process in known if process.pid == frontend_pid
                    )
                    frontend_root.kill()
                    frontend_root.wait(5)
                if scenario == "worker-restart":
                    (root / "restart-worker").touch()
                    _wait_until(lambda p=launcher: "[worker] ready generation 2" in observe(p))
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


@pytest.mark.skipif(os.name != "nt", reason="Windows-local launcher reservation")
@pytest.mark.parametrize("shell", ["powershell", "pwsh"])
def test_concurrent_launchers_serialize_via_project_reservation(tmp_path: Path, shell: str):
    executable = shutil.which(shell)
    if executable is None:
        pytest.skip(f"{shell} is unavailable")

    shared_temp = tmp_path / "shared_temp"
    shared_temp.mkdir(parents=True)

    def setup_checkout(name: str) -> tuple[Path, Path]:
        checkout = tmp_path / name
        scripts = checkout / "scripts"
        scripts.mkdir(parents=True)
        shutil.copy2(SCRIPT, scripts / SCRIPT.name)
        native = SCRIPT.with_name("dev-process-job.cs")
        if native.exists():
            shutil.copy2(native, scripts / native.name)
        env_file = checkout / ".env"
        env_file.write_text("# isolated\n")
        return checkout, env_file

    checkout_a, env_a = setup_checkout("checkout_a")
    checkout_b, env_b = setup_checkout("checkout_b")

    signal_a_ready = shared_temp / "a_ready.signal"
    signal_a_release = shared_temp / "a_release.signal"

    wrapper_a = checkout_a / "invoke_a.ps1"
    wrapper_a.write_text(
        "param([string]$EnvFile, [int]$PostgresPort, [int]$ApiPort, [int]$FrontendPort)\n"
        "function docker {\n"
        "  if ($args[0] -eq 'ps') {\n"
        "    [IO.File]::WriteAllText($env:KNORA_SIGNAL_READY, 'ready')\n"
        "    $deadline = [DateTime]::UtcNow.AddSeconds(15)\n"
        "    while (-not (Test-Path -LiteralPath $env:KNORA_SIGNAL_RELEASE)) {\n"
        "      if ([DateTime]::UtcNow -gt $deadline) { throw 'TIMEOUT_WAITING_FOR_RELEASE' }\n"
        "      Start-Sleep -Milliseconds 50\n"
        "    }\n"
        "    $global:LASTEXITCODE = 0\n"
        "    return\n"
        "  }\n"
        "  throw 'COMPOSE_MUTATION_ATTEMPTED'\n"
        "}\n"
        "& $env:KNORA_TEST_SCRIPT @PSBoundParameters -EmbeddingProvider invalid\n"
        "exit $LASTEXITCODE\n"
    )

    calls_b = checkout_b / "docker_calls_b.txt"
    wrapper_b = checkout_b / "invoke_b.ps1"
    wrapper_b.write_text(
        "param([string]$EnvFile, [int]$PostgresPort, [int]$ApiPort, [int]$FrontendPort)\n"
        "function docker {\n"
        "  Add-Content -LiteralPath $env:KNORA_CALLS_B -Value ($args -join ' ')\n"
        "  $global:LASTEXITCODE = 0\n"
        "  throw 'COMPOSE_MUTATION_ATTEMPTED'\n"
        "}\n"
        "& $env:KNORA_TEST_SCRIPT @PSBoundParameters -EmbeddingProvider invalid\n"
        "exit $LASTEXITCODE\n"
    )

    port_pg = _unused_port()
    port_api = _unused_port()
    port_ui = _unused_port()

    env_vars = {
        **os.environ,
        "TEMP": str(shared_temp),
        "TMP": str(shared_temp),
    }

    proc_a = subprocess.Popen(
        [
            executable,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(wrapper_a),
            "-EnvFile",
            str(env_a),
            "-PostgresPort",
            str(port_pg),
            "-ApiPort",
            str(port_api),
            "-FrontendPort",
            str(port_ui),
        ],
        cwd=str(checkout_a),
        env={
            **env_vars,
            "KNORA_TEST_SCRIPT": str(checkout_a / "scripts" / "start-dev.ps1"),
            "KNORA_SIGNAL_READY": str(signal_a_ready),
            "KNORA_SIGNAL_RELEASE": str(signal_a_release),
        },
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    try:
        _wait_until(lambda: signal_a_ready.exists() or proc_a.poll() is not None, timeout=15)
        assert signal_a_ready.exists(), f"A failed to reach preflight: {proc_a.poll()}"

        proc_b = subprocess.run(
            [
                executable,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(wrapper_b),
                "-EnvFile",
                str(env_b),
                "-PostgresPort",
                str(port_pg),
                "-ApiPort",
                str(port_api),
                "-FrontendPort",
                str(port_ui),
            ],
            cwd=str(checkout_b),
            env={
                **env_vars,
                "KNORA_TEST_SCRIPT": str(checkout_b / "scripts" / "start-dev.ps1"),
                "KNORA_CALLS_B": str(calls_b),
            },
            capture_output=True,
            text=True,
            timeout=15,
        )

        assert proc_b.returncode == 2, proc_b.stderr
        assert "DEV_PROJECT_RESERVED:knora-dev" in proc_b.stderr
        assert not calls_b.exists() or calls_b.read_text().strip() == ""
        assert "COMPOSE_MUTATION_ATTEMPTED" not in proc_b.stderr
    finally:
        signal_a_release.write_text("release")
        out_a, err_a = proc_a.communicate(timeout=15)

    lock_file = shared_temp / "knora-dev-reservation-knora-dev.lock"
    assert not lock_file.exists(), "Lock file was not cleaned up after A exited cleanly"


@pytest.mark.skipif(os.name != "nt", reason="Windows-local launcher reservation")
@pytest.mark.parametrize("shell", ["powershell", "pwsh"])
def test_launcher_retains_reservation_on_force_kill_and_allows_manual_cleanup(
    tmp_path: Path, shell: str
):
    executable = shutil.which(shell)
    if executable is None:
        pytest.skip(f"{shell} is unavailable")

    shared_temp = tmp_path / "shared_temp"
    shared_temp.mkdir(parents=True)

    checkout = tmp_path / "checkout"
    scripts = checkout / "scripts"
    scripts.mkdir(parents=True)
    shutil.copy2(SCRIPT, scripts / SCRIPT.name)
    native = SCRIPT.with_name("dev-process-job.cs")
    if native.exists():
        shutil.copy2(native, scripts / native.name)
    env_file = checkout / ".env"
    env_file.write_text("# isolated\n")

    signal_ready = shared_temp / "a_ready.signal"
    signal_release = shared_temp / "a_release.signal"

    wrapper = checkout / "invoke.ps1"
    wrapper.write_text(
        "param([string]$EnvFile, [int]$PostgresPort, [int]$ApiPort, [int]$FrontendPort)\n"
        "function docker {\n"
        "  if ($args[0] -eq 'ps') {\n"
        "    [IO.File]::WriteAllText($env:KNORA_SIGNAL_READY, 'ready')\n"
        "    $deadline = [DateTime]::UtcNow.AddSeconds(15)\n"
        "    while (-not (Test-Path -LiteralPath $env:KNORA_SIGNAL_RELEASE)) {\n"
        "      if ([DateTime]::UtcNow -gt $deadline) { throw 'TIMEOUT_WAITING_FOR_RELEASE' }\n"
        "      Start-Sleep -Milliseconds 50\n"
        "    }\n"
        "    $global:LASTEXITCODE = 0\n"
        "    return\n"
        "  }\n"
        "  throw 'COMPOSE_MUTATION_ATTEMPTED'\n"
        "}\n"
        "& $env:KNORA_TEST_SCRIPT @PSBoundParameters -EmbeddingProvider invalid\n"
        "exit $LASTEXITCODE\n"
    )

    port_pg = _unused_port()
    port_api = _unused_port()
    port_ui = _unused_port()

    env_vars = {
        **os.environ,
        "TEMP": str(shared_temp),
        "TMP": str(shared_temp),
    }

    outsider = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(120)"],
        creationflags=subprocess.CREATE_NO_WINDOW,
    )

    try:
        proc_a = subprocess.Popen(
            [
                executable,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(wrapper),
                "-EnvFile",
                str(env_file),
                "-PostgresPort",
                str(port_pg),
                "-ApiPort",
                str(port_api),
                "-FrontendPort",
                str(port_ui),
            ],
            cwd=str(checkout),
            env={
                **env_vars,
                "KNORA_TEST_SCRIPT": str(checkout / "scripts" / "start-dev.ps1"),
                "KNORA_SIGNAL_READY": str(signal_ready),
                "KNORA_SIGNAL_RELEASE": str(signal_release),
            },
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        _wait_until(lambda: signal_ready.exists() or proc_a.poll() is not None, timeout=15)
        assert signal_ready.exists()

        proc_a.kill()
        proc_a.wait(timeout=10)

        assert outsider.poll() is None

        lock_file = shared_temp / "knora-dev-reservation-knora-dev.lock"
        assert lock_file.exists(), "Lock file was deleted on abnormal termination"

        proc_b = subprocess.run(
            [
                executable,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(wrapper),
                "-EnvFile",
                str(env_file),
                "-PostgresPort",
                str(port_pg),
                "-ApiPort",
                str(port_api),
                "-FrontendPort",
                str(port_ui),
            ],
            cwd=str(checkout),
            env={
                **env_vars,
                "KNORA_TEST_SCRIPT": str(checkout / "scripts" / "start-dev.ps1"),
                "KNORA_SIGNAL_READY": str(shared_temp / "b_ready.signal"),
                "KNORA_SIGNAL_RELEASE": str(shared_temp / "b_release.signal"),
            },
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert proc_b.returncode == 2
        assert "DEV_PROJECT_RESERVED:knora-dev" in proc_b.stderr

        lock_file.unlink()

        signal_release.write_text("release")
        proc_c = subprocess.run(
            [
                executable,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(wrapper),
                "-EnvFile",
                str(env_file),
                "-PostgresPort",
                str(port_pg),
                "-ApiPort",
                str(port_api),
                "-FrontendPort",
                str(port_ui),
            ],
            cwd=str(checkout),
            env={
                **env_vars,
                "KNORA_TEST_SCRIPT": str(checkout / "scripts" / "start-dev.ps1"),
                "KNORA_SIGNAL_READY": str(shared_temp / "c_ready.signal"),
                "KNORA_SIGNAL_RELEASE": str(signal_release),
            },
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert "DEV_PROJECT_RESERVED:knora-dev" not in proc_c.stderr
    finally:
        outsider.kill()
        outsider.wait(timeout=10)


@pytest.mark.skipif(os.name != "nt", reason="Windows-local launcher reservation")
@pytest.mark.parametrize("shell", ["powershell", "pwsh"])
def test_launcher_retains_reservation_on_mutating_startup_uncertainty(launcher_runtime, shell: str):
    executable = shutil.which(shell)
    if executable is None:
        pytest.skip(f"{shell} is unavailable")

    root, _ = launcher_runtime
    shared_temp = root / "shared_temp"
    shared_temp.mkdir(parents=True, exist_ok=True)
    lock_file = shared_temp / "knora-dev-reservation-knora-dev.lock"

    custom_wrapper = root / "uncertainty_wrapper.ps1"
    custom_wrapper.write_text(
        textwrap.dedent("""
        param(
            [string]$EnvFile,
            [int]$PostgresPort,
            [int]$ApiPort,
            [int]$FrontendPort,
            [string]$PythonExe,
            [string]$EmbeddingProvider = 'deterministic-local'
        )
        $ErrorActionPreference = 'Stop'
        function docker {
            $global:LASTEXITCODE = 0
            if ($args[0] -eq 'ps') { return }
            if ($args[0] -eq 'volume' -and $args[1] -eq 'ls') { return }
            if ($args[0] -eq 'volume' -and $args[1] -eq 'inspect') {
                $global:LASTEXITCODE = 1
                return
            }
            if ($args[0] -eq 'compose' -and $args -contains 'up') {
                if ($env:KNORA_SIMULATE_MUTATING_FAILURE -eq '1') {
                    $startInfo = New-Object Diagnostics.ProcessStartInfo
                    $startInfo.FileName = 'powershell.exe'
                    $startInfo.Arguments = '-NoProfile -Command Start-Sleep -Seconds 30'
                    $startInfo.UseShellExecute = $false
                    $startInfo.CreateNoWindow = $true
                    $ownedChild = [Diagnostics.Process]::Start($startInfo)
                    [Console]::WriteLine('OWNED_REVIEW_CHILD_PID=' + $ownedChild.Id)
                    throw 'SIMULATED_MUTATING_STARTUP_UNCERTAIN'
                }
                return
            }
            if ($args -contains 'exec') { '1'; return }
            return
        }
        if (-not $PSBoundParameters.ContainsKey('EmbeddingProvider')) {
            $PSBoundParameters['EmbeddingProvider'] = 'deterministic-local'
        }
        $PSBoundParameters['NoBrowser'] = $true
        $PSBoundParameters['GenerationProvider'] = 'deterministic-local'
        & $env:KNORA_TEST_SCRIPT @PSBoundParameters
        exit $LASTEXITCODE
        """)
    )

    port_pg = _unused_port()
    port_api = _unused_port()
    port_ui = _unused_port()

    env_vars = {
        **os.environ,
        "TEMP": str(shared_temp),
        "TMP": str(shared_temp),
        "KNORA_TEST_SCRIPT": str(root / "scripts" / "start-dev.ps1"),
        "KNORA_SIMULATE_MUTATING_FAILURE": "1",
        "SESSION_SECRET": "synthetic-session-secret-000000000000",
        "KNORA_CANONICAL_MINIO_ACCESS_KEY": "synthetic-access",
        "KNORA_CANONICAL_MINIO_SECRET_KEY": "synthetic-secret",
    }

    child_proc = None
    log_a = root / "proc_a.log"
    try:
        with log_a.open("w", encoding="utf-8") as out:
            proc_a = subprocess.run(
                [
                    executable,
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(custom_wrapper),
                    "-EnvFile",
                    str(root / "empty.env"),
                    "-PythonExe",
                    sys.executable,
                    "-PostgresPort",
                    str(port_pg),
                    "-ApiPort",
                    str(port_api),
                    "-FrontendPort",
                    str(port_ui),
                ],
                cwd=str(root),
                env=env_vars,
                stdout=out,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=15,
            )

        output_a = log_a.read_text(encoding="utf-8", errors="replace")
        assert proc_a.returncode == 2, output_a
        assert "DEV_RUNTIME_FAILED" in output_a
        assert "DEV_RESERVATION_RETAINED" in output_a

        match = re.search(r"OWNED_REVIEW_CHILD_PID=(\d+)", output_a)
        assert match is not None, f"Expected child PID marker in stdout: {proc_a.stdout}"
        child_pid = int(match.group(1))
        child_proc = psutil.Process(child_pid)
        assert child_proc.is_running()

        assert lock_file.exists(), (
            "Reservation lock must be retained when mutating startup is uncertain"
        )

        # Subsequent invocation B must be rejected due to retained lock
        env_vars_b = dict(env_vars)
        env_vars_b["KNORA_SIMULATE_MUTATING_FAILURE"] = "0"
        proc_b = subprocess.run(
            [
                executable,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(custom_wrapper),
                "-EnvFile",
                str(root / "empty.env"),
                "-PythonExe",
                sys.executable,
                "-PostgresPort",
                str(port_pg),
                "-ApiPort",
                str(port_api),
                "-FrontendPort",
                str(port_ui),
            ],
            cwd=str(root),
            env=env_vars_b,
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert proc_b.returncode == 2
        assert "DEV_PROJECT_RESERVED:knora-dev" in proc_b.stderr

        # Manual remediation cleans the child process and unlinks the lock
        child_proc.kill()
        child_proc.wait(timeout=5)
        child_proc = None
        lock_file.unlink()

        # Invocation C can now proceed past reservation check
        proc_c = subprocess.run(
            [
                executable,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(custom_wrapper),
                "-EnvFile",
                str(root / "empty.env"),
                "-PythonExe",
                sys.executable,
                "-EmbeddingProvider",
                "invalid",
                "-PostgresPort",
                str(port_pg),
                "-ApiPort",
                str(port_api),
                "-FrontendPort",
                str(port_ui),
            ],
            cwd=str(root),
            env=env_vars_b,
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert "DEV_PROJECT_RESERVED:knora-dev" not in proc_c.stderr
        assert "INVALID_EMBEDDING_PROVIDER" in proc_c.stderr
    finally:
        if child_proc is not None:
            with suppress(psutil.NoSuchProcess):
                child_proc.kill()
                child_proc.wait(timeout=5)
        if lock_file.exists():
            with suppress(OSError):
                lock_file.unlink()


@pytest.mark.skipif(os.name != "nt", reason="Windows-local launcher")
@pytest.mark.parametrize("shell", ["powershell", "pwsh"])
def test_daily_launcher_docker_metadata_timeout_aborts_and_cleans_reservation(tmp_path, shell):
    executable = shutil.which(shell)
    if executable is None:
        pytest.skip(f"{shell} is unavailable")

    fake_bin = tmp_path / "bin with spaces"
    fake_bin.mkdir()
    fake_docker = fake_bin / "docker.cmd"
    # The fake docker CLI hangs for 30s when asked for metadata
    fake_docker.write_text(
        '@echo off\r\npowershell.exe -NoProfile -Command "Start-Sleep -Seconds 30"\r\n'
    )

    env_file = tmp_path / ".env"
    env_file.write_text("# isolated\n")

    wrapper = tmp_path / "invoke.ps1"
    wrapper.write_text(
        textwrap.dedent("""
        param([string]$EnvFile, [int]$PostgresPort, [int]$ApiPort, [int]$FrontendPort)
        Set-StrictMode -Version Latest
        function Get-NetTCPConnection { throw 'CIM_QUERY_UNAVAILABLE' }
        & $env:KNORA_TEST_SCRIPT @PSBoundParameters
        exit $LASTEXITCODE
        """)
    )

    with socket.socket() as s1, socket.socket() as s2, socket.socket() as s3:
        s1.bind(("127.0.0.1", 0))
        s2.bind(("127.0.0.1", 0))
        s3.bind(("127.0.0.1", 0))
        port_pg = s1.getsockname()[1]
        port_api = s2.getsockname()[1]
        port_ui = s3.getsockname()[1]

    temp_dir = tmp_path / "temp"
    temp_dir.mkdir()
    env_vars = {
        **os.environ,
        "PATH": f"{fake_bin};{os.environ.get('PATH', '')}",
        "TEMP": str(temp_dir),
        "TMP": str(temp_dir),
        "KNORA_TEST_SCRIPT": str(SCRIPT),
    }

    start_time = time.time()
    result = subprocess.run(
        [
            executable,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(wrapper),
            "-EnvFile",
            str(env_file),
            "-PostgresPort",
            str(port_pg),
            "-ApiPort",
            str(port_api),
            "-FrontendPort",
            str(port_ui),
        ],
        env=env_vars,
        capture_output=True,
        text=True,
        timeout=22,
    )
    elapsed = time.time() - start_time

    assert result.returncode == 2, (
        f"Expected returncode 2, got {result.returncode}. Stderr: {result.stderr}"
    )
    assert "DOCKER_METADATA_TIMEOUT:knora-dev" in result.stderr
    assert 9 <= elapsed <= 19, (
        f"Elapsed time {elapsed}s was outside expected bounded timeout window"
    )

    lock_file = temp_dir / "knora-dev-reservation-knora-dev.lock"
    assert not lock_file.exists(), "Reservation lock must be released when metadata times out"


@pytest.mark.skipif(os.name != "nt", reason="Windows-local launcher")
@pytest.mark.parametrize("shell", ["powershell", "pwsh"])
def test_daily_launcher_docker_metadata_pipe_buffer_and_spaced_path(tmp_path, shell):
    executable = shutil.which(shell)
    if executable is None:
        pytest.skip(f"{shell} is unavailable")

    fake_bin = tmp_path / "bin with spaces"
    fake_bin.mkdir()
    fake_docker = fake_bin / "docker.cmd"
    # Emits large stdout exceeding 64KB pipe buffer and returns invalid ownership
    fake_docker.write_text(
        "@echo off\r\n"
        "powershell.exe -NoProfile -Command \"1..1000 | ForEach-Object { 'x' * 80 }\"\r\n"
    )

    env_file = tmp_path / ".env"
    env_file.write_text("# isolated\n")

    wrapper = tmp_path / "invoke.ps1"
    wrapper.write_text(
        textwrap.dedent("""
        param([string]$EnvFile, [int]$PostgresPort, [int]$ApiPort, [int]$FrontendPort)
        Set-StrictMode -Version Latest
        function Get-NetTCPConnection { throw 'CIM_QUERY_UNAVAILABLE' }
        & $env:KNORA_TEST_SCRIPT @PSBoundParameters
        exit $LASTEXITCODE
        """)
    )

    with socket.socket() as s1, socket.socket() as s2, socket.socket() as s3:
        s1.bind(("127.0.0.1", 0))
        s2.bind(("127.0.0.1", 0))
        s3.bind(("127.0.0.1", 0))
        port_pg = s1.getsockname()[1]
        port_api = s2.getsockname()[1]
        port_ui = s3.getsockname()[1]

    temp_dir = tmp_path / "temp"
    temp_dir.mkdir()
    env_vars = {
        **os.environ,
        "PATH": f"{fake_bin};{os.environ.get('PATH', '')}",
        "TEMP": str(temp_dir),
        "TMP": str(temp_dir),
        "KNORA_TEST_SCRIPT": str(SCRIPT),
    }

    result = subprocess.run(
        [
            executable,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(wrapper),
            "-EnvFile",
            str(env_file),
            "-PostgresPort",
            str(port_pg),
            "-ApiPort",
            str(port_api),
            "-FrontendPort",
            str(port_ui),
        ],
        env=env_vars,
        capture_output=True,
        text=True,
        timeout=10,
    )
    # The launcher successfully consumed large pipe buffer without deadlock,
    # found unverified containers/volumes, and exited safely.
    assert result.returncode == 2
    assert "COMPOSE_PROJECT_OWNERSHIP_UNVERIFIED:knora-dev" in result.stderr


@pytest.mark.skipif(os.name != "nt", reason="Windows-local launcher volume safety")
@pytest.mark.parametrize("shell", ["powershell", "pwsh"])
def test_launcher_refuses_when_volume_inspect_fails_on_existing_volume(tmp_path: Path, shell: str):
    executable = shutil.which(shell)
    if executable is None:
        pytest.skip(f"{shell} is unavailable")

    repo_dir = str(SCRIPT.parents[1]).replace("\\", "/")
    inspect_marker = tmp_path / "inspect_called.marker"
    marker_str = str(inspect_marker).replace("\\", "/")

    wrapper = tmp_path / "invoke.ps1"
    wrapper.write_text(
        textwrap.dedent(f"""
        param([string]$EnvFile, [int]$PostgresPort, [int]$ApiPort, [int]$FrontendPort)
        $ErrorActionPreference = 'Stop'
        function docker {{
            $global:LASTEXITCODE = 0
            if ($args[0] -eq 'ps') {{
                return @('fake-pg-id')
            }}
            if ($args[0] -eq 'inspect' -and $args[1] -eq 'fake-pg-id') {{
                if ($args[-1] -like '*Config.Labels*') {{
                    return @{{
                        'com.docker.compose.project' = 'knora-dev'
                        'com.docker.compose.service' = 'postgres'
                        'com.docker.compose.project.working_dir' = (Resolve-Path '{repo_dir}').Path
                    }} | ConvertTo-Json -Compress
                }}
                if ($args[-1] -like '*Mounts*') {{
                    return @(@{{
                        Type = 'volume'
                        Name = 'knora-dev_knora_postgres_data'
                        Destination = '/var/lib/postgresql/data'
                    }}) | ConvertTo-Json -Depth 5 -Compress
                }}
                if ($args[-1] -like '*State*') {{
                    return @{{ Running = $false }} | ConvertTo-Json -Compress
                }}
                return '{{}}'
            }}
            if ($args[0] -eq 'volume' -and $args[1] -eq 'ls') {{
                return @('knora-dev_knora_postgres_data')
            }}
            if ($args[0] -eq 'volume' -and $args[1] -eq 'inspect') {{
                [System.IO.File]::WriteAllText('{marker_str}', 'called')
                $global:LASTEXITCODE = 1
                return
            }}
            throw "UNEXPECTED_DOCKER_CALL: $($args -join ' ')"
        }}
        & $env:KNORA_TEST_SCRIPT @PSBoundParameters -EmbeddingProvider invalid
        exit $LASTEXITCODE
        """)
    )

    port_pg = _unused_port()
    port_api = _unused_port()
    port_ui = _unused_port()

    env_file = tmp_path / ".env"
    env_file.write_text("# isolated\n")
    temp_dir = tmp_path / "temp"
    temp_dir.mkdir()

    env_vars = {
        **os.environ,
        "TEMP": str(temp_dir),
        "TMP": str(temp_dir),
        "KNORA_TEST_SCRIPT": str(SCRIPT),
    }

    result = subprocess.run(
        [
            executable,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(wrapper),
            "-EnvFile",
            str(env_file),
            "-PostgresPort",
            str(port_pg),
            "-ApiPort",
            str(port_api),
            "-FrontendPort",
            str(port_ui),
        ],
        env=env_vars,
        capture_output=True,
        text=True,
        timeout=15,
    )

    assert inspect_marker.exists(), "docker volume inspect must be invoked"
    assert result.returncode == 2, result.stderr
    assert "COMPOSE_PROJECT_OWNERSHIP_UNVERIFIED:knora-dev" in result.stderr


@pytest.mark.skipif(os.name != "nt", reason="Windows-local launcher metadata deadline")
@pytest.mark.parametrize("shell", ["powershell", "pwsh"])
def test_launcher_docker_metadata_terminates_child_holding_pipe_within_deadline(
    tmp_path: Path, shell: str
):
    executable = shutil.which(shell)
    if executable is None:
        pytest.skip(f"{shell} is unavailable")

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_exe = fake_bin / "docker.exe"

    csharp_source = textwrap.dedent("""
    using System;
    using System.Diagnostics;
    using System.Reflection;
    using System.Threading;
    using System.IO;
    public class FakeDockerNestedPipe {
        public static void Main(string[] args) {
            string folder = Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location);
            string mode = args.Length == 0 ? "root" : args[0];
            string pidFile = Path.Combine(folder, mode + ".pid");
            File.WriteAllText(pidFile, Process.GetCurrentProcess().Id.ToString());
            if (mode == "leaf") { Thread.Sleep(30000); return; }
            string targetMode = mode == "root" ? "middle" : "leaf";
            var start = new ProcessStartInfo(Assembly.GetExecutingAssembly().Location, targetMode);
            start.UseShellExecute = false;
            start.CreateNoWindow = true;
            Process.Start(start);
            if (mode == "middle") Thread.Sleep(30000);
        }
    }
    """)

    compile_cmd = [
        "powershell.exe",
        "-NoProfile",
        "-Command",
        (
            f"Add-Type -TypeDefinition @'{csharp_source}'@ "
            f"-OutputAssembly '{fake_exe}' -OutputType ConsoleApplication"
        ),
    ]
    subprocess.run(compile_cmd, check=True)

    env_file = tmp_path / ".env"
    env_file.write_text("# isolated\n")

    wrapper = tmp_path / "invoke.ps1"
    wrapper.write_text(
        textwrap.dedent("""
        param([string]$EnvFile, [int]$PostgresPort, [int]$ApiPort, [int]$FrontendPort)
        Set-StrictMode -Version Latest
        function Get-NetTCPConnection { throw 'CIM_QUERY_UNAVAILABLE' }
        & $env:KNORA_TEST_SCRIPT @PSBoundParameters
        exit $LASTEXITCODE
        """)
    )

    port_pg = _unused_port()
    port_api = _unused_port()
    port_ui = _unused_port()

    temp_dir = tmp_path / "temp"
    temp_dir.mkdir()
    env_vars = {
        **os.environ,
        "PATH": f"{fake_bin};{os.environ.get('PATH', '')}",
        "TEMP": str(temp_dir),
        "TMP": str(temp_dir),
        "KNORA_TEST_SCRIPT": str(SCRIPT),
    }

    middle_pid = None
    leaf_pid = None
    try:
        start_time = time.time()
        result = subprocess.run(
            [
                executable,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(wrapper),
                "-EnvFile",
                str(env_file),
                "-PostgresPort",
                str(port_pg),
                "-ApiPort",
                str(port_api),
                "-FrontendPort",
                str(port_ui),
            ],
            env=env_vars,
            capture_output=True,
            text=True,
            timeout=22,
        )
        elapsed = time.time() - start_time

        assert result.returncode == 2, result.stderr
        assert "DOCKER_METADATA_TIMEOUT:knora-dev" in result.stderr
        assert 9 <= elapsed <= 19, f"Elapsed time {elapsed}s outside expected bounded timeout"

        middle_pid_file = fake_bin / "middle.pid"
        leaf_pid_file = fake_bin / "leaf.pid"
        if middle_pid_file.exists():
            middle_pid = int(middle_pid_file.read_text().strip())
            assert not psutil.pid_exists(middle_pid), (
                f"Middle process {middle_pid} must be terminated"
            )
        if leaf_pid_file.exists():
            leaf_pid = int(leaf_pid_file.read_text().strip())
            assert not psutil.pid_exists(leaf_pid), f"Leaf descendant {leaf_pid} must be terminated"
    finally:
        for pid in (middle_pid, leaf_pid):
            if pid and psutil.pid_exists(pid):
                with suppress(psutil.NoSuchProcess):
                    psutil.Process(pid).kill()


@pytest.mark.skipif(os.name != "nt", reason="Windows-local launcher mount/label verification")
@pytest.mark.parametrize("shell", ["powershell", "pwsh"])
@pytest.mark.parametrize(
    "case",
    [
        "valid",
        "null-labels",
        "empty-labels",
        "missing-project",
        "missing-role",
        "empty-project",
        "empty-role",
        "wrong-project",
        "wrong-role",
        "wrong-destination",
    ],
)
def test_launcher_verifies_volume_destination_and_role_label(tmp_path: Path, shell: str, case: str):
    executable = shutil.which(shell)
    if executable is None:
        pytest.skip(f"{shell} is unavailable")

    dest = (
        "/var/lib/postgresql/wrong_data"
        if case == "wrong-destination"
        else "/var/lib/postgresql/data"
    )

    repo_dir = str(SCRIPT.parents[1]).replace("\\", "/")
    wrapper = tmp_path / "invoke.ps1"
    wrapper.write_text(
        textwrap.dedent(f"""
        param([string]$EnvFile, [int]$PostgresPort, [int]$ApiPort, [int]$FrontendPort)
        $ErrorActionPreference = 'Stop'
        function docker {{
            $global:LASTEXITCODE = 0
            if ($args[0] -eq 'ps') {{
                return @('fake-pg-id')
            }}
            if ($args[0] -eq 'inspect' -and $args[1] -eq 'fake-pg-id') {{
                if ($args[-1] -like '*Config.Labels*') {{
                    return @{{
                        'com.docker.compose.project' = 'knora-dev'
                        'com.docker.compose.service' = 'postgres'
                        'com.docker.compose.project.working_dir' = (Resolve-Path '{repo_dir}').Path
                    }} | ConvertTo-Json -Compress
                }}
                if ($args[-1] -like '*Mounts*') {{
                    return @(@{{
                        Type = 'volume'
                        Name = 'knora-dev_knora_postgres_data'
                        Destination = '{dest}'
                    }}) | ConvertTo-Json -Depth 5 -Compress
                }}
                if ($args[-1] -like '*State*') {{
                    return @{{ Running = $false }} | ConvertTo-Json -Compress
                }}
                return '{{}}'
            }}
            if ($args[0] -eq 'volume' -and $args[1] -eq 'ls') {{
                return @('knora-dev_knora_postgres_data')
            }}
            if ($args[0] -eq 'volume' -and $args[1] -eq 'inspect') {{
                if ($args[2] -ne 'knora-dev_knora_postgres_data') {{
                    $global:LASTEXITCODE = 1
                    return
                }}
                if ($args[-1] -like '*{{.Name}}*') {{
                    return 'knora-dev_knora_postgres_data'
                }}
                if ('{case}' -eq 'null-labels') {{ return 'null' }}
                if ('{case}' -eq 'empty-labels') {{ return '{{}}' }}
                if ('{case}' -eq 'missing-project') {{
                    $meta = @{{ 'com.docker.compose.volume' = 'knora_postgres_data' }}
                    return ($meta | ConvertTo-Json -Compress)
                }}
                if ('{case}' -eq 'missing-role') {{
                    $meta = @{{ 'com.docker.compose.project' = 'knora-dev' }}
                    return ($meta | ConvertTo-Json -Compress)
                }}
                if ('{case}' -eq 'empty-project') {{
                    $meta = @{{
                        'com.docker.compose.project' = ''
                        'com.docker.compose.volume' = 'knora_postgres_data'
                    }}
                    return ($meta | ConvertTo-Json -Compress)
                }}
                if ('{case}' -eq 'empty-role') {{
                    $meta = @{{
                        'com.docker.compose.project' = 'knora-dev'
                        'com.docker.compose.volume' = ''
                    }}
                    return ($meta | ConvertTo-Json -Compress)
                }}
                if ('{case}' -eq 'wrong-project') {{
                    $meta = @{{
                        'com.docker.compose.project' = 'other-proj'
                        'com.docker.compose.volume' = 'knora_postgres_data'
                    }}
                    return ($meta | ConvertTo-Json -Compress)
                }}
                if ('{case}' -eq 'wrong-role') {{
                    $meta = @{{
                        'com.docker.compose.project' = 'knora-dev'
                        'com.docker.compose.volume' = 'wrong_role'
                    }}
                    return ($meta | ConvertTo-Json -Compress)
                }}
                return @{{
                    'com.docker.compose.project' = 'knora-dev'
                    'com.docker.compose.volume' = 'knora_postgres_data'
                }} | ConvertTo-Json -Compress
            }}
            throw "UNEXPECTED_DOCKER_CALL: $($args -join ' ')"
        }}
        & $env:KNORA_TEST_SCRIPT @PSBoundParameters -EmbeddingProvider invalid
        exit $LASTEXITCODE
        """)
    )

    port_pg = _unused_port()
    port_api = _unused_port()
    port_ui = _unused_port()

    env_file = tmp_path / ".env"
    env_file.write_text("# isolated\n")
    temp_dir = tmp_path / "temp"
    temp_dir.mkdir()

    env_vars = {
        **os.environ,
        "TEMP": str(temp_dir),
        "TMP": str(temp_dir),
        "KNORA_TEST_SCRIPT": str(SCRIPT),
    }

    result = subprocess.run(
        [
            executable,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(wrapper),
            "-EnvFile",
            str(env_file),
            "-PostgresPort",
            str(port_pg),
            "-ApiPort",
            str(port_api),
            "-FrontendPort",
            str(port_ui),
        ],
        env=env_vars,
        capture_output=True,
        text=True,
        timeout=15,
    )

    if case == "valid":
        assert "INVALID_EMBEDDING_PROVIDER" in result.stderr
        assert "COMPOSE_PROJECT_OWNERSHIP_UNVERIFIED" not in result.stderr
    else:
        assert result.returncode == 2, result.stderr
        assert "COMPOSE_PROJECT_OWNERSHIP_UNVERIFIED:knora-dev" in result.stderr
