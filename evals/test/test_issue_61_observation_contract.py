from types import SimpleNamespace

import httpx
import pytest
from evals.runners.milestone_3 import (
    M3Observation,
    ObservationFailure,
    ProductionM3Executor,
    validate_public_response,
)


def test_public_refusal_is_validated_and_retained_for_refusal_correctness() -> None:
    projection = validate_public_response(
        {
            "decision": "REFUSAL",
            "answer": None,
            "citations": [],
            "refusal_reason": "INSUFFICIENT_EVIDENCE",
            "trace_id": "trace-1",
        }
    )

    observation = M3Observation.success(
        case_id="refusal",
        candidates=(),
        retrieval_latency_ms=1.0,
        end_to_end_latency_ms=2.0,
        retrieval_configuration_id="retrieval-m3-rrf-v1",
        chunk_set_provenance_id="set-1",
        source_bindings=(),
        decision=projection.decision,
        public_answer=projection.answer,
        refusal_reason=projection.refusal_reason,
        refusal_correctness=True,
    )

    assert observation.decision == "REFUSAL"
    assert observation.refusal_reason == "INSUFFICIENT_EVIDENCE"
    assert observation.refusal_correctness is True


def test_malformed_refusal_fails_without_refusal_correctness() -> None:
    with pytest.raises(ObservationFailure, match="PUBLIC_RESPONSE_INVALID"):
        validate_public_response(
            {
                "decision": "REFUSAL",
                "answer": "not-null",
                "citations": [],
                "refusal_reason": "INSUFFICIENT_EVIDENCE",
                "trace_id": "trace-1",
            }
        )


def test_success_observation_requires_validated_public_response_contract() -> None:
    with pytest.raises(ValueError, match="public response is invalid"):
        M3Observation.success(
            case_id="case",
            candidates=(),
            retrieval_latency_ms=1.0,
            end_to_end_latency_ms=2.0,
            retrieval_configuration_id="retrieval-m3-rrf-v1",
            chunk_set_provenance_id="set-1",
            source_bindings=(),
        )


def test_direct_incomplete_observation_is_not_a_success() -> None:
    assert M3Observation(case_id="case").is_success is False


def test_refusal_requires_explicit_null_answer_field() -> None:
    with pytest.raises(ObservationFailure, match="PUBLIC_RESPONSE_INVALID"):
        validate_public_response(
            {
                "decision": "REFUSAL",
                "citations": [],
                "refusal_reason": "INSUFFICIENT_EVIDENCE",
                "trace_id": "trace-1",
            }
        )


@pytest.mark.asyncio
async def test_executor_accepts_reader_tuple_markers_at_postgres_seam() -> None:
    def handle(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "decision": "REFUSAL",
                "answer": None,
                "citations": [],
                "refusal_reason": "INSUFFICIENT_EVIDENCE",
                "trace_id": "trace-tuple",
            },
        )

    binding = SimpleNamespace(
        workspace_id="workspace",
        retrieval_configuration_id="retrieval-m3-rrf-v1",
        embedding_configuration_id="embedding-local-m1-v2",
        chunk_set_provenance_id="set-1",
        source_bindings=(),
    )
    trace = _answer_trace(
        trace_id="trace-tuple",
        decision="REFUSAL",
        answer=None,
        refusal_reason="INSUFFICIENT_EVIDENCE",
        parsed_markers=(),
        candidates=(),
        alias_mapping={},
    )
    client = httpx.AsyncClient(transport=httpx.MockTransport(handle))
    observation = await ProductionM3Executor(
        endpoint="http://knora.test/v1/questions",
        api_key="secret",
        trace_reader=SimpleNamespace(read_trace=lambda **_kwargs: trace),
        client=client,
        environment=SimpleNamespace(binding=binding),
        clock=iter((0.0, 0.010)).__next__,
        clock_resolution_ms=1.0,
    ).execute(
        SimpleNamespace(
            id="refusal",
            workspace_id="workspace",
            question="question",
            refusal_expectation="INSUFFICIENT_EVIDENCE",
        )
    )
    await client.aclose()

    assert observation.is_success
    assert observation.refusal_correctness is True


