from dataclasses import replace

import pytest
from evals.datasets.vietnamese_rag_v1 import VietnameseCase, VietnameseDataset
from evals.runners.vietnamese_retrieval import (
    ActiveChunkBinding,
    CandidateObservation,
    RetrievalObservation,
    evaluate_retrieval,
    validate_active_corpus,
)


def _dataset():
    cases = tuple(
        VietnameseCase(
            id=f"answer-{index}",
            question=f"Question {index}",
            source_key="source.pdf",
            page_start=1,
            acceptable_chunk_checksums=(f"{index}" * 64,),
            required_facts=("fact",),
            expected_behavior="ANSWER",
            split="held_out",
        )
        for index in (1, 2, 3)
    ) + (VietnameseCase("negative", "Unknown?", "source.pdf", None, (), (), "REFUSAL", "held_out"),)
    return VietnameseDataset(
        cases,
        "v1",
        "a" * 64,
        "profile",
        "sha256:" + "b" * 64,
        "c" * 64,
        ("set",),
        "retrieval-qwen-v1",
    )


def _observation(case_id, ranked, *, insufficient=False, **changes):
    value = dict(
        case_id=case_id,
        observation_id=f"trace-{case_id}",
        source="production_trace",
        profile_id="profile",
        corpus_sha256="c" * 64,
        retrieval_configuration_id="retrieval-qwen-v1",
        chunk_set_ids=("set",),
        candidates=tuple(
            CandidateObservation(
                source_key="source.pdf", page_start=1, checksum=checksum, similarity=1 - rank / 20
            )
            for rank, checksum in enumerate(ranked, 1)
        ),
        insufficient_evidence=insufficient,
        latency_ms=12.0,
    )
    value.update(changes)
    return RetrievalObservation(**value)


def test_scores_literal_rankings_and_refusal_separately():
    observations = (
        _observation("answer-1", ("1" * 64,)),
        _observation("answer-2", tuple(letter * 64 for letter in "wxyz") + ("2" * 64,)),
        _observation("answer-3", ("x" * 64, "y" * 64), insufficient=True),
        _observation("negative", (), insufficient=True),
    )
    report = evaluate_retrieval(_dataset(), observations)
    assert report.hit_at_1 == pytest.approx(1 / 3)
    assert report.hit_at_5 == pytest.approx(2 / 3)
    assert report.mrr == pytest.approx((1 + 1 / 5) / 3)
    assert report.false_insufficient_evidence_count == 1
    assert report.negative_refusal_rate == 1.0
    assert report.mean_latency_ms == 12.0


def test_raw_diagnostic_does_not_claim_sufficiency_or_refusal_metrics():
    observations = tuple(
        _observation(f"answer-{index}", (f"{index}" * 64,), source="answering_store_diagnostic")
        for index in (1, 2, 3)
    ) + (_observation("negative", (), source="answering_store_diagnostic"),)
    report = evaluate_retrieval(_dataset(), observations)
    assert report.hit_at_5 == 1.0
    assert report.false_insufficient_evidence_count is None
    assert report.negative_refusal_rate is None


@pytest.mark.parametrize(
    ("change", "error"),
    [
        ({"profile_id": "other"}, "profile"),
        ({"corpus_sha256": "0" * 64}, "corpus"),
        ({"retrieval_configuration_id": "other"}, "retrieval"),
        ({"chunk_set_ids": ("other",)}, "chunk set"),
        ({"observation_id": ""}, "observation"),
    ],
)
def test_rejects_mismatched_provenance(change, error):
    observations = [_observation(f"answer-{index}", (f"{index}" * 64,)) for index in (1, 2, 3)]
    observations.append(_observation("negative", (), insufficient=True, **change))
    with pytest.raises(ValueError, match=error):
        evaluate_retrieval(_dataset(), observations)


def test_rejects_missing_case_observation():
    with pytest.raises(ValueError, match="missing"):
        evaluate_retrieval(_dataset(), [_observation("answer-1", ("1" * 64,))])


def test_hit_uses_first_of_two_acceptable_chunks():
    dataset = _dataset()
    cases = list(dataset.cases)
    cases[0] = replace(cases[0], acceptable_chunk_checksums=("1" * 64, "z" * 64))
    observations = [
        _observation("answer-1", ("z" * 64,)),
        _observation("answer-2", ("2" * 64,)),
        _observation("answer-3", ("3" * 64,)),
        _observation("negative", (), insufficient=True),
    ]
    assert evaluate_retrieval(replace(dataset, cases=tuple(cases)), observations).hit_at_1 == 1.0


def test_active_corpus_requires_profile_source_page_and_chunk_checksum():
    dataset = _dataset()
    chunks = tuple(
        ActiveChunkBinding("source.pdf", "c" * 64, "set", "profile", 1, f"{index}" * 64)
        for index in (1, 2, 3)
    )
    validate_active_corpus(dataset, chunks)
    with pytest.raises(ValueError, match="label"):
        validate_active_corpus(dataset, chunks[:-1])
    with pytest.raises(ValueError, match="profile"):
        validate_active_corpus(
            dataset,
            (*chunks[:-1], ActiveChunkBinding("source.pdf", "c" * 64, "set", "other", 1, "3" * 64)),
        )
