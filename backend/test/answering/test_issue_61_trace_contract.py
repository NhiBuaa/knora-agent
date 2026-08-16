from dataclasses import dataclass, replace

import pytest

from knora.answering.interface import QuestionCommand
from knora.answering.module import AnswerQuestion
from knora.answering.stores import (
    BranchObservation,
    QuestionTraceRecord,
    RetrievalCandidate,
    RetrievalConfiguration,
    RetrievalResult,
)
from knora.domain.access import WorkspacePrincipal
from knora.providers.embedding import EmbeddingBatch, EmbeddingConfiguration
from knora.providers.generation import GenerationResult


def _candidate(*, token_count: int = 1) -> RetrievalCandidate:
    return RetrievalCandidate(
        document_id="document-1",
        document_version_id="version-1",
        source_key="support/a",
        source_name="a.txt",
        chunk_set_id="chunk-set-1",
        embedding_set_id="embedding-set-1",
        embedding_configuration_id="embedding-local-m1-v2",
        chunk_id="chunk-1",
        chunk_ordinal=0,
        heading_path=(),
        start_line=1,
        end_line=1,
        content="fact",
        content_checksum="sha256:fact",
        token_count=token_count,
        cosine_distance=0.1,
        similarity=0.9,
        fusion_score=1 / 61,
        vector_contribution={"branch_rank": 1, "similarity": 0.9},
    )


class EmbeddingProvider:
    def embed(self, texts, configuration):
        return EmbeddingBatch(
            vectors=(tuple([0.0] * configuration.dimensions),),
            provider=configuration.provider,
            model=configuration.model,
        )


class GenerationProvider:
    async def generate(self, **kwargs) -> GenerationResult:
        return GenerationResult(
            decision="ANSWER",
            answer="fact [[E1]]",
            cited_evidence_ids=("E1",),
            refusal_reason=None,
            provider="deterministic-local",
            model="test",
            prompt_version="test-v1",
        )


class RefusalGenerationProvider:
    async def generate(self, **kwargs) -> GenerationResult:
        return GenerationResult(
            decision="REFUSAL",
            answer=None,
            cited_evidence_ids=(),
            refusal_reason="INSUFFICIENT_EVIDENCE",
            provider="deterministic-local",
            model="test",
            prompt_version="test-v1",
        )


@dataclass
class ResultStore:
    retrieval: RetrievalResult
    traces: list[QuestionTraceRecord]

    def retrieve_candidates(self, **kwargs):
        return self.retrieval

    def persist_trace(self, trace: QuestionTraceRecord) -> str:
        self.traces.append(trace)
        return "trace-1"


@pytest.mark.asyncio
async def test_trace_keeps_branch_observations_outside_fused_decisions() -> None:
    branch_observations = (
        BranchObservation(
            branch="vector",
            status="BELOW_THRESHOLD",
            chunk_id="below-vector",
            similarity=0.4,
        ),
        BranchObservation(
            branch="fts",
            status="ELIGIBLE",
            chunk_id="chunk-1",
            branch_rank=1,
            native_rank=0.5,
            lexical_policy_id="fts-v1",
        ),
    )
    store = ResultStore(
        retrieval=RetrievalResult(
            candidates=(_candidate(),), branch_observations=branch_observations
        ),
        traces=[],
    )
    service = AnswerQuestion(
        embedding_provider=EmbeddingProvider(),
        generation_provider=GenerationProvider(),
        store=store,
        embedding_configuration=EmbeddingConfiguration.milestone_one_local(),
    )

    await service.execute(
        QuestionCommand(workspace_id="workspace", question="question"),
        WorkspacePrincipal(workspace_id="workspace", key_id="test"),
    )

    trace = store.traces[0]
    assert trace.branch_observation_schema_version == 1
    assert trace.branch_observations[0]["status"] == "BELOW_THRESHOLD"
    assert "final_rank" not in trace.branch_observations[0]
    assert "fusion_score" not in trace.branch_observations[0]
    assert trace.candidate_decisions[0]["final_rank"] == 1
    assert trace.candidate_decisions[0]["fusion_score"] == 1 / 61


@pytest.mark.asyncio
async def test_trace_retains_invocation_provenance_and_phase_timing() -> None:
    store = ResultStore(
        retrieval=RetrievalResult(
            candidates=(_candidate(),),
            embedding_set_ids=("embedding-set-1",),
            chunk_set_ids=("chunk-set-1",),
        ),
        traces=[],
    )
    ticks = iter((0.0, 1.0, 2.0, 3.0, 4.0, 5.0))
    service = AnswerQuestion(
        embedding_provider=EmbeddingProvider(),
        generation_provider=GenerationProvider(),
        store=store,
        embedding_configuration=EmbeddingConfiguration.milestone_one_local(),
        clock=lambda: next(ticks),
        clock_resolution_ms=1.0,
    )

    await service.execute(
        QuestionCommand(workspace_id="workspace", question="question"),
        WorkspacePrincipal(workspace_id="workspace", key_id="test"),
    )

    trace = store.traces[0]
    assert trace.embedding_set_ids == ("embedding-set-1",)
    assert trace.chunk_set_ids == ("chunk-set-1",)
    timing = trace.provider_metadata["timing"]
    assert timing["clock_resolution_ms"] == 1.0
    assert timing["phases"]["query_embedding"]["duration_ms"] == 1000.0
    assert timing["phases"]["candidate_retrieval"]["duration_ms"] == 1000.0
    assert timing["phases"]["evidence_selection"]["duration_ms"] == 1000.0
    assert timing["phases"]["generation"]["duration_ms"] == 1000.0
    assert trace.provider_metadata["retrieval"]["latency_ms"] == 2000.0
    assert trace.latency_ms == 5000.0


