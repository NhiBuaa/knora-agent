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
        }
    )
    artifact.write_text(f"{line}\n", encoding="utf-8")

    with pytest.raises(DatasetContractError, match="invalid category"):
        load_release_dataset(artifact)


def test_release_loader_loads_real_file(tmp_path: Path) -> None:
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
            "metadata": {"custom": True},
        }
    )
    artifact.write_text(f"{line}\n", encoding="utf-8")

    dataset = load_release_dataset(artifact)
    assert len(dataset.cases) == 1
    assert dataset.cases[0].id == "rel-custom-01"
    assert dataset.cases[0].category == "multi_intent"
    assert dataset.cases[0].required_groups == ("Quy định 1", "Quy định 2")
    assert len(dataset.dataset_sha256) == 64
