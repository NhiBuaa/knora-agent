"""Offline S2.1 application contracts; no index/runtime or semantic quality claim."""

from dataclasses import asdict, replace
from types import SimpleNamespace

import httpx
import pytest

from knora.answering import stores
from knora.answering.interface import QuestionCommand
from knora.answering.module import AnswerQuestion
from knora.domain.access import WorkspacePrincipal
from knora.domain.errors import KnoraError
from knora.providers.generation import GenerationResult


def generation():
    return stores.LexicalGeneration(
        workspace_id="workspace",
        document_id="doc",
        document_version_id="version",
        chunk_set_id="chunks",
        index_generation_id="index-1",
        lexical_policy_id="bm25-unicode-word-v1",
    )


def candidate(index=1, *, score=12.5):
    return stores.RetrievalCandidate(
        document_id="doc",
        document_version_id="version",
        source_key="policy",
        source_name="policy.pdf",
        chunk_set_id="chunks",
        embedding_set_id=None,
        embedding_configuration_id=None,
        chunk_id=f"chunk-{index}",
        chunk_ordinal=index - 1,
        heading_path=(),
        start_line=1,
        end_line=1,
        content=f"Fact {index}.",
        content_checksum=f"checksum-{index}",
        token_count=2,
        cosine_distance=None,
        similarity=None,
        page_start=1,
        page_end=1,
        start_offset=0,
        end_offset=7,
        bm25_score=score,
        bm25_rank=index,
        index_generation_id="index-1",
    )


def observation(item, *, status="ELIGIBLE", reason=None):
    return stores.BranchObservation(
        branch="bm25",
        status=status,
        chunk_id=item.chunk_id,
        branch_rank=item.bm25_rank,
        raw_score=item.bm25_score,
        score_kind="bm25",
        index_generation_id="index-1",
        lexical_policy_id="bm25-unicode-word-v1",
        decision_reason=reason,
    )


class NeverEmbed:
    def embed(self, *args):
        pytest.fail("BM25 must not invoke an embedding provider")

    embed_queries = embed


class LocalGenerator:
    calls = 0

    async def generate(self, *, question, evidence):
        self.calls += 1
        assert evidence[0].evidence_id == "E1"
        return GenerationResult(
            decision="ANSWER",
            answer="Fact 1. [[E1]]",
            cited_evidence_ids=("E1",),
            refusal_reason=None,
            provider="deterministic-local",
            model="stub",
            prompt_version="offline-test",
        )


class LexicalStore:
    def __init__(self, items=None):
        self.items = (candidate(),) if items is None else items
        self.ready = []
        self.requests = []
        self.traces = []
        observations = tuple(observation(c) for c in self.items) or (
            stores.BranchObservation(
                branch="bm25",
                status="NO_CONTRIBUTION",
                score_kind="bm25",
                lexical_policy_id="bm25-unicode-word-v1",
            ),
        )
        self.result = stores.RetrievalResult(
            candidates=self.items,
            branch_observations=observations,
            chunk_set_ids=("chunks",),
            lexical_generations=(generation(),),
        )

    def require_compatible_corpus(self, *args):
        pytest.fail("BM25 readiness must be independent of EmbeddingSets")

    def require_lexical_corpus(self, workspace_id, lexical_policy_id):
        self.ready.append((workspace_id, lexical_policy_id))

    def retrieve_candidates(self, **kwargs):
        self.requests.append(kwargs)
        return self.result

    def persist_trace(self, trace):
        self.traces.append(trace)
        return "trace-1"


