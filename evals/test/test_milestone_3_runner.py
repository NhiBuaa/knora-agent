from types import SimpleNamespace

import httpx
import pytest
from evals.datasets.milestone_3 import (
    AnswerExpectations,
    EvidenceExpectations,
    Milestone3Case,
    RetrievalRelevance,
)
from evals.runners.milestone_3 import (
    CanonicalChunkReference,
    EvaluationEnvironmentBinding,
    EvaluationEnvironmentSeal,
    M3Observation,
    ObservationFailure,
    ProductionM3Executor,
    PublicCitation,
    SourceBinding,
    VerifiedM3Environment,
    build_report,
    project_trace_candidates,
    score_retrieval,
    semantic_citation_input,
    verify_corpus_closure,
)


def _binding() -> EvaluationEnvironmentBinding:
    return EvaluationEnvironmentBinding(
        dataset_manifest_identity="m3-dataset-v1",
        corpus_manifest_identity="m3-corpus-v1",
        chunk_set_provenance_id="set-1",
        source_bindings=(SourceBinding("support/a", "version-1", "set-1"),),
        workspace_id="workspace",
        retrieval_configuration_id="retrieval-m3-rrf-v1",
    )


def _case(*, case_id: str = "case", applicable: bool = True) -> Milestone3Case:
    return Milestone3Case(
        id=case_id,
        category="lexical_exact_match",
        workspace_id="workspace",
        question="question",
        expected_behavior="ANSWER" if applicable else "REFUSAL",
        retrieval_relevance=RetrievalRelevance(
            applicable=applicable,
            acceptable_relevant_chunks=("support/a#0",) if applicable else (),
        ),
        answer_expectations=AnswerExpectations(("fact",) if applicable else (), None),
        evidence_expectations=EvidenceExpectations(("support/a",), ("support/a#0",)),
        refusal_expectation=None if applicable else "INSUFFICIENT_EVIDENCE",
    )


def _manifest():
    return SimpleNamespace(
        version="m3-corpus-v1",
        workspace_id="workspace",
        chunk_set_id="set-1",
        chunks=frozenset({"support/a#0"}),
    )


def _corpus(*, extra: bool = False):
    documents = [
        SimpleNamespace(
            source_key="support/a",
            document_version_id="version-1",
            chunk_set_id="set-1",
            chunk_references=("support/a#0",),
        )
    ]
    if extra:
        documents.append(
            SimpleNamespace(
                source_key="support/extra",
                document_version_id="version-extra",
                chunk_set_id="set-extra",
                chunk_references=("support/extra#0",),
            )
        )
    return SimpleNamespace(workspace_id="workspace", documents=tuple(documents))


def _environment() -> VerifiedM3Environment:
    return VerifiedM3Environment.prepare(
        binding=_binding(), corpus=_corpus(), manifest=_manifest()
    )


def test_corpus_closure_requires_exact_active_source_set_and_bound_version() -> None:
    verify_corpus_closure(binding=_binding(), corpus=_corpus(), manifest=_manifest())

    with pytest.raises(ObservationFailure, match="CORPUS_CLOSURE_MISMATCH"):
        verify_corpus_closure(binding=_binding(), corpus=_corpus(extra=True), manifest=_manifest())


def test_seal_captures_snapshot_only_after_exclusive_acquire_and_detects_drift() -> None:
    seal = EvaluationEnvironmentSeal(ownership_probe=lambda run_id: run_id == "run-1")
    with pytest.raises(ObservationFailure, match="EVALUATION_SEAL_ACQUIRE_FAILED"):
        seal.acquire(run_id="run-2")
    with pytest.raises(ObservationFailure, match="EVALUATION_SEAL_REQUIRED"):
        seal.capture_preflight(binding=_binding(), corpus=_corpus(), manifest=_manifest())

    seal.acquire(run_id="run-1")
    environment = seal.capture_preflight(
        binding=_binding(), corpus=_corpus(), manifest=_manifest()
    )
    assert environment.binding == _binding()
    seal.verify_unchanged(binding=_binding(), corpus=_corpus(), manifest=_manifest())
    with pytest.raises(ObservationFailure, match="EVALUATION_ENVIRONMENT_DRIFT"):
        seal.verify_unchanged(binding=_binding(), corpus=_corpus(extra=True), manifest=_manifest())
    seal.release()


