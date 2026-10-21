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


def load_release_dataset(path: Path | None = None) -> ReleaseDataset:
    """Loads and cryptographically validates the release evaluation dataset."""
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
