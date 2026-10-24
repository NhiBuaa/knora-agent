"""The Figma harness cannot select or mutate a daily development project."""

import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import tomllib
import uuid
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
POWERSHELL = shutil.which("pwsh") or shutil.which("powershell")


def create_synthetic_frontend(base_dir: Path, **overrides) -> Path:
    fe = base_dir / "frontend"
    fe.mkdir(parents=True, exist_ok=True)
    pkg = overrides.get("pkg_json", {"name": "frontend", "version": "0.0.0"})
    if pkg is not None:
        (fe / "package.json").write_text(json.dumps(pkg) if isinstance(pkg, dict) else pkg)

    pw_test = fe / "node_modules/@playwright/test"
    pw_test.mkdir(parents=True, exist_ok=True)
    pw_test_pkg = overrides.get(
        "pw_test_pkg",
        {
            "name": "@playwright/test",
            "version": "1.48.0",
            "bin": {"playwright": "cli.js"},
            "exports": {"./cli": "./cli.js", "./package.json": "./package.json"},
        },
    )
    if pw_test_pkg is not None:
        (pw_test / "package.json").write_text(
            json.dumps(pw_test_pkg) if isinstance(pw_test_pkg, dict) else pw_test_pkg
        )

    cli_content = overrides.get("cli_content", "#!/usr/bin/env node\nconsole.log('pw-cli');\n")
    if cli_content is not None:
        (pw_test / "cli.js").write_text(cli_content)

    pw = fe / "node_modules/playwright"
    pw.mkdir(parents=True, exist_ok=True)
    pw_pkg = overrides.get(
        "pw_pkg",
        {
            "name": "playwright",
            "version": "1.48.0",
            "exports": {"./package.json": "./package.json"},
        },
    )
    if pw_pkg is not None:
        (pw / "package.json").write_text(json.dumps(pw_pkg) if isinstance(pw_pkg, dict) else pw_pkg)

    pwc = fe / "node_modules/playwright-core"
    pwc.mkdir(parents=True, exist_ok=True)
    pwc_pkg = overrides.get(
        "pwc_pkg",
        {
            "name": "playwright-core",
            "version": "1.48.0",
            "exports": {"./package.json": "./package.json"},
        },
    )
    if pwc_pkg is not None:
        (pwc / "package.json").write_text(
            json.dumps(pwc_pkg) if isinstance(pwc_pkg, dict) else pwc_pkg
        )

    lock = overrides.get(
        "lock_json",
        {
            "name": "frontend",
            "version": "0.0.0",
            "lockfileVersion": 3,
            "packages": {
                "": {"name": "frontend", "version": "0.0.0"},
                "node_modules/@playwright/test": {"version": "1.48.0"},
                "node_modules/playwright": {"version": "1.48.0"},
                "node_modules/playwright-core": {"version": "1.48.0"},
            },
        },
    )
    if lock is not None:
        (fe / "package-lock.json").write_text(json.dumps(lock) if isinstance(lock, dict) else lock)
    return fe


@pytest.fixture
def disposable_runner(tmp_path: Path):
    """Real launcher/OS reservation; replace only Docker, HTTP and realm mutation."""
    create_synthetic_frontend(tmp_path)

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
    create_synthetic_frontend(tmp_path)
    scripts = tmp_path / "scripts"
    scripts.mkdir(exist_ok=True)
    shutil.copy(ROOT / "scripts/prepare-figma-e2e.ps1", scripts)
    fixtures = tmp_path / "test/fixtures/keycloak"
    fixtures.mkdir(parents=True, exist_ok=True)
    shutil.copy(ROOT / "test/fixtures/keycloak/figma-realm.json", fixtures)
    (scripts / "configure-keycloak-auth-flow.ps1").write_text(
        "param($Mode,$BaseUrl,$Project,$AdminUsername,$AdminPassword)\n"
    )

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
        cwd=tmp_path,
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


