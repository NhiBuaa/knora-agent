"""Tests for retrieval ranking development supplement dataset loading and validation."""

import copy
import json
from pathlib import Path

import pytest
from evals.datasets.retrieval_ranking_development_v1 import (
    DatasetContractError,
    load_ranking_development_dataset,
    validate_ranking_approval,
)


@pytest.fixture
def dataset_paths():
    manifest = Path("evals/datasets/retrieval_ranking_development_v1.manifest.json")
    dataset = Path("evals/datasets/retrieval_ranking_development_v1.jsonl")
    approval = Path("evals/datasets/retrieval_ranking_development_v1.approval.json")
    return manifest, dataset, approval


def test_clean_ranking_development_dataset_loads_and_passes_approval(dataset_paths):
    manifest_path, dataset_path, approval_path = dataset_paths

    dataset = load_ranking_development_dataset(manifest_path, dataset_path)
    approval = json.loads(approval_path.read_text(encoding="utf-8"))

    validate_ranking_approval(dataset, approval)

    assert dataset.schema_version == 1
    assert dataset.version == "retrieval-ranking-development-v1"
    assert len(dataset.candidate_universe) == 47
    assert len(dataset.candidate_universe_ids) == 47
    assert len(dataset.cases) == 60

    # Verify distribution
    refusals = [c for c in dataset.cases if c.expected_behavior == "REFUSAL"]
    answers = [c for c in dataset.cases if c.expected_behavior == "ANSWER"]
    assert len(refusals) == 8
    assert len(answers) == 52

    # Every refusal case has 0 positive judgments
    for r in refusals:
        assert all(j.grade == 0 for j in r.judgments)
        assert len(r.relevant_chunk_ids) == 0

    # Exhaustive judgments for every case
    for case in dataset.cases:
        assert len(case.judgments) == 47
        assert set(case.judgments_by_chunk_id.keys()) == dataset.candidate_universe_ids


def test_tampered_jsonl_content_fails_dataset_sha(tmp_path, dataset_paths):
    manifest_path, dataset_path, _ = dataset_paths
    bad_dataset = tmp_path / "bad.jsonl"
    content = dataset_path.read_text(encoding="utf-8")
    bad_dataset.write_text(content.replace("pdf-v3-001", "pdf-v3-tampered", 1), encoding="utf-8")

    with pytest.raises(DatasetContractError, match="dataset_sha256 drift"):
        load_ranking_development_dataset(manifest_path, bad_dataset)


def test_duplicate_case_id_rejected(tmp_path, dataset_paths):
    manifest_path, dataset_path, _ = dataset_paths
    # Parse jsonl, duplicate first line, adjust manifest dataset_sha256
    lines = dataset_path.read_text(encoding="utf-8").strip().splitlines()
    lines.append(lines[0])
    bad_bytes = ("\n".join(lines) + "\n").encode("utf-8")
    import hashlib

    new_sha = hashlib.sha256(bad_bytes).hexdigest()

    bad_jsonl = tmp_path / "bad.jsonl"
    bad_jsonl.write_bytes(bad_bytes)

    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_data["dataset_sha256"] = new_sha
    bad_manifest = tmp_path / "bad_manifest.json"
    bad_manifest.write_text(json.dumps(manifest_data), encoding="utf-8")

    with pytest.raises(DatasetContractError, match="duplicate case id"):
        load_ranking_development_dataset(bad_manifest, bad_jsonl)


def test_non_development_split_rejected(tmp_path, dataset_paths):
    manifest_path, dataset_path, _ = dataset_paths
    lines = dataset_path.read_text(encoding="utf-8").strip().splitlines()
    record = json.loads(lines[0])
    record["split"] = "held_out"
    lines[0] = json.dumps(record, sort_keys=True)
    bad_bytes = ("\n".join(lines) + "\n").encode("utf-8")
    import hashlib

    new_sha = hashlib.sha256(bad_bytes).hexdigest()

    bad_jsonl = tmp_path / "bad.jsonl"
    bad_jsonl.write_bytes(bad_bytes)

    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_data["dataset_sha256"] = new_sha
    bad_manifest = tmp_path / "bad_manifest.json"
    bad_manifest.write_text(json.dumps(manifest_data), encoding="utf-8")

    with pytest.raises(DatasetContractError, match="split must be 'development'"):
        load_ranking_development_dataset(bad_manifest, bad_jsonl)


