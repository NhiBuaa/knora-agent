"""Source-gold contract tests for the PDF retrieval review candidate."""

import hashlib
import json
import shutil
from pathlib import Path

import pytest
from evals.datasets.pdf_retrieval_v3_v1 import (
    DatasetContractError,
    load_dataset,
    validate_approval,
)

ROOT = Path(__file__).parents[1]
MANIFEST = ROOT / "datasets/pdf_retrieval_v3_v1.manifest.json"
DATA = ROOT / "datasets/pdf_retrieval_v3_v1.jsonl"


def _copy_candidate(tmp_path):
    datasets = tmp_path / "datasets"
    corpora = tmp_path / "corpora"
    datasets.mkdir()
    shutil.copytree(ROOT / "corpora/pdf_retrieval_v3_v1", corpora / "pdf_retrieval_v3_v1")
    manifest = datasets / MANIFEST.name
    data = datasets / DATA.name
    shutil.copyfile(MANIFEST, manifest)
    shutil.copyfile(DATA, data)
    return manifest, data


def _edit_data(manifest, data, edit):
    records = [json.loads(line) for line in data.read_text(encoding="utf-8").splitlines()]
    edit(records)
    data.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
        newline="\n",
    )
    metadata = json.loads(manifest.read_text(encoding="utf-8"))
    metadata["dataset_sha256"] = hashlib.sha256(data.read_bytes()).hexdigest()
    manifest.write_text(json.dumps(metadata), encoding="utf-8")


def test_checked_in_candidate_has_exact_distribution_and_source_closure():
    dataset = load_dataset(MANIFEST, DATA)
    assert len(dataset.sources) == 16
    assert len(dataset.cases) == 60
    assert len(dataset.anchors) >= 60
    assert {anchor.source_id for anchor in dataset.anchors} == {
        source.id for source in dataset.sources
    }
    assert len({case.question for case in dataset.cases}) == 60


def test_modified_pdf_is_rejected(tmp_path):
    manifest, data = _copy_candidate(tmp_path)
    source_path = tmp_path / "corpora/pdf_retrieval_v3_v1/clean-01.pdf"
    source_path.write_bytes(source_path.read_bytes() + b"\n% drift\n")
    with pytest.raises(DatasetContractError, match="sha256"):
        load_dataset(manifest, data)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda rows: rows[0]["evidence_groups"][0].__setitem__(0, "absent"), "anchor"),
        (lambda rows: rows[0]["evidence_groups"].__setitem__(0, []), "group"),
        (lambda rows: rows[0].update(parent_case_id="absent"), "parent"),
        (lambda rows: rows[0].update(expected_behavior="REFUSAL"), "REFUSAL"),
    ],
)
def test_invalid_gold_is_rejected(tmp_path, change, message):
    manifest, data = _copy_candidate(tmp_path)
    _edit_data(manifest, data, lambda rows: change(rows))
    with pytest.raises(DatasetContractError, match=message):
        load_dataset(manifest, data)


def test_nonexistent_anchor_page_is_rejected(tmp_path):
    manifest, data = _copy_candidate(tmp_path)
    metadata = json.loads(manifest.read_text(encoding="utf-8"))
    metadata["anchors"][0]["page"] = 999
    manifest.write_text(json.dumps(metadata), encoding="utf-8")
    with pytest.raises(DatasetContractError, match="page"):
        load_dataset(manifest, data)


def test_follow_up_parent_must_precede_child(tmp_path):
    manifest, data = _copy_candidate(tmp_path)

    def change(rows):
        child = next(row for row in rows if row["category"] == "follow_up")
        child["parent_case_id"] = rows[-1]["id"]

    _edit_data(manifest, data, change)
    with pytest.raises(DatasetContractError, match="parent"):
        load_dataset(manifest, data)


def test_approval_requires_owner_and_both_digests():
    dataset = load_dataset(MANIFEST, DATA)
    approval = {
        "status": "approved",
        "owner": "NhiBuaa",
        "corpus_sha256": dataset.corpus_sha256,
        "dataset_sha256": dataset.dataset_sha256,
    }
    validate_approval(dataset, approval)
    for drift in (
        {"status": "pending"},
        {"owner": "someone-else"},
        {"corpus_sha256": "0" * 64},
        {"dataset_sha256": "0" * 64},
    ):
        with pytest.raises(DatasetContractError, match="approval"):
            validate_approval(dataset, approval | drift)


@pytest.mark.parametrize(
    ("edit", "message"),
    [
        (lambda manifest: manifest.update(corpus_digest_scheme="unknown"), "digest scheme"),
        (lambda manifest: manifest["sources"][0].update(path="../outside.pdf"), "path"),
        (lambda manifest: manifest["sources"][0].update(license="unknown"), "license"),
        (lambda manifest: manifest["anchors"][0].update(page=True), "page"),
        (lambda manifest: manifest["anchors"][0].update(text=""), "anchor text"),
        (lambda manifest: manifest["anchors"].append(manifest["anchors"][0]), "duplicate"),
        (lambda manifest: manifest["sources"][0].update(page_count=999), "page_count"),
        (lambda manifest: manifest["anchors"][0].update(text="changed visible gold"), "corpus"),
    ],
)
def test_manifest_contract_is_not_bypassed_by_declared_metadata(tmp_path, edit, message):
    manifest, data = _copy_candidate(tmp_path)
    metadata = json.loads(manifest.read_text(encoding="utf-8"))
    edit(metadata)
    manifest.write_text(json.dumps(metadata), encoding="utf-8")
    with pytest.raises(DatasetContractError, match=message):
        load_dataset(manifest, data)


def test_invalid_pdf_is_rejected_even_when_declared_hash_matches(tmp_path):
    manifest, data = _copy_candidate(tmp_path)
    metadata = json.loads(manifest.read_text(encoding="utf-8"))
    source = metadata["sources"][0]
    pdf = manifest.parents[1] / source["path"]
    pdf.write_bytes(b"not a PDF")
    source["sha256"] = hashlib.sha256(pdf.read_bytes()).hexdigest()
    manifest.write_text(json.dumps(metadata), encoding="utf-8")
    with pytest.raises(DatasetContractError, match="PDF"):
        load_dataset(manifest, data)


def test_distribution_cannot_be_reduced_to_remove_difficult_cases(tmp_path):
    manifest, data = _copy_candidate(tmp_path)
    _edit_data(manifest, data, lambda rows: rows.pop())
    with pytest.raises(DatasetContractError, match="distribution"):
        load_dataset(manifest, data)


def test_multi_hop_rejects_or_alternatives_satisfiable_from_one_source(tmp_path):
    manifest, data = _copy_candidate(tmp_path)

    def change(rows):
        case = next(row for row in rows if row["category"] == "multi_hop")
        # r1 is a legal choice in both groups; the second source h11 is optional.
        case["evidence_groups"] = [["r1", "h11"], ["r1"]]

    _edit_data(manifest, data, change)
    with pytest.raises(DatasetContractError, match="multi_hop"):
        load_dataset(manifest, data)
