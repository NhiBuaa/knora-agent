"""Tests for the release held-out evaluation dataset contracts and integrity.

Refs #153 (Retrieval V3 Stage 8 Task 2).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from evals.datasets.pdf_retrieval_release_v1 import DatasetContractError, load_release_dataset


def test_release_dataset_loading_and_contract() -> None:
    dataset = load_release_dataset()
    assert dataset.version == "pdf_retrieval_release_v1"
    assert len(dataset.cases) >= 4
    assert len(dataset.dataset_sha256) == 64

    # Test case lookups
    c1 = dataset.get_case("rel-001")
    assert c1 is not None
    assert c1.category == "multi_intent"
    assert c1.required_groups == ("Chương 2", "Chương 5")
    assert c1.expected_source_verification == "found"

    c2 = dataset.get_case("rel-002")
    assert c2 is not None
    assert c2.category == "source_absence"
    assert c2.expected_source_verification == "verified_absent"


def test_release_dataset_immutability_and_hash_stability() -> None:
    d1 = load_release_dataset()
    d2 = load_release_dataset()
    assert d1.dataset_sha256 == d2.dataset_sha256


def test_release_loader_rejects_missing_artifact(tmp_path: Path) -> None:
    with pytest.raises((FileNotFoundError, ValueError)):
        load_release_dataset(tmp_path / "missing.jsonl")


def test_release_loader_rejects_duplicate_case_ids(tmp_path: Path) -> None:
    artifact = tmp_path / "duplicates.jsonl"
    line1 = json.dumps(
        {
            "id": "rel-dup",
            "category": "standard",
            "question": "Question 1",
            "required_groups": ["G1"],
            "expected_source_verification": "found",
            "expected_answer_contains": ["A1"],
            "reference_answer": "Answer 1",
            "metadata": {"split": "held_out"},
        }
    )
    line2 = json.dumps(
        {
            "id": "rel-dup",
            "category": "standard",
            "question": "Question 2",
            "required_groups": ["G2"],
            "expected_source_verification": "found",
            "expected_answer_contains": ["A2"],
            "reference_answer": "Answer 2",
            "metadata": {"split": "held_out"},
        }
    )
    artifact.write_text(f"{line1}\n{line2}\n", encoding="utf-8")

    with pytest.raises(DatasetContractError, match="Duplicate case id: rel-dup"):
        load_release_dataset(artifact)


def test_release_loader_rejects_invalid_category(tmp_path: Path) -> None:
    artifact = tmp_path / "invalid_category.jsonl"
    line = json.dumps(
        {
            "id": "rel-bad-cat",
            "category": "non_existent_category",
            "question": "Question",
            "required_groups": ["G1"],
            "expected_source_verification": "found",
            "expected_answer_contains": ["A1"],
            "reference_answer": "Answer",
            "metadata": {"split": "held_out"},
        }
    )
    artifact.write_text(f"{line}\n", encoding="utf-8")

    with pytest.raises(DatasetContractError, match="invalid category"):
        load_release_dataset(artifact)


def test_release_loader_loads_real_file(tmp_path: Path) -> None:
    import hashlib

    artifact = tmp_path / "valid.jsonl"
    line = json.dumps(
        {
            "id": "rel-custom-01",
            "category": "multi_intent",
            "question": "Hỏi về quy định 1 và 2",
            "required_groups": ["Quy định 1", "Quy định 2"],
            "expected_source_verification": "found",
            "expected_answer_contains": ["Nội dung"],
            "reference_answer": "Trả lời đầy đủ",
            "metadata": {"custom": True, "split": "held_out"},
        }
    )
    data_bytes = f"{line}\n".encode()
    artifact.write_bytes(data_bytes)
    data_hash = hashlib.sha256(data_bytes).hexdigest()

    manifest = tmp_path / "valid.manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "dataset_version": "pdf_retrieval_release_v1",
                "dataset_sha256": data_hash,
                "num_cases": 1,
            }
        ),
        encoding="utf-8",
    )
    approval = tmp_path / "valid.approval.json"
    approval.write_text(
        json.dumps(
            {
                "status": "approved",
                "owner": "NhiBuaa",
                "dataset_version": "pdf_retrieval_release_v1",
                "dataset_sha256": data_hash,
            }
        ),
        encoding="utf-8",
    )

    dataset = load_release_dataset(artifact)
    assert len(dataset.cases) == 1
    assert dataset.cases[0].id == "rel-custom-01"
    assert dataset.cases[0].category == "multi_intent"
    assert dataset.cases[0].required_groups == ("Quy định 1", "Quy định 2")
    assert len(dataset.dataset_sha256) == 64


def test_release_loader_rejects_contaminated_split(tmp_path: Path) -> None:
    artifact = tmp_path / "bad_split.jsonl"
    line = json.dumps(
        {
            "id": "rel-train",
            "category": "standard",
            "question": "Question",
            "required_groups": ["G1"],
            "expected_source_verification": "found",
            "expected_answer_contains": ["A1"],
            "reference_answer": "Answer",
            "metadata": {"split": "train"},
        }
    )
    artifact.write_text(f"{line}\n", encoding="utf-8")
    with pytest.raises(DatasetContractError, match="invalid split"):
        load_release_dataset(artifact)


def test_release_loader_rejects_missing_split(tmp_path: Path) -> None:
    artifact = tmp_path / "missing_split.jsonl"
    line = json.dumps(
        {
            "id": "rel-nosplit",
            "category": "standard",
            "question": "Question",
            "required_groups": ["G1"],
            "expected_source_verification": "found",
            "expected_answer_contains": ["A1"],
            "reference_answer": "Answer",
            "metadata": {},
        }
    )
    artifact.write_text(f"{line}\n", encoding="utf-8")
    with pytest.raises(DatasetContractError, match="missing or invalid split"):
        load_release_dataset(artifact)


def test_release_loader_rejects_manifest_hash_mismatch(tmp_path: Path) -> None:
    artifact = tmp_path / "data.jsonl"
    line = json.dumps(
        {
            "id": "rel-test-1",
            "category": "standard",
            "question": "Question",
            "required_groups": ["G1"],
            "expected_source_verification": "found",
            "expected_answer_contains": ["A1"],
            "reference_answer": "Answer",
            "metadata": {"split": "held_out"},
        }
    )
    artifact.write_text(f"{line}\n", encoding="utf-8")
    manifest = tmp_path / "data.manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "dataset_version": "pdf_retrieval_release_v1",
                "dataset_sha256": "wrong" * 16,
                "num_cases": 1,
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(DatasetContractError, match="Manifest dataset_sha256 mismatch"):
        load_release_dataset(artifact, manifest_path=manifest)


def test_validate_approval_checks_owner_and_version() -> None:
    from evals.datasets.pdf_retrieval_release_v1 import validate_approval

    dataset = load_release_dataset()
    valid_approval = {
        "status": "approved",
        "owner": "NhiBuaa",
        "dataset_version": dataset.version,
        "dataset_sha256": dataset.dataset_sha256,
    }
    validate_approval(dataset, valid_approval)

    with pytest.raises(DatasetContractError, match="Owner approval missing"):
        validate_approval(dataset, {"status": "pending"})

    with pytest.raises(DatasetContractError, match="Approval dataset_sha256 mismatch"):
        validate_approval(
            dataset,
            {
                "status": "approved",
                "owner": "NhiBuaa",
                "dataset_version": dataset.version,
                "dataset_sha256": "wrong" * 16,
            },
        )


def test_explicit_path_still_requires_manifest_and_approval(tmp_path: Path) -> None:
    from evals.datasets import pdf_retrieval_release_v1

    real_file = Path(pdf_retrieval_release_v1.__file__).with_name("pdf_retrieval_release_v1.jsonl")
    valid_release_bytes = real_file.read_bytes()

    target = tmp_path / "unapproved-release.jsonl"
    target.write_bytes(valid_release_bytes)
    with pytest.raises(
        DatasetContractError, match="Release manifest missing|Release approval missing"
    ):
        load_release_dataset(target, enforce_approval=True)


def test_missing_canonical_dataset_rejects_sample_fallback_when_approval_enforced(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from evals.datasets import pdf_retrieval_release_v1

    # Point __file__ to a dir where default jsonl does not exist
    dummy_file = tmp_path / "datasets" / "fake_loader.py"
    dummy_file.parent.mkdir(parents=True, exist_ok=True)
    dummy_file.write_text("# fake", encoding="utf-8")
    monkeypatch.setattr(pdf_retrieval_release_v1, "__file__", str(dummy_file))

    with pytest.raises(
        DatasetContractError, match="Release dataset not found at canonical location"
    ):
        load_release_dataset(enforce_approval=True)
