import asyncio
from dataclasses import dataclass, field

import pytest

from knora.answering.interface import QuestionCommand
from knora.answering.module import AnswerQuestion
from knora.answering.stores import QuestionTraceRecord, RetrievalCandidate
from knora.domain.access import WorkspacePrincipal
from knora.providers.embedding import EmbeddingBatch, EmbeddingConfiguration
from knora.providers.generation import GenerationResult


@dataclass
class EmptyStore:
    traces: list[QuestionTraceRecord] = field(default_factory=list)

    def retrieve_candidates(self, **kwargs) -> tuple[RetrievalCandidate, ...]:
        return ()

    def persist_trace(self, trace: QuestionTraceRecord) -> str:
        self.traces.append(trace)
        return "trace-refusal"


class QueryEmbeddingProvider:
    def embed(self, texts, configuration):
        return EmbeddingBatch(
            vectors=(tuple([0.0] * configuration.dimensions),),
            provider=configuration.provider,
            model=configuration.model,
            provider_request_id="embedding-request-1",
            usage={"prompt_tokens": 4, "total_tokens": 4},
            cost={
                "amount_usd": "0.00000008",
                "currency": "USD",
                "pricing_version": "test-pricing-v1",
            },
        )


class MismatchedQueryEmbeddingProvider:
    def embed(self, texts, configuration):
        return EmbeddingBatch(
            vectors=(tuple([0.0] * configuration.dimensions),),
            provider="unexpected-provider",
            model=configuration.model,
        )


class WorkerThreadQueryEmbeddingProvider(QueryEmbeddingProvider):
    def embed(self, texts, configuration):
        with pytest.raises(RuntimeError, match="no running event loop"):
            asyncio.get_running_loop()
        return super().embed(texts, configuration)


class GeneratorThatMustNotRun:
    async def generate(self, **kwargs):
        raise AssertionError("generation must not run without qualified evidence")


@pytest.mark.asyncio
async def test_query_embedding_configuration_mismatch_fails_before_retrieval() -> None:
    service = AnswerQuestion(
        embedding_provider=MismatchedQueryEmbeddingProvider(),
        generation_provider=GeneratorThatMustNotRun(),
        store=EmptyStore(),
        embedding_configuration=EmbeddingConfiguration.milestone_one_local(),
    )

    with pytest.raises(Exception, match="EMBEDDING_CONFIGURATION_MISMATCH"):
        await service.execute(
            QuestionCommand(workspace_id="workspace-a", question="What is the refund policy?"),
            WorkspacePrincipal(workspace_id="workspace-a", key_id="test-a"),
        )


@pytest.mark.asyncio
async def test_query_embedding_does_not_block_the_async_application_path() -> None:
    service = AnswerQuestion(
        embedding_provider=WorkerThreadQueryEmbeddingProvider(),
        generation_provider=GeneratorThatMustNotRun(),
        store=EmptyStore(),
        embedding_configuration=EmbeddingConfiguration.milestone_one_local(),
    )

    result = await service.execute(
        QuestionCommand(workspace_id="workspace-a", question="What is the refund policy?"),
        WorkspacePrincipal(workspace_id="workspace-a", key_id="test-a"),
    )

    assert result.decision == "REFUSAL"


def retrieval_candidate(
    chunk_id: str, ordinal: int, *, similarity: float | None = None
) -> RetrievalCandidate:
    resolved_similarity = similarity if similarity is not None else 0.9 - ordinal / 100
    return RetrievalCandidate(
        document_id="document-1",
        document_version_id="version-1",
        source_key="support/refunds",
        source_name="refunds.md",
        chunk_set_id="chunk-set-1",
        embedding_set_id="embedding-set-1",
        embedding_configuration_id="embedding-local-m1-v2",
        chunk_id=chunk_id,
        chunk_ordinal=ordinal,
        heading_path=("Refunds",),
        start_line=ordinal + 3,
        end_line=ordinal + 3,
        content=f"Evidence content {ordinal}",
        content_checksum=f"sha256:{chunk_id}",
        token_count=20,
        cosine_distance=1.0 - resolved_similarity,
        similarity=resolved_similarity,
    )


@dataclass
class CandidateStore(EmptyStore):
    candidates: tuple[RetrievalCandidate, ...] = ()

    def retrieve_candidates(self, **kwargs) -> tuple[RetrievalCandidate, ...]:
        return self.candidates


