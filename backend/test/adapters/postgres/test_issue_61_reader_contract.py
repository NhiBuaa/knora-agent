import math
from types import SimpleNamespace

import pytest

from knora.adapters.postgres.evaluation_reader import (
    _ordered_candidate_ids,
    _retrieval_latency,
    _validate_branch_observations,
    _validate_candidate_budget_evidence,
    _validate_embedding_provenance,
    _validate_trace_metadata,
)


def _phase_timing(*, retrieval_latency_ms: float = 2.0) -> dict[str, object]:
    return {
        "retrieval": {"latency_ms": retrieval_latency_ms},
        "timing": {
            "clock_resolution_ms": 1.0,
            "phases": {
                "query_embedding": {"start_tick": 0.0, "end_tick": 0.0, "duration_ms": 0.0},
                "candidate_retrieval": {
                    "start_tick": 0.0,
                    "end_tick": 0.001,
                    "duration_ms": 1.0,
                },
                "evidence_selection": {
                    "start_tick": 0.001,
                    "end_tick": 0.002,
                    "duration_ms": 1.0,
                },
                "generation": {"start_tick": 0.002, "end_tick": 0.002, "duration_ms": 0.0},
            },
        },
    }


def _trace(**updates: object) -> SimpleNamespace:
    values: dict[str, object] = {
        "trace_schema_version": 2,
        "branch_observation_schema_version": 1,
        "question": "What is the refund period?",
        "retrieval_configuration_id": "retrieval-m3-rrf-v1",
        "embedding_configuration_id": "embedding-local-m1-v2",
        "embedding_set_ids": ["embedding-set-1"],
        "chunk_set_ids": ["chunk-set-1"],
        "fusion_policy_version": "rrf-v1",
        "candidate_decisions": [],
        "branch_observations": [
            {
                "schema_version": 1,
                "branch": "vector",
                "status": "NO_CONTRIBUTION",
                "chunk_id": None,
                "branch_rank": None,
                "cosine_distance": None,
                "similarity": None,
                "native_rank": None,
                "lexical_policy_id": None,
                "normalized_lexemes": [],
                "omitted_lexemes": [],
            },
            {
                "schema_version": 1,
                "branch": "fts",
                "status": "INELIGIBLE",
                "chunk_id": None,
                "branch_rank": None,
                "cosine_distance": None,
                "similarity": None,
                "native_rank": None,
                "lexical_policy_id": "fts-v1",
                "normalized_lexemes": [],
                "omitted_lexemes": [],
            },
        ],
        "provider_metadata": _phase_timing(),
        "decision": "REFUSAL",
        "answer": None,
        "refusal_reason": "INSUFFICIENT_EVIDENCE",
        "parsed_markers": [],
    }
    values.update(updates)
    return SimpleNamespace(**values)


def test_reader_accepts_authority_decisions_and_reasons() -> None:
    decisions = [
        {
            "chunk_id": "selected",
            "final_rank": 1,
            "fusion_score": 1 / 61,
            "final_decision": "SELECTED",
            "decision_reason": None,
            "vector_contribution": {
                "branch_rank": 1,
                "cosine_distance": 0.1,
                "similarity": 0.9,
            },
            "fts_contribution": None,
        },
        {
            "chunk_id": "budget",
            "final_rank": 2,
            "fusion_score": 1 / 62,
            "final_decision": "BUDGET_EXCEEDED",
            "decision_reason": "TOKEN_BUDGET",
            "budget_evidence": {
                "max_evidence_chunks": 5,
                "max_evidence_tokens": 3000,
                "selected_chunk_count": 1,
                "selected_token_count": 2000,
                "candidate_token_count": 1500,
                "token_total": 3500,
            },
            "vector_contribution": {
                "branch_rank": 2,
                "cosine_distance": 0.2,
                "similarity": 0.8,
            },
            "fts_contribution": None,
        },
    ]

    assert _ordered_candidate_ids(decisions) == ["selected", "budget"]