async def execute(store, *, embedding_provider=None):
    generator = LocalGenerator()
    service = AnswerQuestion(
        embedding_provider=embedding_provider,
        embedding_configuration=None,
        generation_provider=generator,
        store=store,
        retrieval_configuration=stores.RetrievalConfiguration.bm25_diagnostic_v1(),
    )
    response = await service.execute(
        QuestionCommand(workspace_id="workspace", question="Fact?"),
        WorkspacePrincipal(workspace_id="workspace", key_id="offline"),
    )
    return response, generator


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", [None, NeverEmbed()])
async def test_bm25_answers_without_embedding_or_embedding_set(provider):
    store = LexicalStore()
    response, generator = await execute(store, embedding_provider=provider)
    assert response.decision == "ANSWER"
    assert response.citations[0].document_version_id == "version"
    assert generator.calls == 1
    assert store.ready == [("workspace", "bm25-unicode-word-v1")]
    assert store.requests[0]["query_vector"] is None
    assert store.requests[0]["embedding_configuration"] is None
    trace = store.traces[0]
    assert trace.embedding_configuration_id is None
    assert trace.embedding_set_ids == ()
    assert trace.trace_schema_version == 3
    assert trace.provider_metadata["embedding"] == {"status": "not_run"}
    assert trace.provider_metadata["timing"]["phases"]["query_embedding"]["status"] == "not_run"
    assert trace.provider_metadata["retrieval"]["lexical_generations"] == [asdict(generation())]
    assert trace.candidate_decisions[0]["bm25_contribution"] == {
        "raw_score": 12.5,
        "branch_rank": 1,
        "index_generation_id": "index-1",
    }


@pytest.mark.asyncio
async def test_empty_bm25_refuses_without_generation_or_fabricated_provider_usage():
    store = LexicalStore(())
    response, generator = await execute(store)
    assert response.decision == "REFUSAL"
    assert generator.calls == 0
    assert "generation" not in store.traces[0].provider_metadata
    assert store.traces[0].branch_observations[0]["status"] == "NO_CONTRIBUTION"


@pytest.mark.asyncio
@pytest.mark.parametrize("drift", ["embedding", "generation", "workspace", "score", "branch"])
async def test_bm25_rejects_invalid_provenance_before_generation(drift):
    store = LexicalStore()
    if drift == "embedding":
        store.result = replace(
            store.result, candidates=(replace(candidate(), embedding_set_id="fake"),)
        )
    elif drift == "generation":
        store.result = replace(store.result, lexical_generations=())
    elif drift == "workspace":
        store.result = replace(
            store.result, lexical_generations=(replace(generation(), workspace_id="foreign"),)
        )
    elif drift == "score":
        store.result = replace(store.result, candidates=(candidate(score=float("nan")),))
    else:
        store.result = replace(store.result, branch_observations=())
    with pytest.raises(KnoraError, match="RETRIEVAL_PROVENANCE_INVALID"):
        await execute(store)
    assert store.traces == []


@pytest.mark.asyncio
async def test_bm25_selection_keeps_native_scores_and_distinct_budget_reasons():
    store = LexicalStore(tuple(candidate(i, score=20 - i) for i in range(1, 8)))
    await execute(store)
    decisions = store.traces[0].candidate_decisions
    assert len(decisions) == 7
    assert sum(d["final_decision"] == "SELECTED" for d in decisions) == 5
    assert decisions[-1]["decision_reason"] == "CHUNK_COUNT_LIMIT"
    assert decisions[-1]["bm25_contribution"]["raw_score"] == 13


@pytest.mark.asyncio
async def test_resolver_selects_lexical_mode_before_embedding_readiness():
    store = LexicalStore()
    service = AnswerQuestion(
        embedding_provider=NeverEmbed(),
        embedding_configuration=None,
        generation_provider=LocalGenerator(),
        store=store,
        retrieval_configuration_resolver=SimpleNamespace(
            resolve=lambda **_: stores.RetrievalConfiguration.bm25_diagnostic_v1()
        ),
    )
    result = await service.execute(
        QuestionCommand(workspace_id="workspace", question="Fact?"),
        WorkspacePrincipal(workspace_id="workspace", key_id="offline"),
    )
    assert result.decision == "ANSWER"