class ReorderedGenerator:
    async def generate(self, *, question, evidence):
        assert [item.evidence_id for item in evidence] == ["E1", "E2"]
        assert all("chunk-" not in item.content for item in evidence)
        return GenerationResult(
            decision="ANSWER",
            answer="Second evidence first. [[E2]] First evidence next. [[E1]]",
            cited_evidence_ids=("E2", "E1"),
            refusal_reason=None,
            provider="deterministic-local",
            model="controlled-test",
            prompt_version="test-v1",
            finish_reason="stop",
            provider_request_id="generation-request-1",
            usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            cost={
                "amount_usd": "0.00002",
                "currency": "USD",
                "pricing_version": "test-pricing-v1",
            },
        )


class InvalidAliasGenerator:
    async def generate(self, *, question, evidence):
        return GenerationResult(
            decision="ANSWER",
            answer="Invented citation. [[E9]]",
            cited_evidence_ids=("E9",),
            refusal_reason=None,
            provider="deterministic-local",
            model="controlled-test",
            prompt_version="test-v1",
        )


class InvalidAnswerTypeGenerator:
    async def generate(self, *, question, evidence):
        return GenerationResult(
            decision="ANSWER",
            answer=123,
            cited_evidence_ids=("E1",),
            refusal_reason=None,
            provider="deterministic-local",
            model="controlled-test",
            prompt_version="test-v1",
        )


class RefusalGenerator:
    async def generate(self, *, question, evidence):
        return GenerationResult(
            decision="REFUSAL",
            answer=None,
            cited_evidence_ids=(),
            refusal_reason="INSUFFICIENT_EVIDENCE",
            provider="deterministic-local",
            model="controlled-test",
            prompt_version="test-v1",
        )


@dataclass
class FailingTraceStore(CandidateStore):
    def persist_trace(self, trace: QuestionTraceRecord) -> str:
        raise RuntimeError("trace persistence unavailable")


@pytest.mark.asyncio
async def test_no_qualified_evidence_persists_refusal_without_generation() -> None:
    store = EmptyStore()
    service = AnswerQuestion(
        embedding_provider=QueryEmbeddingProvider(),
        generation_provider=GeneratorThatMustNotRun(),
        store=store,
        embedding_configuration=EmbeddingConfiguration.milestone_one_local(),
    )

    result = await service.execute(
        QuestionCommand(workspace_id="workspace-a", question="Who won the World Cup?"),
        WorkspacePrincipal(workspace_id="workspace-a", key_id="test-a"),
    )

    assert result.decision == "REFUSAL"
    assert result.refusal_reason == "INSUFFICIENT_EVIDENCE"
    assert result.citations == ()
    assert result.trace_id == "trace-refusal"
    assert store.traces[0].generation_status == "not_called"


@pytest.mark.asyncio
async def test_empty_fused_candidates_persist_refusal_without_generation() -> None:
    store = CandidateStore(candidates=())
    service = AnswerQuestion(
        embedding_provider=QueryEmbeddingProvider(),
        generation_provider=GeneratorThatMustNotRun(),
        store=store,
        embedding_configuration=EmbeddingConfiguration.milestone_one_local(),
    )

    result = await service.execute(
        QuestionCommand(workspace_id="workspace-a", question="No eligible branch contribution"),
        WorkspacePrincipal(workspace_id="workspace-a", key_id="test-a"),
    )

    assert result.decision == "REFUSAL"
    assert store.traces[0].retrieved_chunk_ids == ()
    assert store.traces[0].candidate_decisions == ()


@pytest.mark.asyncio
async def test_answer_projects_citations_in_first_marker_order() -> None:
    store = CandidateStore(
        candidates=(retrieval_candidate("chunk-1", 0), retrieval_candidate("chunk-2", 2))
    )
    service = AnswerQuestion(
        embedding_provider=QueryEmbeddingProvider(),
        generation_provider=ReorderedGenerator(),
        store=store,
        embedding_configuration=EmbeddingConfiguration.milestone_one_local(),
    )

    result = await service.execute(
        QuestionCommand(workspace_id="workspace-a", question="What is the refund policy?"),
        WorkspacePrincipal(workspace_id="workspace-a", key_id="test-a"),
    )

    assert result.decision == "ANSWER"
    assert [citation.evidence_id for citation in result.citations] == ["E2", "E1"]
    assert [citation.content_checksum for citation in result.citations] == [
        "sha256:chunk-2",
        "sha256:chunk-1",
    ]
    assert store.traces[0].alias_mapping == {"E1": "chunk-1", "E2": "chunk-2"}
    assert store.traces[0].validation_outcome == "valid"
    metadata = store.traces[0].provider_metadata
    assert metadata["retrieval"] == {"latency_ms": pytest.approx(0.0, abs=1000.0)}
    assert metadata["embedding"] == {
        "provider": "deterministic-local",
        "model": "text-embedding-3-small",
        "provider_request_id": "embedding-request-1",
        "usage": {"prompt_tokens": 4, "total_tokens": 4},
        "cost": {
            "amount_usd": "0.00000008",
            "currency": "USD",
            "pricing_version": "test-pricing-v1",
        },
    }
    assert metadata["generation"] == {
        "provider": "deterministic-local",
        "model": "controlled-test",
        "prompt_version": "test-v1",
        "finish_reason": "stop",
        "provider_request_id": "generation-request-1",
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        "cost": {
            "amount_usd": "0.00002",
            "currency": "USD",
            "pricing_version": "test-pricing-v1",
        },
    }
    assert set(metadata["timing"]["phases"]) == {
        "query_embedding",
        "candidate_retrieval",
        "evidence_selection",
        "generation",
    }


