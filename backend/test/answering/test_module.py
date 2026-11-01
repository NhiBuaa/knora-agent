import asyncio
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from unittest.mock import Mock

import httpx
import pytest

from knora.answering.interface import ConversationContext, QuestionCommand
from knora.answering.module import AnswerQuestion
from knora.answering.query_planning import QueryPlan, Subquestion
from knora.answering.stores import QuestionTraceRecord, RetrievalCandidate, RetrievalConfiguration
from knora.domain.access import WorkspacePrincipal
from knora.domain.errors import KnoraError
from knora.providers.embedding import EmbeddingBatch, EmbeddingConfiguration
from knora.providers.generation import GenerationResult
from knora.providers.ollama.generation import OllamaGenerationProvider
from knora.workspaces.ports import WorkspaceAdmission


@dataclass
class EmptyStore:
    traces: list[QuestionTraceRecord] = field(default_factory=list)
    incompatible: bool = False
    readiness_calls: list[tuple[str, str]] = field(default_factory=list)

    def require_compatible_corpus(self, workspace_id: str, embedding_configuration_id: str) -> None:
        self.readiness_calls.append((workspace_id, embedding_configuration_id))
        if self.incompatible:
            raise KnoraError("REINDEX_REQUIRED")

    def retrieve_candidates(self, **kwargs) -> tuple[RetrievalCandidate, ...]:
        return ()

    def persist_trace(self, trace: QuestionTraceRecord) -> str:
        self.traces.append(trace)
        return "trace-refusal"


class QueryEmbeddingProvider:
    def embed(self, texts, configuration):
        return EmbeddingBatch(
            vectors=tuple(tuple([0.0] * configuration.dimensions) for _ in texts),
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


class CountingQueryEmbeddingProvider(QueryEmbeddingProvider):
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def embed(self, texts, configuration):
        self.calls.append(texts)
        return super().embed(texts, configuration)


@pytest.mark.asyncio
async def test_incompatible_corpus_rejects_before_provider_and_retrieval_lookup() -> None:
    class DenseRetrievalConfiguration:
        def resolve(self, *, workspace_id: str):
            return RetrievalConfiguration.milestone_one()

    store = EmptyStore(incompatible=True)
    provider = CountingQueryEmbeddingProvider()
    service = AnswerQuestion(
        embedding_provider=provider,
        generation_provider=GeneratorThatMustNotRun(),
        store=store,
        embedding_configuration=EmbeddingConfiguration.milestone_one_local(),
        retrieval_configuration_resolver=DenseRetrievalConfiguration(),
    )

    with pytest.raises(KnoraError, match="REINDEX_REQUIRED"):
        await service.execute(
            QuestionCommand(workspace_id="workspace-a", question="What is the policy?"),
            WorkspacePrincipal(workspace_id="workspace-a", key_id="test-a"),
        )

    assert store.readiness_calls == [("workspace-a", "embedding-local-m1-v2")]
    assert provider.calls == []
    assert store.traces == []


@pytest.mark.asyncio
async def test_conversation_turn_reuses_its_admission_without_reopening_workspace() -> None:
    class AdmissionMustNotBeOpened:
        def admit(self, **kwargs):
            raise AssertionError(f"conversation worker attempted another admission: {kwargs}")

        def close(self, **kwargs):
            raise AssertionError(f"answering closed the Conversation admission: {kwargs}")

    question = "  Why  is this archived?  "
    admission = WorkspaceAdmission(
        id="admission-1",
        workspace_id="workspace-a",
        operation="conversation_turn",
        operation_id="turn-1",
        admitted_at=datetime(2026, 9, 26, tzinfo=UTC),
    )
    store = EmptyStore()
    provider = CountingQueryEmbeddingProvider()
    service = AnswerQuestion(
        embedding_provider=provider,
        generation_provider=GeneratorThatMustNotRun(),
        store=store,
        embedding_configuration=EmbeddingConfiguration.milestone_one_local(),
        admission_store=AdmissionMustNotBeOpened(),
    )

    result = await service.execute(
        QuestionCommand(workspace_id="workspace-a", question=question, turn_id="turn-1"),
        WorkspacePrincipal(workspace_id="workspace-a", key_id="conversation-worker"),
        workspace_admission=admission,
    )

    assert result.decision == "REFUSAL"
    assert provider.calls == [[question]]
    assert store.traces[0].question == question


@pytest.mark.asyncio
async def test_conversation_admission_cannot_be_reused_for_another_turn() -> None:
    admission = WorkspaceAdmission(
        id="admission-1",
        workspace_id="workspace-a",
        operation="conversation_turn",
        operation_id="turn-1",
        admitted_at=datetime(2026, 9, 26, tzinfo=UTC),
    )
    store = EmptyStore()
    provider = CountingQueryEmbeddingProvider()
    service = AnswerQuestion(
        embedding_provider=provider,
        generation_provider=GeneratorThatMustNotRun(),
        store=store,
        embedding_configuration=EmbeddingConfiguration.milestone_one_local(),
    )

    with pytest.raises(KnoraError, match="WORKSPACE_ACCESS_DENIED"):
        await service.execute(
            QuestionCommand(
                workspace_id="workspace-a",
                question="What is in this conversation?",
                turn_id="turn-2",
            ),
            WorkspacePrincipal(workspace_id="workspace-a", key_id="conversation-worker"),
            workspace_admission=admission,
        )

    assert store.readiness_calls == []
    assert provider.calls == []
    assert store.traces == []


@pytest.mark.asyncio
async def test_conversation_turn_id_requires_a_persisted_admission() -> None:
    store = EmptyStore()
    provider = CountingQueryEmbeddingProvider()
    service = AnswerQuestion(
        embedding_provider=provider,
        generation_provider=GeneratorThatMustNotRun(),
        store=store,
        embedding_configuration=EmbeddingConfiguration.milestone_one_local(),
    )

    with pytest.raises(KnoraError, match="CONVERSATION_ADMISSION_REQUIRED"):
        await service.execute(
            QuestionCommand(
                workspace_id="workspace-a",
                question="What is in this conversation?",
                turn_id="turn-1",
            ),
            WorkspacePrincipal(workspace_id="workspace-a", key_id="conversation-worker"),
        )

    assert store.readiness_calls == []
    assert provider.calls == []
    assert store.traces == []


@pytest.mark.asyncio
async def test_cross_workspace_question_rejects_before_readiness_lookup() -> None:
    store = EmptyStore(incompatible=True)
    provider = CountingQueryEmbeddingProvider()
    service = AnswerQuestion(
        embedding_provider=provider,
        generation_provider=GeneratorThatMustNotRun(),
        store=store,
        embedding_configuration=EmbeddingConfiguration.milestone_one_local(),
    )

    with pytest.raises(KnoraError, match="WORKSPACE_ACCESS_DENIED"):
        await service.execute(
            QuestionCommand(workspace_id="workspace-b", question="What is the policy?"),
            WorkspacePrincipal(workspace_id="workspace-a", key_id="test-a"),
        )

    assert store.readiness_calls == []
    assert provider.calls == []


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


def generation_repair_case(generator, *, v3=True, stale=False, verifier=None):
    from knora.answering.stores import BranchObservation, LexicalGeneration, RetrievalResult

    config = replace(
        RetrievalConfiguration.bm25_top8_v1(),
        id="retrieval-bm25-top8-v3" if v3 else "retrieval-bm25-top8-v1",
    )
    candidate = replace(
        retrieval_candidate("refund", 0),
        content="Đổi trả trong 7 ngày.",
        embedding_set_id=None,
        embedding_configuration_id=None,
        cosine_distance=None,
        similarity=None,
        bm25_score=5.0,
        bm25_rank=1,
        index_generation_id="generation-1",
    )
    snapshot = LexicalGeneration(
        "workspace-a",
        "document-1",
        "version-1",
        "chunk-set-1",
        "generation-1",
        config.lexical_policy_id,
    )

    class Store(EmptyStore):
        def require_lexical_corpus(self, *args):
            pass

        def revalidate_lexical_snapshot(self, *args):
            if stale and generator.calls:
                raise KnoraError("RETRIEVAL_PROVENANCE_INVALID")

        def retrieve_candidates(self, **kwargs):
            return RetrievalResult(
                (candidate,),
                (
                    BranchObservation(
                        branch="bm25",
                        status="ELIGIBLE",
                        chunk_id="refund",
                        branch_rank=1,
                        raw_score=5.0,
                        score_kind="bm25",
                        index_generation_id="generation-1",
                        lexical_policy_id=config.lexical_policy_id,
                    ),
                ),
                chunk_set_ids=("chunk-set-1",),
                lexical_generations=(snapshot,),
            )

    store = Store()
    return store, AnswerQuestion(
        embedding_provider=None,
        generation_provider=generator,
        answer_support_verifier=verifier,
        store=store,
        embedding_configuration=None,
        retrieval_configuration=config,
    )


class RepairGenerator:
    def __init__(self, repair="valid", invalid_alias=False):
        self.repair = repair
        self.invalid_alias = invalid_alias
        self.calls = []

    async def generate(self, *, question, evidence):
        self.calls.append((question, evidence))
        return GenerationResult(
            "ANSWER",
            "Đổi trả trong 70 ngày. [[E9]]"
            if self.invalid_alias
            else "Đổi trả trong 70 ngày. [[E1]]",
            ("E9",) if self.invalid_alias else ("E1",),
            None,
            provider="cloudflare-workers-ai",
            prompt_version="initial-v1",
            usage={"total_tokens": 10},
            provider_request_id="initial",
        )

    async def repair_generation(self, *, question, evidence):
        self.calls.append((question, evidence))
        if self.repair == "network":
            raise KnoraError("PROVIDER_REQUEST_FAILED")
        if self.repair == "refusal":
            return GenerationResult("REFUSAL", None, (), "INSUFFICIENT_EVIDENCE")
        return GenerationResult(
            "ANSWER",
            f"Đổi trả trong {7 if self.repair == 'valid' else 70} ngày. [[E1]]",
            ("E1",),
            None,
            provider="cloudflare-workers-ai",
            prompt_version="repair-v1",
            usage={"total_tokens": 5},
            provider_request_id="repair",
        )


class ProjectedGenerator(RepairGenerator):
    async def generate(self, *, question, evidence):
        from knora.providers.openai_compatible.answer_blocks import compose_answer_projection

        self.calls.append((question, evidence))
        answer, cited, projection = compose_answer_projection(
            {
                "decision": "ANSWER",
                "before": [
                    {
                        "text": "La période de retour est de 7 jours.",
                        "bold": None,
                        "support": ["E1"],
                    }
                ],
                "items": [],
                "after": [],
                "refusal_reason": None,
            },
            evidence,
        )
        return GenerationResult(
            "ANSWER",
            answer,
            cited,
            None,
            provider="cloudflare-workers-ai",
            answer_projection=projection,
        )


class SupportVerifier:
    def __init__(self, outcome="supported"):
        self.outcome = outcome
        self.calls = []

    async def verify(self, **kwargs):
        from knora.answering.answer_support import validate_support

        self.calls.append(kwargs)
        if self.outcome == "unavailable":
            raise KnoraError("PROVIDER_REQUEST_FAILED")
        quote = kwargs["evidence"][0].content
        verdict = {
            "answer_digest": kwargs["answer_projection"].answer_digest,
            "snapshot_digest": kwargs["snapshot_digest"],
            "statements": [
                {
                    "id": "S1",
                    "verdict": "SUPPORTED" if self.outcome == "supported" else "UNKNOWN",
                    "source_refs": [
                        {
                            "alias": "E1",
                            "exact_quote": quote,
                            "start": 0,
                            "end": len(quote),
                            "reason": "ENTAILMENT",
                        }
                    ],
                }
            ],
            "groups": [
                {"id": gid, "verdict": "ANSWERED", "statement_ids": ["S1"]}
                for gid, _ in kwargs["groups"]
            ],
        }
        return validate_support(
            verdict,
            answer=kwargs["answer"],
            projection=kwargs["answer_projection"],
            evidence=kwargs["evidence"],
            snapshot_digest=kwargs["snapshot_digest"],
            group_ids=tuple(g[0] for g in kwargs["groups"]),
        ), {"provider": "cloudflare-workers-ai"}


@pytest.mark.asyncio
async def test_v3_supported_paraphrase_uses_one_generation_and_one_verification():
    from knora.answering.answer_support import validate_trace_support

    generator, verifier = ProjectedGenerator(), SupportVerifier()
    store, service = generation_repair_case(generator, verifier=verifier)
    result = await service.execute(
        QuestionCommand(workspace_id="workspace-a", question="Đổi trả trong bao nhiêu ngày?"),
        WorkspacePrincipal(workspace_id="workspace-a", key_id="test"),
    )
    assert result.decision == "ANSWER"
    assert len(generator.calls) == len(verifier.calls) == 1
    trace = store.traces[0]
    assert trace.trace_schema_version == 4
    assert trace.provider_metadata["answer_support"]["status"] == "supported"
    assert "attempts" not in trace.provider_metadata["generation"]
    candidate = trace.alias_mapping["E1"]
    checksum = trace.provider_metadata["answer_support"]["snapshot_binding"]["sources"][0][
        "content_checksum"
    ]
    validate_trace_support(trace, {candidate: ("Đổi trả trong 7 ngày.", checksum)})
    with pytest.raises(KnoraError):
        validate_trace_support(trace, {candidate: ("Đổi trả trong 70 ngày.", "changed")})


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "outcome,error",
    [("unknown", "GENERATION_OUTPUT_INVALID"), ("unavailable", "PROVIDER_REQUEST_FAILED")],
)
async def test_v3_unverified_answer_is_not_published_or_repaired(outcome, error):
    generator, verifier = ProjectedGenerator(), SupportVerifier(outcome)
    store, service = generation_repair_case(generator, verifier=verifier)
    with pytest.raises(KnoraError, match=error):
        await service.execute(
            QuestionCommand(workspace_id="workspace-a", question="Đổi trả trong bao nhiêu ngày?"),
            WorkspacePrincipal(workspace_id="workspace-a", key_id="test"),
        )
    assert len(generator.calls) == len(verifier.calls) == 1
    assert len(store.traces) == 1 and store.traces[0].validation_outcome == "invalid"
    assert store.traces[0].provider_metadata["answer_support"]["status"] == (
        "invalid" if outcome == "unknown" else "unavailable"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "v3,stale,error",
    [(False, False, "GENERATION_OUTPUT_INVALID"), (True, True, "RETRIEVAL_PROVENANCE_INVALID")],
)
async def test_legacy_validation_and_v3_snapshot_fence(v3, stale, error):
    generator, verifier = ProjectedGenerator(), SupportVerifier()
    if not v3:
        generator = RepairGenerator(invalid_alias=True)
    _, service = generation_repair_case(generator, v3=v3, stale=stale, verifier=verifier)
    with pytest.raises(KnoraError, match=error):
        await service.execute(
            QuestionCommand(workspace_id="workspace-a", question="Đổi trả trong bao nhiêu ngày?"),
            WorkspacePrincipal(workspace_id="workspace-a", key_id="test"),
        )
    assert len(generator.calls) == 1 and not verifier.calls


