"""Execute isolated OTP configuration at its HTTP, Docker and filesystem boundaries."""

import base64
import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
POWERSHELL = shutil.which("pwsh") or shutil.which("powershell")
pytestmark = pytest.mark.skipif(POWERSHELL is None, reason="PowerShell unavailable")
ALIAS = "knora-email-otp-reset"
OWNER = "Knora isolated email OTP recovery v1"


def environment() -> dict[str, str]:
    return {
        key: value
        for key, value in os.environ.items()
        if not re.match(
            r"^(COMPOSE_|FIGMA_E2E_|M5_E2E_|KEYCLOAK_|KNORA_|DOCKER_|SESSION_SECRET$)", key
        )
    }


def state() -> dict:
    return {
        "realm": {
            "id": "actual-isolated-realm-id",
            "realm": "knora-dev",
            "resetCredentialsFlow": "reset credentials",
            "emailTheme": "keycloak",
            "resetPasswordAllowed": False,
            "verifyEmail": True,
            "smtpServer": {"host": "mail"},
        },
        "providers": [{"id": "knora-reset-email-otp"}, {"id": "reset-password"}],
        "required": [
            {"alias": "UPDATE_PASSWORD", "providerId": "UPDATE_PASSWORD", "enabled": True}
        ],
        "flows": [],
        "executions": [],
        "mutations": [],
        "dockerMutations": [],
        "owner": "knora-figma-e2e",
        "service": "keycloak",
        "workingDir": str(ROOT),
        "hostIp": "127.0.0.1",
        "ignored": True,
        "restricted": True,
    }


def prepared(data: dict) -> None:
    data["flows"] = [
        {
            "id": "owned-flow",
            "alias": ALIAS,
            "description": OWNER,
            "providerId": "basic-flow",
            "topLevel": True,
            "builtIn": False,
        }
    ]
    data["executions"] = [
        {
            "id": "otp",
            "providerId": "knora-reset-email-otp",
            "requirement": "REQUIRED",
            "priority": 10,
            "index": 0,
            "level": 0,
            "authenticationFlow": None,
        },
        {
            "id": "password",
            "providerId": "reset-password",
            "requirement": "REQUIRED",
            "priority": 20,
            "index": 1,
            "level": 0,
            "authenticationFlow": None,
        },
    ]