def test_bm25_configuration_is_uncalibrated_and_not_a_vector_threshold():
    config = stores.RetrievalConfiguration.bm25_diagnostic_v1()
    assert config.candidate_k == 200
    assert config.min_similarity is None
    assert config.strategy == "bm25-only"
    assert config.max_evidence_chunks == 5
    assert config.max_evidence_tokens == 3000
    with pytest.raises(ValueError, match="BM25"):
        replace(config, min_similarity=0.65)
    with pytest.raises(ValueError, match="threshold"):
        replace(stores.RetrievalConfiguration.milestone_one(), min_similarity=None)
    assert stores.RetrievalConfiguration.milestone_one().min_similarity == 0.65


@pytest.mark.asyncio
async def test_dense_without_embedding_configuration_fails_closed():
    service = AnswerQuestion(
        embedding_provider=None,
        embedding_configuration=None,
        generation_provider=LocalGenerator(),
        store=SimpleNamespace(),
    )
    with pytest.raises(KnoraError, match="EMBEDDING_CONFIGURATION_REQUIRED"):
        await service.execute(
            QuestionCommand(workspace_id="workspace", question="Fact?"),
            WorkspacePrincipal(workspace_id="workspace", key_id="offline"),
        )


@pytest.mark.asyncio
async def test_postgres_lexical_path_is_explicitly_unavailable_until_s22():
    from knora.adapters.postgres.answering_store import PostgresAnsweringStore

    def no_session():
        pytest.fail("S2.1 must not open a database for lexical readiness")

    with pytest.raises(KnoraError, match="LEXICAL_RETRIEVAL_UNAVAILABLE"):
        await execute(PostgresAnsweringStore(no_session))


@pytest.mark.asyncio
async def test_dense_candidates_cannot_omit_embedding_identity():
    from knora.providers.embedding import EmbeddingBatch, EmbeddingConfiguration

    class DenseStore:
        def require_compatible_corpus(self, *args):
            pass

        def retrieve_candidates(self, **kwargs):
            return (candidate(),)

    class Embeddings:
        def embed(self, texts, configuration):
            return EmbeddingBatch(
                vectors=((0.0,) * configuration.dimensions,),
                provider=configuration.provider,
                model=configuration.model,
            )

    service = AnswerQuestion(
        embedding_provider=Embeddings(),
        embedding_configuration=EmbeddingConfiguration.milestone_one_local(),
        generation_provider=LocalGenerator(),
        store=DenseStore(),
    )
    with pytest.raises(KnoraError, match="RETRIEVAL_PROVENANCE_INVALID"):
        await service.execute(
            QuestionCommand(workspace_id="workspace", question="Fact?"),
            WorkspacePrincipal(workspace_id="workspace", key_id="offline"),
        )


@pytest.mark.asyncio
async def test_bm25_preserves_rank_rejection_without_selecting_it():
    store = LexicalStore()
    rejected = candidate(201, score=0.1)
    store.result = replace(
        store.result,
        branch_observations=store.result.branch_observations
        + (observation(rejected, status="RANK_LIMIT", reason="RANK_LIMIT"),),
    )
    await execute(store)
    assert store.traces[0].branch_observations[-1]["decision_reason"] == "RANK_LIMIT"
    assert store.traces[0].retrieved_chunk_ids == ("chunk-1",)


def projections(store):
    from knora.adapters.postgres.evaluation_reader import EvaluationCandidateProjection

    decisions = {d["chunk_id"]: d for d in store.traces[0].candidate_decisions}
    return tuple(
        EvaluationCandidateProjection(
            chunk_id=c.chunk_id,
            document_version_id=c.document_version_id,
            chunk_set_id=c.chunk_set_id,
            source_key=c.source_key,
            chunk_ordinal=c.chunk_ordinal,
            workspace_id="workspace",
            content=c.content,
            start_line=1,
            end_line=1,
            final_rank=decisions[c.chunk_id]["final_rank"],
            fusion_score=None,
            final_decision=decisions[c.chunk_id]["final_decision"],
            decision_reason=decisions[c.chunk_id]["decision_reason"],
            vector_contribution=None,
            fts_contribution=None,
            raw_sha256="a" * 64,
            parser_configuration_id="pypdf-layout-v2",
            normalizer_configuration_id="normalizer",
            chunking_configuration_id="chunker",
            page_start=1,
            page_end=1,
            start_offset=0,
            end_offset=7,
            content_checksum=c.content_checksum,
            document_id="doc",
            token_count=2,
            bm25_contribution=decisions[c.chunk_id]["bm25_contribution"],
        )
        for c in store.items
    )


