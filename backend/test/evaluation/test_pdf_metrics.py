from dataclasses import asdict, replace

import pytest

from knora.evaluation.contracts import (
    Case,
    DatasetIdentity,
    DatasetSelection,
    EvidenceAnchor,
    EvidenceGroup,
    FreezeApproval,
    GoldDataset,
    NoAnswerScope,
    PdfSource,
    digest_json,
    freeze_dataset,
    select_cases,
)
from knora.evaluation.pdf_metrics import score_pdf_run


def inputs():
    anchors = tuple(EvidenceAnchor("version-1", page, f"Fact {page}") for page in (1, 2, 3))
    base = Case(
        "base",
        "What is known?",
        "ANSWER",
        "Facts 1 and 3",
        ("1", "3"),
        "en",
        "multi-hop",
        (EvidenceGroup(anchors[:2]), EvidenceGroup(anchors[2:])),
    )
    follow_up = replace(base, case_id="follow-up", context_dependencies=("base",))
    no_answer = Case(
        "no-answer",
        "What is absent?",
        "REFUSAL",
        None,
        (),
        "en",
        "no-answer",
        (),
        no_answer_scope=NoAnswerScope(("version-1",), "Reviewed original PDF"),
    )
    gold = GoldDataset(
        DatasetIdentity("pdf-set", 1, "workspace-1", "pdf-gold-v1", "pdf-metrics-v1"),
        (PdfSource("document-1", "version-1", "a" * 64),),
        (base, follow_up, no_answer),
    )
    frozen = freeze_dataset(gold, FreezeApproval("issuer", "owner", gold.digest))
    bindings = {
        digest_json(asdict(anchor)): {"status": "READY", "chunk_ids": [f"chunk-{index}"]}
        for index, anchor in enumerate(anchors, 1)
    }
    return frozen, bindings


def observed(**changes):
    return {
        "status": "OBSERVED",
        "trace_id": "trace-1",
        "decision": "ANSWER",
        "candidate_chunk_ids": ["chunk-1", "chunk-3"],
        "generation_chunk_ids": ["chunk-1"],
        "citation_correctness": True,
        **changes,
    }


def score(observation=None, *, selected=("base",), bindings=None):
    frozen, ready = inputs()
    return score_pdf_run(
        frozen,
        select_cases(frozen, selected),
        ready if bindings is None else bindings,
        {selected[0]: observed() if observation is None else observation},
        run_id="run-1",
        binding_digest="b" * 64,
    )


@pytest.mark.parametrize(
    ("candidates", "numerator", "value"),
    [(["chunk-2", "chunk-3"], 2, 1.0), (["chunk-1"], 1, 0.5), ([], 0, 0.0)],
)
def test_groups_require_all_groups_and_accept_either_alternative(candidates, numerator, value):
    report = score(observed(candidate_chunk_ids=candidates, generation_chunk_ids=[]))
    assert report["retrieval"]["numerator"] == numerator
    assert report["retrieval"]["denominator"] == 2
    assert report["retrieval"]["value"] == value
    assert report["population"]["evaluable"] == 1


def test_duplicate_candidates_preserve_first_order_and_do_not_inflate_coverage():
    candidates = ["chunk-3", "chunk-2", "chunk-3", "chunk-1", "chunk-2"]
    report = score(observed(candidate_chunk_ids=candidates))
    assert report["cases"][0]["candidate_chunk_ids"] == ["chunk-3", "chunk-2", "chunk-1"]
    assert report["retrieval"]["numerator"] == 2
    assert candidates == ["chunk-3", "chunk-2", "chunk-3", "chunk-1", "chunk-2"]


def test_each_reviewed_chunk_is_independently_sufficient_for_anchor():
    _, bindings = inputs()
    bindings[next(iter(bindings))]["chunk_ids"] = ["alternate-chunk", "chunk-1"]
    report = score(observed(candidate_chunk_ids=["alternate-chunk", "chunk-3"]), bindings=bindings)
    assert report["retrieval"]["value"] == 1.0


def test_full_fused_candidates_and_generation_evidence_are_separate_scopes_without_cutoff():
    report = score(
        observed(candidate_chunk_ids=[f"miss-{i}" for i in range(10)] + ["chunk-1", "chunk-3"])
    )
    assert report["retrieval"]["value"] == 1.0
    assert report["retrieval"]["scope"] == "full_ordered_fused_candidates"
    assert report["retrieval"]["k"] is None
    assert report["generation_evidence_coverage"]["value"] == 0.5


def test_false_refusal_does_not_remove_answerable_case_from_retrieval():
    report = score(observed(decision="REFUSAL"))
    assert report["population"]["applicable"] == 1
    assert report["retrieval"]["value"] == 1.0
    assert report["cases"][0]["refusal_correctness"] is False


def test_no_answer_case_has_no_retrieval_score_or_denominator():
    report = score(observed(decision="REFUSAL"), selected=("no-answer",))
    assert report["population"]["observed"] == 1
    assert report["population"]["applicable"] == 0
    assert report["population"]["evaluable"] == 0
    assert report["retrieval"]["denominator"] == 0
    assert report["retrieval"]["value"] is None
    assert report["cases"][0]["refusal_correctness"] is True