WRAPPER = r"""
param($StatePath, $ScriptPath, $RootPath, $Actions, $SnapshotPath, $VaultPath)
$ErrorActionPreference = 'Stop'
$global:data = Get-Content -Raw -LiteralPath $StatePath | ConvertFrom-Json
$global:tokenCount = 0
function docker {
    $global:LASTEXITCODE = 0
    if ($args[0] -eq 'ps') {
        if ($global:data.extraService) { return @('owned-keycloak', 'retained-proof') }
        return 'owned-keycloak'
    }
    if ($args[0] -eq 'inspect') {
        if ($args[1] -eq 'retained-proof') {
            return ConvertTo-Json -Depth 100 -InputObject @(@{
                Name="/knora-figma-e2e-$($global:data.extraService)-1"
                State=@{Running=$global:data.extraRunning}
                Config=@{Labels=@{
                    'com.docker.compose.project'='knora-figma-e2e'
                    'com.docker.compose.service'=$global:data.extraService
                    'com.docker.compose.project.working_dir'=$global:data.workingDir
                }}
                NetworkSettings=@{Ports=@{}}
            })
        }
        return ConvertTo-Json -Depth 100 -InputObject @(@{
            Name='/knora-figma-e2e-keycloak-1'; State=@{Running=$true}
            Config=@{Labels=@{
                'com.docker.compose.project'=$global:data.owner
                'com.docker.compose.service'=$global:data.service
                'com.docker.compose.project.working_dir'=$global:data.workingDir
            }}
            NetworkSettings=@{Ports=@{'8080/tcp'=@(@{HostIp=$global:data.hostIp;HostPort='8380'})}}
        })
    }
    if ($args[0] -eq 'compose' -and 'config' -in $args) {
        if (($args -join ' ') -match 'figma-otp-runtime') {
            return $global:data.runtimeConfig | ConvertTo-Json -Depth 100
        }
        return $global:data.baseConfig | ConvertTo-Json -Depth 100
    }
    $global:data.dockerMutations += ,@($args)
    if ($global:data.failStart) { $global:LASTEXITCODE = 1 }
}
function git {
    if ('check-ignore' -in $args) {
        $global:LASTEXITCODE = if ($global:data.ignored) { 0 } else { 1 }
        return
    }
    if ('ls-files' -in $args) { $global:LASTEXITCODE = 0; return }
    if ('rev-parse' -in $args) {
        if ($global:data.gitFailure) { $global:LASTEXITCODE = 128; return }
        $global:LASTEXITCODE = 0; return $RootPath
    }
    $global:LASTEXITCODE = 128
}
function Get-Acl {
    param($LiteralPath)
    $acl = [pscustomobject]@{AreAccessRulesProtected=$global:data.restricted}
    $acl | Add-Member ScriptMethod GetAccessRules {
        param($Explicit, $Inherited, $TargetType)
        $sid = if ($global:data.restricted) {
            [Security.Principal.WindowsIdentity]::GetCurrent().User
        } else { [Security.Principal.SecurityIdentifier]::new('S-1-1-0') }
        return @([pscustomobject]@{IdentityReference=$sid;AccessControlType='Allow';
            FileSystemRights=[Security.AccessControl.FileSystemRights]::FullControl})
    }
    return $acl
}
function Invoke-RestMethod {
    param($Method='Get', $Uri, $Headers, $ContentType, $Body, $TimeoutSec)
    $realmUri = 'http://127.0.0.1:8380/admin/realms/knora-dev'
    if ($Uri -eq 'http://127.0.0.1:8380/realms/master/protocol/openid-connect/token' -and
        $Method -eq 'Post') {
        $global:tokenCount++
        return @{access_token="NEVER_PRINT_TOKEN_$global:tokenCount"}
    }
    if ($Uri -eq 'http://127.0.0.1:8380/realms/knora-dev/.well-known/openid-configuration') {
        return @{issuer='http://127.0.0.1:8380/realms/knora-dev'}
    }
    if ($Headers.Authorization -ne "Bearer NEVER_PRINT_TOKEN_$global:tokenCount") {
        throw 'Incorrect authorization boundary'
    }
    if ($global:data.requireFreshToken -and $global:data.dockerMutations.Count -gt 0 -and
        $global:tokenCount -lt 2) { throw 'Preflight token expired during build' }
    if ($Method -eq 'Get') {
        switch ($Uri) {
            $realmUri { return $global:data.realm }
            "$realmUri/authentication/authenticator-providers" { return $global:data.providers }
            "$realmUri/authentication/required-actions" { return $global:data.required }
            "$realmUri/authentication/flows" { return $global:data.flows }
            "$realmUri/authentication/flows/knora-email-otp-reset/executions" {
                return $global:data.executions
            }
            default { throw 'Unexpected GET boundary' }
        }
    }
    $payload = $Body | ConvertFrom-Json
    $global:data.mutations += ,@{method=$Method;uri=$Uri;payload=$payload}
    if ($global:data.failMutation -and $global:data.mutations.Count -eq $global:data.failMutation) {
        throw 'NEVER_PRINT_ERROR_BODY_PASSWORD'
    }
    if ($Method -eq 'Post' -and $Uri -eq "$realmUri/authentication/flows") {
        $payload | Add-Member NoteProperty id 'owned-flow'
        $global:data.flows += $payload; return
    }
    $executionUri = "$realmUri/authentication/flows/knora-email-otp-reset/executions"
    if ($Method -eq 'Post' -and $Uri -eq "$executionUri/execution") {
        $global:data.executions += [pscustomobject]@{
            id="exec-$($global:data.executions.Count)";providerId=$payload.provider
            priority=$payload.priority;index=$global:data.executions.Count;level=0
            authenticationFlow=$null;requirement='DISABLED'
        }
        return
    }
    if ($Method -eq 'Put' -and $Uri -eq $executionUri) {
        $execution = @($global:data.executions | Where-Object id -eq $payload.id)
        if ($execution.Count -ne 1) { throw 'Wrong execution update' }
        $execution[0].requirement=$payload.requirement; $execution[0].priority=$payload.priority
        return
    }
    if ($Method -eq 'Put' -and $Uri -eq $realmUri) {
        foreach ($property in $payload.PSObject.Properties) {
            $global:data.realm.($property.Name)=$property.Value
        }
        return
    }
    throw 'Unexpected mutation boundary'
}
try {
    foreach ($action in ($Actions -split ',')) {
        $parameters = @{AdminUsername='NEVER_PRINT_USERNAME';AdminPassword='NEVER_PRINT_PASSWORD'}
        switch ($action) {
            'default' { & $ScriptPath @parameters }
            'BindOptIn' {
                & $ScriptPath -Mode Bind -EnableIsolatedOtp @parameters -SnapshotPath $SnapshotPath
            }
            'RestoreWrongId' {
                $global:data.realm.id='recreated-realm'
                & $ScriptPath -Mode Restore @parameters -SnapshotPath $SnapshotPath
            }
            'RestoreWrongTarget' {
                $saved = Get-Content -Raw -LiteralPath $SnapshotPath | ConvertFrom-Json
                $saved.($global:data.snapshotField) = 'wrong-target'
                $saved | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $SnapshotPath
                & $ScriptPath -Mode Restore @parameters -SnapshotPath $SnapshotPath
            }
            'RuntimeCheck' {
                & $ScriptPath -VaultPath $VaultPath -CheckConfigurationOnly @parameters
            }
            'RuntimePrepare' { & $ScriptPath -VaultPath $VaultPath @parameters }
            default {
                if ($global:data.targetParameters) {
                    $parameters += @{
                        BaseUrl=$global:data.targetParameters.baseUrl
                        Realm=$global:data.targetParameters.realm
                        Project=$global:data.targetParameters.project
                    }
                }
                & $ScriptPath -Mode $action @parameters -SnapshotPath $SnapshotPath
            }
        }
    }
} finally {
    $global:data | ConvertTo-Json -Depth 100 | Set-Content -LiteralPath "$StatePath.result"
}
"""


