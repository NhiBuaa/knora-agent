import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest
from evals.runners.evaluation import (
    DatasetValidationError,
    EvaluationCase,
    EvaluationDataset,
    EvaluationObservation,
    EvaluationProvenance,
    build_report,
    load_corpus_manifest,
    load_dataset,
    load_dataset_manifest,
    normalize_report,
    score_retrieval,
    validate_mode,
    validate_relevance_references,
    verify_active_corpus,
    write_report_atomic,
)

DATASET = Path(__file__).parents[1] / "datasets" / "milestone_1.jsonl"
CORPUS_MANIFEST = Path(__file__).parents[1] / "corpora" / "milestone_1" / "manifest.json"
OPENAI_CORPUS_MANIFEST = (
    Path(__file__).parents[1] / "corpora" / "milestone_1" / "manifest.openai-compatible.json"
)
DATASET_MANIFEST = Path(__file__).parents[1] / "datasets" / "milestone_1.manifest.json"


def test_milestone_one_dataset_has_the_approved_case_contract() -> None:
    dataset = load_dataset(DATASET)

    assert 20 <= len(dataset.cases) <= 25
    assert {case.category for case in dataset.cases} == {
        "answerable",
        "unanswerable",
        "ambiguous",
        "adversarial_near_miss",
    }
    assert all(case.expected_source_documents is not None for case in dataset.cases)
    assert all(case.acceptable_relevant_chunks is not None for case in dataset.cases)
    assert all(
        case.required_facts or case.reference_answer
        for case in dataset.cases
        if case.expected_behavior == "ANSWER"
    )