@pytest.mark.asyncio
async def test_executor_rejects_embedding_configuration_mismatch() -> None:
    def handle(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "decision": "REFUSAL",
                "answer": None,
                "citations": [],
                "refusal_reason": "INSUFFICIENT_EVIDENCE",
                "trace_id": "trace-embedding",
            },
        )

    trace = _answer_trace(
        trace_id="trace-embedding",
        decision="REFUSAL",
        answer=None,
        refusal_reason="INSUFFICIENT_EVIDENCE",
        parsed_markers=(),
        candidates=(),
        alias_mapping={},
        embedding_configuration_id="embedding-other",
    )
    binding = SimpleNamespace(
        workspace_id="workspace",
        retrieval_configuration_id="retrieval-m3-rrf-v1",
        embedding_configuration_id="embedding-expected",
        chunk_set_provenance_id="set-1",
        source_bindings=(),
    )
    client = httpx.AsyncClient(transport=httpx.MockTransport(handle))
    observation = await ProductionM3Executor(
        endpoint="http://knora.test/v1/questions",
        api_key="secret",
        trace_reader=SimpleNamespace(read_trace=lambda **_kwargs: trace),
        client=client,
        environment=SimpleNamespace(binding=binding),
        clock=iter((0.0, 0.010)).__next__,
        clock_resolution_ms=1.0,
    ).execute(
        SimpleNamespace(
            id="refusal",
            workspace_id="workspace",
            question="question",
            refusal_expectation="INSUFFICIENT_EVIDENCE",
        )
    )
    await client.aclose()

    assert observation.failure_code == "EMBEDDING_CONFIGURATION_MISMATCH"


@pytest.mark.asyncio
async def test_executor_rejects_missing_embedding_configuration_binding() -> None:
    def handle(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "decision": "REFUSAL",
                "answer": None,
                "citations": [],
                "refusal_reason": "INSUFFICIENT_EVIDENCE",
                "trace_id": "trace-missing-embedding",
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handle))
    observation = await ProductionM3Executor(
        endpoint="http://knora.test/v1/questions",
        api_key="secret",
        trace_reader=SimpleNamespace(
            read_trace=lambda **_kwargs: pytest.fail("trace must not be read")
        ),
        client=client,
        environment=SimpleNamespace(
            binding=SimpleNamespace(
                workspace_id="workspace",
                retrieval_configuration_id="retrieval-m3-rrf-v1",
                chunk_set_provenance_id="set-1",
                source_bindings=(),
            )
        ),
        clock=iter((0.0, 0.010)).__next__,
        clock_resolution_ms=1.0,
    ).execute(
        SimpleNamespace(
            id="refusal",
            workspace_id="workspace",
            question="question",
            refusal_expectation="INSUFFICIENT_EVIDENCE",
        )
    )
    await client.aclose()

    assert observation.failure_code == "EVALUATION_ENVIRONMENT_BINDING_INVALID"


def test_citation_alias_must_map_to_selected_fused_candidate() -> None:
    from evals.runners.milestone_3 import _validate_public_citation_aliases

    excluded = SimpleNamespace(chunk_id="chunk-1", final_decision="BUDGET_EXCEEDED")
    with pytest.raises(ObservationFailure, match="CITATION_STRUCTURAL_ERROR"):
        _validate_public_citation_aliases(
            citation_ids=("E1",),
            alias_mapping={"E1": "chunk-1"},
            candidates=(excluded,),
        )


def test_citation_aliases_must_map_one_to_one_to_selected_candidates() -> None:
    from evals.runners.milestone_3 import _validate_public_citation_aliases

    selected = (
        SimpleNamespace(chunk_id="chunk-1", final_decision="SELECTED"),
        SimpleNamespace(chunk_id="chunk-2", final_decision="SELECTED"),
    )
    with pytest.raises(ObservationFailure, match="CITATION_STRUCTURAL_ERROR"):
        _validate_public_citation_aliases(
            citation_ids=("E1", "E2"),
            alias_mapping={"E1": "chunk-1", "E2": "chunk-1"},
            candidates=selected,
        )


def test_valid_answer_requires_marker_and_citation_order() -> None:
    projection = validate_public_response(
        {
            "decision": "ANSWER",
            "answer": "fact [[E1]]",
            "citations": [
                {
                    "evidence_id": "E1",
                    "source_key": "support/a",
                    "excerpt": "fact",
                    "start_line": 1,
                    "end_line": 1,
                }
            ],
            "refusal_reason": None,
            "trace_id": "trace-1",
        }
    )
    assert projection.decision == "ANSWER"
    assert projection.citation_evidence_ids == ("E1",)
    assert projection.answer_marker_ids == ("E1",)


def test_public_answer_rejects_unknown_marker_token() -> None:
    with pytest.raises(ObservationFailure, match="CITATION_STRUCTURAL_ERROR"):
        validate_public_response(
            {
                "decision": "ANSWER",
                "answer": "fact [[E1]] [[X1]]",
                "citations": [
                    {
                        "evidence_id": "E1",
                        "source_key": "support/a",
                        "excerpt": "fact",
                        "start_line": 1,
                        "end_line": 1,
                    }
                ],
                "refusal_reason": None,
                "trace_id": "trace-1",
            }
        )


