"""Tests for dense search scale diagnostic dataset loading and invariants."""

import json
from pathlib import Path

import pytest
from evals.datasets.dense_search_scale_v1 import (
    ScaleDatasetContractError,
    load_dense_scale_dataset,
    validate_scale_approval,
)


@pytest.fixture
def dataset_paths():
    manifest = Path("evals/datasets/dense_search_scale_v1.manifest.json")
    dataset = Path("evals/datasets/dense_search_scale_v1.jsonl")
    approval = Path("evals/datasets/dense_search_scale_v1.approval.json")
    return manifest, dataset, approval


def test_clean_scale_dataset_loads_and_passes_approval(dataset_paths):
    manifest_path, dataset_path, approval_path = dataset_paths

    dataset = load_dense_scale_dataset(manifest_path, dataset_path)
    approval = json.loads(approval_path.read_text(encoding="utf-8"))

    validate_scale_approval(dataset, approval)

    assert dataset.schema_version == 1
    assert dataset.version == "dense-search-scale-v1"
    assert dataset.dimensions == 768
    assert dataset.metric == "Cosine"
    assert dataset.total_population == 300
    assert dataset.eligible_population == 250
    assert dataset.decoy_population == 50
    assert len(dataset.queries) == 5

    # Every query has 200 neighbors and 200 scores
    for q in dataset.queries:
        assert len(q.exact_top200) == 200
        assert len(q.exact_top200_scores) == 200
        # Scores descending
        assert list(q.exact_top200_scores) == sorted(q.exact_top200_scores, reverse=True)


def test_population_under_201_rejected_for_ann_recall200(tmp_path, dataset_paths):
    manifest_path, dataset_path, _ = dataset_paths

    # Truncate jsonl to 150 points (less than 201 required)
    lines = dataset_path.read_text(encoding="utf-8").strip().splitlines()[:150]
    bad_bytes = ("\n".join(lines) + "\n").encode("utf-8")
    import hashlib

    new_sha = hashlib.sha256(bad_bytes).hexdigest()

    bad_jsonl = tmp_path / "bad.jsonl"
    bad_jsonl.write_bytes(bad_bytes)

    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_data["dataset_sha256"] = new_sha
    bad_manifest = tmp_path / "bad_manifest.json"
    bad_manifest.write_text(json.dumps(manifest_data), encoding="utf-8")

    with pytest.raises(ScaleDatasetContractError, match="must be >= 201 for ANN Recall@200 claims"):
        load_dense_scale_dataset(bad_manifest, bad_jsonl)


def test_mismatched_vector_dimensions_rejected(tmp_path, dataset_paths):
    manifest_path, dataset_path, _ = dataset_paths

    lines = dataset_path.read_text(encoding="utf-8").strip().splitlines()
    rec = json.loads(lines[0])
    rec["vector"] = rec["vector"][:512]  # Truncate from 768 to 512
    lines[0] = json.dumps(rec, sort_keys=True)
    bad_bytes = ("\n".join(lines) + "\n").encode("utf-8")
    import hashlib

    new_sha = hashlib.sha256(bad_bytes).hexdigest()

    bad_jsonl = tmp_path / "bad.jsonl"
    bad_jsonl.write_bytes(bad_bytes)

    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_data["dataset_sha256"] = new_sha
    bad_manifest = tmp_path / "bad_manifest.json"
    bad_manifest.write_text(json.dumps(manifest_data), encoding="utf-8")

    with pytest.raises(ScaleDatasetContractError, match="vector must have exactly 768 dimensions"):
        load_dense_scale_dataset(bad_manifest, bad_jsonl)


def test_foreign_decoy_in_exact_ground_truth_rejected(tmp_path, dataset_paths):
    manifest_path, dataset_path, _ = dataset_paths

    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    # Insert a decoy point (foreign tenant) into the exact_top200 of query 0
    top200 = list(manifest_data["queries"][0]["exact_top200"])
    top200[0] = "point-decoy-001"
    manifest_data["queries"][0]["exact_top200"] = top200

    bad_manifest = tmp_path / "bad_manifest.json"
    bad_manifest.write_text(json.dumps(manifest_data), encoding="utf-8")

    with pytest.raises(ScaleDatasetContractError, match="belongs to foreign tenant"):
        load_dense_scale_dataset(bad_manifest, dataset_path)


def test_scale_approval_validation_catches_tampering(dataset_paths):
    manifest_path, dataset_path, approval_path = dataset_paths
    dataset = load_dense_scale_dataset(manifest_path, dataset_path)
    approval = json.loads(approval_path.read_text(encoding="utf-8"))

    bad_approval = dict(approval)
    bad_approval["owner"] = "attacker"
    with pytest.raises(ScaleDatasetContractError, match="owner scale approval missing"):
        validate_scale_approval(dataset, bad_approval)