@pytest.mark.parametrize(
    ("decision_reason", "budget_evidence"),
    [
        (
            "CHUNK_COUNT_LIMIT",
            {
                "max_evidence_chunks": 5,
                "max_evidence_tokens": 3000,
                "selected_chunk_count": 1,
                "selected_token_count": 2000,
                "candidate_token_count": 1500,
                "token_total": 3500,
            },
        ),
        (
            "TOKEN_BUDGET",
            {
                "max_evidence_chunks": 5,
                "max_evidence_tokens": 3000,
                "selected_chunk_count": 5,
                "selected_token_count": 2500,
                "candidate_token_count": 1000,
                "token_total": 3500,
            },
        ),
    ],
)
def test_reader_rejects_swapped_budget_reason(
    decision_reason: str, budget_evidence: dict[str, int]
) -> None:
    with pytest.raises(LookupError, match="candidate decision is invalid"):
        _ordered_candidate_ids(
            [
                {
                    "chunk_id": "budget",
                    "final_rank": 1,
                    "fusion_score": 1 / 61,
                    "final_decision": "BUDGET_EXCEEDED",
                    "decision_reason": decision_reason,
                    "budget_evidence": budget_evidence,
                    "vector_contribution": {
                        "branch_rank": 1,
                        "cosine_distance": 0.1,
                        "similarity": 0.9,
                    },
                    "fts_contribution": None,
                }
            ]
        )


def test_reader_rejects_budget_evidence_not_bound_to_chunk_token_count() -> None:
    decisions = [
        {
            "chunk_id": "budget",
            "final_rank": 1,
            "fusion_score": 1 / 61,
            "final_decision": "BUDGET_EXCEEDED",
            "decision_reason": "TOKEN_BUDGET",
            "budget_evidence": {
                "max_evidence_chunks": 5,
                "max_evidence_tokens": 3000,
                "selected_chunk_count": 1,
                "selected_token_count": 2000,
                "candidate_token_count": 1500,
                "token_total": 3500,
            },
            "vector_contribution": {
                "branch_rank": 1,
                "cosine_distance": 0.1,
                "similarity": 0.9,
            },
            "fts_contribution": None,
        }
    ]
    with pytest.raises(LookupError, match="budget evidence is invalid"):
        _validate_candidate_budget_evidence(
            decisions,
            {"budget": (SimpleNamespace(token_count=1499), object(), object())},
        )


@pytest.mark.parametrize(
    "decision",
    [
        {"chunk_id": "unknown", "final_rank": 1, "final_decision": "UNKNOWN"},
        {
            "chunk_id": "unknown-reason",
            "final_rank": 1,
            "final_decision": "BUDGET_EXCEEDED",
            "decision_reason": "UNKNOWN",
        },
    ],
)
def test_reader_rejects_unknown_decision_or_reason(decision: dict[str, object]) -> None:
    with pytest.raises(LookupError, match="candidate decision is invalid"):
        _ordered_candidate_ids([decision])


def test_reader_rejects_budget_decision_without_authority_reason() -> None:
    with pytest.raises(LookupError, match="candidate decision is invalid"):
        _ordered_candidate_ids(
            [
                {
                    "chunk_id": "budget-no-reason",
                    "final_rank": 1,
                    "fusion_score": 1 / 61,
                    "final_decision": "BUDGET_EXCEEDED",
                    "decision_reason": None,
                    "vector_contribution": {
                        "branch_rank": 1,
                        "cosine_distance": 0.1,
                        "similarity": 0.9,
                    },
                    "fts_contribution": None,
                }
            ]
        )


def test_reader_rejects_incomplete_branch_contribution() -> None:
    with pytest.raises(LookupError, match="candidate decision is invalid"):
        _ordered_candidate_ids(
            [
                {
                    "chunk_id": "chunk-1",
                    "final_rank": 1,
                    "fusion_score": 1 / 61,
                    "final_decision": "SELECTED",
                    "decision_reason": None,
                    "vector_contribution": {"branch_rank": 1, "similarity": 0.9},
                    "fts_contribution": None,
                }
            ]
        )


