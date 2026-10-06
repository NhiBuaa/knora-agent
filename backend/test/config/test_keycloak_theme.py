"""Contracts for the Keycloak 26.3.3 presentation assets."""

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
POWERSHELL = shutil.which("pwsh") or shutil.which("powershell")


def test_dev_realm_selects_packaged_theme_without_changing_oidc_redirects() -> None:
    realm = json.loads((ROOT / "test/fixtures/keycloak/dev-realm.json").read_text())
    client = next(item for item in realm["clients"] if item["clientId"] == "knora-web")

    assert realm["loginTheme"] == "knora"
    assert client["redirectUris"] == ["http://127.0.0.1:3000/api/auth/callback"]


def test_dev_compose_mounts_theme_read_only() -> None:
    compose = yaml.safe_load((ROOT / "docker-compose.dev.yml").read_text())
    volumes = compose["services"]["keycloak-dev"]["volumes"]

    assert "./themes/knora:/opt/keycloak/themes/knora:ro" in volumes


def test_theme_inherits_inspected_keycloak_v2_resources() -> None:
    properties = dict(
        line.split("=", 1)
        for line in (ROOT / "themes/knora/login/theme.properties").read_text().splitlines()
        if line and not line.startswith("#")
    )

    assert properties["parent"] == "keycloak.v2"
    assert properties["import"] == "common/keycloak"
    assert properties["styles"] == "css/styles.css css/knora.css"
    assert properties["stylesCommon"] == (
        "vendor/patternfly-v5/patternfly.min.css vendor/patternfly-v5/patternfly-addons.css"
    )


def test_theme_bundles_licensed_fonts_and_app_colors() -> None:
    resources = ROOT / "themes/knora/login/resources"
    css = (resources / "css/knora.css").read_text()

    for color in (
        "#EFFCFA",
        "#FFFFFF",
        "#33A15B",
        "#784131",
        "#1F3B36",
        "#D9E2DE",
        "#0B1412",
        "#12201C",
        "#4DBB73",
        "#C68F79",
        "#D7EFE6",
        "#2A3D36",
    ):
        assert color in css
    assert "localhost" not in css
    assert (resources / "fonts/inter-latin-vietnamese.woff2").is_file()
    assert (resources / "fonts/roboto-slab-latin-vietnamese.woff2").is_file()
    assert (resources / "fonts/OFL-Inter.txt").is_file()
    assert (resources / "fonts/LICENSE-RobotoSlab.txt").is_file()


def test_four_native_forms_retain_keycloak_actions_and_escape_messages() -> None:
    theme = ROOT / "themes/knora/login"
    login = (theme / "login.ftl").read_text()
    register = (theme / "register.ftl").read_text()
    update = (theme / "login-update-password.ftl").read_text()
    info = (theme / "info.ftl").read_text()
    assert "${url.loginAction}" in login and 'name="credentialId"' in login
    assert "${url.registrationAction}" in register and "password-confirm" in register
    assert "${url.loginAction}" in update and "password-new" in update
    assert "cancel-aia" in update and "logoutOtherSessions" in update
    assert "kcSanitize(message.summary)?no_esc" in info
    for template in (login, register, update):
        assert 'novalidate="novalidate"' in template
        assert "registrationLayout" in template
    assert 'name="firstName"' not in register and 'name="lastName"' not in register


def test_identity_assets_are_original_bytes_with_intrinsic_dimensions() -> None:
    folder = ROOT / "themes/knora/login/resources/images"
    manifest = json.loads((folder / "figma-assets.json").read_text())
    assert {item["file"] for item in manifest["assets"]} == {"ad252.svg", "bf7a4.svg", "42cef.svg"}
    for item in manifest["assets"]:
        assert (
            hashlib.sha256((folder / item["file"]).read_bytes()).hexdigest().upper()
            == item["sha256"]
        )
        assert item["rootWidth"] == "18" and item["rootHeight"] == "18"
        assert item["sourceNodeIds"]