@pytest.mark.parametrize("status", ["MISSING", "AMBIGUOUS", "READY"])
def test_unready_or_empty_binding_keeps_entire_case_unscorable(status):
    _, bindings = inputs()
    # The candidate covers the other alternative; an unresolved alternative still blocks scoring.
    bindings[list(bindings)[1]] = {"status": status, "chunk_ids": []}
    report = score(bindings=bindings)
    assert report["population"]["observed"] == 1
    assert report["population"]["evaluable"] == 0
    assert report["retrieval"]["applicable_denominator"] == 2
    assert report["retrieval"]["denominator"] == 0
    assert report["retrieval"]["value"] is None
    assert report["cases"][0]["reasons"]


@pytest.mark.parametrize(
    "observation",
    [
        observed(trace_id=None),
        observed(trace_id=""),
        {"status": "FAILED", "failure_code": "PROVIDER_ERROR"},
        {"status": "NOT_RUN"},
        {"status": "BLOCKED"},
        {"status": "INDETERMINATE"},
        observed(candidate_chunk_ids="chunk-1"),
        observed(candidate_chunk_ids=[None]),
        observed(generation_chunk_ids=None),
        observed(decision="UNKNOWN"),
        observed(citation_correctness="yes"),
        {"status": "UNKNOWN"},
        [],
    ],
)
def test_incomplete_failed_or_malformed_observation_is_visible_without_zero_score(observation):
    report = score(observation)
    assert len(report["cases"]) == 1
    assert report["cases"][0]["evaluable"] is False
    assert report["cases"][0]["reasons"]
    assert report["retrieval"]["value"] is None
    assert report["retrieval"]["applicable_denominator"] == 2


def test_context_only_and_unobserved_selected_cases_remain_disclosed():
    report = score(selected=("follow-up", "no-answer"))
    assert report["population"] == {
        "dataset": 3,
        "selected": 2,
        "context_only": 1,
        "attempted": 1,
        "observed": 1,
        "applicable": 1,
        "evaluable": 1,
    }
    assert [case["case_id"] for case in report["cases"]] == ["follow-up", "no-answer"]
    assert report["cases"][1]["status"] == "NOT_RUN"
    assert [case["case_id"] for case in report["context_only_cases"]] == ["base"]
    assert report["retrieval"]["denominator"] == 2


def test_report_keeps_frozen_gold_and_run_identity_without_mutation():
    frozen, bindings = inputs()
    before = frozen.to_json()
    selection = select_cases(frozen, ("base",))
    observations = {"base": observed()}
    report = score_pdf_run(
        frozen, selection, bindings, observations, run_id="run-1", binding_digest="b" * 64
    )
    assert report["dataset"] == asdict(frozen.reference)
    assert report["selection_digest"] == digest_json(asdict(selection))
    assert report["binding_digest"] == "b" * 64
    assert report["run_id"] == "run-1"
    assert report["workspace_id"] == "workspace-1"
    assert report["report_kind"] == "deterministic_partial_pdf"
    assert report["quality_status"] == "SEMANTIC_PENDING"
    assert report["schema_version"] == 1
    case = report["cases"][0]
    assert case["question"] == "What is known?"
    assert case["reference_answer"] == "Facts 1 and 3"
    assert case["required_facts"] == ["1", "3"]
    assert case["evidence_groups"][0]["alternatives"][0]["physical_page"] == 1
    assert frozen.to_json() == before
    assert (
        score_pdf_run(
            frozen, selection, bindings, observations, run_id="run-1", binding_digest="b" * 64
        )
        == report
    )


def test_unscorable_case_does_not_erase_valid_case_or_reduce_applicable_population():
    frozen, bindings = inputs()
    report = score_pdf_run(
        frozen,
        select_cases(frozen, ("base", "follow-up")),
        bindings,
        {"base": observed(), "follow-up": {"status": "FAILED", "failure_code": "PROVIDER_ERROR"}},
        run_id="run-1",
        binding_digest="b" * 64,
    )
    assert report["population"] == {
        "dataset": 3,
        "selected": 2,
        "context_only": 0,
        "attempted": 2,
        "observed": 1,
        "applicable": 2,
        "evaluable": 1,
    }
    assert report["retrieval"]["denominator"] == 2
    assert report["retrieval"]["applicable_denominator"] == 4
    assert report["retrieval"]["value"] == 1.0
    assert report["cases"][1]["failure_code"] == "PROVIDER_ERROR"


@pytest.mark.parametrize(
    ("binding", "reason"),
    [
        (None, "MISSING_BINDING"),
        ([], "MALFORMED_BINDING"),
        ({"status": "READY", "chunk_ids": [None]}, "MALFORMED_BINDING"),
    ],
)
def test_missing_or_malformed_anchor_mapping_cannot_crash_or_become_valid_miss(binding, reason):
    _, bindings = inputs()
    bindings[next(iter(bindings))] = binding
    report = score(bindings=bindings)
    assert report["cases"][0]["reasons"] == [reason]
    assert report["retrieval"]["value"] is None


def test_forged_selection_fails_before_scoring():
    frozen, bindings = inputs()
    selection = DatasetSelection(frozen.reference, ("follow-up",), ())
    with pytest.raises(ValueError, match="context-only"):
        score_pdf_run(frozen, selection, bindings, {}, run_id="run-1", binding_digest="b" * 64)