def test_compose_entry_points_and_production_excludes_test_services() -> None:
    assert {p.name for p in ROOT.glob("docker-compose*.yml")} == {
        "docker-compose.yml",
        "docker-compose.dev.yml",
        "docker-compose.s2.yml",
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


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell guard runner unavailable")
def test_check_frontend_only_valid(tmp_path: Path) -> None:
    create_synthetic_frontend(tmp_path)
    scripts = tmp_path / "scripts"
    scripts.mkdir(exist_ok=True)
    shutil.copy(ROOT / "scripts/prepare-figma-e2e.ps1", scripts)
    proc = subprocess.run(
        [
            POWERSHELL,
            "-NoProfile",
            "-File",
            str(scripts / "prepare-figma-e2e.ps1"),
            "-CheckFrontendOnly",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert "FIGMA_FRONTEND_OK" in proc.stdout


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell guard runner unavailable")
@pytest.mark.parametrize(
    ("override", "expected_code"),
    [
        ({"lock_json": None}, "FIGMA_FRONTEND_UNAVAILABLE"),
        ({"lock_json": "{invalid json}"}, "FIGMA_FRONTEND_METADATA_INVALID"),
        (
            {
                "pw_test_pkg": {
                    "name": "@playwright/test",
                    "version": "1.47.0",
                    "bin": {"playwright": "cli.js"},
                    "exports": {"./cli": "./cli.js", "./package.json": "./package.json"},
                }
            },
            "FIGMA_FRONTEND_LOCK_MISMATCH",
        ),
        (
            {
                "lock_json": {
                    "name": "frontend",
                    "version": "0.0.0",
                    "lockfileVersion": 3,
                    "packages": {
                        "": {"name": "frontend", "version": "0.0.0"},
                        "node_modules/@playwright/test": {
                            "version": "1.48.0",
                            "dependencies": {"some-subdep": "^1.0.0"},
                        },
                        "node_modules/some-subdep": {"version": "1.0.0"},
                        "node_modules/playwright": {"version": "1.48.0"},
                        "node_modules/playwright-core": {"version": "1.48.0"},
                    },
                }
            },
            "FIGMA_FRONTEND_LOCK_MISMATCH",
        ),
    ],
)
def test_check_frontend_only_failure_matrix(
    tmp_path: Path, override: dict, expected_code: str
) -> None:
    fe = create_synthetic_frontend(tmp_path, **override)
    if "some-subdep" in str(override):
        sub = fe / "node_modules/some-subdep"
        sub.mkdir(parents=True, exist_ok=True)
        (sub / "package.json").write_text(json.dumps({"name": "some-subdep", "version": "2.0.0"}))
    scripts = tmp_path / "scripts"
    scripts.mkdir(exist_ok=True)
    shutil.copy(ROOT / "scripts/prepare-figma-e2e.ps1", scripts)
    proc = subprocess.run(
        [
            POWERSHELL,
            "-NoProfile",
            "-File",
            str(scripts / "prepare-figma-e2e.ps1"),
            "-CheckFrontendOnly",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert proc.returncode != 0
    assert expected_code in proc.stderr


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell guard runner unavailable")
def test_check_frontend_only_cli_outside_package(tmp_path: Path) -> None:
    fe = create_synthetic_frontend(tmp_path)
    outside = tmp_path / "frontend/node_modules/outside-cli.js"
    outside.write_text("console.log(1);")
    (fe / "node_modules/@playwright/test/cli.js").unlink()
    pw_test_pkg = {
        "name": "@playwright/test",
        "version": "1.48.0",
        "bin": {"playwright": "../../outside-cli.js"},
    }
    (fe / "node_modules/@playwright/test/package.json").write_text(json.dumps(pw_test_pkg))
    scripts = tmp_path / "scripts"
    scripts.mkdir(exist_ok=True)
    shutil.copy(ROOT / "scripts/prepare-figma-e2e.ps1", scripts)
    proc = subprocess.run(
        [
            POWERSHELL,
            "-NoProfile",
            "-File",
            str(scripts / "prepare-figma-e2e.ps1"),
            "-CheckFrontendOnly",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert proc.returncode != 0
    assert "FIGMA_FRONTEND_OWNERSHIP_REJECTED" in proc.stderr


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell guard runner unavailable")
def test_check_frontend_only_path_with_spaces(tmp_path: Path) -> None:
    spaced = tmp_path / "path with spaces"
    spaced.mkdir()
    create_synthetic_frontend(spaced)
    scripts = spaced / "scripts"
    scripts.mkdir(exist_ok=True)
    shutil.copy(ROOT / "scripts/prepare-figma-e2e.ps1", scripts)
    proc = subprocess.run(
        [
            POWERSHELL,
            "-NoProfile",
            "-File",
            str(scripts / "prepare-figma-e2e.ps1"),
            "-CheckFrontendOnly",
        ],
        cwd=spaced,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert "FIGMA_FRONTEND_OK" in proc.stdout


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell guard runner unavailable")
def test_check_frontend_only_rejects_external_junction(tmp_path: Path) -> None:
    sibling = tmp_path / "frontend-sibling"
    sibling.mkdir()
    fe = create_synthetic_frontend(tmp_path)
    shutil.rmtree(fe / "node_modules")
    nm = fe / "node_modules"
    try:
        nm.symlink_to(sibling, target_is_directory=True)
    except (OSError, NotImplementedError):
        subprocess.run(
            [
                POWERSHELL,
                "-NoProfile",
                "-Command",
                f'New-Item -ItemType Junction -Path "{nm}" -Target "{sibling}"',
            ],
            capture_output=True,
        )
    if not nm.is_dir():
        pytest.skip("Junction creation unsupported")
    scripts = tmp_path / "scripts"
    scripts.mkdir(exist_ok=True)
    shutil.copy(ROOT / "scripts/prepare-figma-e2e.ps1", scripts)
    proc = subprocess.run(
        [
            POWERSHELL,
            "-NoProfile",
            "-File",
            str(scripts / "prepare-figma-e2e.ps1"),
            "-CheckFrontendOnly",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert proc.returncode != 0
    assert "FIGMA_FRONTEND_OWNERSHIP_REJECTED" in proc.stderr


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell guard runner unavailable")
def test_check_frontend_only_does_not_invoke_docker(tmp_path: Path) -> None:
    create_synthetic_frontend(tmp_path)
    scripts = tmp_path / "scripts"
    scripts.mkdir(exist_ok=True)
    shutil.copy(ROOT / "scripts/prepare-figma-e2e.ps1", scripts)
    harness = tmp_path / "test-docker.ps1"
    harness.write_text(
        r"""
$ErrorActionPreference = 'Stop'
function docker { throw 'DOCKER_INVOKED' }
& ./scripts/prepare-figma-e2e.ps1 -CheckFrontendOnly
"""
    )
    proc = subprocess.run(
        [POWERSHELL, "-NoProfile", "-File", str(harness)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert "FIGMA_FRONTEND_OK" in proc.stdout
    assert "DOCKER_INVOKED" not in (proc.stdout + proc.stderr)


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell guard runner unavailable")
def test_check_configuration_only_does_not_require_frontend_dependencies(tmp_path: Path) -> None:
    scripts = tmp_path / "scripts"
    scripts.mkdir(exist_ok=True)
    shutil.copy(ROOT / "scripts/prepare-figma-e2e.ps1", scripts)
    fixtures = tmp_path / "test/fixtures/keycloak"
    fixtures.mkdir(parents=True)
    shutil.copy(ROOT / "test/fixtures/keycloak/figma-realm.json", fixtures)
    project = "knora-figma-e2e"
    graph = compose_graph("figma")
    graph["name"] = project
    (tmp_path / "graph.json").write_text(json.dumps(graph))
    harness = tmp_path / "test-config.ps1"
    harness.write_text(
        r"""
$ErrorActionPreference = 'Stop'
function docker {
    $global:LASTEXITCODE = 0
    if ($args -contains 'config') {
        Get-Content -Raw $env:TEST_GRAPH
    }
}
& ./scripts/prepare-figma-e2e.ps1 -CheckConfigurationOnly
"""
    )
    clean_env = {
        k: v
        for k, v in os.environ.items()
        if not re.match(
            r"^(COMPOSE_|FIGMA_E2E_|M5_E2E_|KEYCLOAK_|KNORA_|DOCKER_|SESSION_SECRET$)", k
        )
    }
    clean_env["TEST_GRAPH"] = str(tmp_path / "graph.json")
    proc = subprocess.run(
        [POWERSHELL, "-NoProfile", "-File", str(harness)],
        cwd=tmp_path,
        env=clean_env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert "FIGMA_CONFIG_OK" in proc.stdout


def test_backend_services_use_root_context_and_dockerfile_contract() -> None:
    prod = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    dev = yaml.safe_load((ROOT / "docker-compose.dev.yml").read_text(encoding="utf-8"))
    s2 = yaml.safe_load((ROOT / "docker-compose.s2.yml").read_text(encoding="utf-8"))

    for doc, svc, name in [
        (prod, "api", "prod-api"),
        (dev, "api", "dev-api"),
        (dev, "figma-api", "dev-figma-api"),
        (s2, "application", "s2-application"),
    ]:
        build = doc["services"][svc]["build"]
        assert build["context"] == ".", f"{name} must use root context, got {build.get('context')}"
        assert build["dockerfile"] == "backend/Dockerfile", f"{name} must use backend/Dockerfile"

    dockerfile_text = (ROOT / "backend/Dockerfile").read_text(encoding="utf-8")
    assert "WORKDIR /app" in dockerfile_text
    assert "COPY backend/pyproject.toml backend/alembic.ini ./" in dockerfile_text
    assert "COPY backend/migrations ./migrations" in dockerfile_text
    assert "COPY backend/src ./src" in dockerfile_text
    assert (
        'CMD ["uvicorn", "knora.main:app", "--host", "0.0.0.0", "--port", "8000"]'
        in dockerfile_text
    )

    with open(ROOT / "backend/pyproject.toml", "rb") as f:
        pyproject = tomllib.load(f)
    force_include = (
        pyproject.get("tool", {})
        .get("hatch", {})
        .get("build", {})
        .get("targets", {})
        .get("wheel", {})
        .get("force-include", {})
    )
    assert len(force_include) == 16
    for src in force_include:
        rel = src.replace("../", "").replace("\\", "/")
        assert rel in dockerfile_text, (
            f"Force include source {rel} must be staged in backend/Dockerfile"
        )


def test_dockerignore_exact_allowlist_matches_tracked_and_resources() -> None:
    src_files = subprocess.check_output(
        ["git", "ls-files", "-z", "--", "backend/src"], cwd=ROOT, text=True
    ).split("\0")
    src_files = sorted([f.replace("\\", "/") for f in src_files if f])
    assert len(src_files) == 177
    for f in src_files:
        assert f.endswith(".py"), f"Src file must be .py: {f}"

    mig_files = subprocess.check_output(
        ["git", "ls-files", "-z", "--", "backend/migrations"], cwd=ROOT, text=True
    ).split("\0")
    mig_files = sorted([f.replace("\\", "/") for f in mig_files if f])
    assert len(mig_files) == 53
    for f in mig_files:
        assert f.endswith(".py") or f.endswith("script.py.mako"), (
            f"Migration file must be .py or script.py.mako: {f}"
        )

    with open(ROOT / "backend/pyproject.toml", "rb") as f:
        pyproject = tomllib.load(f)
    force_include = (
        pyproject.get("tool", {})
        .get("hatch", {})
        .get("build", {})
        .get("targets", {})
        .get("wheel", {})
        .get("force-include", {})
    )
    res_files = sorted([src.replace("../", "").replace("\\", "/") for src in force_include])
    assert len(res_files) == 16

    expected_allowlist = set(
        [
            "backend/Dockerfile",
            "backend/Dockerfile.dockerignore",
            "backend/pyproject.toml",
            "backend/alembic.ini",
        ]
        + mig_files
        + src_files
        + res_files
    )

    dockerignore_lines = (
        (ROOT / "backend/Dockerfile.dockerignore").read_text(encoding="utf-8").splitlines()
    )
    rules = [
        line.strip()
        for line in dockerignore_lines
        if line.strip() and not line.strip().startswith("#")
    ]
    assert rules[0] == "**", "First rule must be **"

    negations = set()
    for r in rules:
        if r.startswith("!"):
            entry = r[1:].replace("\\", "/")
            assert not entry.endswith("/"), f"Directory negation is forbidden: {entry}"
            assert "*" not in entry, f"Glob negation is forbidden in exact allowlist: {entry}"
            negations.add(entry)

    missing = expected_allowlist - negations
    extra = negations - expected_allowlist
    assert negations == expected_allowlist, f"Negations mismatch: missing={missing}, extra={extra}"


def test_docker_build_probe_enforces_exact_context_exclusion(tmp_path: Path) -> None:
    if shutil.which("docker") is None:
        pytest.skip("Docker CLI not available")
    check = subprocess.run(["docker", "version"], capture_output=True, text=True)
    if check.returncode != 0:
        pytest.skip("Docker daemon unavailable")

    ctx = tmp_path / "probe_ctx"
    out = tmp_path / "probe_out"
    ctx.mkdir()
    out.mkdir()

    dockerignore_content = (ROOT / "backend/Dockerfile.dockerignore").read_text(encoding="utf-8")
    (ctx / "backend").mkdir(parents=True)
    (ctx / "backend/Dockerfile").write_text("FROM scratch\nCOPY . /context/\n")
    (ctx / "backend/Dockerfile.dockerignore").write_text(dockerignore_content, encoding="utf-8")
    (ctx / ".dockerignore").write_text("!**\n")

    allowed_samples = [
        ctx / "backend/pyproject.toml",
        ctx / "backend/alembic.ini",
        ctx / "backend/src/knora/main.py",
        ctx / "backend/migrations/env.py",
        ctx / "docs/design/m3-improvement-claim-rule-v1.policy.json",
        ctx / "evals/datasets/milestone_3.jsonl",
    ]
    for p in allowed_samples:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"dummy payload for {p.name}\n")

    sentinels = [
        ctx / "backend/src/client-private-key.pem",
        ctx / "backend/src/private_credentials.py",
        ctx / "backend/migrations/credentials.json",
        ctx / ".env",
        ctx / "docs/private-note.txt",
        ctx / "evals/private-note.txt",
        ctx / "node_modules/private.txt",
        ctx / ".git/config",
        ctx / "backend/unexpected_new_file.txt",
    ]
    for s in sentinels:
        s.parent.mkdir(parents=True, exist_ok=True)
        s.write_text("SENTINEL_SECRET\n")

    cmd = [
        "docker",
        "buildx",
        "build",
        "--file",
        str(ctx / "backend/Dockerfile"),
        "--output",
        f"type=local,dest={out}",
        str(ctx),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    assert res.returncode == 0, f"Docker probe build failed: {res.stderr}\n{res.stdout}"

    exported = {
        p.relative_to(out / "context").as_posix()
        for p in (out / "context").rglob("*")
        if p.is_file()
    }

    for p in allowed_samples:
        rel = p.relative_to(ctx).as_posix()
        assert rel in exported, f"Allowed file {rel} was not exported to context"

    for s in sentinels:
        rel = s.relative_to(ctx).as_posix()
        assert rel not in exported, f"Sentinel file {rel} was leaked into build context!"