def test_invalid_grade_rejected(tmp_path, dataset_paths):
    manifest_path, dataset_path, _ = dataset_paths
    lines = dataset_path.read_text(encoding="utf-8").strip().splitlines()
    record = json.loads(lines[0])
    record["judgments"][0]["grade"] = 2  # Not in (0, 1)
    lines[0] = json.dumps(record, sort_keys=True)
    bad_bytes = ("\n".join(lines) + "\n").encode("utf-8")
    import hashlib

    new_sha = hashlib.sha256(bad_bytes).hexdigest()

    bad_jsonl = tmp_path / "bad.jsonl"
    bad_jsonl.write_bytes(bad_bytes)

    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_data["dataset_sha256"] = new_sha
    bad_manifest = tmp_path / "bad_manifest.json"
    bad_manifest.write_text(json.dumps(manifest_data), encoding="utf-8")

    with pytest.raises(DatasetContractError, match="grade must be 0 or 1"):
        load_ranking_development_dataset(bad_manifest, bad_jsonl)


def test_unjudged_chunk_in_case_rejected(tmp_path, dataset_paths):
    manifest_path, dataset_path, _ = dataset_paths
    lines = dataset_path.read_text(encoding="utf-8").strip().splitlines()
    record = json.loads(lines[0])
    record["judgments"].pop()  # Missing 1 chunk judgment
    lines[0] = json.dumps(record, sort_keys=True)
    bad_bytes = ("\n".join(lines) + "\n").encode("utf-8")
    import hashlib

    new_sha = hashlib.sha256(bad_bytes).hexdigest()

    bad_jsonl = tmp_path / "bad.jsonl"
    bad_jsonl.write_bytes(bad_bytes)

    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_data["dataset_sha256"] = new_sha
    bad_manifest = tmp_path / "bad_manifest.json"
    bad_manifest.write_text(json.dumps(manifest_data), encoding="utf-8")

    with pytest.raises(DatasetContractError, match="exhaustively cover candidate universe"):
        load_ranking_development_dataset(bad_manifest, bad_jsonl)


def test_refusal_case_with_positive_grade_rejected(tmp_path, dataset_paths):
    manifest_path, dataset_path, _ = dataset_paths
    lines = dataset_path.read_text(encoding="utf-8").strip().splitlines()
    # Find a refusal case (e.g. pdf-v3-053)
    for idx, line in enumerate(lines):
        record = json.loads(line)
        if record["expected_behavior"] == "REFUSAL":
            record["judgments"][0]["grade"] = 1
            record["relevant_chunk_ids"] = [record["judgments"][0]["chunk_id"]]
            lines[idx] = json.dumps(record, sort_keys=True)
            break
    bad_bytes = ("\n".join(lines) + "\n").encode("utf-8")
    import hashlib

    new_sha = hashlib.sha256(bad_bytes).hexdigest()

    bad_jsonl = tmp_path / "bad.jsonl"
    bad_jsonl.write_bytes(bad_bytes)

    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_data["dataset_sha256"] = new_sha
    bad_manifest = tmp_path / "bad_manifest.json"
    bad_manifest.write_text(json.dumps(manifest_data), encoding="utf-8")

    with pytest.raises(
        DatasetContractError, match="REFUSAL case .* must have 0 positive judgments"
    ):
        load_ranking_development_dataset(bad_manifest, bad_jsonl)


def test_approval_validation_catches_tampered_approval(dataset_paths):
    manifest_path, dataset_path, approval_path = dataset_paths
    dataset = load_ranking_development_dataset(manifest_path, dataset_path)
    approval = json.loads(approval_path.read_text(encoding="utf-8"))

    # Tamper owner
    bad_owner = copy.deepcopy(approval)
    bad_owner["owner"] = "attacker"
    with pytest.raises(DatasetContractError, match="owner ranking approval missing"):
        validate_ranking_approval(dataset, bad_owner)

    # Tamper status
    bad_status = copy.deepcopy(approval)
    bad_status["status"] = "pending"
    with pytest.raises(DatasetContractError, match="owner ranking approval missing"):
        validate_ranking_approval(dataset, bad_status)

    # Tamper derivation
    bad_derivation = copy.deepcopy(approval)
    bad_derivation["derivation_sha256"] = "0" * 64
    with pytest.raises(DatasetContractError, match="owner ranking approval missing"):
        validate_ranking_approval(dataset, bad_derivation)
