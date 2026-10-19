"""The Figma harness cannot select or mutate a daily development project."""

import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
POWERSHELL = shutil.which("pwsh") or shutil.which("powershell")


@pytest.fixture
def disposable_runner(tmp_path: Path):
    """Real launcher/OS reservation; replace only Docker, HTTP and realm mutation."""
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    shutil.copy(ROOT / "scripts/prepare-figma-e2e.ps1", scripts)
    fixtures = tmp_path / "test/fixtures/keycloak"
    fixtures.mkdir(parents=True)
    shutil.copy(ROOT / "test/fixtures/keycloak/figma-realm.json", fixtures)
    (scripts / "configure-keycloak-auth-flow.ps1").write_text(
        "param($Mode,$BaseUrl,$Project,$AdminUsername,$AdminPassword)\n"
    )
    project = f"knora-figma-e2e-agent-{uuid.uuid4().hex[:12]}"
    graph = compose_graph("figma")
    graph["name"] = project
    for name, volume in graph["volumes"].items():
        volume["name"] = f"{project}_{name}"
    (tmp_path / "graph.json").write_text(json.dumps(graph))
    command = r"""
$ErrorActionPreference = 'Stop'
function docker {
    $global:LASTEXITCODE = 0
    if ($args[0] -eq 'compose' -and
        $args[[Array]::IndexOf($args, '--project-name') + 1] -cne $env:TEST_PROJECT) {
        throw 'WRONG_PROJECT_TARGET'
    }
    if ($args -contains 'config') {
        $graph = Get-Content -Raw $env:TEST_GRAPH | ConvertFrom-Json
        $graph.name = $env:TEST_PROJECT
        foreach ($volume in $graph.volumes.PSObject.Properties) {
            $volume.Value.name = "$($env:TEST_PROJECT)_$($volume.Name)"
        }
        $graph | ConvertTo-Json -Depth 30
    }
    elseif ($args -contains 'up') {
        Add-Content -LiteralPath $env:TEST_EVENTS -Value 'up'
        if ($env:TEST_MODE -eq 'wait-start') {
            while (-not (Test-Path -LiteralPath $env:TEST_RELEASE)) { Start-Sleep -Milliseconds 50 }
        }
        if ($env:TEST_MODE -in 'wait-start','start-failure') { $global:LASTEXITCODE = 1 }
    } elseif ($args -contains 'down') {
        Add-Content -LiteralPath $env:TEST_EVENTS -Value 'down'
        if ($args -notcontains '--volumes') { throw 'VOLUMES_NOT_CLEANED' }
        if ($env:TEST_MODE -eq 'wait-cleanup') {
            while (-not (Test-Path -LiteralPath $env:TEST_RELEASE)) { Start-Sleep -Milliseconds 50 }
        }
        if ($env:TEST_MODE -eq 'cleanup-failure') { $global:LASTEXITCODE = 1 }
    } elseif ($args[0] -eq 'ps' -and $env:TEST_MODE -eq 'retained') { 'foreign-container' }
    elseif ($args[0] -eq 'ps' -and $env:TEST_MODE -eq 'cleanup-retained' -and
        (Test-Path -LiteralPath $env:TEST_EVENTS) -and
        (Get-Content -LiteralPath $env:TEST_EVENTS) -contains 'down') { 'leftover-container' }
    elseif ($args[0] -eq 'ps' -and $env:TEST_MODE -eq 'inspection-failure') {
        $global:LASTEXITCODE = 1
    } elseif ($args[0] -eq $env:TEST_MODE -and $args -notcontains '--filter') {
        "$($env:TEST_PROJECT)_retained"
    }
}
function Invoke-RestMethod { @{} }
function New-Object {
    if ($args[0] -ne 'Net.Sockets.TcpClient') {
        return Microsoft.PowerShell.Utility\New-Object @args
    }
    $client = [pscustomobject]@{ Connected = ($env:TEST_MODE -eq 'port-in-use') }
    $client | Add-Member -MemberType ScriptMethod -Name ConnectAsync -Value {
        [Threading.Tasks.Task]::FromResult($this.Connected)
    }
    $client | Add-Member -MemberType ScriptMethod -Name Dispose -Value {}
    $client
}
$parameters = @{ Project = $env:TEST_PROJECT }
# Reproduce the pre-fix race too, without requiring the new lifecycle parameter.
if ($env:TEST_PROJECT -ne 'knora-figma-e2e' -and
    (Get-Command ./scripts/prepare-figma-e2e.ps1).Parameters.ContainsKey('Run')) {
    $parameters.Run = {
        Add-Content -LiteralPath $env:TEST_EVENTS -Value 'verify'
        if ($env:TEST_MODE -eq 'wait-verify') {
            while (-not (Test-Path -LiteralPath $env:TEST_RELEASE)) { Start-Sleep -Milliseconds 50 }
        }
        if ($env:TEST_MODE -eq 'verification-failure') { throw 'VERIFY_FAILED' }
    }
}
& ./scripts/prepare-figma-e2e.ps1 @parameters
"""
    environment = {
        key: value
        for key, value in os.environ.items()
        if not re.match(
            r"^(COMPOSE_|FIGMA_E2E_|M5_E2E_|KEYCLOAK_|KNORA_|DOCKER_|SESSION_SECRET$)", key
        )
    }
    environment.update(
        TEST_GRAPH=str(tmp_path / "graph.json"),
        TEST_PROJECT=project,
        TEST_EVENTS=str(tmp_path / "events"),
        TEST_RELEASE=str(tmp_path / "release"),
    )

    def start(mode: str, *, legacy: bool = False):
        return subprocess.Popen(
            [POWERSHELL, "-NoProfile", "-Command", command],
            cwd=tmp_path,
            env={
                **environment,
                "TEST_MODE": mode,
                "TEST_PROJECT": "knora-figma-e2e" if legacy else project,
            },
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    claim = Path(tempfile.gettempdir()) / f"knora-figma-reservation-{project}.lock"
    assert not claim.exists()
    try:
        yield start, tmp_path
    finally:
        # This unique test project uses only doubles; no Compose child can survive it.
        claim.unlink(missing_ok=True)


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell guard runner unavailable")
@pytest.mark.parametrize(
    ("phase", "before_release", "after_release"),
    [
        ("wait-start", ["up"], ["up", "down"]),
        ("wait-verify", ["up", "verify"], ["up", "verify", "down"]),
        ("wait-cleanup", ["up", "verify", "down"], ["up", "verify", "down"]),
    ],
)
def test_disposable_reservation_rejects_concurrent_launcher(
    disposable_runner, phase: str, before_release: list[str], after_release: list[str]
) -> None:
    start, directory = disposable_runner
    first = start(phase)
    second = None
    try:
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if (directory / "events").exists() and (
                directory / "events"
            ).read_text().splitlines() == before_release:
                break
            time.sleep(0.05)
        assert (directory / "events").read_text().splitlines() == before_release
        second = start("wait-start")
        try:
            output, error = second.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            pytest.fail("Competing invocation entered startup instead of refusing ownership")
        assert second.returncode != 0
        assert "FIGMA_PROJECT_RESERVED" in error
        assert "FIGMA_PREPARED" not in output
        assert (directory / "events").read_text().splitlines() == before_release
    finally:
        (directory / "release").touch()
        first.communicate(timeout=15)
        if second is not None:
            second.communicate(timeout=15)
    assert (directory / "events").read_text().splitlines() == after_release


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell guard runner unavailable")
@pytest.mark.parametrize(
    ("mode", "error", "events"),
    [
        ("start-failure", "FIGMA_START_FAILED", ["up", "down"]),
        ("verification-failure", "VERIFY_FAILED", ["up", "verify", "down"]),
        ("retained", "FIGMA_PROJECT_NOT_FRESH", []),
        ("volume", "FIGMA_PROJECT_NOT_FRESH", []),
        ("network", "FIGMA_PROJECT_NOT_FRESH", []),
        ("inspection-failure", "FIGMA_RESOURCE_INSPECTION_FAILED", []),
        ("port-in-use", "FIGMA_PORT_IN_USE", []),
        ("cleanup-failure", "FIGMA_CLEANUP_FAILED", ["up", "verify", "down"]),
    ],
)
def test_disposable_cleanup_only_after_owned_startup(
    disposable_runner, mode: str, error: str, events: list[str]
) -> None:
    start, directory = disposable_runner
    process = start(mode)
    _, stderr = process.communicate(timeout=20)
    assert process.returncode != 0
    assert error in stderr
    path = directory / "events"
    assert (path.read_text().splitlines() if path.exists() else []) == events


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell guard runner unavailable")
def test_disposable_reservation_released_after_cleanup(disposable_runner) -> None:
    start, directory = disposable_runner
    for _ in range(2):
        process = start("success")
        output, error = process.communicate(timeout=20)
        assert process.returncode == 0, error
        assert "FIGMA_PREPARED" in output
    assert (directory / "events").read_text().splitlines() == [
        "up",
        "verify",
        "down",
        "up",
        "verify",
        "down",
    ]


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell guard runner unavailable")
def test_killed_launcher_keeps_claim_before_compose_can_create_resources(disposable_runner) -> None:
    start, directory = disposable_runner
    first = start("wait-start")
    try:
        deadline = time.monotonic() + 15
        while not (directory / "events").exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        assert (directory / "events").read_text().splitlines() == ["up"]
    finally:
        first.kill()
        first.communicate(timeout=15)
    # A surviving native Compose child may still be building: resource lists are empty.
    second = start("success")
    _, error = second.communicate(timeout=20)
    assert second.returncode != 0
    assert "FIGMA_PROJECT_RESERVED" in error
    assert (directory / "events").read_text().splitlines() == ["up"]


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell guard runner unavailable")
@pytest.mark.parametrize("mode", ["cleanup-failure", "cleanup-retained"])
def test_failed_cleanup_keeps_claim_instead_of_allowing_reuse(disposable_runner, mode: str) -> None:
    start, directory = disposable_runner
    first = start(mode)
    _, error = first.communicate(timeout=20)
    assert first.returncode != 0
    assert "FIGMA_CLEANUP_FAILED" in error
    second = start("success")
    _, error = second.communicate(timeout=20)
    assert second.returncode != 0
    assert "FIGMA_PROJECT_RESERVED" in error
    assert (directory / "events").read_text().splitlines() == ["up", "verify", "down"]


def test_figma_compose_has_exact_isolated_loopback_bindings() -> None:
    graph = yaml.safe_load((ROOT / "docker-compose.dev.yml").read_text())
    expected = {
        "figma-postgres": ["127.0.0.1:5543:5432"],
        "figma-keycloak": ["127.0.0.1:8380:8080"],
        "figma-api": ["127.0.0.1:8800:8000"],
        "figma-minio": ["127.0.0.1:9900:9000", "127.0.0.1:9901:9001"],
        "figma-mail": ["127.0.0.1:1025:1025", "127.0.0.1:8025:8025"],
    }
    for name, bindings in expected.items():
        assert graph["services"][name]["ports"] == bindings
    assert graph["services"]["figma-keycloak"]["environment"]["KC_DB_URL"].endswith("/keycloak")
    assert all(volume is None or "name" not in volume for volume in graph["volumes"].values())


def test_figma_realm_keeps_native_profile_and_separate_callback() -> None:
    realm = json.loads((ROOT / "test/fixtures/keycloak/figma-realm.json").read_text())
    assert realm["realm"] == "knora-dev"
    assert realm["verifyEmail"] is False
    assert realm["registrationAllowed"] is True
    assert realm["resetPasswordAllowed"] is True
    assert realm["loginWithEmailAllowed"] is True
    assert realm["duplicateEmailsAllowed"] is False
    client = next(c for c in realm["clients"] if c["clientId"] == "knora-web")
    assert client["redirectUris"] == ["http://127.0.0.1:3300/api/auth/callback"]
    assert client["baseUrl"] == "http://127.0.0.1:3300"
    assert client["rootUrl"] == "http://127.0.0.1:3300"
    assert realm["smtpServer"]["host"] == "mail"


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell guard runner unavailable")
@pytest.mark.parametrize(
    "name",
    [
        "COMPOSE_PROJECT_NAME",
        "COMPOSE_FILE",
        "KEYCLOAK_ISSUER",
        "KNORA_DATABASE_URL",
        "DOCKER_HOST",
        "DOCKER_CONTEXT",
    ],
)
def test_prepare_rejects_ambient_overrides_before_docker(name: str) -> None:
    environment = {
        key: value
        for key, value in os.environ.items()
        if not re.match(
            r"^(COMPOSE_|FIGMA_E2E_|M5_E2E_|KEYCLOAK_|KNORA_|DOCKER_|SESSION_SECRET$)", key
        )
    }
    environment[name] = "unauthorized-target"
    result = subprocess.run(
        [
            POWERSHELL,
            "-NoProfile",
            "-File",
            str(ROOT / "scripts/prepare-figma-e2e.ps1"),
            "-CheckConfigurationOnly",
        ],
        capture_output=True,
        text=True,
        env=environment,
        cwd=ROOT,
        check=False,
    )
    assert result.returncode != 0
    assert "FIGMA_AMBIENT_OVERRIDE_REJECTED" in result.stderr


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell guard runner unavailable")
@pytest.mark.parametrize("field", ["baseUrl", "rootUrl"])
@pytest.mark.parametrize(
    "value", [None, "https://evil.example", "http://127.0.0.1:3300/old?code=secret"]
)
def test_prepare_rejects_untrusted_completion_origin_before_docker(
    tmp_path: Path, field: str, value: str | None
) -> None:
    scripts = tmp_path / "scripts"
    fixtures = tmp_path / "test/fixtures/keycloak"
    scripts.mkdir()
    fixtures.mkdir(parents=True)
    shutil.copy(ROOT / "scripts/prepare-figma-e2e.ps1", scripts)
    realm = json.loads((ROOT / "test/fixtures/keycloak/figma-realm.json").read_text())
    client = next(c for c in realm["clients"] if c["clientId"] == "knora-web")
    client.update(baseUrl="http://127.0.0.1:3300", rootUrl="http://127.0.0.1:3300")
    if value is None:
        client.pop(field)
    else:
        client[field] = value
    (fixtures / "figma-realm.json").write_text(json.dumps(realm))
    # The shim proves the guard fails before even read-only Docker configuration.
    (tmp_path / "docker.cmd").write_text("@echo DOCKER_MUST_NOT_RUN\n@exit /b 1\n")
    environment = {
        key: item
        for key, item in os.environ.items()
        if not re.match(
            r"^(COMPOSE_|FIGMA_E2E_|M5_E2E_|KEYCLOAK_|KNORA_|DOCKER_|SESSION_SECRET$)", key
        )
    }
    environment["PATH"] = str(tmp_path) + os.pathsep + environment.get("PATH", "")
    result = subprocess.run(
        [
            POWERSHELL,
            "-NoProfile",
            "-File",
            str(scripts / "prepare-figma-e2e.ps1"),
            "-CheckConfigurationOnly",
        ],
        capture_output=True,
        text=True,
        env=environment,
        cwd=tmp_path,
        check=False,
    )
    assert result.returncode != 0
    assert "FIGMA_FIXTURE_REJECTED" in result.stderr
    assert "DOCKER_MUST_NOT_RUN" not in result.stdout


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell guard runner unavailable")
def test_ordinary_preparation_has_no_resource_reset(disposable_runner) -> None:
    start, directory = disposable_runner
    for _ in range(2):
        process = start("success", legacy=True)
        output, error = process.communicate(timeout=20)
        assert process.returncode == 0, error
        assert "FIGMA_PREPARED" in output
    assert (directory / "events").read_text().splitlines() == ["up", "up"]


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell guard runner unavailable")
@pytest.mark.parametrize("resource", ["ps", "volume", "network"])
def test_disposable_project_refuses_retained_resources_before_start(
    tmp_path: Path, resource: str
) -> None:
    project = "knora-figma-e2e-agent-guard"
    graph = compose_graph("figma")
    graph["name"] = project
    for name, volume in graph["volumes"].items():
        volume["name"] = f"{project}_{name}"
    graph_path = tmp_path / "graph.json"
    graph_path.write_text(json.dumps(graph))
    command = """
function docker {
    if ($args[0] -eq 'compose' -and $args -contains 'config') {
        Get-Content -Raw $env:TEST_GRAPH
    } elseif ($args[0] -eq $env:TEST_RESOURCE) {
        'retained-resource'
    } elseif ($args -contains 'up') {
        throw 'MUTATION_MUST_NOT_RUN'
    }
    $global:LASTEXITCODE = 0
}
& ./scripts/prepare-figma-e2e.ps1 -Project knora-figma-e2e-agent-guard -Run {
    throw 'VERIFICATION_MUST_NOT_RUN'
}
"""
    environment = {
        key: value
        for key, value in os.environ.items()
        if not re.match(
            r"^(COMPOSE_|FIGMA_E2E_|M5_E2E_|KEYCLOAK_|KNORA_|DOCKER_|SESSION_SECRET$)", key
        )
    }
    environment.update(TEST_GRAPH=str(graph_path), TEST_RESOURCE=resource)
    result = subprocess.run(
        [POWERSHELL, "-NoProfile", "-Command", command],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "FIGMA_PROJECT_NOT_FRESH" in result.stderr
    assert "MUTATION_MUST_NOT_RUN" not in result.stderr
    assert "FIGMA_PROJECT_FRESH=" not in result.stdout


def compose_graph(*profiles: str) -> dict:
    environment = {
        key: value
        for key, value in os.environ.items()
        if not re.match(
            r"^(COMPOSE_|FIGMA_E2E_|M5_E2E_|KEYCLOAK_|KNORA_|DOCKER_|SESSION_SECRET$)", key
        )
    }
    args = [
        "docker",
        "compose",
        "-f",
        str(ROOT / "docker-compose.dev.yml"),
        "--project-name",
        "knora-figma-e2e",
    ]
    for profile in profiles:
        args += ["--profile", profile]
    result = subprocess.run(
        args + ["config", "--format", "json"],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


def test_only_two_compose_entry_points_and_production_excludes_test_services() -> None:
    assert {p.name for p in ROOT.glob("docker-compose*.yml")} == {
        "docker-compose.yml",
        "docker-compose.dev.yml",
    }
    production = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
    assert set(production["services"]) == {"postgres", "minio", "minio-init", "api"}
    assert "KNORA_STORAGE_PROOF" not in json.dumps(production)
    assert "start-dev" not in json.dumps(production)


def test_default_dev_graph_does_not_start_figma_or_proof_services() -> None:
    graph = compose_graph()
    assert set(graph["services"]) == {
        "postgres",
        "minio",
        "minio-init",
        "api",
        "keycloak-dev",
        "keycloak-dev-db",
    }
    assert graph["services"]["api"]["environment"]["KNORA_M5_E2E_FAULTS_ENABLED"] == "false"
    assert "KNORA_STORAGE_PROOF" not in json.dumps(graph)


def test_figma_graph_preserves_storage_names_and_isolated_dependencies() -> None:
    graph = compose_graph("figma")
    services = graph["services"]
    assert set(services["figma-api"]["depends_on"]) == {
        "figma-postgres",
        "figma-minio-init",
        "figma-keycloak",
    }
    assert "@figma-postgres:" in services["figma-api"]["environment"]["KNORA_DATABASE_URL"]
    assert services["figma-keycloak"]["environment"]["KC_DB_URL"] == (
        "jdbc:postgresql://figma-keycloak-db:5432/keycloak"
    )
    for service, volume in (
        ("figma-postgres", "postgres_data"),
        ("figma-keycloak-db", "keycloak_database"),
        ("figma-minio", "minio_data"),
    ):
        assert services[service]["volumes"][0]["source"] == volume
        assert graph["volumes"][volume]["name"] == f"knora-figma-e2e_{volume}"
    assert "KNORA_STORAGE_PROOF" not in json.dumps(graph)
    assert "storage-probe" not in json.dumps(graph)


def test_proof_and_fault_services_are_explicit_and_share_only_test_database() -> None:
    graph = compose_graph("figma", "otp-proof", "commit-reply-fault")
    for name, port in (("figma-keycloak-proof-main", "8380"), ("figma-keycloak-proof", "8381")):
        node = graph["services"][name]
        assert (
            node["environment"]["KC_DB_URL"] == "jdbc:postgresql://figma-keycloak-db:5432/keycloak"
        )
        assert node["environment"]["KNORA_STORAGE_PROOF"] == "enabled"
        # Fails the probe's >=32 character authorization requirement without launcher provisioning.
        assert len(node["environment"]["KNORA_STORAGE_PROOF_SECRET"]) < 32
        assert node["ports"][0]["published"] == port
        assert node["ports"][0]["host_ip"] == "127.0.0.1"
    assert not graph["services"]["otp-commit-proxy"].get("ports")
    assert "KNORA_STORAGE_PROOF" not in graph["services"]["figma-keycloak"]["environment"]


def test_figma_launcher_uses_explicit_service_list() -> None:
    script = (ROOT / "scripts/prepare-figma-e2e.ps1").read_text()
    command = next(line for line in script.splitlines() if " up -d " in line)
    assert command.split("--build ")[1].split() == [
        "figma-postgres",
        "figma-keycloak-db",
        "figma-keycloak",
        "figma-mail",
        "figma-minio",
        "figma-minio-init",
        "figma-api",
    ]