@pytest.mark.asyncio
async def test_invalid_generation_is_traced_then_raises_explicit_error() -> None:
    store = CandidateStore(candidates=(retrieval_candidate("chunk-1", 0),))
    service = AnswerQuestion(
        embedding_provider=QueryEmbeddingProvider(),
        generation_provider=InvalidAliasGenerator(),
        store=store,
        embedding_configuration=EmbeddingConfiguration.milestone_one_local(),
    )

    with pytest.raises(Exception, match="GENERATION_OUTPUT_INVALID"):
        await service.execute(
            QuestionCommand(workspace_id="workspace-a", question="What is the refund policy?"),
            WorkspacePrincipal(workspace_id="workspace-a", key_id="test-a"),
        )

    assert store.traces[0].validation_outcome == "invalid"
    assert store.traces[0].parsed_markers == ("E9",)


@pytest.mark.asyncio
async def test_invalid_generation_type_is_traced_then_raises_explicit_error() -> None:
    store = CandidateStore(candidates=(retrieval_candidate("chunk-1", 0),))
    service = AnswerQuestion(
        embedding_provider=QueryEmbeddingProvider(),
        generation_provider=InvalidAnswerTypeGenerator(),
        store=store,
        embedding_configuration=EmbeddingConfiguration.milestone_one_local(),
    )

    with pytest.raises(Exception, match="GENERATION_OUTPUT_INVALID"):
        await service.execute(
            QuestionCommand(workspace_id="workspace-a", question="What is the refund policy?"),
            WorkspacePrincipal(workspace_id="workspace-a", key_id="test-a"),
        )

    assert store.traces[0].validation_outcome == "invalid"
    assert store.traces[0].parsed_markers == ()


@pytest.mark.asyncio
async def test_valid_provider_refusal_uses_nullable_public_answer_and_persists_generation() -> None:
    store = CandidateStore(candidates=(retrieval_candidate("chunk-1", 0),))
    service = AnswerQuestion(
        embedding_provider=QueryEmbeddingProvider(),
        generation_provider=RefusalGenerator(),
        store=store,
        embedding_configuration=EmbeddingConfiguration.milestone_one_local(),
    )

    result = await service.execute(
        QuestionCommand(workspace_id="workspace-a", question="Is this evidence conclusive?"),
        WorkspacePrincipal(workspace_id="workspace-a", key_id="test-a"),
    )

    assert result.decision == "REFUSAL"
    assert result.refusal_reason == "INSUFFICIENT_EVIDENCE"
    assert result.citations == ()
    assert result.answer is None
    assert store.traces[0].generation_status == "completed"
    assert store.traces[0].validation_outcome == "valid"


@pytest.mark.asyncio
async def test_trace_persistence_failure_prevents_answer_delivery() -> None:
    store = FailingTraceStore(
        candidates=(retrieval_candidate("chunk-1", 0), retrieval_candidate("chunk-2", 2))
    )
    service = AnswerQuestion(
        embedding_provider=QueryEmbeddingProvider(),
        generation_provider=ReorderedGenerator(),
        store=store,
        embedding_configuration=EmbeddingConfiguration.milestone_one_local(),
    )

    with pytest.raises(RuntimeError, match="trace persistence unavailable"):
        await service.execute(
            QuestionCommand(workspace_id="workspace-a", question="What is the refund policy?"),
            WorkspacePrincipal(workspace_id="workspace-a", key_id="test-a"),
        )