def test_metric_contract_uses_scoped_canonical_identity_and_uncut_mrr() -> None:
    chunk_set = "set-1"
    case = _case()
    observation = M3Observation.success(
        case_id="case",
        candidates=tuple(
            CanonicalChunkReference(chunk_set, f"support/x{index}", 0) for index in range(1, 9)
        )
        + (CanonicalChunkReference(chunk_set, "support/a", 0),),
        retrieval_latency_ms=3.0,
        end_to_end_latency_ms=9.0,
        retrieval_configuration_id="retrieval-m3-rrf-v1",
        chunk_set_provenance_id=chunk_set,
        source_bindings=_binding().source_bindings,
    )

    report = score_retrieval((case,), (observation,), binding=_binding())

    assert report["metric_contract"] == "m3-retrieval-metrics-v1"
    assert report["recall_k"] == 8
    assert report["recall_at_8"] == 0.0
    assert report["mrr"] == pytest.approx(1 / 9)
    assert report["denominator"] == 1


def test_metric_contract_keeps_valid_miss_but_excludes_inapplicable_and_failure() -> None:
    chunk_set = "set-1"
    applicable = _case(case_id="applicable")
    refusal = _case(case_id="refusal", applicable=False)
    miss = M3Observation.success(
        case_id="applicable",
        candidates=(),
        retrieval_latency_ms=1.0,
        end_to_end_latency_ms=2.0,
        retrieval_configuration_id="retrieval-m3-rrf-v1",
        chunk_set_provenance_id=chunk_set,
        source_bindings=_binding().source_bindings,
    )
    failed = M3Observation.failure("applicable", "TRACE_PROVENANCE_INVALID")

    report = score_retrieval(
        (applicable, refusal),
        (
            miss,
            M3Observation.success(
                case_id="refusal",
                candidates=(),
                retrieval_latency_ms=1.0,
                end_to_end_latency_ms=2.0,
                retrieval_configuration_id="retrieval-m3-rrf-v1",
                chunk_set_provenance_id=chunk_set,
                source_bindings=_binding().source_bindings,
            ),
        ),
        binding=_binding(),
    )
    failed_report = score_retrieval((applicable,), (failed,), binding=_binding())

    assert report["denominator"] == 1
    assert report["recall_at_8"] == 0.0
    assert report["mrr"] == 0.0
    assert failed_report["denominator"] == 0
    assert failed_report["cases"][0]["exclusion_reason"] == "TRACE_PROVENANCE_INVALID"


def test_report_keeps_per_observation_duration_and_failure_without_aggregation() -> None:
    case = _case()
    observation = M3Observation.success(
        case_id="case",
        candidates=(CanonicalChunkReference("set-1", "support/a", 0),),
        retrieval_latency_ms=3.5,
        end_to_end_latency_ms=9.5,
        retrieval_configuration_id="retrieval-m3-rrf-v1",
        chunk_set_provenance_id="set-1",
        source_bindings=_binding().source_bindings,
    )

    report = build_report((case,), (observation,), binding=_binding())

    assert report["retrieval"]["recall_at_8"] == 1.0
    assert report["observations"] == [
        {
            "case_id": "case",
            "status": "observed",
            "retrieval_latency_ms": 3.5,
            "end_to_end_latency_ms": 9.5,
            "retrieval_configuration_id": "retrieval-m3-rrf-v1",
            "chunk_set_provenance_id": "set-1",
            "source_bindings": [
                {
                    "source_key": "support/a",
                    "production_document_version_id": "version-1",
                    "production_chunk_set_id": "set-1",
                }
            ],
        }
    ]


def test_trace_projection_requires_single_matching_chunk_set_and_unique_identity() -> None:
    candidates = (
        SimpleNamespace(
            document_version_id="version-1",
            chunk_set_id="set-1",
            source_key="support/a",
            chunk_ordinal=0,
        ),
        SimpleNamespace(
            document_version_id="version-1",
            chunk_set_id="set-1",
            source_key="support/a",
            chunk_ordinal=0,
        ),
    )

    with pytest.raises(ObservationFailure, match="DUPLICATE_CANONICAL_CHUNK_REFERENCE"):
        project_trace_candidates(candidates, binding=_binding())

    with pytest.raises(ObservationFailure, match="SOURCE_BINDING_MISMATCH"):
        project_trace_candidates(
            (
                SimpleNamespace(
                    document_version_id="version-1",
                    chunk_set_id="other",
                    source_key="support/a",
                    chunk_ordinal=0,
                ),
            ),
            binding=_binding(),
        )


