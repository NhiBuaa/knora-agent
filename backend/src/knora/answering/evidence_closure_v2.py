from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SealedEvidenceItem:
    reference: str
    byte_count: int
    sha256: str


@dataclass(frozen=True, slots=True)
class ScannerResult:
    schema_version: int
    seal_id: str
    sealed_manifest_sha256: str
    item_count: int
    total_byte_count: int
    aggregate_match_count: int
    completed_at: str
    status: str
    references: tuple[str, ...]


def close_scanner_result(
    *,
    seal_id: str,
    sealed_manifest_sha256: str,
    manifest: tuple[SealedEvidenceItem, ...],
    per_item_match_counts: dict[str, int],
    completed_at: str,
) -> ScannerResult:
    references = tuple(item.reference for item in manifest)
    if len(set(references)) != len(references):
        raise ValueError("sealed manifest references must be unique")
    if set(per_item_match_counts) != set(references):
        raise ValueError("scanner result references must equal sealed manifest")
    if any(len(item.sha256) != 64 or item.byte_count < 0 for item in manifest):
        raise ValueError("invalid sealed item")
    if any(count < 0 for count in per_item_match_counts.values()):
        raise ValueError("invalid exact match count")
    aggregate = sum(per_item_match_counts.values())
    return ScannerResult(
        schema_version=1,
        seal_id=seal_id,
        sealed_manifest_sha256=sealed_manifest_sha256,
        item_count=len(manifest),
        total_byte_count=sum(item.byte_count for item in manifest),
        aggregate_match_count=aggregate,
        completed_at=completed_at,
        status="PASS" if aggregate == 0 else "FAIL",
        references=references,
    )