def run(
    tmp_path: Path, data: dict, actions: str, *, runtime: bool = False, vault: Path | None = None
) -> tuple[subprocess.CompletedProcess, dict]:
    fixture = tmp_path / "state.json"
    fixture.write_text(json.dumps(data))
    wrapper = tmp_path / "run.ps1"
    wrapper.write_text(WRAPPER)
    script = "prepare-figma-otp-runtime.ps1" if runtime else "configure-keycloak-email-otp.ps1"
    result = subprocess.run(
        [
            POWERSHELL,
            "-NoProfile",
            "-File",
            str(wrapper),
            str(fixture),
            str(ROOT / "scripts" / script),
            str(ROOT),
            actions,
            str(tmp_path / "snapshot.json"),
            str(vault or tmp_path / "missing-vault"),
        ],
        cwd=ROOT,
        env=environment(),
        capture_output=True,
        text=True,
        check=False,
    )
    after = json.loads(Path(str(fixture) + ".result").read_text())
    for secret in (
        "NEVER_PRINT_TOKEN",
        "NEVER_PRINT_PASSWORD",
        "NEVER_PRINT_USERNAME",
        "NEVER_PRINT_ERROR_BODY_PASSWORD",
    ):
        assert secret not in result.stdout + result.stderr
    return result, after


@pytest.mark.parametrize("actions", ["default", "Inspect", "Diff"])
def test_read_only_modes_never_create_flow_or_change_binding(tmp_path: Path, actions: str) -> None:
    result, after = run(tmp_path, state(), actions)
    assert result.returncode == 0, result.stderr
    assert after["mutations"] == []
    assert after["realm"]["resetCredentialsFlow"] == "reset credentials"
    assert not (tmp_path / "snapshot.json").exists()


