import hashlib
import json
from pathlib import Path

import pytest
from evals.datasets.vietnamese_rag_v1 import DatasetContractError, load_vietnamese_dataset


def _case(**changes):
    value = {
        "id": "guideline-chapters-01",
        "question": "Cần trình bày báo cáo bao nhiêu chương?",
        "source_key": "Teacher Manh - Guidelines 2024.pdf",
        "page_start": 1,
        "acceptable_chunk_checksums": ["a" * 64],
        "required_facts": ["gợi ý 7 chương"],
        "expected_behavior": "ANSWER",
        "split": "held_out",
    }
    value.update(changes)
    return value


def _load(tmp_path, records, **manifest_changes):
    data = tmp_path / "cases.jsonl"
    data.write_text(
        "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in records), encoding="utf-8"
    )
    manifest = {
        "version": "vietnamese-rag-v1",
        "dataset_sha256": hashlib.sha256(data.read_bytes().replace(b"\r\n", b"\n")).hexdigest(),
        "profile_id": "embedding-ollama-qwen3-test",
        "model_digest": "sha256:" + "b" * 64,
        "corpus_sha256": "c" * 64,
        "chunk_set_ids": ["chunk-set-test"],
        "retrieval_configuration_id": "retrieval-qwen-v1",
        "sources": [{"source_key": "Teacher Manh - Guidelines 2024.pdf", "raw_sha256": "c" * 64}],
    }
    manifest.update(manifest_changes)
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return load_vietnamese_dataset(data, path)


def test_loader_accepts_held_out_seven_chapter_case(tmp_path):
    dataset = _load(tmp_path, [_case()])
    assert dataset.cases[0].page_start == 1
    assert dataset.cases[0].split == "held_out"


@pytest.mark.parametrize(
    ("records", "message"),
    [
        ([_case(), _case()], "duplicate"),
        ([_case(source_key="")], "source_key"),
        ([_case(page_start=None)], "page_start"),
        ([_case(required_facts=[])], "required_facts"),
        ([_case(expected_behavior="REFUSAL", required_facts=["unsupported"])], "required_facts"),
        ([_case(id="same", split="calibration"), _case(id="same", split="held_out")], "duplicate"),
    ],
)
def test_loader_rejects_invalid_labels(tmp_path, records, message):
    with pytest.raises(DatasetContractError, match=message):
        _load(tmp_path, records)


def test_loader_rejects_manifest_hash_mismatch(tmp_path):
    with pytest.raises(DatasetContractError, match="dataset_sha256"):
        _load(tmp_path, [_case()], dataset_sha256="0" * 64)


def test_loader_rejects_source_digest_inconsistent_with_single_pdf_corpus(tmp_path):
    with pytest.raises(DatasetContractError, match="source digest"):
        _load(
            tmp_path,
            [_case()],
            sources=[{"source_key": "Teacher Manh - Guidelines 2024.pdf", "raw_sha256": "d" * 64}],
        )


def test_loader_rejects_shared_gold_chunk_across_fit_and_held_out(tmp_path):
    records = [
        _case(id="fit", split="calibration"),
        _case(id="gate", split="held_out", question="Another question"),
    ]
    with pytest.raises(DatasetContractError, match="split independence"):
        _load(tmp_path, records)


def test_loader_accepts_crlf_checkout_with_lf_manifest_digest(tmp_path):
    dataset = _load(tmp_path, [_case()])
    path = tmp_path / "cases.jsonl"
    path.write_bytes(path.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
    assert load_vietnamese_dataset(path, tmp_path / "manifest.json") == dataset


def test_checked_in_set_has_30_to_50_distinct_cases_and_separate_negative_gate():
    root = Path(__file__).parents[1] / "datasets"
    dataset = load_vietnamese_dataset(
        root / "vietnamese_rag_v1.jsonl", root / "vietnamese_rag_v1.manifest.json"
    )
    assert 30 <= len(dataset.cases) <= 50
    assert len({case.question for case in dataset.cases}) == len(dataset.cases)
    assert any(
        case.id == "guideline-chapters-01" and case.split == "held_out" for case in dataset.cases
    )
    assert all(
        case.split == "held_out" for case in dataset.cases if case.expected_behavior == "REFUSAL"
    )
