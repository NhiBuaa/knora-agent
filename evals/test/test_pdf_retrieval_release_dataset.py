"""Tests for the release held-out evaluation dataset contracts and integrity.

Refs #153 (Retrieval V3 Stage 8 Task 2).
"""

from __future__ import annotations

from evals.datasets.pdf_retrieval_release_v1 import load_release_dataset


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
