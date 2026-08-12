import json
from pathlib import Path

import pytest
from evals.datasets.milestone_3 import (
    DatasetContractError,
    load_milestone_3_corpus_manifest,
    load_milestone_3_dataset,
    load_milestone_3_dataset_manifest,
    validate_milestone_3_references,
)

ROOT = Path(__file__).parents[1]
DATASET = ROOT / "datasets" / "milestone_3.jsonl"
DATASET_MANIFEST = ROOT / "datasets" / "milestone_3.manifest.json"
CORPUS_MANIFEST = ROOT / "corpora" / "milestone_3" / "manifest.json"


def test_milestone_three_dataset_exposes_complete_case_semantics() -> None:
    dataset = load_milestone_3_dataset(DATASET)

    assert 50 <= len(dataset.cases) <= 100
    assert {case.category for case in dataset.cases} == {
        "lexical_exact_match",
        "semantic_paraphrase",
        "multi_source",
        "insufficient_evidence_refusal",
    }
    for case in dataset.cases:
        assert case.expected_behavior in {"ANSWER", "REFUSAL"}
        assert case.workspace_id == "evaluation-m3-v1"
        if case.expected_behavior == "ANSWER":
            assert case.retrieval_relevance.applicable is True
            assert case.retrieval_relevance.acceptable_relevant_chunks
            assert case.answer_expectations.required_facts
            assert case.evidence_expectations.expected_source_documents
        else:
            assert case.retrieval_relevance.applicable is False
            assert not case.retrieval_relevance.acceptable_relevant_chunks
            assert case.refusal_expectation == "INSUFFICIENT_EVIDENCE"


def test_milestone_three_contract_separates_retrieval_from_answer_and_evidence() -> None:
    dataset = load_milestone_3_dataset(DATASET)
    multi_chunk_case = next(
        case
        for case in dataset.cases
        if len(case.retrieval_relevance.acceptable_relevant_chunks) > 1
    )

    assert multi_chunk_case.retrieval_relevance.applicable is True
    assert multi_chunk_case.answer_expectations.required_facts
    assert multi_chunk_case.evidence_expectations.expected_source_documents
    assert multi_chunk_case.evidence_expectations.acceptable_cited_chunks


def test_milestone_three_manifests_and_references_are_compatible() -> None:
    dataset = load_milestone_3_dataset(DATASET)
    identity = load_milestone_3_dataset_manifest(DATASET_MANIFEST, DATASET)
    corpus = load_milestone_3_corpus_manifest(CORPUS_MANIFEST)

    assert identity.version == "m3-dataset-v1"
    assert corpus.version == "m3-corpus-v1"
    validate_milestone_3_references(dataset, corpus)


def test_milestone_three_dataset_manifest_rejects_tampering(tmp_path: Path) -> None:
    changed_dataset = tmp_path / DATASET.name
    changed_dataset.write_bytes(DATASET.read_bytes() + b"\n")

    with pytest.raises(DatasetContractError, match="dataset checksum mismatch"):
        load_milestone_3_dataset_manifest(DATASET_MANIFEST, changed_dataset)


def test_milestone_three_corpus_manifest_rejects_tampering(tmp_path: Path) -> None:
    manifest = json.loads(CORPUS_MANIFEST.read_text(encoding="utf-8"))
    copied = tmp_path / "manifest.json"
    copied.write_text(json.dumps(manifest), encoding="utf-8")
    for document in manifest["documents"]:
        source = CORPUS_MANIFEST.parent / document["path"]
        (tmp_path / document["path"]).write_bytes(source.read_bytes())
    (tmp_path / manifest["documents"][0]["path"]).write_text("tampered\n", encoding="utf-8")

    with pytest.raises(DatasetContractError, match="corpus checksum mismatch"):
        load_milestone_3_corpus_manifest(copied)


def test_milestone_three_corpus_manifest_rejects_ambiguous_chunk_reference(
    tmp_path: Path,
) -> None:
    manifest = json.loads(CORPUS_MANIFEST.read_text(encoding="utf-8"))
    manifest["documents"][1]["chunk_references"] = ["support/refund-policy#0"]
    copied = tmp_path / "manifest.json"
    copied.write_text(json.dumps(manifest), encoding="utf-8")
    for document in manifest["documents"]:
        source = CORPUS_MANIFEST.parent / document["path"]
        (tmp_path / document["path"]).write_bytes(source.read_bytes())

    with pytest.raises(DatasetContractError, match="ambiguous Chunk reference"):
        load_milestone_3_corpus_manifest(copied)


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda record: {
                key: value for key, value in record.items() if key != "answer_expectations"
            },
            "missing field: answer_expectations",
        ),
        (
            lambda record: {
                **record,
                "answer_expectations": {"required_facts": []},
            },
            "ANSWER case lexical-01 requires non-empty required facts",
        ),
        (
            lambda record: {
                **record,
                "retrieval_relevance": {
                    "applicable": False,
                    "acceptable_relevant_chunks": ["support/refund-policy#0"],
                },
            },
            "ANSWER case lexical-01 requires applicable retrieval relevance",
        ),
    ],
)
def test_milestone_three_validator_rejects_missing_case_semantics(
    tmp_path: Path, mutate, message: str
) -> None:
    records = [json.loads(line) for line in DATASET.read_text(encoding="utf-8").splitlines()]
    records[0] = mutate(records[0])
    path = tmp_path / "invalid.jsonl"
    path.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")

    with pytest.raises(DatasetContractError, match=message):
        load_milestone_3_dataset(path)


def test_milestone_three_validator_rejects_unresolved_reference_but_allows_multiple_chunks(
    tmp_path: Path,
) -> None:
    dataset = load_milestone_3_dataset(DATASET)
    corpus = load_milestone_3_corpus_manifest(CORPUS_MANIFEST)
    validate_milestone_3_references(dataset, corpus)

    records = [json.loads(line) for line in DATASET.read_text(encoding="utf-8").splitlines()]
    records[0]["retrieval_relevance"]["acceptable_relevant_chunks"] = ["unknown#0"]
    path = tmp_path / "unknown-reference.jsonl"
    path.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")

    with pytest.raises(DatasetContractError, match="references unknown relevant Chunk"):
        validate_milestone_3_references(load_milestone_3_dataset(path), corpus)


def test_milestone_three_validator_rejects_citation_outside_expected_source(
    tmp_path: Path,
) -> None:
    records = [json.loads(line) for line in DATASET.read_text(encoding="utf-8").splitlines()]
    records[0]["evidence_expectations"]["acceptable_cited_chunks"] = ["support/shipping-policy#0"]
    path = tmp_path / "wrong-citation-source.jsonl"
    path.write_text(
        "\n".join(json.dumps(record) for record in records) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(
        DatasetContractError, match="cites a Chunk outside expected source documents"
    ):
        validate_milestone_3_references(
            load_milestone_3_dataset(path),
            load_milestone_3_corpus_manifest(CORPUS_MANIFEST),
        )