def test_registration_profile_keeps_native_validations_and_optional_names() -> None:
    realm = json.loads((ROOT / "test/fixtures/keycloak/dev-realm.json").read_text())
    provider = realm["components"]["org.keycloak.userprofile.UserProfileProvider"][0]
    profile = json.loads(provider["config"]["kc.user.profile.config"][0])
    attributes = {item["name"]: item for item in profile["attributes"]}
    for name in ("firstName", "lastName"):
        assert "required" not in attributes[name]
        assert attributes[name]["permissions"]["edit"] == ["admin", "user"]
        assert "person-name-prohibited-characters" in attributes[name]["validations"]
    assert attributes["email"]["required"] == {"roles": ["user"]}
    assert realm["verifyEmail"] is False


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell runner unavailable")
def test_profile_diff_preserves_custom_metadata_and_admin_name_requirement(tmp_path: Path) -> None:
    profile = {
        "attributes": [
            {
                "name": "firstName",
                "required": {"roles": ["user", "admin"]},
                "permissions": {"edit": ["user", "admin"]},
                "validations": {"length": {"max": 255}},
            },
            {
                "name": "lastName",
                "required": {"roles": ["user"]},
                "annotations": {"custom": "retained"},
            },
            {"name": "custom", "validations": {"length": {"max": 42}}, "multivalued": True},
        ],
        "groups": [{"name": "retained"}],
        "unmanagedAttributePolicy": "ADMIN_VIEW",
    }
    result = _profile_diff(tmp_path, profile)
    assert result.returncode == 0, result.stderr
    diff = json.loads(result.stdout)
    assert diff["profileBefore"] == profile
    after = diff["profileAfter"]
    assert after["attributes"][0]["required"] == {"roles": ["admin"]}
    assert "required" not in after["attributes"][1]
    assert after["attributes"][2] == profile["attributes"][2]
    assert after["groups"] == profile["groups"]
    assert after["unmanagedAttributePolicy"] == "ADMIN_VIEW"
    assert diff["verifyEmailPreserved"] is True


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell runner unavailable")
@pytest.mark.parametrize("required", [{"roles": ["user"]}, {"scopes": ["profile"]}])
def test_profile_diff_reports_required_custom_attributes(tmp_path: Path, required: dict) -> None:
    result = _profile_diff(tmp_path, {"attributes": [{"name": "custom", "required": required}]})
    assert result.returncode != 0
    assert "custom" in result.stdout
    assert "KEYCLOAK_REQUIRED_CUSTOM_ATTRIBUTE_CONFLICT" in result.stderr


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell runner unavailable")
@pytest.mark.parametrize("required", [{"roles": ["user"]}, {"scopes": ["profile"]}])
@pytest.mark.parametrize("mode", ["Diff", "Apply"])
def test_profile_rejects_unsubmittable_required_locale_before_mutation(
    tmp_path: Path, required: dict, mode: str
) -> None:
    result = _profile_diff(
        tmp_path, {"attributes": [{"name": "locale", "required": required}]}, mode=mode
    )
    assert result.returncode != 0
    assert "locale" in result.stdout
    assert "KEYCLOAK_REQUIRED_CUSTOM_ATTRIBUTE_CONFLICT" in result.stderr
    assert "UNEXPECTED_PROFILE_MUTATION" not in result.stderr
    assert not (tmp_path / "snapshot.json").exists()
    assert (tmp_path / "snapshot.json.put-count").read_text().strip() == "0"