@pytest.mark.asyncio
async def test_bm25_offline_reader_and_pdf_capture_preserve_scores_and_selection():
    from evals.runners.pdf_retrieval_v3 import PdfHttpExecutor, build_report

    from knora.adapters.postgres.evaluation_reader import project_bm25_trace

    store = LexicalStore(tuple(candidate(i, score=20 - i) for i in range(1, 8)))
    response, _ = await execute(store)
    projected = projections(store)
    trace = project_bm25_trace(
        trace_id="trace-1",
        record=store.traces[0],
        candidates=projected,
        authorized_generations=(generation(),),
    )
    async with httpx.AsyncClient(
        base_url="http://offline.test",
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=asdict(response))),
    ) as client:
        executor = PdfHttpExecutor(
            client=client,
            headers={},
            reader=SimpleNamespace(
                read_trace=lambda **_: trace, read_pdf_chunks=lambda **_: projected
            ),
            workspace_id="workspace",
            run_id="run",
            embedding_configuration_id=None,
            retrieval_configuration_id="retrieval-bm25-diagnostic-v1",
        )
        row = await executor.execute(
            SimpleNamespace(id="case", question="Fact?", parent_case_id=None)
        )
    assert row["failure_code"] is None
    diagnostic = row["retrieval_diagnostics"]
    assert diagnostic["schema_version"] == 1
    assert diagnostic["ordered_candidate_ids"] == [f"chunk-{i}" for i in range(1, 8)]
    assert diagnostic["generation_evidence_chunk_ids"] == [f"chunk-{i}" for i in range(1, 6)]
    assert diagnostic["candidate_decisions"][-1]["decision_reason"] == "CHUNK_COUNT_LIMIT"
    assert diagnostic["branch_observations"][0]["raw_score"] == 19
    assert diagnostic["score_policy"]["numeric_cutoff"] is None
    assert diagnostic["score_policy"]["beyond_limit"] == "unknown"
    case = SimpleNamespace(id="case", expected_behavior="ANSWER", evidence_groups=(("anchor",),))
    dataset = SimpleNamespace(cases=(case,), dataset_sha256="gold", corpus_sha256="corpus")
    report = build_report(dataset, [row], {"anchor": ("chunk-7",)}, {})
    supplement = report["cases"][0]["retrieval_diagnostics"]
    assert supplement["coverage"]["retrieved_top8"] == [True]
    assert supplement["coverage"]["generation_selected"] == [False]
    assert supplement["branch_observations"][0]["raw_score"] == 19
    assert report["metrics"]["all_evidence_groups_covered"] == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("drift", ["authority", "decision", "alias", "embedding", "policy"])
