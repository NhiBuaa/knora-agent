"""The Figma harness cannot select or mutate a daily development project."""

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
POWERSHELL = shutil.which("pwsh") or shutil.which("powershell")


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


def test_ordinary_preparation_has_no_resource_reset() -> None:
    script = (ROOT / "scripts/prepare-figma-e2e.ps1").read_text()
    for destructive in ("volume rm", "compose down", "compose rm", "prepare-local-e2e"):
        assert destructive not in script


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
    assert set(graph["services"]) == {"postgres", "minio", "minio-init", "api", "keycloak-dev"}
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