@pytest.mark.parametrize(
    "field,value,code",
    [
        ("owner", "knora-dev", "OTP_RESOURCE_OWNERSHIP_REJECTED"),
        ("service", "keycloak-proof", "OTP_RESOURCE_OWNERSHIP_REJECTED"),
        ("workingDir", "C:/foreign-worktree", "OTP_RESOURCE_OWNERSHIP_REJECTED"),
        ("hostIp", "0.0.0.0", "OTP_PORT_OWNERSHIP_REJECTED"),
        ("providers", [{"id": "reset-password"}], "OTP_AUTHENTICATOR_REQUIRED"),
        ("required", [], "OTP_NATIVE_UPDATE_PASSWORD_REQUIRED"),
        (
            "required",
            [{"alias": "UPDATE_PASSWORD", "providerId": "UPDATE_PASSWORD", "enabled": False}],
            "OTP_NATIVE_UPDATE_PASSWORD_REQUIRED",
        ),
    ],
)
def test_configuration_guards_fail_before_mutation(
    tmp_path: Path, field: str, value, code: str
) -> None:
    data = state()
    data[field] = value
    result, after = run(tmp_path, data, "Prepare")
    assert result.returncode != 0
    assert code in result.stderr
    assert after["mutations"] == []


@pytest.mark.parametrize(
    "field,value",
    [("baseUrl", "http://localhost:8380"), ("realm", "knora-figma-e2e"), ("project", "knora-dev")],
)
def test_configuration_rejects_inexact_targets(tmp_path: Path, field: str, value: str) -> None:
    data = state()
    data["targetParameters"] = {
        "baseUrl": "http://127.0.0.1:8380",
        "realm": "knora-dev",
        "project": "knora-figma-e2e",
        field: value,
    }
    result, after = run(tmp_path, data, "Prepare")
    assert result.returncode != 0
    assert "OTP_EXACT_TARGET_REQUIRED" in result.stderr
    assert after["mutations"] == []


@pytest.mark.parametrize("conflict", ["foreign", "builtIn", "order", "requirement", "subflow"])
def test_conflicting_existing_alias_fails_closed(tmp_path: Path, conflict: str) -> None:
    data = state()
    prepared(data)
    if conflict == "foreign":
        data["flows"][0]["description"] = "Foreign administrator flow"
    elif conflict == "builtIn":
        data["flows"][0]["builtIn"] = True
    elif conflict == "order":
        data["executions"].reverse()
    elif conflict == "requirement":
        data["executions"][1]["requirement"] = "DISABLED"
    else:
        data["executions"][0]["authenticationFlow"] = True
    result, after = run(tmp_path, data, "Prepare")
    assert result.returncode != 0
    assert "OTP_FLOW_CONFLICT" in result.stderr
    assert after["mutations"] == []


def test_prepare_creates_ordered_required_executions_and_repeat_is_noop(tmp_path: Path) -> None:
    data = state()
    result, after = run(tmp_path, data, "Prepare,Prepare")
    assert result.returncode == 0, result.stderr
    assert after["realm"] == data["realm"]
    assert len(after["mutations"]) == 5
    assert after["flows"][0]["alias"] == ALIAS
    assert after["flows"][0]["description"] == OWNER
    assert [(e["providerId"], e["requirement"], e["priority"]) for e in after["executions"]] == [
        ("knora-reset-email-otp", "REQUIRED", 10),
        ("reset-password", "REQUIRED", 20),
    ]
    assert all(
        ALIAS in m["uri"] or m["uri"].endswith("/authentication/flows") for m in after["mutations"]
    )


def test_bind_requires_explicit_opt_in(tmp_path: Path) -> None:
    data = state()
    prepared(data)
    result, after = run(tmp_path, data, "Bind")
    assert result.returncode != 0
    assert "OTP_BIND_OPT_IN_REQUIRED" in result.stderr
    assert after["mutations"] == []


def test_bind_saves_exact_prior_fields_and_restore_retains_unbound_flow(tmp_path: Path) -> None:
    data = state()
    prepared(data)
    result, after = run(tmp_path, data, "BindOptIn,BindOptIn,Restore")
    assert result.returncode == 0, result.stderr
    saved = json.loads((tmp_path / "snapshot.json").read_text(encoding="utf-8-sig"))
    assert saved["realmId"] == "actual-isolated-realm-id"
    assert saved["settings"] == {
        "resetCredentialsFlow": "reset credentials",
        "emailTheme": "keycloak",
        "resetPasswordAllowed": False,
    }
    assert after["realm"] == data["realm"]
    assert after["flows"] == data["flows"]
    assert len(after["mutations"]) == 2
    assert after["mutations"][0]["payload"] == {
        "resetCredentialsFlow": ALIAS,
        "emailTheme": "knora",
        "resetPasswordAllowed": True,
    }
    assert all(set(m["payload"]) == set(saved["settings"]) for m in after["mutations"])