def _answer_trace(**updates: object) -> SimpleNamespace:
    values: dict[str, object] = {
        "trace_id": "trace-1",
        "workspace_id": "workspace",
        "retrieval_configuration_id": "retrieval-m3-rrf-v1",
        "embedding_configuration_id": "embedding-local-m1-v2",
        "decision": "ANSWER",
        "answer": "answer [[E1]]",
        "refusal_reason": None,
        "parsed_markers": ["E1"],
        "candidates": (),
        "retrieval_latency_ms": 4.0,
        "alias_mapping": {},
    }
    values.update(updates)
    return SimpleNamespace(**values)


@pytest.mark.asyncio
async def test_executor_measures_end_to_end_only_through_http_response() -> None:
    def handle(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "decision": "ANSWER",
                "answer": "answer [[E1]]",
                "citations": [
                    {
                        "evidence_id": "E1",
                        "source_key": "support/a",
                        "excerpt": "answer",
                        "start_line": 1,
                        "end_line": 1,
                    }
                ],
                "refusal_reason": None,
                "trace_id": "trace-1",
            },
        )

    class DelayedReader:
        def read_trace(self, **_kwargs: object) -> SimpleNamespace:
            import time

            time.sleep(0.05)
            return _answer_trace(
                candidates=(
                    SimpleNamespace(
                        chunk_id="chunk-1",
                        document_version_id="version-1",
                        chunk_set_id="set-1",
                        source_key="support/a",
                        chunk_ordinal=0,
                        start_line=1,
                        end_line=1,
                        final_decision="SELECTED",
                    ),
                ),
                alias_mapping={"E1": "chunk-1"},
            )

    ticks = iter((0.0, 0.010))
    binding = SimpleNamespace(
        workspace_id="workspace",
        retrieval_configuration_id="retrieval-m3-rrf-v1",
        embedding_configuration_id="embedding-local-m1-v2",
        chunk_set_provenance_id="set-1",
        source_bindings=(
            SimpleNamespace(
                source_key="support/a",
                production_document_version_id="version-1",
                production_chunk_set_id="set-1",
            ),
        ),
    )
    binding.source_binding = lambda source_key: next(
        item for item in binding.source_bindings if item.source_key == source_key
    )
    client = httpx.AsyncClient(transport=httpx.MockTransport(handle))
    observation = await ProductionM3Executor(
        endpoint="http://knora.test/v1/questions",
        api_key="secret",
        trace_reader=DelayedReader(),
        client=client,
        environment=SimpleNamespace(binding=binding),
        clock=lambda: next(ticks),
        clock_resolution_ms=1.0,
    ).execute(
        SimpleNamespace(
            id="case",
            workspace_id="workspace",
            question="question",
            refusal_expectation=None,
        )
    )
    await client.aclose()

    assert observation.end_to_end_latency_ms == 10.0


@pytest.mark.asyncio
async def test_executor_rejects_nonfinite_retrieval_latency() -> None:
    def handle(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "decision": "REFUSAL",
                "answer": None,
                "citations": [],
                "refusal_reason": "INSUFFICIENT_EVIDENCE",
                "trace_id": "trace-1",
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handle))
    observation = await ProductionM3Executor(
        endpoint="http://knora.test/v1/questions",
        api_key="secret",
        trace_reader=SimpleNamespace(
            read_trace=lambda **_kwargs: _answer_trace(
                decision="REFUSAL",
                answer=None,
                refusal_reason="INSUFFICIENT_EVIDENCE",
                parsed_markers=[],
                candidates=(),
                retrieval_latency_ms=float("nan"),
            )
        ),
        client=client,
        environment=SimpleNamespace(
            binding=SimpleNamespace(
                workspace_id="workspace",
                retrieval_configuration_id="retrieval-m3-rrf-v1",
                embedding_configuration_id="embedding-local-m1-v2",
                chunk_set_provenance_id="set-1",
                source_bindings=(),
            )
        ),
        clock=iter((0.0, 0.010)).__next__,
        clock_resolution_ms=1.0,
    ).execute(
        SimpleNamespace(
            id="case",
            workspace_id="workspace",
            question="question",
            refusal_expectation=None,
        )
    )
    await client.aclose()

    assert observation.failure_code == "RETRIEVAL_LATENCY_INVALID"