def test_reader_validates_versioned_branch_observations() -> None:
    _validate_branch_observations(
        [
            {
                "schema_version": 1,
                "branch": "vector",
                    "status": "BELOW_THRESHOLD",
                    "chunk_id": "chunk-1",
                    "cosine_distance": 0.7,
                    "similarity": 0.3,
                    "normalized_lexemes": [],
                    "omitted_lexemes": [],
            }
        ]
    )

    with pytest.raises(LookupError, match="branch observation is invalid"):
        _validate_branch_observations(
            [
                {
                    "schema_version": 1,
                    "branch": "vector",
                    "status": "UNKNOWN",
                    "chunk_id": "chunk-1",
                }
            ]
        )


@pytest.mark.parametrize("status", ["BELOW_THRESHOLD", "INELIGIBLE"])
def test_reader_rejects_branch_rank_on_non_eligible_observation(status: str) -> None:
    branch = "vector" if status == "BELOW_THRESHOLD" else "fts"
    observation = {
        "schema_version": 1,
        "branch": branch,
        "status": status,
        "chunk_id": "chunk-1",
        "branch_rank": 1,
        "normalized_lexemes": [],
        "omitted_lexemes": [],
    }
    if branch == "vector":
        observation.update({"cosine_distance": 0.7, "similarity": 0.3})
    else:
        observation.update(
            {"native_rank": None, "lexical_policy_id": "fts-bm25-v1"}
        )

    with pytest.raises(LookupError, match="branch observation is invalid"):
        _validate_branch_observations([observation])


def test_reader_rejects_missing_branch_observations() -> None:
    with pytest.raises(LookupError, match="branch observation is invalid"):
        _validate_branch_observations([])


def test_reader_rejects_unknown_lexical_policy() -> None:
    with pytest.raises(LookupError, match="branch observation is invalid"):
        _validate_branch_observations(
            [
                {
                    "schema_version": 1,
                    "branch": "fts",
                    "status": "ELIGIBLE",
                    "chunk_id": "chunk-1",
                    "branch_rank": 1,
                    "native_rank": 0.5,
                    "lexical_policy_id": "fts-unknown",
                    "normalized_lexemes": ["refund"],
                    "omitted_lexemes": [],
                }
            ]
        )


def test_reader_rejects_nonfinite_retrieval_latency() -> None:
    with pytest.raises(LookupError, match="retrieval latency is invalid"):
        _retrieval_latency({"retrieval": {"latency_ms": math.nan}})


def test_reader_rejects_unknown_fusion_policy_provenance() -> None:
    with pytest.raises(LookupError, match="trace provenance is invalid"):
        _validate_trace_metadata(_trace(fusion_policy_version="made-up"))


def test_reader_rejects_retrieval_latency_outside_phase_boundary() -> None:
    with pytest.raises(LookupError, match="retrieval latency is invalid"):
        _validate_trace_metadata(_trace(provider_metadata=_phase_timing(retrieval_latency_ms=99.0)))


def test_reader_rejects_fused_candidate_without_branch_contribution() -> None:
    with pytest.raises(LookupError, match="candidate decision is invalid"):
        _ordered_candidate_ids(
            [
                {
                    "chunk_id": "chunk-1",
                    "final_rank": 1,
                    "fusion_score": 0.0,
                    "final_decision": "SELECTED",
                    "decision_reason": None,
                    "vector_contribution": None,
                    "fts_contribution": None,
                }
            ]
        )


def test_reader_rejects_contribution_without_matching_eligible_observation() -> None:
    trace = _trace(
        candidate_decisions=[
            {
                "chunk_id": "chunk-1",
                "final_rank": 1,
                "fusion_score": 1 / 61,
                "final_decision": "SELECTED",
                "decision_reason": None,
                "vector_contribution": {
                    "branch_rank": 1,
                    "cosine_distance": 0.1,
                    "similarity": 0.9,
                },
                "fts_contribution": None,
            }
        ],
        branch_observations=[
            {
                "schema_version": 1,
                "branch": "vector",
                "status": "NO_CONTRIBUTION",
                "chunk_id": "chunk-1",
                "branch_rank": None,
                "cosine_distance": None,
                "similarity": None,
                "native_rank": None,
                "lexical_policy_id": None,
                "normalized_lexemes": [],
                "omitted_lexemes": [],
            },
            {
                "schema_version": 1,
                "branch": "fts",
                "status": "INELIGIBLE",
                "chunk_id": "chunk-1",
                "branch_rank": None,
                "cosine_distance": None,
                "similarity": None,
                "native_rank": None,
                "lexical_policy_id": "fts-v1",
                "normalized_lexemes": [],
                "omitted_lexemes": [],
            },
        ],
    )

    with pytest.raises(LookupError, match="candidate decision is invalid"):
        _validate_trace_metadata(trace)


