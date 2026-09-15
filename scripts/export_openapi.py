"""Export and verify Knora's checked-in FastAPI OpenAPI contract."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT / "backend" / "src"
CONTRACT_PATH = ROOT / "docs" / "openapi.json"
MANIFEST_PATH = ROOT / "docs" / "openapi-manifest.json"


def _canonical_json(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )


def _render_artifacts() -> tuple[bytes, bytes]:
    sys.path.insert(0, str(SOURCE_ROOT))
    from knora.main import app

    contract = _canonical_json(app.openapi())
    manifest = _canonical_json(
        {
            "contract": "docs/openapi.json",
            "openapi": json.loads(contract)["openapi"],
            "schema_version": 1,
            "sha256": hashlib.sha256(contract).hexdigest(),
            "source": "knora.main:app",
        }
    )
    return contract, manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail when checked-in artifacts differ from the current application schema",
    )
    args = parser.parse_args()
    contract, manifest = _render_artifacts()

    if args.check:
        current_contract = CONTRACT_PATH.read_bytes() if CONTRACT_PATH.exists() else None
        current_manifest = MANIFEST_PATH.read_bytes() if MANIFEST_PATH.exists() else None
        if current_contract != contract or current_manifest != manifest:
            print("OpenAPI artifacts are stale; run scripts/export_openapi.py", file=sys.stderr)
            return 1
        print("OpenAPI artifacts are current")
        return 0

    CONTRACT_PATH.write_bytes(contract)
    MANIFEST_PATH.write_bytes(manifest)
    print(f"Wrote {CONTRACT_PATH}")
    print(f"Wrote {MANIFEST_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