def test_binding_requires_every_manifest_and_environment_identity() -> None:
    with pytest.raises(ObservationFailure, match="EVALUATION_ENVIRONMENT_BINDING_INVALID"):
        EvaluationEnvironmentBinding.from_mapping(
            {"schema_version": 1, "workspace_id": "workspace"}
        )

    binding = EvaluationEnvironmentBinding.from_mapping(
        {"schema_version": 3, **_binding().provenance()}
    )

    assert binding == _binding()


@pytest.mark.parametrize(
    "candidate",
    [
        SimpleNamespace(
            source_key="support/a",
            document_version_id="other",
            chunk_set_id="set-1",
            chunk_ordinal=0,
        ),
        SimpleNamespace(source_key="support/a", chunk_set_id="set-1", chunk_ordinal=0),
        SimpleNamespace(
            source_key="unknown",
            document_version_id="version-1",
            chunk_set_id="set-1",
            chunk_ordinal=0,
        ),
    ],
)
def test_trace_projection_requires_exact_per_source_version_and_chunk_set_binding(
    candidate,
) -> None:
    with pytest.raises(ObservationFailure, match="SOURCE_BINDING_MISMATCH"):
        project_trace_candidates((candidate,), binding=_binding())

    with pytest.raises(ObservationFailure, match="SOURCE_BINDING_MISMATCH"):
        project_trace_candidates(
            (
                SimpleNamespace(
                    document_version_id="version-1", source_key="support/a", chunk_ordinal=0
                ),
            ),
            binding=_binding(),
        )


@pytest.mark.asyncio
async def test_production_executor_uses_response_trace_and_returns_observation_failure() -> None:
    case = _case()

    def handle(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/questions"
        return httpx.Response(
            200,
            json={
                "decision": "ANSWER",
                "answer": "answer [[E1]]",
                "citations": [
                    {
                        "evidence_id": "E1",
                        "source_key": "support/a",
                        "excerpt": "public excerpt",
                        "start_line": 1,
                        "end_line": 2,
                    }
                ],
                "refusal_reason": None,
                "trace_id": "trace-1",
            },
        )

    trace = SimpleNamespace(
        trace_id="trace-1",
        workspace_id="workspace",
        retrieval_configuration_id="retrieval-m3-rrf-v1",
        candidates=(
            SimpleNamespace(
                chunk_id="chunk-1",
                document_version_id="version-1",
                chunk_set_id="set-1",
                source_key="support/a",
                chunk_ordinal=0,
            ),
        ),
        retrieval_latency_ms=4.0,
        alias_mapping={"E1": "chunk-1"},
    )
    calls: list[dict[str, str]] = []
    reader = SimpleNamespace(
        read_trace=lambda **kwargs: calls.append(kwargs) or trace,
    )
    client = httpx.AsyncClient(transport=httpx.MockTransport(handle))
    executor = ProductionM3Executor(
        endpoint="http://knora.test/v1/questions",
        api_key="secret",
        trace_reader=reader,
        client=client,
        environment=_environment(),
    )

    observation = await executor.execute(case)
    await client.aclose()

    assert calls == [{"trace_id": "trace-1", "workspace_id": "workspace"}]
    assert observation.is_success
    assert observation.candidates == (CanonicalChunkReference("set-1", "support/a", 0),)
    assert observation.retrieval_latency_ms == 4.0
    assert observation.end_to_end_latency_ms is not None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("trace_update", "expected_failure"),
    [
        ({"trace_id": "other"}, "RESPONSE_TRACE_ID_MISMATCH"),
        ({"workspace_id": "other"}, "TRACE_WORKSPACE_MISMATCH"),
        ({"retrieval_configuration_id": "other"}, "RETRIEVAL_CONFIGURATION_MISMATCH"),
        ({"retrieval_latency_ms": None}, "RETRIEVAL_LATENCY_INVALID"),
    ],
)
async def test_production_executor_excludes_invalid_trace_observations(
    trace_update: dict[str, object], expected_failure: str
) -> None:
    case = _case()

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
                        "excerpt": "public excerpt",
                        "start_line": 1,
                        "end_line": 2,
                    }
                ],
                "refusal_reason": None,
                "trace_id": "trace-1",
            },
        )

    trace_values: dict[str, object] = {
        "trace_id": "trace-1",
        "workspace_id": "workspace",
        "retrieval_configuration_id": "retrieval-m3-rrf-v1",
        "candidates": (
            SimpleNamespace(
                chunk_id="chunk-1",
                document_version_id="version-1",
                chunk_set_id="set-1",
                source_key="support/a",
                chunk_ordinal=0,
            ),
        ),
        "retrieval_latency_ms": 4.0,
        "alias_mapping": {"E1": "chunk-1"},
    }
    trace_values.update(trace_update)
    reader = SimpleNamespace(read_trace=lambda **_kwargs: SimpleNamespace(**trace_values))
    client = httpx.AsyncClient(transport=httpx.MockTransport(handle))
    executor = ProductionM3Executor(
        endpoint="http://knora.test/v1/questions",
        api_key="secret",
        trace_reader=reader,
        client=client,
        environment=_environment(),
    )

    observation = await executor.execute(case)
    await client.aclose()

    assert observation.is_success is False
    assert observation.failure_code == expected_failure