@pytest.mark.asyncio
async def test_v3_missing_projection_or_verifier_fails_closed_without_repair():
    generator = RepairGenerator()
    store, service = generation_repair_case(generator)
    with pytest.raises(KnoraError, match="GENERATION_OUTPUT_INVALID"):
        await service.execute(
            QuestionCommand(workspace_id="workspace-a", question="Đổi trả trong bao nhiêu ngày?"),
            WorkspacePrincipal(workspace_id="workspace-a", key_id="test"),
        )
    assert len(generator.calls) == 1 and store.traces[0].validation_outcome == "invalid"


@pytest.mark.asyncio
async def test_ollama_answer_projects_pdf_provenance_from_selected_chunk() -> None:
    candidate = replace(
        retrieval_candidate("pdf-chunk-1", 0),
        source_key="Teacher Manh - Guidelines 2024.pdf",
        source_name="Teacher Manh - Guidelines 2024.pdf",
        page_start=1,
        page_end=1,
        content="Gợi ý gồm 7 chương. Báo cáo nhỏ có thể gộp một số chương.",
    )
    store = CandidateStore(candidates=(candidate,))

    async def endpoint(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            return httpx.Response(
                200,
                json={"models": [{"name": "qwen3:8b", "digest": "sha256:" + "b" * 64}]},
            )
        return httpx.Response(
            200,
            json={
                "model": "qwen3:8b",
                "message": {
                    "role": "assistant",
                    "content": (
                        '{"decision":"ANSWER","answer":"Gợi ý 7 chương; báo cáo nhỏ '
                        'có thể gộp một số chương. [[E1]]","cited_evidence_ids":["E1"],'
                        '"refusal_reason":null}'
                    ),
                },
                "done": True,
            },
        )

    service = AnswerQuestion(
        embedding_provider=QueryEmbeddingProvider(),
        generation_provider=OllamaGenerationProvider(
            base_url="http://ollama.test:11434",
            expected_digest="sha256:" + "b" * 64,
            client=httpx.AsyncClient(transport=httpx.MockTransport(endpoint)),
        ),
        store=store,
        embedding_configuration=EmbeddingConfiguration.milestone_one_local(),
    )
    result = await service.execute(
        QuestionCommand(workspace_id="workspace-a", question="Báo cáo có mấy chương?"),
        WorkspacePrincipal(workspace_id="workspace-a", key_id="test-a"),
    )
    assert result.decision == "ANSWER"
    assert result.citations[0].document_id == candidate.document_id
    assert result.citations[0].document_version_id == candidate.document_version_id
    assert store.traces[0].alias_mapping == {"E1": candidate.chunk_id}
    assert result.citations[0].source_key == candidate.source_key
    assert result.citations[0].page_start == 1


@pytest.mark.asyncio
async def test_containment_sends_unique_fact_to_generation_and_projects_its_citation():
    shared = "The report has seven sections."
    store = CandidateStore(
        candidates=(
            replace(retrieval_candidate("chapter", 1), content=shared, page_start=1, page_end=1),
            replace(
                retrieval_candidate("date", 0),
                content="Updated 2031-02-03. " + shared,
                page_start=1,
                page_end=1,
            ),
        )
    )

    class DateGenerator:
        async def generate(self, *, question, evidence):
            assert [(item.evidence_id, item.content) for item in evidence] == [
                ("E1", shared),
                ("E2", "Updated 2031-02-03. " + shared),
            ]
            return GenerationResult(
                decision="ANSWER",
                answer="2031-02-03. [[E2]]",
                cited_evidence_ids=("E2",),
                refusal_reason=None,
                provider="deterministic-local",
                model="test",
                prompt_version="test",
            )

    result = await AnswerQuestion(
        embedding_provider=QueryEmbeddingProvider(),
        generation_provider=DateGenerator(),
        store=store,
        embedding_configuration=EmbeddingConfiguration.milestone_one_local(),
        retrieval_configuration=RetrievalConfiguration.evidence_containment_v1(),
    ).execute(
        QuestionCommand(workspace_id="workspace-a", question="When was it updated?"),
        WorkspacePrincipal(workspace_id="workspace-a", key_id="test"),
    )
    assert result.decision == "ANSWER"
    assert result.citations[0].content_checksum == "sha256:date"
    assert result.citations[0].evidence_id == "E2"
    assert result.citations[0].page_start == 1
    assert store.traces[0].retrieval_configuration_id == "retrieval-evidence-containment-v1"


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


@pytest.mark.asyncio
async def test_follow_up_uses_context_without_treating_it_as_evidence() -> None:
    class RecordingStore(CandidateStore):
        def __init__(self, candidates):
            super().__init__(candidates=candidates)
            self.retrieval_requests = []

        def retrieve_candidates(self, **kwargs):
            self.retrieval_requests.append(kwargs)
            return super().retrieve_candidates(**kwargs)

    class RecordingGenerator:
        def __init__(self):
            self.questions = []

        async def generate(self, *, question, evidence):
            self.questions.append(question)
            return GenerationResult(
                decision="ANSWER",
                answer="The guide suggests seven chapters. [[E1]]",
                cited_evidence_ids=("E1",),
                refusal_reason=None,
                provider="deterministic-local",
                model="controlled-test",
                prompt_version="test-v1",
            )

    question = "How many chapters does the guide suggest?"
    context = ConversationContext(
        policy_id="conversation-context-v1",
        transcript='[{"question":"What does the guide cover?","answer":"Report structure."}]',
        retrieval_query=(
            f"Previous user question: What does the guide cover?\nCurrent question: {question}"
        ),
        selected_turn_ids=("turn-prior",),
        token_count=31,
    )
    embedding = CountingQueryEmbeddingProvider()
    generator = RecordingGenerator()
    candidate = retrieval_candidate("chunk-follow-up", 0)
    store = RecordingStore((candidate,))
    service = AnswerQuestion(
        embedding_provider=embedding,
        generation_provider=generator,
        store=store,
        embedding_configuration=EmbeddingConfiguration.milestone_one_local(),
    )
    admission = WorkspaceAdmission(
        id="admission-current",
        workspace_id="workspace-a",
        operation="conversation_turn",
        operation_id="turn-current",
        admitted_at=datetime(2026, 9, 26, tzinfo=UTC),
    )

    result = await service.execute(
        QuestionCommand(
            workspace_id="workspace-a",
            question=question,
            turn_id="turn-current",
            conversation_context=context,
        ),
        WorkspacePrincipal(workspace_id="workspace-a", key_id="worker"),
        workspace_admission=admission,
    )

    assert embedding.calls == [[context.retrieval_query]]
    assert store.retrieval_requests[0]["query_text"] == context.retrieval_query
    assert question in generator.questions[0]
    assert context.transcript in generator.questions[0]
    assert "turn-prior" not in generator.questions[0]
    assert "not evidence" in generator.questions[0].lower()
    assert "freshly retrieved evidence" in generator.questions[0].lower()
    assert store.traces[0].question == question
    assert store.traces[0].conversation_turn_id == "turn-current"
    assert store.traces[0].provider_metadata["conversation_context"] == {
        "policy_id": "conversation-context-v1",
        "retrieval_query": context.retrieval_query,
        "selected_turn_ids": ["turn-prior"],
    }
    assert all(citation.source_key == "support/refunds" for citation in result.citations)


@pytest.mark.asyncio
async def test_prior_answer_cannot_bypass_fresh_evidence_refusal_for_a_follow_up() -> None:
    question = "Which planet is made of cheese?"
    context = ConversationContext(
        policy_id="conversation-context-v1",
        transcript=(
            '[{"question":"What did the last answer say?","answer":"Mars is made of cheese."}]'
        ),
        retrieval_query=(
            f"Previous user question: What did the last answer say?\nCurrent question: {question}"
        ),
        selected_turn_ids=("turn-prior",),
        token_count=24,
    )
    store = EmptyStore()
    embedding = CountingQueryEmbeddingProvider()
    service = AnswerQuestion(
        embedding_provider=embedding,
        generation_provider=GeneratorThatMustNotRun(),
        store=store,
        embedding_configuration=EmbeddingConfiguration.milestone_one_local(),
    )
    admission = WorkspaceAdmission(
        id="admission-current",
        workspace_id="workspace-a",
        operation="conversation_turn",
        operation_id="turn-current",
        admitted_at=datetime(2026, 9, 26, tzinfo=UTC),
    )

    result = await service.execute(
        QuestionCommand(
            workspace_id="workspace-a",
            question=question,
            turn_id="turn-current",
            conversation_context=context,
        ),
        WorkspacePrincipal(workspace_id="workspace-a", key_id="worker"),
        workspace_admission=admission,
    )

    assert result.decision == "REFUSAL"
    assert result.refusal_reason == "INSUFFICIENT_EVIDENCE"
    assert result.citations == ()
    assert embedding.calls == [[context.retrieval_query]]
    assert store.traces[0].question == question
    assert store.traces[0].conversation_turn_id == "turn-current"


@pytest.mark.asyncio
async def test_multi_query_variants_are_executed_and_merged_in_v3() -> None:
    """F18: Verify all query plan variants are searched and merged via cross-query pooling."""
    from unittest.mock import Mock

    from knora.answering.sequential_dependence import CorpusStatistics
    from knora.answering.stores import (
        BranchObservation,
        LexicalGeneration,
        RetrievalCandidate,
        RetrievalResult,
    )

    searched_queries = []

    c1 = RetrievalCandidate(
        document_id="doc-1",
        document_version_id="ver-1",
        source_key="policy",
        source_name="policy.pdf",
        chunk_set_id="cset-1",
        embedding_set_id=None,
        embedding_configuration_id="embedding-local-m1-v2",
        chunk_id="chunk-1",
        chunk_ordinal=0,
        heading_path=("Section 1",),
        start_line=1,
        end_line=5,
        content="Evidence content",
        content_checksum="chk-1",
        token_count=10,
        cosine_distance=None,
        similarity=None,
        fusion_score=0.5,
        index_generation_id="gen-1",
    )

    snapshot = LexicalGeneration(
        workspace_id="workspace-a",
        document_id="doc-1",
        document_version_id="ver-1",
        chunk_set_id="cset-1",
        index_generation_id="gen-1",
        lexical_policy_id="bm25-word-frozen47-population-v1",
        statistics_digest="a" * 64,
    )
    obs = (
        BranchObservation(
            branch="fused",
            status="ELIGIBLE",
            chunk_id="chunk-1",
            branch_rank=1,
            raw_score=0.5,
            score_kind="dbsf",
            index_generation_id="gen-1",
        ),
    )
    v3_result = RetrievalResult(
        candidates=(c1,),
        branch_observations=obs,
        chunk_set_ids=("cset-1",),
        lexical_generations=(snapshot,),
    )

    class SpyStore(EmptyStore):
        def require_lexical_corpus(self, workspace_id, lexical_policy_id=None):
            pass

        def revalidate_lexical_snapshot(self, *args, **kwargs):
            pass

        def read_corpus_statistics(self, workspace_id, policy_id):
            return CorpusStatistics(
                total_tokens=1000,
                total_chunks=10,
                unigram_frequencies={"evidence": 5, "content": 5},
                statistics_digest="a" * 64,
            )

        def retrieve_candidates(self, **kwargs):
            searched_queries.append(kwargs["query_text"])
            return v3_result

    store = SpyStore()
    mock_gen = Mock()
    mock_gen.generate = Mock(
        side_effect=lambda **kwargs: asyncio.sleep(
            0,
            result=GenerationResult(
                decision="ANSWER",
                answer="Evidence content [[E1]].",
                cited_evidence_ids=("E1",),
                refusal_reason=None,
            ),
        )
    )

    service = AnswerQuestion(
        embedding_provider=QueryEmbeddingProvider(),
        generation_provider=mock_gen,
        store=store,
        embedding_configuration=EmbeddingConfiguration.milestone_one_local(),
        retrieval_configuration=RetrievalConfiguration.hybrid_rerank_top8_v3(),
    )

    # Typo query generates variants
    question = "chuong2 quy dinh thoi han bao hanh san pham"
    result = await service.execute(
        QuestionCommand(workspace_id="workspace-a", question=question),
        WorkspacePrincipal(workspace_id="workspace-a", key_id="test-a"),
    )

    assert result is not None
    assert len(searched_queries) >= 2
    assert question in searched_queries
    assert any("chương 2" in q for q in searched_queries)


@pytest.mark.asyncio
async def test_single_intent_missing_evidence_triggers_recovery() -> None:
    """F13: Single-intent queries without required evidence trigger recovery pass."""
    from knora.answering.stores import (
        BranchObservation,
        LexicalGeneration,
        RetrievalCandidate,
        RetrievalResult,
    )

    recovery_called = False

    c_unrelated = RetrievalCandidate(
        document_id="doc-1",
        document_version_id="ver-1",
        source_key="policy",
        source_name="policy.pdf",
        chunk_set_id="cset-1",
        embedding_set_id=None,
        embedding_configuration_id=None,
        chunk_id="chunk-unrelated",
        chunk_ordinal=0,
        heading_path=("Chương 1",),
        start_line=1,
        end_line=5,
        content="Nội dung điều khoản chung về nhân sự",
        content_checksum="chk-unrelated",
        token_count=10,
        cosine_distance=None,
        similarity=None,
        bm25_score=5.0,
        bm25_rank=1,
        index_generation_id="gen-1",
    )

    snapshot = LexicalGeneration(
        workspace_id="workspace-a",
        document_id="doc-1",
        document_version_id="ver-1",
        chunk_set_id="cset-1",
        index_generation_id="gen-1",
        lexical_policy_id="bm25-word-frozen47-population-v1",
        statistics_digest="a" * 64,
    )
    obs = (
        BranchObservation(
            branch="bm25",
            status="ELIGIBLE",
            chunk_id="chunk-unrelated",
            branch_rank=1,
            raw_score=5.0,
            score_kind="bm25",
            index_generation_id="gen-1",
            lexical_policy_id="bm25-word-frozen47-population-v1",
        ),
    )
    initial_result = RetrievalResult(
        candidates=(c_unrelated,),
        branch_observations=obs,
        chunk_set_ids=("cset-1",),
        lexical_generations=(snapshot,),
    )

    class RecoveryAwareStore(EmptyStore):
        def require_lexical_corpus(self, workspace_id, lexical_policy_id=None):
            pass

        def revalidate_lexical_snapshot(self, *args, **kwargs):
            pass

        def retrieve_candidates(self, **kwargs):
            nonlocal recovery_called
            query = kwargs.get("query_text", "")
            # Recovery lookup searches for missing section anchor 'Mục 3.1'
            if "Mục 3.1" in query:
                recovery_called = True
            return initial_result

    store = RecoveryAwareStore()
    bm25_v3_config = replace(
        RetrievalConfiguration.bm25_top8_v1(),
        id="retrieval-bm25-top8-v3",
    )
    service = AnswerQuestion(
        embedding_provider=QueryEmbeddingProvider(),
        generation_provider=GeneratorThatMustNotRun(),
        store=store,
        embedding_configuration=EmbeddingConfiguration.milestone_one_local(),
        retrieval_configuration=bm25_v3_config,
    )

    # Query with section anchor 'Mục 3.1' but initial candidate only contains Chapter 1
    question = "Quy định tại Mục 3.1"
    result = await service.execute(
        QuestionCommand(workspace_id="workspace-a", question=question),
        WorkspacePrincipal(workspace_id="workspace-a", key_id="test-a"),
    )

    assert result.decision == "REFUSAL"
    assert recovery_called is True


class MultiQueryAnswerCase:
    def __init__(self) -> None:
        self.reranker_calls = 0
        self.generator_calls = 0
        self.verifier_calls = 0
        self.valid_answer_traces = ()
        self._second_has_foreign = False

    def second_result_has_foreign_generation(self) -> None:
        self._second_has_foreign = True

    async def execute_multi_query(self) -> None:
        from knora.answering.query_planning import QueryPlan, Subquestion
        from knora.answering.stores import (
            BranchObservation,
            LexicalGeneration,
            RetrievalCandidate,
            RetrievalConfiguration,
            RetrievalResult,
        )

        c1 = RetrievalCandidate(
            document_id="doc-1",
            document_version_id="ver-1",
            source_key="policy",
            source_name="policy.pdf",
            chunk_set_id="cset-1",
            embedding_set_id=None,
            embedding_configuration_id=None,
            chunk_id="chunk-1",
            chunk_ordinal=0,
            heading_path=(),
            start_line=1,
            end_line=5,
            content="Content 1",
            content_checksum="chk-1",
            token_count=5,
            cosine_distance=None,
            similarity=None,
            bm25_score=5.0,
            bm25_rank=1,
            index_generation_id="gen-1",
        )
        gen1 = LexicalGeneration(
            workspace_id="ws-1",
            document_id="doc-1",
            document_version_id="ver-1",
            chunk_set_id="cset-1",
            index_generation_id="gen-1",
            lexical_policy_id="bm25-word-frozen47-population-v1",
            statistics_digest="a" * 64,
        )
        res1 = RetrievalResult(
            candidates=(c1,),
            branch_observations=(
                BranchObservation(
                    branch="bm25",
                    status="ELIGIBLE",
                    chunk_id="chunk-1",
                    branch_rank=1,
                    raw_score=5.0,
                    score_kind="bm25",
                    index_generation_id="gen-1",
                    lexical_policy_id="bm25-word-frozen47-population-v1",
                ),
            ),
            chunk_set_ids=("cset-1",),
            lexical_generations=(gen1,),
        )

        foreign_gen = "gen-foreign" if self._second_has_foreign else "gen-1"
        c2 = RetrievalCandidate(
            document_id="doc-1",
            document_version_id="ver-1",
            source_key="policy",
            source_name="policy.pdf",
            chunk_set_id="cset-1",
            embedding_set_id=None,
            embedding_configuration_id=None,
            chunk_id="chunk-2",
            chunk_ordinal=1,
            heading_path=(),
            start_line=6,
            end_line=10,
            content="Content 2",
            content_checksum="chk-2",
            token_count=5,
            cosine_distance=None,
            similarity=None,
            bm25_score=4.0,
            bm25_rank=1,
            index_generation_id=foreign_gen,
        )
        gen2 = LexicalGeneration(
            workspace_id="ws-1",
            document_id="doc-1",
            document_version_id="ver-1",
            chunk_set_id="cset-1",
            index_generation_id=foreign_gen,
            lexical_policy_id="bm25-word-frozen47-population-v1",
            statistics_digest="a" * 64 if not self._second_has_foreign else "b" * 64,
        )
        res2 = RetrievalResult(
            candidates=(c2,),
            branch_observations=(
                BranchObservation(
                    branch="bm25",
                    status="ELIGIBLE",
                    chunk_id="chunk-2",
                    branch_rank=1,
                    raw_score=4.0,
                    score_kind="bm25",
                    index_generation_id=foreign_gen,
                    lexical_policy_id="bm25-word-frozen47-population-v1",
                ),
            ),
            chunk_set_ids=("cset-1",),
            lexical_generations=(gen2,),
        )

        query_call_count = 0

        class SpyStore(EmptyStore):
            def require_lexical_corpus(self, workspace_id, lexical_policy_id=None):
                pass

            def revalidate_lexical_snapshot(self, *args, **kwargs):
                pass

            def retrieve_candidates(self, **kwargs):
                nonlocal query_call_count
                query_call_count += 1
                if query_call_count == 1:
                    return res1
                return res2

        class SpyReranker:
            def __init__(self, outer):
                self.outer = outer

            def rerank(self, question, candidates):
                self.outer.reranker_calls += 1
                return None

        class SpyGenerator:
            def __init__(self, outer):
                self.outer = outer

            async def generate(self, **kwargs):
                self.outer.generator_calls += 1
                return None

        class SpyPlanner:
            def plan(self, query):
                return QueryPlan(
                    query_id="q-test-1",
                    original_query=query,
                    is_fast_path=False,
                    subquestions=(
                        Subquestion("sq1", "query part 1", ()),
                        Subquestion("sq2", "query part 2", ()),
                    ),
                    variants=(),
                    protected_spans=(),
                )

        bm25_config = replace(
            RetrievalConfiguration.bm25_top8_v1(),
            id="retrieval-bm25-top8-v3",
            reranking_policy_id="rerank-bge-v1",
        )

        service = AnswerQuestion(
            embedding_provider=QueryEmbeddingProvider(),
            generation_provider=SpyGenerator(self),
            reranking_provider=SpyReranker(self),
            store=SpyStore(),
            embedding_configuration=EmbeddingConfiguration.milestone_one_local(),
            retrieval_configuration=bm25_config,
            query_planner=SpyPlanner(),
        )

        await service.execute(
            QuestionCommand(workspace_id="ws-1", question="query part 1 and query part 2"),
            WorkspacePrincipal(workspace_id="ws-1", key_id="key-1"),
        )


@pytest.fixture
def answer_case():
    return MultiQueryAnswerCase()


@pytest.mark.asyncio
async def test_secondary_query_mismatch_stops_before_any_provider(
    answer_case: MultiQueryAnswerCase,
) -> None:
    answer_case.second_result_has_foreign_generation()
    with pytest.raises(KnoraError):
        await answer_case.execute_multi_query()
    assert answer_case.reranker_calls == 0
    assert answer_case.generator_calls == 0
    assert answer_case.verifier_calls == 0
    assert answer_case.valid_answer_traces == ()


@pytest.mark.asyncio
async def test_query_scheduling_refuses_when_more_than_4_required_groups() -> None:
    """F18/R3-N04: Questions decomposing into > 4 required groups refuse for clarification."""

    class PlannerWith5Groups:
        def plan(self, query):
            return QueryPlan(
                query_id="q-5groups",
                original_query=query,
                is_fast_path=False,
                subquestions=tuple(
                    Subquestion(f"sq_{i}", f"subquestion {i}", required=True) for i in range(1, 6)
                ),
                variants=(),
                protected_spans=(),
            )

    store = Mock()
    store.persist_trace.return_value = "trace-5groups"

    generator = Mock()
    embedding_provider = Mock()
    embedding_config = EmbeddingConfiguration.milestone_one_local()
    retrieval_config = RetrievalConfiguration.hybrid_rerank_top8_v3()

    service = AnswerQuestion(
        store=store,
        generation_provider=generator,
        embedding_provider=embedding_provider,
        embedding_configuration=embedding_config,
        retrieval_configuration=retrieval_config,
        query_planner=PlannerWith5Groups(),
    )

    res = await service.execute(
        QuestionCommand(workspace_id="ws-1", question="complex multi-part question"),
        WorkspacePrincipal(workspace_id="ws-1", key_id="key-1"),
    )

    assert res.decision == "REFUSAL"
    assert res.refusal_reason == "CLARIFICATION_REQUIRED"
    assert res.requests_clarification is True
    assert generator.generate.call_count == 0


@pytest.mark.asyncio
async def test_vector_cardinality_and_finiteness_enforcement() -> None:
    """R3-N04: Embedding provider returning non-finite values or wrong count fails closed."""

    class PlannerWith2Groups:
        def plan(self, query):
            return QueryPlan(
                query_id="q-2groups",
                original_query=query,
                is_fast_path=False,
                subquestions=(
                    Subquestion("sq_1", "part 1", required=True),
                    Subquestion("sq_2", "part 2", required=True),
                ),
                variants=(),
                protected_spans=(),
            )

    store = Mock()
    generator = Mock()
    embedding_config = EmbeddingConfiguration(
        id="cf-bge",
        dimensions=4,
        distance_metric="cosine",
        provider="cloudflare",
        model="@cf/baai/bge-base-en-v1.5",
    )
    retrieval_config = RetrievalConfiguration.hybrid_rerank_top8_v3()

    # Case 1: Count mismatch (returns 1 vector instead of N)
    bad_count_provider = Mock()
    bad_count_provider.embed_queries.return_value = EmbeddingBatch(
        provider="cloudflare",
        model="@cf/baai/bge-base-en-v1.5",
        vectors=((0.1, 0.2, 0.3, 0.4),),  # 1 vector for 3 queries
    )
    service_bad_count = AnswerQuestion(
        store=store,
        generation_provider=generator,
        embedding_provider=bad_count_provider,
        embedding_configuration=embedding_config,
        retrieval_configuration=retrieval_config,
        query_planner=PlannerWith2Groups(),
    )
    with pytest.raises(KnoraError) as exc_info:
        await service_bad_count.execute(
            QuestionCommand(workspace_id="ws-1", question="part 1 and part 2"),
            WorkspacePrincipal(workspace_id="ws-1", key_id="key-1"),
        )
    assert exc_info.value.code == "EMBEDDING_DIMENSION_MISMATCH"

    # Case 2: Non-finite vector value (NaN/Inf)
    nan_provider = Mock()
    nan_provider.embed_queries.return_value = EmbeddingBatch(
        provider="cloudflare",
        model="@cf/baai/bge-base-en-v1.5",
        vectors=(
            (0.1, 0.2, float("nan"), 0.4),
            (0.1, 0.2, 0.3, 0.4),
            (0.1, 0.2, 0.3, 0.4),
        ),
    )
    service_nan = AnswerQuestion(
        store=store,
        generation_provider=generator,
        embedding_provider=nan_provider,
        embedding_configuration=embedding_config,
        retrieval_configuration=retrieval_config,
        query_planner=PlannerWith2Groups(),
    )
    with pytest.raises(KnoraError) as exc_info:
        await service_nan.execute(
            QuestionCommand(workspace_id="ws-1", question="part 1 and part 2"),
            WorkspacePrincipal(workspace_id="ws-1", key_id="key-1"),
        )
    assert exc_info.value.code == "EMBEDDING_DIMENSION_MISMATCH"


class RecoverableGenerator(ProjectedGenerator):
    def __init__(self, *, malformed=False, repeat=False, refusal=False):
        super().__init__()
        self.malformed, self.repeat, self.refusal = malformed, repeat, refusal
        self.feedback = []

    async def generate(self, **kwargs):
        if self.malformed:
            from knora.providers.generation import GenerationFailure

            self.calls.append(kwargs)
            raise GenerationFailure(
                "GENERATION_OUTPUT_INVALID",
                {
                    "failure": "invalid_generation_completion",
                    "completion_digest": "bad-json",
                    "provider": {
                        "provider": "cloudflare-workers-ai",
                        "provider_request_id": "bad-1",
                    },
                },
            )
        return await super().generate(**kwargs)

    async def repair_grounded_generation(self, *, question, evidence, feedback):
        self.feedback.append(feedback)
        result = await ProjectedGenerator.generate(self, question=question, evidence=evidence)
        if self.refusal:
            return replace(
                result,
                decision="REFUSAL",
                answer=None,
                cited_evidence_ids=(),
                answer_projection=None,
                refusal_reason="INSUFFICIENT_EVIDENCE",
            )
        if self.repeat:
            return result
        from knora.providers.openai_compatible.answer_blocks import compose_grounded_answer

        answer, aliases, projection = compose_grounded_answer(
            {
                "decision": "ANSWER",
                "before": [{"text": "Đổi trả trong 7 ngày.", "support": ["E1"]}],
                "items": [],
                "after": [],
                "refusal_reason": None,
            },
            evidence,
        )
        return replace(
            result, answer=answer, cited_evidence_ids=aliases, answer_projection=projection
        )


class RecoverableVerifier(SupportVerifier):
    def __init__(self, *, malformed=False):
        super().__init__()
        self.malformed = malformed

    async def verify(self, **kwargs):
        from knora.answering.answer_support import AnswerSupportFailure

        if not self.calls:
            self.calls.append(kwargs)
            raise AnswerSupportFailure(
                "GENERATION_OUTPUT_INVALID",
                {"failure": "invalid_verifier_envelope", "completion_digest": "wire-1"}
                if self.malformed
                else {
                    "failure": "unsupported_answer",
                    "failed_id": "S1",
                    "verdict": {
                        "statements": [{"id": "S1", "verdict": "UNKNOWN", "source_refs": []}],
                        "groups": [{"id": "question", "verdict": "MISSING", "statement_ids": []}],
                    },
                },
            )
        return await super().verify(**kwargs)


async def run_recovery_case(generator, verifier):
    store, service = generation_repair_case(generator, verifier=verifier)
    result = await service.execute(
        QuestionCommand(workspace_id="workspace-a", question="Đổi trả trong bao nhiêu ngày?"),
        WorkspacePrincipal(workspace_id="workspace-a", key_id="test"),
    )
    return result, store


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome", ["supported", "unavailable", "foreign"])
async def test_source_preparation_avoids_discarded_generation_but_requires_fresh_proof(outcome):
    class SourceVerifier(SupportVerifier):
        async def prepare_candidate(self, **kwargs):
            assert "answer" not in kwargs and "feedback" not in kwargs
            return [{"text": "Đổi trả trong 7 ngày.", "support": ["E1"]}], {
                "provider": "other-provider" if outcome == "foreign" else "cloudflare-workers-ai",
                "model": "@cf/openai/gpt-oss-120b",
                "provider_request_id": "source-generation-receipt",
                "source_inventory": {"binding": "same-snapshot"},
            }

        async def verify(self, **kwargs):
            assert kwargs["feedback"]["source_inventory"] == {"binding": "same-snapshot"}
            return await super().verify(**kwargs)

    generator, verifier = RecoverableGenerator(), SourceVerifier(outcome)
    store, service = generation_repair_case(generator, verifier=verifier)
    command = QuestionCommand(workspace_id="workspace-a", question="Đổi trả trong bao nhiêu ngày?")
    principal = WorkspacePrincipal(workspace_id="workspace-a", key_id="test")
    if outcome in {"unavailable", "foreign"}:
        with pytest.raises(KnoraError, match="PROVIDER_REQUEST_FAILED"):
            await service.execute(command, principal)
    else:
        result = await service.execute(command, principal)
        assert result.answer == "Đổi trả trong **7 ngày**. [[E1]]"
    assert generator.calls == [] and generator.feedback == []
    attempts = store.traces[0].provider_metadata["generation_recovery"]["attempts"]
    assert [a["phase"] for a in attempts] == (
        ["source_generation"] if outcome == "foreign" else ["source_generation", "verification"]
    )
    assert attempts[0]["provider"]["provider_request_id"] == "source-generation-receipt"


@pytest.mark.asyncio
@pytest.mark.parametrize("sufficiency", ["insufficient", "unavailable"])
async def test_empty_source_draft_is_not_itself_proof_of_insufficiency(sufficiency):
    class EmptySource(SupportVerifier):
        async def prepare_candidate(self, **kwargs):
            return [], {"provider": "cloudflare-workers-ai", "provider_request_id": "empty-draft"}

        async def assess_sufficiency(self, **kwargs):
            assert "answer" not in kwargs
            if sufficiency == "unavailable":
                raise KnoraError("PROVIDER_REQUEST_FAILED")
            return True, {"provider_request_id": "independent-sufficiency"}

    generator = RecoverableGenerator()
    store, service = generation_repair_case(generator, verifier=EmptySource())
    if sufficiency == "unavailable":
        with pytest.raises(KnoraError, match="PROVIDER_REQUEST_FAILED"):
            await service.execute(
                QuestionCommand(
                    workspace_id="workspace-a", question="Đổi trả trong bao nhiêu ngày?"
                ),
                WorkspacePrincipal(workspace_id="workspace-a", key_id="test"),
            )
        assert store.traces[0].validation_outcome == "invalid"
    else:
        result = await service.execute(
            QuestionCommand(workspace_id="workspace-a", question="Đổi trả trong bao nhiêu ngày?"),
            WorkspacePrincipal(workspace_id="workspace-a", key_id="test"),
        )
        assert result.decision == "REFUSAL"
        support = store.traces[0].provider_metadata["answer_support"]
        assert support["coverage"] == "unverified" and support["scope"] == "provided_evidence"
    assert not generator.calls


@pytest.mark.asyncio
async def test_recovery_does_not_rebuild_the_same_rejected_inventory_candidate():
    from knora.answering.answer_support import AnswerSupportFailure
    from knora.providers.openai_compatible.answer_blocks import compose_grounded_answer

    class SourceVerifier(SupportVerifier):
        async def prepare_candidate(self, **kwargs):
            return [{"text": "Đổi trả trong 7 ngày.", "support": ["E1"]}], {
                "provider": "cloudflare-workers-ai",
                "source_inventory": {"binding": "same"},
            }

        async def verify(self, **kwargs):
            if not self.calls:
                self.calls.append(kwargs)
                raise AnswerSupportFailure(
                    "GENERATION_OUTPUT_INVALID",
                    {
                        "failure": "unsupported_answer",
                        "failed_id": "S1",
                        "source_facts": [{"id": "question", "source_fact": "Seven days."}],
                        "repair_facts": [{"text": "Đổi trả trong 7 ngày.", "support": ["E1"]}],
                        "verdict": {"statements": [{"id": "S1", "verdict": "UNKNOWN"}]},
                    },
                )
            return await super().verify(**kwargs)

    class Repair(RecoverableGenerator):
        async def repair_grounded_generation(self, *, question, evidence, feedback):
            self.feedback.append(feedback)
            result = await ProjectedGenerator.generate(self, question=question, evidence=evidence)
            answer, aliases, projection = compose_grounded_answer(
                {
                    "decision": "ANSWER",
                    "before": [{"text": "Thời hạn đổi trả là 7 ngày.", "support": ["E1"]}],
                    "items": [],
                    "after": [],
                    "refusal_reason": None,
                },
                evidence,
            )
            return replace(
                result, answer=answer, cited_evidence_ids=aliases, answer_projection=projection
            )

    generator = Repair()
    result, store = await run_recovery_case(generator, SourceVerifier())
    assert result.decision == "ANSWER" and len(generator.feedback) == 1
    assert [
        a["phase"] for a in store.traces[0].provider_metadata["generation_recovery"]["attempts"]
    ] == [
        "source_generation",
        "verification",
        "repair",
        "verification",
    ]


@pytest.mark.asyncio
async def test_v3_malformed_generation_is_repaired_and_proof_is_persisted():
    from knora.answering.answer_support import validate_trace_support

    generator, verifier = RecoverableGenerator(malformed=True), SupportVerifier()
    result, store = await run_recovery_case(generator, verifier)
    assert result.answer == "Đổi trả trong **7 ngày**. [[E1]]"
    audit = store.traces[0].provider_metadata["generation_recovery"]
    assert [a["phase"] for a in audit["attempts"]] == ["generation", "repair", "verification"]
    assert audit["attempts"][0]["observation"]["provider"]["provider_request_id"] == "bad-1"
    assert generator.feedback[0]["failure"] == "invalid_generation_completion"
    trace = store.traces[0]
    source = trace.provider_metadata["answer_support"]["snapshot_binding"]["sources"][0]
    validate_trace_support(
        trace, {trace.alias_mapping["E1"]: ("Đổi trả trong 7 ngày.", source["content_checksum"])}
    )


@pytest.mark.asyncio
async def test_v3_semantic_rejection_gets_corrected_answer_and_fresh_proof():
    generator, verifier = RecoverableGenerator(), RecoverableVerifier()
    result, store = await run_recovery_case(generator, verifier)
    assert result.answer == "Đổi trả trong **7 ngày**. [[E1]]"
    assert (
        verifier.calls[0]["answer_projection"].answer_digest
        != verifier.calls[1]["answer_projection"].answer_digest
    )
    assert generator.feedback[0]["verdict"]["statements"][0]["verdict"] == "UNKNOWN"
    assert store.traces[0].provider_metadata["answer_support"]["status"] == "supported"


@pytest.mark.asyncio
@pytest.mark.parametrize("final_outcome", ["supported", "unavailable"])
@pytest.mark.parametrize("preparation", [False, True])
async def test_inventory_repair_builds_a_new_candidate_then_requires_fresh_proof(
    final_outcome, preparation
):
    from knora.answering.answer_support import AnswerSupportFailure

    class Verifier(SupportVerifier):
        async def verify(self, **kwargs):
            if not self.calls:
                self.calls.append(kwargs)
                raise AnswerSupportFailure(
                    "GENERATION_OUTPUT_INVALID",
                    {
                        "failure": "source_candidate_ready"
                        if preparation
                        else "unsupported_answer",
                        "failed_id": "S1",
                        "repair_facts": [{"text": "Đổi trả trong 7 ngày.", "support": ["E1"]}],
                        "provider": {"source_inventory": {"binding": "same-snapshot"}},
                        "verdict": {"statements": [{"id": "S1", "verdict": "UNKNOWN"}]},
                    },
                )
            assert (
                kwargs["answer_projection"].answer_digest
                != self.calls[0]["answer_projection"].answer_digest
            )
            assert kwargs["feedback"]["source_inventory"] == {"binding": "same-snapshot"}
            return await super().verify(**kwargs)

    generator, verifier = RecoverableGenerator(), Verifier(final_outcome)
    store, service = generation_repair_case(generator, verifier=verifier)
    command = QuestionCommand(workspace_id="workspace-a", question="Đổi trả trong bao nhiêu ngày?")
    principal = WorkspacePrincipal(workspace_id="workspace-a", key_id="test")
    if final_outcome == "unavailable":
        with pytest.raises(KnoraError, match="PROVIDER_REQUEST_FAILED"):
            await service.execute(command, principal)
        assert store.traces[0].validation_outcome == "invalid"
        assert store.traces[0].provider_metadata["answer_support"]["status"] == "unavailable"
    else:
        result = await service.execute(command, principal)
        assert result.decision == "ANSWER"
    assert len(verifier.calls) == 2
    assert not generator.feedback
    attempts = store.traces[0].provider_metadata["generation_recovery"]["attempts"]
    assert [a["phase"] for a in attempts] == [
        "generation",
        "verification",
        "source_repair",
        "verification",
    ]
    assert attempts[2]["operation"] == "compose_inventory_candidate"
    assert "provider" not in attempts[2]


@pytest.mark.asyncio
async def test_source_preparation_does_not_reject_an_identical_valid_draft():
    from knora.answering.answer_support import AnswerSupportFailure
    from knora.providers.openai_compatible.answer_blocks import compose_grounded_answer

    class SameDraft(RecoverableGenerator):
        async def generate(self, **kwargs):
            result = await super().generate(**kwargs)
            answer, aliases, projection = compose_grounded_answer(
                dict(
                    decision="ANSWER",
                    before=[],
                    items=[{"text": "Đổi trả trong 7 ngày.", "support": ["E1"]}],
                    after=[],
                    refusal_reason=None,
                ),
                kwargs["evidence"],
            )
            return replace(
                result, answer=answer, cited_evidence_ids=aliases, answer_projection=projection
            )

    class Prepare(SupportVerifier):
        async def verify(self, **kwargs):
            if not self.calls:
                self.calls.append(kwargs)
                raise AnswerSupportFailure(
                    "GENERATION_OUTPUT_INVALID",
                    {
                        "failure": "source_candidate_ready",
                        "repair_facts": [{"text": "Đổi trả trong 7 ngày.", "support": ["E1"]}],
                        "provider": {"source_inventory": {"binding": "same"}},
                    },
                )
            assert kwargs["answer"] == self.calls[0]["answer"]
            return await super().verify(**kwargs)

    result, store = await run_recovery_case(SameDraft(), Prepare())
    assert result.decision == "ANSWER"
    assert store.traces[0].provider_metadata["generation_recovery"]["stop_reason"] == "supported"


@pytest.mark.asyncio
@pytest.mark.parametrize("statement_verdict", ["SUPPORTED", "UNKNOWN"])
async def test_missing_covered_group_repairs_without_redundant_sufficiency_call(statement_verdict):
    from knora.answering.answer_support import AnswerSupportFailure

    class Verifier(SupportVerifier):
        async def assess_sufficiency(self, **kwargs):
            pytest.fail("A missing group with source facts already has actionable repair data")

        async def verify(self, **kwargs):
            if not self.calls:
                self.calls.append(kwargs)
                group_id = kwargs["groups"][0][0]
                raise AnswerSupportFailure(
                    "GENERATION_OUTPUT_INVALID",
                    {
                        "failure": "unsupported_answer",
                        "failed_id": group_id if statement_verdict == "SUPPORTED" else "S1",
                        "source_facts": [{"id": group_id, "source_fact": "Seven days."}],
                        "verdict": {
                            "statements": [{"id": "S1", "verdict": statement_verdict}],
                            "groups": [
                                {"id": group_id, "verdict": "MISSING", "statement_ids": ["S1"]}
                            ],
                        },
                    },
                )
            return await super().verify(**kwargs)

    generator, verifier = RecoverableGenerator(), Verifier()
    result, store = await run_recovery_case(generator, verifier)
    assert result.decision == "ANSWER"
    assert generator.feedback[0]["source_facts"][0]["source_fact"] == "Seven days."
    assert [
        a["phase"] for a in store.traces[0].provider_metadata["generation_recovery"]["attempts"]
    ] == ["generation", "verification", "repair", "verification"]


@pytest.mark.asyncio
@pytest.mark.parametrize("fact_mismatch", [False, True])
async def test_source_facts_do_not_skip_sufficiency_after_failed_repair_or_fact_mismatch(
    fact_mismatch,
):
    from knora.answering.answer_support import AnswerSupportFailure

    class Verifier(SupportVerifier):
        async def verify(self, **kwargs):
            self.calls.append(kwargs)
            raise AnswerSupportFailure(
                "GENERATION_OUTPUT_INVALID",
                {
                    "failure": "unsupported_answer",
                    "failed_id": "S1",
                    "source_facts": [{"id": kwargs["groups"][0][0], "source_fact": "Seven days."}],
                    "verdict": {"statements": [{"id": "S1", "verdict": "UNKNOWN"}]},
                    **(
                        {"fact_mismatch": "Page count is not required length"}
                        if fact_mismatch
                        else {}
                    ),
                },
            )

        async def assess_sufficiency(self, **kwargs):
            assert len(self.calls) == (1 if fact_mismatch else 2)
            assert "answer" not in kwargs
            return True, {"result": {"groups": []}}

    generator, verifier = RecoverableGenerator(), Verifier()
    result, store = await run_recovery_case(generator, verifier)
    assert result.decision == "REFUSAL"
    assert len(generator.feedback) == (0 if fact_mismatch else 1)
    assert store.traces[0].provider_metadata["answer_support"]["coverage"] == "unverified"


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome", ["insufficient", "answerable", "unavailable", "stale"])
async def test_semantic_recovery_only_refuses_after_independent_sufficiency_check(outcome):
    class Verifier(RecoverableVerifier):
        async def assess_sufficiency(self, **kwargs):
            assert "answer" not in kwargs
            if outcome == "unavailable":
                raise KnoraError("PROVIDER_REQUEST_FAILED")
            if outcome == "stale":
                raise KnoraError("RETRIEVAL_PROVENANCE_INVALID")
            return outcome == "insufficient", {
                "provider_request_id": "source-check",
                "result": {"groups": []},
            }

    generator, verifier = RecoverableGenerator(), Verifier()
    store, service = generation_repair_case(generator, verifier=verifier)
    if outcome in {"unavailable", "stale"}:
        with pytest.raises(
            KnoraError,
            match="PROVIDER_REQUEST_FAILED"
            if outcome == "unavailable"
            else "RETRIEVAL_PROVENANCE_INVALID",
        ):
            await service.execute(
                QuestionCommand(
                    workspace_id="workspace-a", question="Đổi trả trong bao nhiêu ngày?"
                ),
                WorkspacePrincipal(workspace_id="workspace-a", key_id="test"),
            )
        assert not generator.feedback
        assert store.traces[0].validation_outcome == "invalid"
    else:
        result, store = await run_recovery_case(generator, verifier)
        if outcome == "insufficient":
            assert result.decision == "REFUSAL" and result.answer is None
            assert result.refusal_reason == "INSUFFICIENT_EVIDENCE"
            assert not generator.feedback
            observation = store.traces[0].provider_metadata["answer_support"]
            assert observation["coverage"] == "unverified"
            assert observation["scope"] == "provided_evidence"
        else:
            assert result.answer == "Đổi trả trong **7 ngày**. [[E1]]"
            assert generator.feedback
        assert store.traces[0].validation_outcome == "valid"


@pytest.mark.asyncio
async def test_v3_verifier_format_repair_keeps_same_candidate():
    generator, verifier = RecoverableGenerator(), RecoverableVerifier(malformed=True)
    result, store = await run_recovery_case(generator, verifier)
    assert result.decision == "ANSWER"
    assert len(generator.calls) == 1 and not generator.feedback
    assert verifier.calls[0]["answer"] == verifier.calls[1]["answer"]
    assert verifier.calls[1]["feedback"]["failure"] == "invalid_verifier_envelope"
    assert len(store.traces[0].provider_metadata["generation_recovery"]["attempts"]) == 3


@pytest.mark.asyncio
@pytest.mark.parametrize("refusal", [False, True])
async def test_v3_repair_cannot_repeat_rejected_candidate_or_hide_as_refusal(refusal):
    generator, verifier = RecoverableGenerator(repeat=True, refusal=refusal), RecoverableVerifier()
    store, service = generation_repair_case(generator, verifier=verifier)
    with pytest.raises(KnoraError, match="GENERATION_OUTPUT_INVALID"):
        await service.execute(
            QuestionCommand(workspace_id="workspace-a", question="Đổi trả trong bao nhiêu ngày?"),
            WorkspacePrincipal(workspace_id="workspace-a", key_id="test"),
        )
    assert len(generator.calls) == 2 and len(verifier.calls) == 1
    assert store.traces[0].validation_outcome == "invalid"


@pytest.mark.asyncio
async def test_v3_unavailable_provider_is_not_retried_with_recovery_enabled():
    generator, verifier = RecoverableGenerator(), SupportVerifier("unavailable")
    store, service = generation_repair_case(generator, verifier=verifier)
    with pytest.raises(KnoraError, match="PROVIDER_REQUEST_FAILED"):
        await service.execute(
            QuestionCommand(workspace_id="workspace-a", question="Đổi trả trong bao nhiêu ngày?"),
            WorkspacePrincipal(workspace_id="workspace-a", key_id="test"),
        )
    assert len(generator.calls) == 1 and not generator.feedback
    assert store.traces[0].validation_outcome == "invalid"


@pytest.mark.asyncio
async def test_v3_repeated_malformed_verifier_stops_without_regeneration():
    from knora.answering.answer_support import AnswerSupportFailure

    class BrokenVerifier(SupportVerifier):
        async def verify(self, **kwargs):
            self.calls.append(kwargs)
            raise AnswerSupportFailure(
                "GENERATION_OUTPUT_INVALID",
                {
                    "failure": "invalid_verifier_envelope",
                    "completion_digest": "same-wire",
                    "provider": {"provider_request_id": str(len(self.calls))},
                },
            )

    generator, verifier = RecoverableGenerator(), BrokenVerifier()
    store, service = generation_repair_case(generator, verifier=verifier)
    with pytest.raises(KnoraError, match="GENERATION_OUTPUT_INVALID"):
        await service.execute(
            QuestionCommand(workspace_id="workspace-a", question="Đổi trả trong bao nhiêu ngày?"),
            WorkspacePrincipal(workspace_id="workspace-a", key_id="test"),
        )
    assert len(verifier.calls) == 2 and len(generator.calls) == 1
    assert (
        store.traces[0].provider_metadata["generation_recovery"]["stop_reason"]
        == "repeated_failure"
    )


@pytest.mark.asyncio
async def test_v3_recovery_uses_original_request_deadline_and_records_cancellation(monkeypatch):
    from knora.answering.answer_support import AnswerSupportFailure

    timeout = asyncio.timeout
    monkeypatch.setattr(
        asyncio, "timeout", lambda seconds: timeout(0.1 if seconds == 90 else seconds)
    )

    class SlowVerifier(SupportVerifier):
        async def verify(self, **kwargs):
            self.calls.append(kwargs)
            if len(self.calls) == 1:
                # Consume the first request's budget; the recovery must not start a new one.
                await asyncio.sleep(0.06)
                raise AnswerSupportFailure(
                    "GENERATION_OUTPUT_INVALID",
                    {
                        "failure": "invalid_verifier_envelope",
                        "completion_digest": "first-wire",
                    },
                )
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError as error:
                error.observation = {"provider": {"provider_request_id": "completed-selection"}}
                raise

    generator, verifier = RecoverableGenerator(), SlowVerifier()
    store, service = generation_repair_case(generator, verifier=verifier)
    with pytest.raises(KnoraError, match="PROVIDER_REQUEST_FAILED"):
        await service.execute(
            QuestionCommand(workspace_id="workspace-a", question="Đổi trả trong bao nhiêu ngày?"),
            WorkspacePrincipal(workspace_id="workspace-a", key_id="test"),
        )
    assert len(verifier.calls) == 2
    audit = store.traces[0].provider_metadata["generation_recovery"]
    assert audit["attempts"][-1]["status"] == "cancelled"
    assert audit["attempts"][-1]["observation"]["provider"]["provider_request_id"] == (
        "completed-selection"
    )
    assert audit["stop_reason"] == "cancelled_or_deadline"
    assert store.traces[0].validation_outcome == "invalid"


@pytest.mark.asyncio
async def test_v3_generation_parse_failure_always_has_invalid_trace():
    class BrokenGenerator(RecoverableGenerator):
        async def repair_grounded_generation(self, **kwargs):
            return await self.generate(question=kwargs["question"], evidence=kwargs["evidence"])

    generator = BrokenGenerator(malformed=True)
    store, service = generation_repair_case(generator, verifier=SupportVerifier())
    with pytest.raises(KnoraError, match="GENERATION_OUTPUT_INVALID"):
        await service.execute(
            QuestionCommand(workspace_id="workspace-a", question="Đổi trả trong bao nhiêu ngày?"),
            WorkspacePrincipal(workspace_id="workspace-a", key_id="test"),
        )
    assert len(store.traces) == 1
    assert store.traces[0].generation_status == "failed"
    assert store.traces[0].validation_outcome == "invalid"
    assert store.traces[0].answer is None


@pytest.mark.asyncio
async def test_v3_snapshot_change_during_repair_prevents_verification():
    generator, verifier = RecoverableGenerator(), RecoverableVerifier()
    store, service = generation_repair_case(generator, verifier=verifier)
    original_revalidate = store.revalidate_lexical_snapshot

    def fence(*args):
        original_revalidate(*args)
        if len(generator.calls) > 1:
            raise KnoraError("RETRIEVAL_PROVENANCE_INVALID")

    store.revalidate_lexical_snapshot = fence
    with pytest.raises(KnoraError, match="RETRIEVAL_PROVENANCE_INVALID"):
        await service.execute(
            QuestionCommand(workspace_id="workspace-a", question="Đổi trả trong bao nhiêu ngày?"),
            WorkspacePrincipal(workspace_id="workspace-a", key_id="test"),
        )
    assert len(generator.calls) == 2 and len(verifier.calls) == 1
    assert store.traces[0].validation_outcome == "invalid"


@pytest.mark.asyncio
async def test_v3_recovery_has_no_arbitrary_two_call_ceiling():
    from knora.answering.answer_support import AnswerSupportFailure

    class SeveralFormats(SupportVerifier):
        async def verify(self, **kwargs):
            if len(self.calls) < 3:
                self.calls.append(kwargs)
                raise AnswerSupportFailure(
                    "GENERATION_OUTPUT_INVALID",
                    {
                        "failure": "invalid_verifier_envelope",
                        "completion_digest": f"wire-{len(self.calls)}",
                    },
                )
            return await super().verify(**kwargs)

    generator, verifier = RecoverableGenerator(), SeveralFormats()
    result, store = await run_recovery_case(generator, verifier)
    assert result.decision == "ANSWER" and len(verifier.calls) == 4
    assert len(generator.calls) == 1
    assert len(store.traces[0].provider_metadata["generation_recovery"]["attempts"]) == 5


@pytest.mark.asyncio
@pytest.mark.parametrize("final_outcome", ["supported", "unavailable"])
async def test_v3_unsupported_extra_statement_is_removed_then_entire_answer_reverified(
    final_outcome,
):
    from knora.answering.answer_support import AnswerSupportFailure
    from knora.providers.openai_compatible.answer_blocks import compose_grounded_answer

    class ExtraClaim(RecoverableGenerator):
        async def generate(self, *, question, evidence):
            self.calls.append((question, evidence))
            answer, aliases, projection = compose_grounded_answer(
                {
                    "decision": "ANSWER",
                    "before": [
                        {"text": "Đổi trả trong 7 ngày.", "support": ["E1"]},
                        {"text": "Luôn được miễn phí vận chuyển.", "support": ["E1"]},
                    ],
                    "items": [],
                    "after": [],
                    "refusal_reason": None,
                },
                evidence,
            )
            return GenerationResult(
                "ANSWER",
                answer,
                aliases,
                None,
                provider="cloudflare-workers-ai",
                answer_projection=projection,
            )

    class RejectExtra(SupportVerifier):
        async def verify(self, **kwargs):
            if not self.calls:
                self.calls.append(kwargs)
                raise AnswerSupportFailure(
                    "GENERATION_OUTPUT_INVALID",
                    {
                        "failure": "unsupported_answer",
                        "failed_id": "S2",
                        "verdict": {
                            "statements": [
                                {"id": "S1", "verdict": "SUPPORTED", "source_refs": []},
                                {"id": "S2", "verdict": "UNKNOWN", "source_refs": []},
                            ],
                            "groups": [],
                        },
                    },
                )
            return await super().verify(**kwargs)

    generator, verifier = ExtraClaim(), RejectExtra(final_outcome)
    if final_outcome == "unavailable":
        store, service = generation_repair_case(generator, verifier=verifier)
        with pytest.raises(KnoraError, match="PROVIDER_REQUEST_FAILED"):
            await service.execute(
                QuestionCommand(
                    workspace_id="workspace-a", question="Đổi trả trong bao nhiêu ngày?"
                ),
                WorkspacePrincipal(workspace_id="workspace-a", key_id="test"),
            )
        assert len(generator.calls) == 1 and len(verifier.calls) == 2
        assert store.traces[0].validation_outcome == "invalid"
        return
    result, store = await run_recovery_case(generator, verifier)
    assert result.answer == "Đổi trả trong **7 ngày**. [[E1]]"
    assert len(generator.calls) == 1 and not generator.feedback
    assert len(verifier.calls) == 2
    assert (
        verifier.calls[0]["answer_projection"].answer_digest
        != verifier.calls[1]["answer_projection"].answer_digest
    )
    assert store.traces[0].provider_metadata["answer_support"]["status"] == "supported"