def test_restore_rejects_recreated_realm(tmp_path: Path) -> None:
    data = state()
    prepared(data)
    result, after = run(tmp_path, data, "BindOptIn,RestoreWrongId")
    assert result.returncode != 0
    assert "OTP_SNAPSHOT_TARGET_REJECTED" in result.stderr
    assert len(after["mutations"]) == 1


@pytest.mark.parametrize("field", ["baseUrl", "realm", "project", "workingDirectory"])
def test_restore_rejects_snapshot_for_different_target(tmp_path: Path, field: str) -> None:
    data = state()
    prepared(data)
    data["snapshotField"] = field
    result, after = run(tmp_path, data, "BindOptIn,RestoreWrongTarget")
    assert result.returncode != 0
    assert "OTP_SNAPSHOT_TARGET_REJECTED" in result.stderr
    assert len(after["mutations"]) == 1


def test_bind_requires_nonempty_actual_realm_id(tmp_path: Path) -> None:
    data = state()
    prepared(data)
    data["realm"]["id"] = ""
    result, after = run(tmp_path, data, "BindOptIn")
    assert result.returncode != 0
    assert "OTP_REALM_REPRESENTATION_REJECTED" in result.stderr
    assert after["mutations"] == []


def test_prepare_partial_failure_retains_custom_flow_without_cleanup(tmp_path: Path) -> None:
    data = state()
    data["failMutation"] = 2
    result, after = run(tmp_path, data, "Prepare")
    assert result.returncode != 0
    assert "OTP_ADMIN_REQUEST_FAILED" in result.stderr
    assert after["flows"][0]["alias"] == ALIAS
    assert len(after["mutations"]) == 2
    assert all(m["method"] == "Post" for m in after["mutations"])
    assert after["realm"] == data["realm"]


def test_partial_bind_failure_preserves_snapshot_and_redacts_error_body(tmp_path: Path) -> None:
    data = state()
    prepared(data)
    data["failMutation"] = 1
    result, after = run(tmp_path, data, "BindOptIn")
    assert result.returncode != 0
    assert "OTP_UPDATE_OR_VERIFICATION_FAILED" in result.stderr
    assert (tmp_path / "snapshot.json").exists()
    assert len(after["mutations"]) == 1