@pytest.mark.asyncio
async def test_production_executor_never_repairs_invalid_public_citations_from_trace() -> None:
    case = _case()

    def handle(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "decision": "ANSWER",
                "answer": "answer [[E1]]",
                "citations": [],
                "refusal_reason": None,
                "trace_id": "trace-1",
            },
        )

    reader = SimpleNamespace(
        read_trace=lambda **_kwargs: SimpleNamespace(
            trace_id="trace-1",
            workspace_id="workspace",
            retrieval_configuration_id="retrieval-m3-rrf-v1",
            candidates=(),
            retrieval_latency_ms=1.0,
            alias_mapping={},
        )
    )
    client = httpx.AsyncClient(transport=httpx.MockTransport(handle))
    executor = ProductionM3Executor(
        endpoint="http://knora.test/v1/questions",
        api_key="secret",
        trace_reader=reader,
        client=client,
        environment=_environment(),
    )

    observation = await executor.execute(case)
    await client.aclose()

    assert observation.failure_code == "CITATION_STRUCTURAL_ERROR"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "alias_mapping",
    [
        {},
        {"E1": "missing-evidence"},
        {"E1": "other-request-chunk"},
    ],
)
async def test_public_alias_must_map_to_evidence_of_correlated_trace(
    alias_mapping: dict[str, str],
) -> None:
    case = _case()

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
                        "excerpt": "public",
                        "start_line": 1,
                        "end_line": 1,
                    }
                ],
                "trace_id": "trace-1",
                "refusal_reason": None,
            },
        )

    trace = SimpleNamespace(
        trace_id="trace-1",
        workspace_id="workspace",
        retrieval_configuration_id="retrieval-m3-rrf-v1",
        retrieval_latency_ms=1.0,
        candidates=(
            SimpleNamespace(
                chunk_id="chunk-1",
                document_version_id="version-1",
                chunk_set_id="set-1",
                source_key="support/a",
                chunk_ordinal=0,
            ),
        ),
        alias_mapping=alias_mapping,
    )
    client = httpx.AsyncClient(transport=httpx.MockTransport(handle))
    observation = await ProductionM3Executor(
        endpoint="http://knora.test/v1/questions",
        api_key="secret",
        trace_reader=SimpleNamespace(read_trace=lambda **_kwargs: trace),
        client=client,
        environment=_environment(),
    ).execute(case)
    await client.aclose()

    assert observation.failure_code == "CITATION_STRUCTURAL_ERROR"


def test_semantic_input_uses_only_public_answer_and_citation_projection() -> None:
    observation = M3Observation.success(
        case_id="case",
        candidates=(CanonicalChunkReference("set-1", "hidden", 0),),
        retrieval_latency_ms=1.0,
        end_to_end_latency_ms=2.0,
        retrieval_configuration_id="retrieval-m3-rrf-v1",
        chunk_set_provenance_id="set-1",
        source_bindings=_binding().source_bindings,
        public_answer="public answer",
        public_citations=(PublicCitation("E1", "support/a", "public excerpt", "support/a:1:2"),),
    )

    assert semantic_citation_input(observation) == {
        "answer": "public answer",
        "citations": [
            {
                "evidence_id": "E1",
                "excerpt": "public excerpt",
                "source_locator": "support/a:1:2",
            }
        ],
    }


def test_observation_failure_cannot_enter_semantic_evaluation() -> None:
    with pytest.raises(ObservationFailure, match="SEMANTIC_INPUT_UNAVAILABLE"):
        semantic_citation_input(M3Observation.failure("case", "RESPONSE_TRACE_ID_MISMATCH"))