def test_reader_rejects_embedding_set_with_unrelated_configuration() -> None:
    with pytest.raises(LookupError, match="trace provenance is invalid"):
        _validate_embedding_provenance(
            embedding_set_ids=["embedding-set-1"],
            chunk_set_ids=["chunk-set-1"],
            embedding_configuration_id="embedding-local-m1-v2",
            rows=[("embedding-set-1", "chunk-set-1", "embedding-other")],
        )


def test_reader_rejects_fabricated_lexical_provenance() -> None:
    trace = _trace(
        retrieval_configuration_id="retrieval-m3-rrf-v2",
        fusion_policy_version="rrf-v2",
        branch_observations=[
            {
                "schema_version": 1,
                "branch": "vector",
                "status": "NO_CONTRIBUTION",
                "chunk_id": None,
                "branch_rank": None,
                "cosine_distance": None,
                "similarity": None,
                "native_rank": None,
                "lexical_policy_id": None,
                "normalized_lexemes": [],
                "omitted_lexemes": [],
            },
            {
                "schema_version": 1,
                "branch": "fts",
                "status": "INELIGIBLE",
                "chunk_id": None,
                "branch_rank": None,
                "cosine_distance": None,
                "similarity": None,
                "native_rank": None,
                "lexical_policy_id": "fts-m3-or-v2",
                "normalized_lexemes": ["fabricated"],
                "omitted_lexemes": [],
            },
        ],
    )

    with pytest.raises(LookupError, match="trace provenance is invalid"):
        _validate_trace_metadata(trace)


def test_reader_accepts_exact_m3_lexical_provenance() -> None:
    trace = _trace(
        retrieval_configuration_id="retrieval-m3-rrf-v2",
        fusion_policy_version="rrf-v2",
        branch_observations=[
            {
                "schema_version": 1,
                "branch": "vector",
                "status": "NO_CONTRIBUTION",
                "chunk_id": None,
                "branch_rank": None,
                "cosine_distance": None,
                "similarity": None,
                "native_rank": None,
                "lexical_policy_id": None,
                "normalized_lexemes": [],
                "omitted_lexemes": [],
            },
            {
                "schema_version": 1,
                "branch": "fts",
                "status": "INELIGIBLE",
                "chunk_id": None,
                "branch_rank": None,
                "cosine_distance": None,
                "similarity": None,
                "native_rank": None,
                "lexical_policy_id": "fts-m3-or-v2",
                "normalized_lexemes": ["refund", "period"],
                "omitted_lexemes": ["what", "is", "the"],
            },
        ],
    )

    _validate_trace_metadata(trace)


def test_reader_rejects_lexical_fields_on_vector_observation() -> None:
    trace = _trace(
        branch_observations=[
            {
                "schema_version": 1,
                "branch": "vector",
                "status": "NO_CONTRIBUTION",
                "chunk_id": None,
                "branch_rank": None,
                "cosine_distance": None,
                "similarity": None,
                "native_rank": None,
                "lexical_policy_id": None,
                "normalized_lexemes": ["refund"],
                "omitted_lexemes": [],
            },
            {
                "schema_version": 1,
                "branch": "fts",
                "status": "INELIGIBLE",
                "chunk_id": None,
                "branch_rank": None,
                "cosine_distance": None,
                "similarity": None,
                "native_rank": None,
                "lexical_policy_id": "fts-v1",
                "normalized_lexemes": [],
                "omitted_lexemes": [],
            },
        ],
    )

    with pytest.raises(LookupError, match="trace provenance is invalid"):
        _validate_trace_metadata(trace)
