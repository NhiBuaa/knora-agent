import inspect

from knora.answering.evidence_closure_v2 import (
    ScannerResult,
    SealedEvidenceItem,
    close_scanner_result,
)


def test_scanner_closure_schema_accepts_only_manifest_references_and_counts() -> None:
    manifest = (
        SealedEvidenceItem("artifact:a", 10, "a" * 64),
        SealedEvidenceItem("artifact:b", 20, "b" * 64),
    )

    result = close_scanner_result(
        seal_id="seal-1",
        sealed_manifest_sha256="c" * 64,
        manifest=manifest,
        per_item_match_counts={"artifact:a": 0, "artifact:b": 0},
        completed_at="2026-08-13T00:00:00Z",
    )

    assert result == ScannerResult(
        schema_version=1,
        seal_id="seal-1",
        sealed_manifest_sha256="c" * 64,
        item_count=2,
        total_byte_count=30,
        aggregate_match_count=0,
        completed_at="2026-08-13T00:00:00Z",
        status="PASS",
        references=("artifact:a", "artifact:b"),
    )
    assert "credential" not in inspect.signature(close_scanner_result).parameters
    assert "search_literal" not in inspect.signature(close_scanner_result).parameters
