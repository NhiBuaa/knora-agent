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
    graph = yaml.safe_load((ROOT / "docker-compose.figma-e2e.yml").read_text())
    assert graph["name"] == "knora-figma-e2e"
    expected = {
        "postgres": ["127.0.0.1:5543:5432"],
        "keycloak": ["127.0.0.1:8380:8080"],
        "api": ["127.0.0.1:8800:8000"],
        "minio": ["127.0.0.1:9900:9000", "127.0.0.1:9901:9001"],
        "mail": ["127.0.0.1:1025:1025", "127.0.0.1:8025:8025"],
    }
    for name, bindings in expected.items():
        assert graph["services"][name]["ports"] == bindings
    assert graph["services"]["keycloak"]["environment"]["KC_DB_URL"].endswith("/keycloak")
    assert all("name" not in volume for volume in graph["volumes"].values())


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