@pytest.mark.asyncio
async def test_trace_uses_closed_token_budget_reason() -> None:
    store = ResultStore(
        retrieval=RetrievalResult(candidates=(_candidate(token_count=4000),)), traces=[]
    )
    service = AnswerQuestion(
        embedding_provider=EmbeddingProvider(),
        generation_provider=GenerationProvider(),
        store=store,
        embedding_configuration=EmbeddingConfiguration.milestone_one_local(),
        retrieval_configuration=RetrievalConfiguration(
            id="retrieval-test",
            candidate_k=8,
            min_similarity=0.0,
            max_evidence_chunks=5,
            max_evidence_tokens=3000,
            overlap_policy="adjacent-token-overlap-v1",
        ),
    )

    await service.execute(
        QuestionCommand(workspace_id="workspace", question="question"),
        WorkspacePrincipal(workspace_id="workspace", key_id="test"),
    )

    decision = store.traces[0].candidate_decisions[0]
    assert decision["final_decision"] == "BUDGET_EXCEEDED"
    assert decision["decision_reason"] == "TOKEN_BUDGET"


@pytest.mark.asyncio
async def test_trace_uses_closed_chunk_count_reason() -> None:
    first = _candidate()
    second = replace(first, chunk_id="chunk-2", chunk_ordinal=1, content="unrelated words")
    store = ResultStore(
        retrieval=RetrievalResult(candidates=(first, second)), traces=[]
    )
    service = AnswerQuestion(
        embedding_provider=EmbeddingProvider(),
        generation_provider=GenerationProvider(),
        store=store,
        embedding_configuration=EmbeddingConfiguration.milestone_one_local(),
        retrieval_configuration=RetrievalConfiguration(
            id="retrieval-test",
            candidate_k=8,
            min_similarity=0.0,
            max_evidence_chunks=1,
            max_evidence_tokens=3000,
            overlap_policy="adjacent-token-overlap-v1",
        ),
    )

    await service.execute(
        QuestionCommand(workspace_id="workspace", question="question"),
        WorkspacePrincipal(workspace_id="workspace", key_id="test"),
    )

    decision = store.traces[0].candidate_decisions[1]
    assert decision["final_decision"] == "BUDGET_EXCEEDED"
    assert decision["decision_reason"] == "CHUNK_COUNT_LIMIT"


@pytest.mark.asyncio
async def test_trace_retains_redundant_overlap_as_observation() -> None:
    first = _candidate()
    second = replace(first, chunk_id="chunk-2", chunk_ordinal=1)
    store = ResultStore(
        retrieval=RetrievalResult(candidates=(first, second)), traces=[]
    )
    service = AnswerQuestion(
        embedding_provider=EmbeddingProvider(),
        generation_provider=GenerationProvider(),
        store=store,
        embedding_configuration=EmbeddingConfiguration.milestone_one_local(),
    )

    await service.execute(
        QuestionCommand(workspace_id="workspace", question="question"),
        WorkspacePrincipal(workspace_id="workspace", key_id="test"),
    )

    decision = store.traces[0].candidate_decisions[1]
    assert decision["final_decision"] == "REDUNDANT_OVERLAP"
    assert decision["decision_reason"] is None


@pytest.mark.asyncio
async def test_public_refusal_answer_is_null_for_empty_evidence() -> None:
    store = ResultStore(retrieval=RetrievalResult(candidates=()), traces=[])
    service = AnswerQuestion(
        embedding_provider=EmbeddingProvider(),
        generation_provider=GenerationProvider(),
        store=store,
        embedding_configuration=EmbeddingConfiguration.milestone_one_local(),
    )

    result = await service.execute(
        QuestionCommand(workspace_id="workspace", question="no evidence"),
        WorkspacePrincipal(workspace_id="workspace", key_id="test"),
    )

    assert result.decision == "REFUSAL"
    assert result.answer is None
    assert store.traces[0].answer is None


@pytest.mark.asyncio
async def test_public_refusal_answer_is_null_for_valid_provider_refusal() -> None:
    store = ResultStore(retrieval=RetrievalResult(candidates=(_candidate(),)), traces=[])
    service = AnswerQuestion(
        embedding_provider=EmbeddingProvider(),
        generation_provider=RefusalGenerationProvider(),
        store=store,
        embedding_configuration=EmbeddingConfiguration.milestone_one_local(),
    )

    result = await service.execute(
        QuestionCommand(workspace_id="workspace", question="uncertain"),
        WorkspacePrincipal(workspace_id="workspace", key_id="test"),
    )

    assert result.decision == "REFUSAL"
    assert result.answer is None
    assert store.traces[0].answer is None


@pytest.mark.asyncio
async def test_retrieval_latency_stops_after_selection_before_generation() -> None:
    store = ResultStore(retrieval=RetrievalResult(candidates=(_candidate(),)), traces=[])
    ticks = iter((0.0, 1.0, 2.5, 3.5, 8.0, 9.0))
    service = AnswerQuestion(
        embedding_provider=EmbeddingProvider(),
        generation_provider=GenerationProvider(),
        store=store,
        embedding_configuration=EmbeddingConfiguration.milestone_one_local(),
        clock=lambda: next(ticks),
        clock_resolution_ms=1.0,
    )

    await service.execute(
        QuestionCommand(workspace_id="workspace", question="question"),
        WorkspacePrincipal(workspace_id="workspace", key_id="test"),
    )

    assert store.traces[0].provider_metadata["retrieval"]["latency_ms"] == 2500.0