def test_dataset_validation_rejects_duplicate_case_ids(tmp_path: Path) -> None:
    lines = DATASET.read_text(encoding="utf-8").splitlines()
    invalid = tmp_path / "duplicate.jsonl"
    invalid.write_text("\n".join([*lines, lines[0]]) + "\n", encoding="utf-8")

    with pytest.raises(DatasetValidationError, match="duplicate case id: refund-window"):
        load_dataset(invalid)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda records: records[:19], "dataset must contain 20 to 25 cases"),
        (
            lambda records: [{**records[0], "category": "unknown"}, *records[1:]],
            "unknown category: unknown",
        ),
        (
            lambda records: [
                {
                    **records[0],
                    "expected_source_documents": [],
                    "acceptable_relevant_chunks": [],
                },
                *records[1:],
            ],
            "ANSWER case refund-window requires relevant sources and chunks",
        ),
        (
            lambda records: [
                {key: value for key, value in records[0].items() if key != "question"},
                *records[1:],
            ],
            "case refund-window missing field: question",
        ),
    ],
)
def test_dataset_validation_rejects_invalid_contract_variants(
    tmp_path: Path, mutation, message: str
) -> None:
    records = [json.loads(line) for line in DATASET.read_text().splitlines()]
    invalid = tmp_path / "invalid.jsonl"
    invalid.write_text(
        "\n".join(json.dumps(record) for record in mutation(records)) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(DatasetValidationError, match=message):
        load_dataset(invalid)


def test_retrieval_metrics_match_an_independent_worked_example() -> None:
    cases = tuple(
        EvaluationCase(
            id=f"case-{index}",
            category="answerable",
            workspace_id="evaluation-m1",
            question=f"question {index}",
            expected_behavior="ANSWER",
            expected_source_documents=("policy",),
            acceptable_relevant_chunks=(f"policy#{index}",),
            required_facts=("fact",),
            reference_answer="answer",
        )
        for index in range(1, 4)
    )
    observations = (
        EvaluationObservation("case-1", ("policy#1", "other#0"), 12.0),
        EvaluationObservation(
            "case-2", ("other#0", "other#1", "other#2", "policy#2"), 18.0
        ),
        EvaluationObservation(
            "case-3",
            ("other#0",),
            30.0,
            provider_error="PROVIDER_REQUEST_FAILED",
        ),
    )

    metrics = score_retrieval(cases, observations, candidate_k=8)

    assert metrics["recall_at_8"] == pytest.approx(2 / 3)
    assert metrics["mrr"] == pytest.approx((1 + 0.25 + 0) / 3)
    assert metrics["hit_rate"] == pytest.approx(2 / 3)
    assert metrics["latency_ms"]["mean"] == 20.0
    assert metrics["denominator"] == 3


def test_local_report_separates_structural_retrieval_and_system_results() -> None:
    case = EvaluationCase(
        id="refund-window",
        category="answerable",
        workspace_id="evaluation-m1",
        question="Refund window?",
        expected_behavior="ANSWER",
        expected_source_documents=("support/refund-policy",),
        acceptable_relevant_chunks=("support/refund-policy#0",),
        required_facts=("30 days",),
        reference_answer="30 days",
    )
    observation = EvaluationObservation(
        case_id=case.id,
        retrieved_chunks=("support/refund-policy#0",),
        retrieval_latency_ms=10.0,
        decision="ANSWER",
        answer="Refunds are accepted within 30 days. [[E1]]",
        refusal_reason=None,
        cited_chunks=("support/refund-policy#0",),
        citation_evidence_ids=("E1",),
        answer_marker_ids=("E1",),
        candidate_workspaces=("evaluation-m1",),
        trace_id="trace-1",
        end_to_end_latency_ms=25.0,
        token_usage={"prompt_tokens": 7, "completion_tokens": 5},
        cost_usd="0.0012",
        provider_error=None,
    )
    provenance = EvaluationProvenance(
        dataset_version="m1-dataset-v1",
        dataset_checksum="sha256:dataset",
        corpus_version="m1-corpus-v1",
        corpus_checksum="sha256:corpus",
        chunking_version="chunking-m1-v1",
        embedding_version="embedding-local-m1-v2",
        retrieval_version="retrieval-m1-v1",
        generation_version="deterministic-m1-v1",
        scorer_version="not-run",
    )

    report = build_report(
        EvaluationDataset((case,)),
        (observation,),
        provenance=provenance,
        mode="deterministic-local",
    )

    assert report["structural"]["pass_rate"] == 1.0
    assert report["structural"]["hard_gate_passed"] is True
    assert report["structural"]["cases"][0]["checks"]["expected_source_documents"] is True
    assert report["retrieval"]["recall_at_8"] == 1.0
    assert report["retrieval"]["cases"] == [
        {
            "id": "refund-window",
            "hit": True,
            "recall_at_8": 1.0,
            "reciprocal_rank": 1.0,
            "retrieved_chunks": ["support/refund-policy#0"],
        }
    ]
    assert report["semantic"] == {"status": "not_run", "reason": "model_backed_required"}
    assert report["system"]["token_usage"] == {
        "completion_tokens": 5,
        "prompt_tokens": 7,
    }
    assert report["system"]["cost_usd"] == "0.0012"
    assert report["system"]["usage_status"] == "observed"
    assert report["system"]["cost_status"] == "observed"
    assert report["system"]["provider_errors"] == 0


def test_report_write_is_atomic_and_never_overwrites_prior_evidence(tmp_path: Path) -> None:
    report_path = tmp_path / "report.json"
    write_report_atomic(report_path, {"schema_version": 1, "status": "complete"})

    assert json.loads(report_path.read_text(encoding="utf-8")) == {
        "schema_version": 1,
        "status": "complete",
    }
    with pytest.raises(FileExistsError, match="report already exists"):
        write_report_atomic(report_path, {"schema_version": 1, "status": "replacement"})


def test_concurrent_report_writers_cannot_replace_the_winner(
    tmp_path: Path, monkeypatch
) -> None:
    report_path = tmp_path / "report.json"
    barrier = threading.Barrier(2)
    original_replace = os.replace

    def racing_replace(source, destination) -> None:
        barrier.wait(timeout=5)
        original_replace(source, destination)

    monkeypatch.setattr(os, "replace", racing_replace)

    def publish(value: int) -> str:
        try:
            write_report_atomic(report_path, {"value": value})
            return "published"
        except FileExistsError:
            return "exists"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = sorted(pool.map(publish, (1, 2)))

    assert outcomes == ["exists", "published"]
    assert json.loads(report_path.read_text(encoding="utf-8"))["value"] in {1, 2}


def test_model_backed_mode_requires_explicit_provider_and_scorer() -> None:
    with pytest.raises(ValueError, match="model-backed mode requires"):
        validate_mode(
            "model-backed",
            provider_mode="deterministic-local",
            scorer_version=None,
        )

    with pytest.raises(ValueError, match="deterministic-local mode requires"):
        validate_mode(
            "deterministic-local",
            provider_mode="openai-compatible",
            scorer_version=None,
        )

    validate_mode(
        "model-backed",
        provider_mode="openai-compatible",
        scorer_version="semantic-scorer-v1",
        scorer_method="llm-judge-v1",
    )

    with pytest.raises(ValueError, match="scorer measurement method"):
        validate_mode(
            "model-backed",
            provider_mode="openai-compatible",
            scorer_version="semantic-scorer-v1",
        )


def test_corpus_manifest_pins_every_document_checksum(tmp_path: Path) -> None:
    manifest = load_corpus_manifest(CORPUS_MANIFEST)
    assert manifest.version == "m1-corpus-v1"
    assert len(manifest.documents) == 3
    assert manifest.chunking_configuration_id == "chunking-m1-v1"
    assert manifest.embedding_configuration_id == "embedding-local-m1-v2"
    validate_relevance_references(load_dataset(DATASET), manifest)
    active = SimpleNamespace(
        workspace_id="evaluation-m1-r2",
        documents=tuple(
            SimpleNamespace(
                source_key=document.source_key,
                normalized_content_checksum=document.normalized_content_sha256,
                chunking_configuration_id=manifest.chunking_configuration_id,
                embedding_configuration_id=manifest.embedding_configuration_id,
                chunk_references=(f"{document.source_key}#0",),
            )
            for document in manifest.documents
        ),
    )
    verify_active_corpus(manifest, active)
    with pytest.raises(ValueError, match="active corpus does not match manifest"):
        verify_active_corpus(
            manifest,
            SimpleNamespace(
                workspace_id="evaluation-m1-r2",
                documents=(*active.documents, SimpleNamespace(source_key="extra")),
            ),
        )

    copied_manifest = json.loads(CORPUS_MANIFEST.read_text(encoding="utf-8"))
    copied_manifest["documents"][0]["normalized_content_sha256"] = "0" * 64
    invalid = tmp_path / "manifest.json"
    invalid.write_text(json.dumps(copied_manifest), encoding="utf-8")
    (tmp_path / "account-security.txt").write_text(
        "Use Forgot password on the sign-in page to reset an account password. "
        "Never send a password to support by email.\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="corpus checksum mismatch"):
        load_corpus_manifest(invalid)


def test_model_backed_corpus_manifest_pins_the_openai_embedding_configuration() -> None:
    manifest = load_corpus_manifest(OPENAI_CORPUS_MANIFEST)

    assert manifest.version == "m1-corpus-openai-v1"
    assert manifest.workspace_id == "evaluation-m1-r2"
    assert manifest.embedding_configuration_id == "embedding-openai-m1-v1"
    assert tuple(document.source_key for document in manifest.documents) == (
        "support/account-security",
        "support/refund-policy",
        "support/shipping-policy",
    )


def test_dataset_manifest_binds_version_to_content_checksum(tmp_path: Path) -> None:
    identity = load_dataset_manifest(DATASET_MANIFEST, DATASET)
    assert identity.version == "m1-dataset-v1"

    changed = tmp_path / "milestone_1.jsonl"
    changed.write_bytes(DATASET.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="dataset checksum mismatch"):
        load_dataset_manifest(DATASET_MANIFEST, changed)


def test_normalized_report_excludes_only_wall_clock_observations() -> None:
    first = {
        "mode": "deterministic-local",
        "retrieval": {"recall_at_8": 1.0, "latency_ms": {"mean": 10.0}},
        "system": {"provider_errors": 0, "end_to_end_latency_ms": {"mean": 20.0}},
    }
    second = {
        "mode": "deterministic-local",
        "retrieval": {"recall_at_8": 1.0, "latency_ms": {"mean": 99.0}},
        "system": {"provider_errors": 0, "end_to_end_latency_ms": {"mean": 101.0}},
    }

    assert normalize_report(first) == normalize_report(second)
    assert first["retrieval"]["latency_ms"]["mean"] == 10.0


def test_normalized_model_report_excludes_scorer_wall_clock_observations() -> None:
    first = {
        "mode": "model-backed",
        "semantic": {"metrics": {"faithfulness": {"mean": 0.8}}},
        "system": {
            "semantic_scorer": {"latency_ms": {"mean": 10.0}, "provider_errors": 0}
        },
    }
    second = {
        "mode": "model-backed",
        "semantic": {"metrics": {"faithfulness": {"mean": 0.8}}},
        "system": {
            "semantic_scorer": {"latency_ms": {"mean": 99.0}, "provider_errors": 0}
        },
    }

    assert normalize_report(first) == normalize_report(second)


def test_any_structural_violation_fails_the_hard_gate() -> None:
    case = EvaluationCase(
        id="unsafe",
        category="answerable",
        workspace_id="evaluation-m1",
        question="question",
        expected_behavior="ANSWER",
        expected_source_documents=("safe/policy",),
        acceptable_relevant_chunks=("safe/policy#0",),
        required_facts=("fact",),
        reference_answer="answer",
    )
    observation = EvaluationObservation(
        case_id="unsafe",
        retrieved_chunks=("safe/policy#0",),
        retrieval_latency_ms=1.0,
        decision="ANSWER",
        answer="unsupported [[E2]]",
        refusal_reason=None,
        cited_chunks=("other/policy#0",),
        citation_evidence_ids=("E1",),
        answer_marker_ids=("E2",),
        candidate_workspaces=("other-workspace",),
        trace_id=None,
        end_to_end_latency_ms=2.0,
    )
    provenance = EvaluationProvenance(
        "dataset-v1",
        "sha256:dataset",
        "corpus-v1",
        "sha256:corpus",
        "chunking-v1",
        "embedding-v1",
        "retrieval-v1",
        "generation-v1",
        "not-run",
    )

    report = build_report(
        EvaluationDataset((case,)),
        (observation,),
        provenance=provenance,
        mode="deterministic-local",
    )

    assert report["structural"]["hard_gate_passed"] is False
    assert report["structural"]["pass_rate"] == 0.0


def test_retrieval_miss_is_reported_without_falsifying_structural_gate() -> None:
    case = EvaluationCase(
        "miss", "answerable", "workspace", "q", "ANSWER", ("doc",), ("doc#0",), ("f",), "a"
    )
    observation = EvaluationObservation(
        "miss",
        (),
        1.0,
        decision="REFUSAL",
        answer="Tôi không tìm thấy đủ thông tin trong knowledge base để trả lời câu hỏi này.",
        refusal_reason="INSUFFICIENT_EVIDENCE",
        trace_id="trace-miss",
    )
    provenance = EvaluationProvenance(
        "d", "sha256:d", "c", "sha256:c", "ch", "e", "r", "g", "not-run"
    )

    report = build_report(
        EvaluationDataset((case,)),
        (observation,),
        provenance=provenance,
        mode="deterministic-local",
    )

    assert report["structural"]["hard_gate_passed"] is True
    assert report["structural"]["cases"][0]["expected_behavior_match"] is False


def test_duplicate_citation_aliases_and_invalid_refusal_answer_fail_structure() -> None:
    answer_case = EvaluationCase(
        "answer",
        "answerable",
        "evaluation-m1",
        "question",
        "ANSWER",
        ("safe/policy",),
        ("safe/policy#0",),
        ("fact",),
        "answer",
    )
    refusal_case = EvaluationCase(
        "refusal",
        "unanswerable",
        "evaluation-m1",
        "question",
        "REFUSAL",
        (),
        (),
        (),
        None,
    )
    observations = (
        EvaluationObservation(
            "answer",
            ("safe/policy#0",),
            1.0,
            decision="ANSWER",
            answer="answer [[E1]] [[E1]]",
            refusal_reason=None,
            cited_chunks=("safe/policy#0", "safe/policy#0"),
            citation_evidence_ids=("E1", "E1"),
            answer_marker_ids=("E1", "E1"),
            candidate_workspaces=("evaluation-m1",),
            trace_id="trace-answer",
        ),
        EvaluationObservation(
            "refusal",
            (),
            1.0,
            decision="REFUSAL",
            answer="custom refusal",
            refusal_reason="INSUFFICIENT_EVIDENCE",
            trace_id="trace-refusal",
        ),
    )
    provenance = EvaluationProvenance(
        "dataset-v1",
        "sha256:dataset",
        "corpus-v1",
        "sha256:corpus",
        "chunking-v1",
        "embedding-v1",
        "retrieval-v1",
        "generation-v1",
        "not-run",
    )

    report = build_report(
        EvaluationDataset((answer_case, refusal_case)),
        observations,
        provenance=provenance,
        mode="deterministic-local",
    )

    assert report["structural"]["hard_gate_passed"] is False
    assert report["structural"]["passed"] == 0


def test_report_rejects_duplicate_observations() -> None:
    case = EvaluationCase(
        "one", "answerable", "workspace", "q", "ANSWER", ("doc",), ("doc#0",), ("f",), "a"
    )
    observation = EvaluationObservation("one", ("doc#0",), 1.0)
    provenance = EvaluationProvenance(
        "d", "sha256:d", "c", "sha256:c", "ch", "e", "r", "g", "not-run"
    )

    with pytest.raises(ValueError, match="exactly one result"):
        build_report(
            EvaluationDataset((case,)),
            (observation, observation),
            provenance=provenance,
            mode="deterministic-local",
        )