@pytest.fixture(scope="module")
def compose_graphs(tmp_path_factory) -> tuple[dict, dict]:
    vault = tmp_path_factory.mktemp("synthetic-compose-vault")
    env = environment()
    env["KNORA_FIGMA_OTP_VAULT_PATH"] = str(vault)
    args = [
        "docker",
        "compose",
        "--project-name",
        "knora-figma-e2e",
        "--project-directory",
        str(ROOT),
        "-f",
        str(ROOT / "docker-compose.figma-e2e.yml"),
    ]
    base = subprocess.run(
        args + ["config", "--format", "json"], env=env, capture_output=True, text=True, check=False
    )
    native = subprocess.run(
        args
        + ["-f", str(ROOT / "docker-compose.figma-otp-runtime.yml"), "config", "--format", "json"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert base.returncode == 0, base.stderr
    assert native.returncode == 0, native.stderr
    return json.loads(base.stdout), json.loads(native.stdout)


def vault_file(vault: Path, value: bytes | None = None) -> Path:
    vault.mkdir()
    digest = hashlib.sha256(b"actual-isolated-realm-id").hexdigest()
    key = vault / ("knora-dev_knora-email-otp-hmac-" + digest)
    key.write_bytes(
        value if value is not None else base64.b64encode(b"synthetic-test-only-material-32byte")
    )
    return key


def runtime_state(graphs: tuple[dict, dict], vault: Path) -> dict:
    data = state()
    data["baseConfig"], data["runtimeConfig"] = json.loads(json.dumps(graphs))
    mount = next(
        m
        for m in data["runtimeConfig"]["services"]["keycloak"]["volumes"]
        if m["target"] == "/opt/keycloak/vault"
    )
    mount["source"] = str(vault)
    return data


def test_real_compose_graph_preserves_base_and_excludes_proof(compose_graphs) -> None:
    base, native = compose_graphs
    assert set(native["services"]) == set(base["services"])
    assert native["volumes"] == base["volumes"]
    for service in base["services"]:
        if service != "keycloak":
            assert native["services"][service] == base["services"][service]
    keycloak = native["services"]["keycloak"]
    assert keycloak["ports"] == base["services"]["keycloak"]["ports"]
    assert keycloak["environment"] == base["services"]["keycloak"]["environment"]
    assert keycloak["build"]["dockerfile"] == "infra/keycloak/Dockerfile"
    assert keycloak["build"]["context"] == str(ROOT)
    assert "--vault-dir=/opt/keycloak/vault" in keycloak["command"]
    assert "storage-probe" not in json.dumps(native)
    assert "KNORA_STORAGE_PROOF" not in json.dumps(native)
    assert next(m for m in keycloak["volumes"] if m["target"] == "/opt/keycloak/vault")["read_only"]


def test_compose_requires_explicit_vault_directory() -> None:
    result = subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            str(ROOT / "docker-compose.figma-e2e.yml"),
            "-f",
            str(ROOT / "docker-compose.figma-otp-runtime.yml"),
            "config",
            "--quiet",
        ],
        env=environment(),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "KNORA_FIGMA_OTP_VAULT_PATH" in result.stderr


def test_runtime_check_is_read_only_and_validates_existing_key(
    tmp_path: Path, compose_graphs
) -> None:
    vault = tmp_path / "vault"
    key = vault_file(vault)
    before = key.read_bytes()
    data = runtime_state(compose_graphs, vault)
    result, after = run(tmp_path, data, "RuntimeCheck", runtime=True, vault=vault)
    assert result.returncode == 0, result.stderr
    assert "OTP_RUNTIME_CONFIG_OK" in result.stdout
    assert after["mutations"] == after["dockerMutations"] == []
    assert key.read_bytes() == before
    assert before.decode() not in result.stdout + result.stderr


def test_git_failure_inside_repository_cannot_bypass_exclusion(
    tmp_path: Path, compose_graphs
) -> None:
    vault = tmp_path / "vault"
    vault_file(vault)
    (vault / ".git").mkdir()
    data = runtime_state(compose_graphs, vault)
    data["gitFailure"] = True
    result, after = run(tmp_path, data, "RuntimeCheck", runtime=True, vault=vault)
    assert result.returncode != 0
    assert "OTP_VAULT_GIT_BOUNDARY_REJECTED" in result.stderr
    assert after["mutations"] == after["dockerMutations"] == []


@pytest.mark.parametrize(
    "fault,code",
    [
        ("missing", "OTP_VAULT_PATH_REQUIRED"),
        ("key_missing", "OTP_VAULT_ENTRY_REQUIRED"),
        ("invalid", "OTP_VAULT_KEY_INVALID"),
        ("short", "OTP_VAULT_KEY_INVALID"),
        ("tracked", "OTP_VAULT_GIT_BOUNDARY_REJECTED"),
        ("wide_acl", "OTP_VAULT_ACCESS_REJECTED"),
        ("mount", "OTP_VAULT_MOUNT_REJECTED"),
        ("mount_missing", "OTP_VAULT_MOUNT_REJECTED"),
        ("foreign", "OTP_RESOURCE_OWNERSHIP_REJECTED"),
        ("proof", "OTP_RUNTIME_GRAPH_REJECTED"),
        ("base_drift", "OTP_RUNTIME_GRAPH_REJECTED"),
    ],
)
def test_runtime_guards_reject_before_start(
    tmp_path: Path, compose_graphs, fault: str, code: str
) -> None:
    vault = tmp_path / "vault"
    key = vault_file(vault)
    data = runtime_state(compose_graphs, vault)
    if fault == "missing":
        vault = tmp_path / "missing"
    elif fault == "key_missing":
        key.rename(vault / "wrong-name")
    elif fault == "invalid":
        key.write_text("private-invalid-value")
    elif fault == "short":
        key.write_bytes(base64.b64encode(b"short"))
    elif fault == "tracked":
        data["ignored"] = False
    elif fault == "wide_acl":
        data["restricted"] = False
    elif fault == "mount":
        next(
            m
            for m in data["runtimeConfig"]["services"]["keycloak"]["volumes"]
            if m["target"] == "/opt/keycloak/vault"
        )["read_only"] = False
    elif fault == "mount_missing":
        data["runtimeConfig"]["services"]["keycloak"]["volumes"] = [
            mount
            for mount in data["runtimeConfig"]["services"]["keycloak"]["volumes"]
            if mount["target"] != "/opt/keycloak/vault"
        ]
    elif fault == "foreign":
        data["owner"] = "knora-dev"
    elif fault == "proof":
        data["runtimeConfig"]["services"]["keycloak-proof"] = {"image": "probe"}
    else:
        data["runtimeConfig"]["services"]["api"]["environment"]["KNORA_KEYCLOAK_ISSUER"] = "foreign"
    result, after = run(tmp_path, data, "RuntimePrepare", runtime=True, vault=vault)
    assert result.returncode != 0
    assert code in result.stderr
    assert after["mutations"] == after["dockerMutations"] == []
    assert "private-invalid-value" not in result.stdout + result.stderr


def test_runtime_prepare_starts_only_keycloak_and_preserves_binding(
    tmp_path: Path, compose_graphs
) -> None:
    vault = tmp_path / "vault"
    vault_file(vault)
    data = runtime_state(compose_graphs, vault)
    result, after = run(tmp_path, data, "RuntimePrepare", runtime=True, vault=vault)
    assert result.returncode == 0, result.stderr
    assert len(after["dockerMutations"]) == 1
    assert after["dockerMutations"][0][-5:] == ["up", "-d", "--build", "--no-deps", "keycloak"]
    assert after["mutations"] == []
    assert after["realm"] == data["realm"]


@pytest.mark.parametrize(
    "fault,code",
    [("start", "OTP_RUNTIME_START_FAILED"), ("provider", "OTP_AUTHENTICATOR_REQUIRED")],
)
def test_runtime_failure_never_changes_reset_binding(
    tmp_path: Path, compose_graphs, fault: str, code: str
) -> None:
    vault = tmp_path / "vault"
    vault_file(vault)
    data = runtime_state(compose_graphs, vault)
    if fault == "start":
        data["failStart"] = True
    else:
        data["providers"] = [{"id": "reset-password"}]
    result, after = run(tmp_path, data, "RuntimePrepare", runtime=True, vault=vault)
    assert result.returncode != 0
    assert code in result.stderr
    assert len(after["dockerMutations"]) == 1
    assert after["mutations"] == []
    assert after["realm"] == data["realm"]


def test_runtime_reauthenticates_after_build_before_provider_verification(
    tmp_path: Path, compose_graphs
) -> None:
    vault = tmp_path / "vault"
    vault_file(vault)
    data = runtime_state(compose_graphs, vault)
    data["requireFreshToken"] = True
    result, after = run(tmp_path, data, "RuntimePrepare", runtime=True, vault=vault)
    assert result.returncode == 0, result.stderr
    assert after["realm"] == data["realm"]
    assert after["mutations"] == []
    assert len(after["dockerMutations"]) == 1


@pytest.mark.parametrize("service", ["keycloak-proof", "otp-commit-proxy"])
@pytest.mark.parametrize("running", [False, True])
def test_runtime_preserves_stopped_owned_proof_but_rejects_active_proof(
    tmp_path: Path, compose_graphs, service: str, running: bool
) -> None:
    vault = tmp_path / "vault"
    vault_file(vault)
    data = runtime_state(compose_graphs, vault)
    data.update(extraService=service, extraRunning=running)
    result, after = run(tmp_path, data, "RuntimeCheck", runtime=True, vault=vault)
    if running:
        assert result.returncode != 0
        assert "OTP_RESOURCE_OWNERSHIP_REJECTED" in result.stderr
    else:
        assert result.returncode == 0, result.stderr
    assert after["mutations"] == after["dockerMutations"] == []
