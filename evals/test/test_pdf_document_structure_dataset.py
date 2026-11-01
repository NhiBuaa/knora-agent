"""Tests for the PDF document structure annotation dataset contract."""

import hashlib
import json
import shutil
from pathlib import Path

import pytest
from evals.datasets.pdf_document_structure_v1 import (
    NormalizedBoundingBox,
    StructureDatasetContractError,
    load_document_structure_dataset,
    validate_approval,
)

ROOT = Path(__file__).parents[1]
MANIFEST = ROOT / "datasets/pdf_document_structure_v1.manifest.json"
DATA = ROOT / "datasets/pdf_document_structure_v1.jsonl"
APPROVAL = ROOT / "datasets/pdf_document_structure_v1.approval.json"


def _copy_dataset(tmp_path: Path):
    datasets_dir = tmp_path / "datasets"
    corpora_dir = tmp_path / "corpora"
    datasets_dir.mkdir()
    shutil.copytree(ROOT / "corpora/pdf_retrieval_v3_v1", corpora_dir / "pdf_retrieval_v3_v1")
    manifest = datasets_dir / MANIFEST.name
    data = datasets_dir / DATA.name
    approval = datasets_dir / APPROVAL.name
    shutil.copyfile(MANIFEST, manifest)
    shutil.copyfile(DATA, data)
    shutil.copyfile(APPROVAL, approval)
    return manifest, data, approval


def test_checked_in_dataset_matches_exact_16_sources_and_closure():
    dataset = load_document_structure_dataset(MANIFEST, DATA)
    assert len(dataset.documents) == 16
    assert dataset.dataset_id == "pdf-document-structure-v1"
    assert dataset.owner == "NhiBuaa"

    categories = {doc.category for doc in dataset.documents}
    assert categories == {
        "clean",
        "hierarchy",
        "multi_column",
        "hard_table",
        "scan_mixed",
        "academic",
    }

    total_pages = sum(doc.page_count for doc in dataset.documents)
    assert total_pages == 35

    # Check approval
    validate_approval(APPROVAL, MANIFEST)


def test_tampered_pdf_source_is_rejected(tmp_path: Path):
    manifest, data, _ = _copy_dataset(tmp_path)
    pdf_path = tmp_path / "corpora/pdf_retrieval_v3_v1/clean-01.pdf"
    pdf_path.write_bytes(pdf_path.read_bytes() + b"\n% tamper\n")

    with pytest.raises(StructureDatasetContractError, match="sha256 mismatch"):
        load_document_structure_dataset(manifest, data)


def test_tampered_jsonl_checksum_is_rejected(tmp_path: Path):
    manifest, data, _ = _copy_dataset(tmp_path)
    content = data.read_text(encoding="utf-8")
    data.write_text(content + "\n", encoding="utf-8")

    with pytest.raises(StructureDatasetContractError, match="checksum mismatch"):
        load_document_structure_dataset(manifest, data)


def test_normalized_bounding_box_constraints():
    # Valid box
    box = NormalizedBoundingBox(0.1, 0.2, 0.8, 0.9)
    assert box.left == 0.1

    # Out of range coordinates
    with pytest.raises(StructureDatasetContractError, match="out of bounds"):
        NormalizedBoundingBox(-0.1, 0.0, 0.5, 0.5)

    with pytest.raises(StructureDatasetContractError, match="out of bounds"):
        NormalizedBoundingBox(0.0, 0.0, 1.1, 0.5)

    # Inverted coordinates
    with pytest.raises(StructureDatasetContractError, match="left .* > right"):
        NormalizedBoundingBox(0.6, 0.1, 0.4, 0.8)

    with pytest.raises(StructureDatasetContractError, match="top .* > bottom"):
        NormalizedBoundingBox(0.1, 0.9, 0.5, 0.2)


def test_invalid_table_cell_bounds_rejected(tmp_path: Path):
    manifest, data, _ = _copy_dataset(tmp_path)
    lines = [json.loads(line) for line in data.read_text(encoding="utf-8").splitlines()]

    # Find a document with tables (hard_table)
    table_doc = next(d for d in lines if d["category"] == "hard_table")
    # Make a cell exceed table dimensions
    table = table_doc["pages"][0]["tables"][0]
    table["cells"][0]["row_index"] = 999  # > num_rows

    data.write_text(
        "\n".join(json.dumps(d, ensure_ascii=False) for d in lines) + "\n",
        encoding="utf-8",
    )
    # Update manifest hash to test structural parser validation
    manifest_dict = json.loads(manifest.read_text(encoding="utf-8"))
    manifest_dict["dataset_sha256"] = hashlib.sha256(data.read_bytes()).hexdigest()
    manifest.write_text(json.dumps(manifest_dict), encoding="utf-8")

    with pytest.raises(StructureDatasetContractError, match="row out of range"):
        load_document_structure_dataset(manifest, data)


def test_duplicate_reading_order_rejected(tmp_path: Path):
    manifest, data, _ = _copy_dataset(tmp_path)
    lines = [json.loads(line) for line in data.read_text(encoding="utf-8").splitlines()]

    clean_doc = next(d for d in lines if d["category"] == "clean")
    page_blocks = clean_doc["pages"][0]["blocks"]
    if len(page_blocks) >= 2:
        page_blocks[1]["reading_order"] = page_blocks[0]["reading_order"]

    data.write_text(
        "\n".join(json.dumps(d, ensure_ascii=False) for d in lines) + "\n",
        encoding="utf-8",
    )
    manifest_dict = json.loads(manifest.read_text(encoding="utf-8"))
    manifest_dict["dataset_sha256"] = hashlib.sha256(data.read_bytes()).hexdigest()
    manifest.write_text(json.dumps(manifest_dict), encoding="utf-8")

    with pytest.raises(StructureDatasetContractError, match="Duplicate reading_order"):
        load_document_structure_dataset(manifest, data)


def test_approval_validation_failures(tmp_path: Path):
    manifest, data, approval = _copy_dataset(tmp_path)

    # Status not approved
    bad_approval = json.loads(approval.read_text(encoding="utf-8"))
    bad_approval["status"] = "pending"
    approval.write_text(json.dumps(bad_approval), encoding="utf-8")
    with pytest.raises(StructureDatasetContractError, match="not 'approved'"):
        validate_approval(approval, manifest)

    # Owner mismatch
    bad_approval["status"] = "approved"
    bad_approval["owner"] = "attacker"
    approval.write_text(json.dumps(bad_approval), encoding="utf-8")
    with pytest.raises(StructureDatasetContractError, match="owner mismatch"):
        validate_approval(approval, manifest)