def _profile_diff(tmp_path: Path, profile: dict, mode: str = "Diff") -> subprocess.CompletedProcess:
    fixture = tmp_path / "profile.json"
    fixture.write_text(json.dumps(profile))
    wrapper = tmp_path / "diff.ps1"
    wrapper.write_text("""
param($ProfilePath, $ScriptPath, $Mode, $SnapshotPath)
$profileFixture = Get-Content -Raw -LiteralPath $ProfilePath | ConvertFrom-Json
$global:putCount = 0
function docker {
    $global:LASTEXITCODE = 0
    if ($args[0] -eq 'ps') { return 'fixture-container' }
    return '[{"NetworkSettings":{"Ports":{"8080/tcp":[{"HostIp":"127.0.0.1","HostPort":"8180"}]}}}]'
}
function Invoke-RestMethod {
    param($Method, $Uri, $Headers, $ContentType, $Body)
    if ($Method -eq 'Post') { return @{ access_token = 'test-only' } }
    if ($Method -eq 'Put') { $global:putCount++; throw 'UNEXPECTED_PROFILE_MUTATION' }
    if ($Uri.EndsWith('/users/profile')) { return $profileFixture }
    return [pscustomobject]@{
        realm = 'knora-dev'; verifyEmail = $true; internationalizationEnabled = $false
    }
}
try {
    $credentials = @{AdminUsername='test-only';AdminPassword='test-only'}
    & $ScriptPath -Mode $Mode @credentials -SnapshotPath $SnapshotPath
} finally {
    $global:putCount | Set-Content -LiteralPath "$SnapshotPath.put-count"
}
""")
    return subprocess.run(
        [
            POWERSHELL,
            "-NoProfile",
            "-File",
            str(wrapper),
            str(fixture),
            str(ROOT / "scripts/configure-keycloak-auth-flow.ps1"),
            mode,
            str(tmp_path / "snapshot.json"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell runner unavailable")
def test_profile_apply_saves_rollback_and_repeat_is_noop(tmp_path: Path) -> None:
    wrapper = tmp_path / "apply.ps1"
    snapshot = tmp_path / "rollback.json"
    wrapper.write_text("""
param($ScriptPath, $SnapshotPath)
$global:profileFixture = [pscustomobject]@{ attributes = @(
    [pscustomobject]@{name='firstName';required=@{roles=@('user')};validations=@{length=@{max=255}}},
    [pscustomobject]@{name='lastName';required=@{roles=@('user')}}
); groups=@(@{name='retained'}) }
$global:realmFixture = [pscustomobject]@{
    realm='knora-dev';verifyEmail=$true;loginTheme='keycloak.v2'
    registrationAllowed=$false;resetPasswordAllowed=$false
    loginWithEmailAllowed=$false;registrationEmailAsUsername=$false;duplicateEmailsAllowed=$false
}
$global:putCount = 0
function docker {
    $global:LASTEXITCODE = 0
    if ($args[0] -eq 'ps') { return 'fixture-container' }
    return '[{"NetworkSettings":{"Ports":{"8080/tcp":[{"HostIp":"127.0.0.1","HostPort":"8180"}]}}}]'
}
function Invoke-RestMethod {
    param($Method, $Uri, $Headers, $ContentType, $Body)
    if ($Method -eq 'Post') { return @{access_token='test-only'} }
    if ($Method -eq 'Put') {
        $global:putCount++
        if ($Uri.EndsWith('/users/profile')) { $global:profileFixture = $Body | ConvertFrom-Json }
        else {
            foreach ($property in ($Body | ConvertFrom-Json).PSObject.Properties) {
                $global:realmFixture.($property.Name) = $property.Value
            }
        }
        return
    }
    if ($Uri.EndsWith('/users/profile')) { return $global:profileFixture }
    return $global:realmFixture
}
$credentials = @{AdminUsername='test-only';AdminPassword='test-only'}
& $ScriptPath -Mode Apply @credentials -SnapshotPath $SnapshotPath | Out-Null
$saved = Get-Content -Raw -LiteralPath $SnapshotPath | ConvertFrom-Json
if ($saved.profile.attributes[0].required.roles[0] -ne 'user' -or
    $saved.settings.verifyEmail -ne $true) { throw 'Snapshot did not preserve original' }
& $ScriptPath -Mode Apply @credentials -SnapshotPath $SnapshotPath | Out-Null
if ($global:putCount -ne 2) { throw 'Repeat apply was not a no-op' }
& $ScriptPath -Mode Rollback @credentials -SnapshotPath $SnapshotPath | Out-Null
if ($global:profileFixture.attributes[0].required.roles[0] -ne 'user' -or
    $global:realmFixture.loginTheme -ne 'keycloak.v2') { throw 'Rollback did not restore original' }
Write-Output 'PROFILE_APPLY_REPEAT_ROLLBACK_VERIFIED'
""")
    result = subprocess.run(
        [
            POWERSHELL,
            "-NoProfile",
            "-File",
            str(wrapper),
            str(ROOT / "scripts/configure-keycloak-auth-flow.ps1"),
            str(snapshot),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "PROFILE_APPLY_REPEAT_ROLLBACK_VERIFIED" in result.stdout
