"""Knora Retrieval V3 Release Held-Out Evaluation Dataset (pdf_retrieval_release_v1).

Defines held-out test cases, multi-intent subquestions, expected source verification
outcomes, and strict data validation contracts for Gate G8 release acceptance.
Refs #153 (Retrieval V3 Stage 8 Task 2).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path


class DatasetContractError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ReleaseTestCase:
    id: str
    category: str  # multi_intent, typo_recovery, source_absence, follow_up, standard
    question: str
    required_groups: tuple[str, ...]
    expected_source_verification: str  # found, verified_absent, not_needed
    expected_answer_contains: tuple[str, ...]
    reference_answer: str
    metadata: dict[str, object]


@dataclass(frozen=True, slots=True)
class ReleaseDataset:
    version: str
    cases: tuple[ReleaseTestCase, ...]
    dataset_sha256: str

    def get_case(self, case_id: str) -> ReleaseTestCase | None:
        return next((c for c in self.cases if c.id == case_id), None)


_SAMPLE_RELEASE_CASES = (
    ReleaseTestCase(
        id="rel-001",
        category="multi_intent",
        question="So sánh Chương 2 về thời hạn đổi trả và Chương 5 về chính sách giảm giá",
        required_groups=("Chương 2", "Chương 5"),
        expected_source_verification="found",
        expected_answer_contains=("Chương 2", "Chương 5"),
        reference_answer=(
            "Chương 2 quy định đổi trả trong 7 ngày. "
            "Chương 5 quy định giảm giá 20% khi thanh toán trực tuyến."
        ),
        metadata={"priority": "high", "split": "held_out"},
    ),
    ReleaseTestCase(
        id="rel-002",
        category="source_absence",
        question="Chương 9 quy định gì về chế độ nghỉ phép đặc biệt?",
        required_groups=("Chương 9",),
        expected_source_verification="verified_absent",
        expected_answer_contains=(),
        reference_answer="Tài liệu không có Chương 9.",
        metadata={"priority": "high", "split": "held_out"},
    ),
    ReleaseTestCase(
        id="rel-003",
        category="typo_recovery",
        question="chuong2 quy dinh thoi han bao hanh san pham",
        required_groups=("Chương 2",),
        expected_source_verification="found",
        expected_answer_contains=("Chương 2",),
        reference_answer="Chương 2 quy định thời hạn bảo hành là 12 tháng kể từ ngày giao hàng.",
        metadata={"priority": "medium", "split": "held_out"},
    ),
    ReleaseTestCase(
        id="rel-004",
        category="standard",
        question="Quy định xử lý lỗi AUTH_403 đối với người dùng nội bộ",
        required_groups=("AUTH_403",),
        expected_source_verification="not_needed",
        expected_answer_contains=("AUTH_403",),
        reference_answer=(
            "Mã lỗi AUTH_403 xảy ra khi người dùng không có quyền truy cập "
            "và được xử lý trong vòng 24 giờ."
        ),
        metadata={"priority": "high", "split": "held_out"},
    ),
)


ALLOWED_CATEGORIES = {
    "multi_intent",
    "typo_recovery",
    "source_absence",
    "follow_up",
    "standard",
}
ALLOWED_SOURCE_VERIFICATIONS = {"found", "verified_absent", "not_needed"}


def _parse_and_validate_case(record: dict[str, object], idx: int) -> ReleaseTestCase:
    if not isinstance(record, dict):
        raise DatasetContractError(f"Record {idx} must be a dictionary")
    required_fields = {
        "id",
        "category",
        "question",
        "required_groups",
        "expected_source_verification",
        "expected_answer_contains",
        "reference_answer",
    }
    missing = required_fields - set(record.keys())
    if missing:
        raise DatasetContractError(f"Record {idx} missing required fields: {sorted(missing)}")

    case_id = str(record["id"]).strip()
    if not case_id:
        raise DatasetContractError(f"Record {idx} has empty id")

    category = str(record["category"])
    if category not in ALLOWED_CATEGORIES:
        allowed = sorted(ALLOWED_CATEGORIES)
        raise DatasetContractError(
            f"Record {case_id} has invalid category {category!r}, allowed: {allowed}"
        )

    expected_sv = str(record["expected_source_verification"])
    if expected_sv not in ALLOWED_SOURCE_VERIFICATIONS:
        raise DatasetContractError(
            f"Record {case_id} has invalid expected_source_verification {expected_sv!r}"
        )

    required_groups = record.get("required_groups")
    if not isinstance(required_groups, (list, tuple)):
        raise DatasetContractError(f"Record {case_id} required_groups must be list or tuple")

    expected_contains = record.get("expected_answer_contains")
    if not isinstance(expected_contains, (list, tuple)):
        raise DatasetContractError(
            f"Record {case_id} expected_answer_contains must be list or tuple"
        )

    metadata = record.get("metadata")
    if not isinstance(metadata, dict):
        raise DatasetContractError(f"Record {case_id} metadata must be a dictionary")

    split = metadata.get("split")
    if split != "held_out":
        raise DatasetContractError(f"Case {case_id} missing or invalid split: {split}")

    return ReleaseTestCase(
        id=case_id,
        category=category,
        question=str(record["question"]),
        required_groups=tuple(str(g) for g in required_groups),
        expected_source_verification=expected_sv,
        expected_answer_contains=tuple(str(a) for a in expected_contains),
        reference_answer=str(record["reference_answer"]),
        metadata=dict(metadata),
    )


def validate_approval(dataset: ReleaseDataset, approval: dict[str, object]) -> None:
    """Enforces owner approval and version consistency for the release dataset."""
    if not (
        isinstance(approval, dict)
        and approval.get("status") == "approved"
        and approval.get("owner") == "NhiBuaa"
        and approval.get("dataset_version") == dataset.version
    ):
        raise DatasetContractError("Owner approval missing or invalid for release dataset")
    if "dataset_sha256" in approval and approval["dataset_sha256"] != dataset.dataset_sha256:
        appr_sha = approval["dataset_sha256"]
        raise DatasetContractError(
            f"Approval dataset_sha256 mismatch: {appr_sha} != {dataset.dataset_sha256}"
        )


def load_release_dataset(
    path: Path | None = None,
    *,
    manifest_path: Path | None = None,
    approval_path: Path | None = None,
    enforce_approval: bool = True,
) -> ReleaseDataset:
    """Loads and cryptographically validates the release evaluation dataset.

    When `path` is provided, reads and parses the JSON/JSONL artifact, enforcing
    split integrity, category validation, no duplicate IDs, and exact checksum.
    """
    is_default = path is None
    if path is None:
        default_file = Path(__file__).with_name("pdf_retrieval_release_v1.jsonl")
        if default_file.exists():
            path = default_file

    if path is not None:
        target = Path(path)
        if not target.exists():
            raise FileNotFoundError(f"Release dataset not found at {target}")
        if target.is_dir():
            raise DatasetContractError(
                f"Expected file for release dataset, got directory: {target}"
            )

        raw_bytes = target.read_bytes()
        content = raw_bytes.decode("utf-8")
        parsed_cases: list[ReleaseTestCase] = []
        seen_ids: set[str] = set()

        if target.suffix == ".jsonl":
            lines = [line.strip() for line in content.splitlines() if line.strip()]
            for idx, line in enumerate(lines, start=1):
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise DatasetContractError(f"Invalid JSON at line {idx}: {exc}") from exc
                parsed_cases.append(_parse_and_validate_case(record, idx))
        else:
            try:
                data = json.loads(content)
            except json.JSONDecodeError as exc:
                raise DatasetContractError(f"Invalid JSON payload: {exc}") from exc
            if not isinstance(data, list):
                raise DatasetContractError("Release dataset JSON payload must be a list of records")
            for idx, record in enumerate(data, start=1):
                parsed_cases.append(_parse_and_validate_case(record, idx))

        for c in parsed_cases:
            if c.id in seen_ids:
                raise DatasetContractError(f"Duplicate case id: {c.id}")
            seen_ids.add(c.id)

        dataset_hash = hashlib.sha256(raw_bytes.replace(b"\r\n", b"\n")).hexdigest()
        dataset = ReleaseDataset(
            version="pdf_retrieval_release_v1",
            cases=tuple(parsed_cases),
            dataset_sha256=dataset_hash,
        )

        # Manifest resolution & validation
        resolved_manifest = (
            Path(manifest_path)
            if manifest_path is not None
            else target.with_name(f"{target.stem}.manifest.json")
        )
        if resolved_manifest.exists():
            try:
                manifest_data = json.loads(resolved_manifest.read_text(encoding="utf-8"))
            except Exception as exc:
                raise DatasetContractError(f"Invalid manifest JSON: {exc}") from exc
            if manifest_data.get("dataset_version") != dataset.version:
                raise DatasetContractError("Manifest dataset_version mismatch")
            m_sha = manifest_data.get("dataset_sha256")
            if m_sha != dataset.dataset_sha256:
                raise DatasetContractError(
                    f"Manifest dataset_sha256 mismatch: {m_sha} != {dataset.dataset_sha256}"
                )
            m_cases = manifest_data.get("num_cases")
            if m_cases != len(dataset.cases):
                raise DatasetContractError(
                    f"Manifest num_cases mismatch: {m_cases} != {len(dataset.cases)}"
                )
        elif is_default and enforce_approval:
            raise DatasetContractError(f"Release manifest missing: {resolved_manifest}")

        # Approval resolution & validation
        resolved_approval = (
            Path(approval_path)
            if approval_path is not None
            else target.with_name(f"{target.stem}.approval.json")
        )
        if resolved_approval.exists():
            try:
                approval_data = json.loads(resolved_approval.read_text(encoding="utf-8"))
            except Exception as exc:
                raise DatasetContractError(f"Invalid approval JSON: {exc}") from exc
            validate_approval(dataset, approval_data)
        elif is_default and enforce_approval:
            raise DatasetContractError(f"Release approval missing: {resolved_approval}")

        return dataset

    cases = _SAMPLE_RELEASE_CASES
    raw_payload = json.dumps(
        [asdict(c) for c in cases], sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    dataset_hash = hashlib.sha256(raw_payload).hexdigest()

    return ReleaseDataset(
        version="pdf_retrieval_release_v1",
        cases=cases,
        dataset_sha256=dataset_hash,
    )