async def test_lexical_projection_fails_closed_on_provenance_drift(drift):
    from knora.adapters.postgres.evaluation_reader import project_bm25_trace

    store = LexicalStore()
    await execute(store)
    record = store.traces[0]
    authorized = (generation(),)
    if drift == "authority":
        authorized = (replace(generation(), index_generation_id="new-active"),)
    elif drift == "decision":
        record.candidate_decisions[0]["final_decision"] = "REDUNDANT_OVERLAP"
    elif drift == "alias":
        record.alias_mapping["E1"] = "missing"
    elif drift == "embedding":
        record = replace(record, embedding_configuration_id="fabricated")
    else:
        record.provider_metadata["retrieval"]["score_policy"]["numeric_cutoff"] = 0.65
    with pytest.raises(LookupError, match="lexical"):
        project_bm25_trace(
            trace_id="trace-1",
            record=record,
            candidates=projections(store),
            authorized_generations=authorized,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "drift", ["duplicate_rank", "rank_order", "contradiction", "empty_contradiction"]
)
async def test_lexical_observation_invariants_reject_before_generation(drift):
    items = (candidate(1, score=20), candidate(2, score=19))
    if drift == "duplicate_rank":
        items = tuple(replace(c, bm25_rank=99) for c in items)
    elif drift == "rank_order":
        items = (replace(items[0], bm25_rank=2), replace(items[1], bm25_rank=1))
    store = LexicalStore(items)
    if drift == "contradiction":
        extra = observation(items[0], status="REVOKED", reason="REVOKED")
        store.result = replace(
            store.result, branch_observations=store.result.branch_observations + (extra,)
        )
    elif drift == "empty_contradiction":
        extra = stores.BranchObservation(
            branch="bm25",
            status="NO_CONTRIBUTION",
            score_kind="bm25",
            lexical_policy_id="bm25-unicode-word-v1",
        )
        store.result = replace(
            store.result, branch_observations=store.result.branch_observations + (extra,)
        )
    with pytest.raises(KnoraError, match="RETRIEVAL_PROVENANCE_INVALID"):
        await execute(store)
    assert not store.traces


@pytest.mark.asyncio
async def test_lexical_revalidation_can_leave_native_rank_gaps_and_distinct_stale_generation():
    items = (candidate(), replace(candidate(3, score=10), bm25_rank=3))
    store = LexicalStore(items)
    rejected = replace(
        observation(candidate(2, score=11), status="STALE_GENERATION", reason="STALE_GENERATION"),
        index_generation_id="old-index",
    )
    store.result = replace(
        store.result, branch_observations=store.result.branch_observations + (rejected,)
    )
    response, _ = await execute(store)
    assert response.decision == "ANSWER"


@pytest.mark.asyncio
@pytest.mark.parametrize("drift", ["invalid", "not_called", "markers", "empty_completed"])
async def test_lexical_projection_rejects_inconsistent_generation_state(drift):
    from knora.adapters.postgres.evaluation_reader import project_bm25_trace

    store = LexicalStore(()) if drift == "empty_completed" else LexicalStore()
    await execute(store)
    record = store.traces[0]
    changes = {
        "invalid": {"validation_outcome": "invalid"},
        "not_called": {"generation_status": "not_called"},
        "markers": {"answer": "Fact 1. [[E2]]"},
        "empty_completed": {"generation_status": "completed", "validation_outcome": "valid"},
    }
    with pytest.raises(LookupError, match="lexical"):
        project_bm25_trace(
            trace_id="trace-1",
            record=replace(record, **changes[drift]),
            candidates=projections(store),
            authorized_generations=(generation(),),
        )


@pytest.mark.asyncio
async def test_lexical_projection_accepts_empty_selection_refusal():
    from knora.adapters.postgres.evaluation_reader import project_bm25_trace

    store = LexicalStore(())
    await execute(store)
    trace = project_bm25_trace(
        trace_id="trace-1",
        record=store.traces[0],
        candidates=(),
        authorized_generations=(generation(),),
    )
    assert trace.decision == "REFUSAL"


@pytest.mark.asyncio
async def test_lexical_projection_accepts_generated_refusal(monkeypatch):
    from knora.adapters.postgres.evaluation_reader import project_bm25_trace

    async def refuse(self, *, question, evidence):
        return GenerationResult(
            decision="REFUSAL",
            answer=None,
            cited_evidence_ids=(),
            refusal_reason="INSUFFICIENT_EVIDENCE",
        )

    monkeypatch.setattr(LocalGenerator, "generate", refuse)
    store = LexicalStore()
    await execute(store)
    trace = project_bm25_trace(
        trace_id="trace-1",
        record=store.traces[0],
        candidates=projections(store),
        authorized_generations=(generation(),),
    )
    assert trace.decision == "REFUSAL"
    assert trace.alias_mapping == {"E1": "chunk-1"}
