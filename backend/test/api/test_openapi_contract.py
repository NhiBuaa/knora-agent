"""Guard the checked-in public OpenAPI contract."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[3]
EXPORT_SCRIPT = ROOT / "scripts" / "export_openapi.py"
OPENAPI_PATH = ROOT / "docs" / "openapi.json"
MANIFEST_PATH = ROOT / "docs" / "openapi-manifest.json"

REQUIRED_PATHS = {
    "/health",
    "/v1/questions",
    "/v1/questions/stream",
    "/v1/workspaces/{workspace_id}/documents",
    "/v1/workspaces/{workspace_id}/documents/{document_id}",
    "/v1/workspaces/{workspace_id}/operator/traces/{trace_id}",
    "/v1/workspaces/{workspace_id}/operator/evaluations/{report_id}",
    "/v1/workspaces/{workspace_id}/operator/operations",
}


def _run_export(*args: str) -> subprocess.CompletedProcess[str]:
    environment = {
        **__import__("os").environ,
        "KNORA_PROVIDER_MODE": "deterministic-local",
        "KNORA_DATABASE_URL": (
            "postgresql+psycopg://knora:knora@127.0.0.1:5432/knora?connect_timeout=3"
        ),
    }
    return subprocess.run(
        [sys.executable, str(EXPORT_SCRIPT), *args],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def test_checked_openapi_has_required_paths_and_public_only_fields() -> None:
    contract = json.loads(OPENAPI_PATH.read_text(encoding="utf-8"))

    assert contract["paths"].keys() >= REQUIRED_PATHS
    assert contract["openapi"].startswith("3.")
    serialized = json.dumps(contract, sort_keys=True)
    for private_name in ("api_key", "key_hash", "secret_key", "raw_token", "provider_api_key"):
        assert private_name not in serialized


def test_openapi_export_is_deterministic_and_matches_checked_artifacts() -> None:
    first = _run_export("--check")
    assert first.returncode == 0, first.stderr or first.stdout

    contract_bytes = OPENAPI_PATH.read_bytes()
    digest = hashlib.sha256(contract_bytes).hexdigest()
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert manifest["contract"] == "docs/openapi.json"
    assert manifest["sha256"] == digest

    second = _run_export("--check")
    assert second.returncode == 0, second.stderr or second.stdout
    assert OPENAPI_PATH.read_bytes() == contract_bytes
