"""Contracts for the Keycloak 26.3.3 presentation assets."""

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]


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
        "vendor/patternfly-v5/patternfly.min.css "
        "vendor/patternfly-v5/patternfly-addons.css"
    )


def test_theme_bundles_licensed_fonts_and_app_colors() -> None:
    resources = ROOT / "themes/knora/login/resources"
    css = (resources / "css/knora.css").read_text()

    for color in ("#EFFCFA", "#FFFFFF", "#33A15B", "#784131", "#1F3B36", "#D9E2DE",
                  "#0B1412", "#12201C", "#4DBB73", "#C68F79", "#D7EFE6", "#2A3D36"):
        assert color in css
    assert "localhost" not in css
    assert (resources / "fonts/inter-latin-vietnamese.woff2").is_file()
    assert (resources / "fonts/roboto-slab-latin-vietnamese.woff2").is_file()
    assert (resources / "fonts/OFL-Inter.txt").is_file()
    assert (resources / "fonts/LICENSE-RobotoSlab.txt").is_file()
