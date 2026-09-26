from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy import event, select, update

from knora.adapters.postgres.answering_store import PostgresAnsweringStore
from knora.adapters.postgres.conversation_store import PostgresConversationStore
from knora.adapters.postgres.database import SessionFactory
from knora.adapters.postgres.document_reader import PostgresDocumentReader
from knora.adapters.postgres.ingestion_store import PostgresIngestionStore
from knora.adapters.postgres.tables import (
    ChunkEmbeddingTable,
    ChunkTable,
    DocumentTable,
    EmbeddingSetTable,
    QuestionTraceTable,
    RetrievalV2CutoverTable,
    WorkspaceTable,
)
from knora.answering.interface import QuestionCommand, QuestionResult
from knora.answering.module import AnswerQuestion
from knora.answering.stores import (
    BranchObservation,
    QuestionTraceRecord,
    RetrievalConfiguration,
)
from knora.domain.access import WorkspacePrincipal
from knora.domain.errors import KnoraError
from knora.ingestion.interface import IngestDocumentCommand
from knora.ingestion.module import IngestDocument
from knora.ingestion.processing import ChunkingConfiguration, DocumentProcessor
from knora.providers.deterministic.embedding import DeterministicEmbeddingProvider
from knora.providers.deterministic.generation import DeterministicGenerationProvider
from knora.providers.embedding import EmbeddingBatch, EmbeddingConfiguration


def ingest(
    workspace_id: str,
    source_key: str,
    *,
    content: bytes = b"# Refunds\n\nRefund requests are accepted within thirty days.\n",
    configuration: EmbeddingConfiguration | None = None,
):
    return IngestDocument(
        processor=DocumentProcessor(),
        embedding_provider=DeterministicEmbeddingProvider(),
        store=PostgresIngestionStore(SessionFactory),
    ).execute(
        IngestDocumentCommand(
            workspace_id=workspace_id,
            source_key=source_key,
            source_name="refunds.md",
            media_type="text/markdown",
            raw_content=content,
            chunking_configuration=ChunkingConfiguration.milestone_one(),
            embedding_configuration=(
                configuration or EmbeddingConfiguration.milestone_one_local()
            ),
        ),
        WorkspacePrincipal(workspace_id=workspace_id, key_id="test"),
    )


def test_readiness_rejects_only_incompatible_active_unarchived_workspace_sets() -> None:
    workspace = f"readiness-{uuid4()}"
    other_workspace = f"readiness-other-{uuid4()}"
    with SessionFactory.begin() as session:
        session.add_all(
            [
                WorkspaceTable(id=workspace, name="Readiness"),
                WorkspaceTable(id=other_workspace, name="Other readiness"),
            ]
        )
    selected = EmbeddingConfiguration(
        id=f"embedding-1024-{uuid4()}",
        provider="deterministic-local",
        model="test-1024",
        dimensions=1024,
        distance_metric="cosine",
    )
    old = EmbeddingConfiguration.milestone_one_local()
    store = PostgresAnsweringStore(SessionFactory)
    store.require_compatible_corpus(workspace, selected.id)
    compatible = ingest(workspace, "support/compatible", configuration=selected)
    store.require_compatible_corpus(workspace, selected.id)
    incompatible = ingest(workspace, "support/old", configuration=old)
    other_old = ingest(other_workspace, "support/other-old", configuration=old)

    with pytest.raises(KnoraError, match="REINDEX_REQUIRED"):
        store.require_compatible_corpus(workspace, selected.id)
    with pytest.raises(KnoraError, match="REINDEX_REQUIRED"):
        store.require_compatible_corpus(workspace, old.id)

    reader = PostgresDocumentReader(SessionFactory)
    reader.archive(
        workspace_id=workspace,
        document_id=incompatible.document_id,
        principal=WorkspacePrincipal(workspace_id=workspace, key_id="test"),
    )

    with SessionFactory() as session:
        selected_vector = tuple(
            session.scalar(
                select(ChunkEmbeddingTable.embedding).where(
                    ChunkEmbeddingTable.embedding_set_id == compatible.embedding_set_id
                )
            )
        )
    candidates = store.retrieve_candidates(
        workspace_id=workspace,
        query_text="refunds",
        query_vector=selected_vector,
        embedding_configuration=selected,
        retrieval_configuration=RetrievalConfiguration.milestone_one(),
    )
    assert candidates
    assert all(candidate.embedding_configuration_id == selected.id for candidate in candidates)

    store.require_compatible_corpus(workspace, selected.id)
    store.require_compatible_corpus(other_workspace, old.id)
    reader.archive(
        workspace_id=other_workspace,
        document_id=other_old.document_id,
        principal=WorkspacePrincipal(workspace_id=other_workspace, key_id="test"),
    )
    store.require_compatible_corpus(other_workspace, selected.id)
    assert compatible.document_id != incompatible.document_id


def test_direct_retrieval_rejects_bad_query_vector_dimension_before_cosine() -> None:
    configuration = EmbeddingConfiguration.milestone_one_local()
    with pytest.raises(KnoraError, match="EMBEDDING_DIMENSION_MISMATCH"):
        PostgresAnsweringStore(SessionFactory).retrieve_candidates(
            workspace_id=f"dimension-{uuid4()}",
            query_text="refund",
            query_vector=tuple([0.0] * 1024),
            embedding_configuration=configuration,
            retrieval_configuration=RetrievalConfiguration.milestone_one(),
        )


@pytest.mark.asyncio
async def test_unarchive_during_query_embedding_requires_reindex_before_generation() -> None:
    workspace = f"readiness-race-{uuid4()}"
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace, name="Readiness race"))
    selected = EmbeddingConfiguration(
        id=f"embedding-1024-{uuid4()}",
        provider="deterministic-local",
        model="test-1024",
        dimensions=1024,
        distance_metric="cosine",
    )
    compatible = ingest(workspace, "support/current", configuration=selected)
    old = ingest(
        workspace,
        "support/old",
        configuration=EmbeddingConfiguration.milestone_one_local(),
    )
    reader = PostgresDocumentReader(SessionFactory)
    principal = WorkspacePrincipal(workspace_id=workspace, key_id="test")
    reader.archive(
        workspace_id=workspace,
        document_id=old.document_id,
        principal=principal,
    )
    with SessionFactory() as session:
        selected_vector = tuple(
            session.scalar(
                select(ChunkEmbeddingTable.embedding).where(
                    ChunkEmbeddingTable.embedding_set_id == compatible.embedding_set_id
                )
            )
        )

    class UnarchivingEmbeddingProvider:
        calls = 0

        def embed(self, texts, configuration):
            self.calls += 1
            reader.unarchive(
                workspace_id=workspace,
                document_id=old.document_id,
                principal=principal,
            )
            return EmbeddingBatch(
                vectors=(selected_vector,),
                provider=configuration.provider,
                model=configuration.model,
            )

    class RecordingGenerationProvider:
        calls = 0

        async def generate(self, **kwargs):
            self.calls += 1
            return await DeterministicGenerationProvider().generate(**kwargs)

    embedding = UnarchivingEmbeddingProvider()
    generation = RecordingGenerationProvider()
    service = AnswerQuestion(
        embedding_provider=embedding,
        generation_provider=generation,
        store=PostgresAnsweringStore(SessionFactory),
        embedding_configuration=selected,
    )

    with pytest.raises(KnoraError, match="REINDEX_REQUIRED"):
        await service.execute(
            QuestionCommand(workspace_id=workspace, question="What is the refund policy?"),
            principal,
        )

    assert embedding.calls == 1
    assert generation.calls == 0


def test_mixed_dimension_vector_queries_guard_distance_in_both_sql_paths() -> None:
    workspace = f"guard-distance-{uuid4()}"
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace, name="Guarded distance"))
    selected = EmbeddingConfiguration(
        id=f"embedding-1024-{uuid4()}",
        provider="deterministic-local",
        model="test-1024",
        dimensions=1024,
        distance_metric="cosine",
    )
    matching = ingest(workspace, "support/matching", configuration=selected)
    ingest(
        workspace,
        "support/below",
        content=b"Galaxies contain stars and interstellar gas.",
        configuration=selected,
    )
    old = ingest(
        workspace, "support/old", configuration=EmbeddingConfiguration.milestone_one_local()
    )
    PostgresDocumentReader(SessionFactory).archive(
        workspace_id=workspace,
        document_id=old.document_id,
        principal=WorkspacePrincipal(workspace_id=workspace, key_id="test"),
    )
    with SessionFactory() as session:
        query_vector = tuple(
            session.scalar(
                select(ChunkEmbeddingTable.embedding).where(
                    ChunkEmbeddingTable.embedding_set_id == matching.embedding_set_id
                )
            )
        )

    vector_sql: list[str] = []

    def capture(_connection, _cursor, statement, _parameters, _context, _many):
        if "<=>" in statement:
            vector_sql.append(statement)

    engine = SessionFactory.kw["bind"]
    event.listen(engine, "before_cursor_execute", capture)
    try:
        result = PostgresAnsweringStore(SessionFactory).retrieve_candidates(
            workspace_id=workspace,
            query_text="refunds",
            query_vector=query_vector,
            embedding_configuration=selected,
            retrieval_configuration=RetrievalConfiguration.milestone_one(),
        )
    finally:
        event.remove(engine, "before_cursor_execute", capture)

    assert any(candidate.embedding_set_id == matching.embedding_set_id for candidate in result)
    assert any(
        observation.status == "BELOW_THRESHOLD"
        for observation in result.branch_observations
    )
    assert len(vector_sql) == 2
    for statement in vector_sql:
        assert "CASE WHEN" in statement
        guarded_expression = statement.split("CASE WHEN", maxsplit=1)[1].split("THEN", maxsplit=1)
        assert "embedding_configuration_id" in guarded_expression[0]
        assert "vector_dims" in guarded_expression[0]
        assert "<=>" in guarded_expression[1]


@pytest.mark.parametrize("hybrid", [False, True])
def test_archive_excludes_new_retrieval_and_unarchive_restores_it(hybrid) -> None:
    workspace = f"archive-{uuid4()}"
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace, name="Archive test"))
    ingested = ingest(workspace, "refunds")
    configuration = EmbeddingConfiguration.milestone_one_local()
    retrieval = replace(
        RetrievalConfiguration.milestone_three_hybrid()
        if hybrid else RetrievalConfiguration.milestone_one(),
        min_similarity=-1.0,
    )
    store = PostgresAnsweringStore(SessionFactory)
    arguments = dict(
        workspace_id=workspace, query_text="refund",
        query_vector=DeterministicEmbeddingProvider().embed(["refund"], configuration).vectors[0],
        embedding_configuration=configuration, retrieval_configuration=retrieval,
    )
    before = store.retrieve_candidates(**arguments)
    assert len(before) > 0
    reader = PostgresDocumentReader(SessionFactory)
    lifecycle_args = dict(
        workspace_id=workspace, document_id=ingested.document_id,
        principal=WorkspacePrincipal(workspace, "test"),
    )
    reader.archive(**lifecycle_args)
    archived = store.retrieve_candidates(**arguments)
    assert len(archived) == 0
    assert archived.embedding_set_ids == ()
    assert archived.chunk_set_ids == ()
    reader.unarchive(**lifecycle_args)
    restored = store.retrieve_candidates(**arguments)
    assert [item.chunk_id for item in restored] == [item.chunk_id for item in before]


def test_retrieval_filters_workspace_and_active_embedding_set_in_sql() -> None:
    workspace_a = f"question-a-{uuid4()}"
    workspace_b = f"question-b-{uuid4()}"
    with SessionFactory.begin() as session:
        session.add_all(
            [
                WorkspaceTable(id=workspace_a, name="Question A"),
                WorkspaceTable(id=workspace_b, name="Question B"),
            ]
        )
    original = ingest(workspace_a, "support/refunds-a")
    changed_content = b"# Refunds\n\nRefund requests are accepted within forty five days.\n"
    active = ingest(workspace_a, "support/refunds-a", content=changed_content)
    ingest(workspace_a, "support/refunds-a-2", content=changed_content)
    other_profile = ingest(
        workspace_a,
        "support/other-configuration",
        content=changed_content,
        configuration=EmbeddingConfiguration(
            id="embedding-other-m1",
            provider="deterministic-local",
            model="text-embedding-3-small",
            dimensions=1536,
            distance_metric="cosine",
        ),
    )
    forbidden = ingest(workspace_b, "support/refunds-b")
    PostgresDocumentReader(SessionFactory).archive(
        workspace_id=workspace_a,
        document_id=other_profile.document_id,
        principal=WorkspacePrincipal(workspace_id=workspace_a, key_id="test"),
    )

    with SessionFactory() as session:
        query_vector = tuple(
            session.scalars(
                select(ChunkEmbeddingTable.embedding)
                .join(
                    EmbeddingSetTable,
                    EmbeddingSetTable.id == ChunkEmbeddingTable.embedding_set_id,
                )
                .where(EmbeddingSetTable.id == forbidden.embedding_set_id)
            ).first()
        )

    candidates = PostgresAnsweringStore(SessionFactory).retrieve_candidates(
        workspace_id=workspace_a,
        query_text="refunds",
        query_vector=query_vector,
        embedding_configuration=EmbeddingConfiguration.milestone_one_local(),
        retrieval_configuration=replace(
            RetrievalConfiguration.milestone_one(), candidate_k=1, min_similarity=0.0
        ),
    )

    assert len(candidates) == 1
    assert candidates[0].source_key in {"support/refunds-a", "support/refunds-a-2"}
    assert candidates[0].similarity < 1.0
    assert all(candidate.embedding_set_id != original.embedding_set_id for candidate in candidates)
    assert all(
        candidate.embedding_set_id == active.embedding_set_id
        for candidate in candidates
        if candidate.source_key == "support/refunds-a"
    )
    assert all(
        candidate.embedding_configuration_id == "embedding-local-m1-v2"
        for candidate in candidates
    )
    assert [
        (-candidate.similarity, candidate.document_id, candidate.chunk_ordinal, candidate.chunk_id)
        for candidate in candidates
    ] == sorted(
        (
            -candidate.similarity,
            candidate.document_id,
            candidate.chunk_ordinal,
            candidate.chunk_id,
        )
        for candidate in candidates
    )


def test_hybrid_uses_explicit_fts_and_rrf_deduplicates_branch_contributions() -> None:
    workspace_id = f"hybrid-{uuid4()}"
    content = b"ZX-42 identifier is eligible for expedited refund processing."
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="Hybrid Retrieval"))
    ingested = ingest(workspace_id, "support/zx-42", content=content)
    configuration = EmbeddingConfiguration.milestone_one_local()
    query_vector = DeterministicEmbeddingProvider().embed(
        [content.decode()], configuration
    ).vectors[0]
    retrieval_configuration = replace(
        RetrievalConfiguration.milestone_three_hybrid(), candidate_k=1, min_similarity=0.0
    )

    store = PostgresAnsweringStore(SessionFactory)
    first = store.retrieve_candidates(
        workspace_id=workspace_id,
        query_text="ZX-42 identifier",
        query_vector=query_vector,
        embedding_configuration=configuration,
        retrieval_configuration=retrieval_configuration,
    )
    second = store.retrieve_candidates(
        workspace_id=workspace_id,
        query_text="ZX-42 identifier",
        query_vector=query_vector,
        embedding_configuration=configuration,
        retrieval_configuration=retrieval_configuration,
    )

    assert [candidate.chunk_id for candidate in first] == [
        candidate.chunk_id for candidate in second
    ]
    assert len(first) == 1
    candidate = first[0]
    assert candidate.embedding_set_id == ingested.embedding_set_id
    assert candidate.vector_contribution == {
        "branch_rank": 1,
        "cosine_distance": candidate.cosine_distance,
        "similarity": candidate.similarity,
    }
    assert candidate.fts_contribution is not None
    assert candidate.fts_contribution["branch_rank"] == 1
    assert candidate.fusion_score == 2 / 61


def test_hybrid_requires_explicit_supported_versioned_policies() -> None:
    store = PostgresAnsweringStore(SessionFactory)
    configuration = EmbeddingConfiguration.milestone_one_local()
    invalid = replace(
        RetrievalConfiguration.milestone_three_hybrid(), fusion_policy_version=None
    )

    with pytest.raises(ValueError, match="unsupported fusion policy"):
        store.retrieve_candidates(
            workspace_id="unused",
            query_text="unused",
            query_vector=tuple([0.0] * configuration.dimensions),
            embedding_configuration=configuration,
            retrieval_configuration=invalid,
        )


def test_hybrid_observes_explicit_fts_ineligibility_for_evaluated_below_threshold_chunk() -> None:
    store = PostgresAnsweringStore(SessionFactory)
    configuration = EmbeddingConfiguration.milestone_one_local()
    retrieval_configuration = RetrievalConfiguration.milestone_three_hybrid()
    below_chunk = "below-threshold-chunk"
    with patch.object(
        store,
        "_vector_observations",
        return_value=(
            BranchObservation(
                branch="vector",
                status="BELOW_THRESHOLD",
                chunk_id=below_chunk,
                cosine_distance=0.9,
                similarity=0.1,
            ),
        ),
    ), patch.object(store, "_fts_eligible_chunk_ids", return_value=set()):
        observations = store._hybrid_observations(
            vector=(),
            fts=(),
            query_text="refund",
            lexical_policy="fts-v1",
            workspace_id="workspace",
            query_vector=(),
            embedding_configuration=configuration,
            retrieval_configuration=retrieval_configuration,
        )

    assert any(
        item.branch == "fts"
        and item.status == "INELIGIBLE"
        and item.chunk_id == below_chunk
        for item in observations
    )


def test_hybrid_checks_fts_eligibility_for_vector_candidate_without_fts_contribution() -> None:
    store = PostgresAnsweringStore(SessionFactory)
    configuration = EmbeddingConfiguration.milestone_one_local()
    retrieval_configuration = RetrievalConfiguration.milestone_three_hybrid()
    vector_candidate = SimpleNamespace(chunk_id="vector-only")
    with patch.object(
        store,
        "_vector_observations",
        return_value=(
            BranchObservation(
                branch="vector",
                status="ELIGIBLE",
                chunk_id="vector-only",
                branch_rank=1,
                cosine_distance=0.1,
                similarity=0.9,
            ),
        ),
    ), patch.object(store, "_fts_eligible_chunk_ids", return_value=set()) as eligibility:
        observations = store._hybrid_observations(
            vector=(vector_candidate,),
            fts=(),
            query_text="refund",
            lexical_policy="fts-v1",
            workspace_id="workspace",
            query_vector=(),
            embedding_configuration=configuration,
            retrieval_configuration=retrieval_configuration,
        )

    eligibility.assert_called_once()
    assert [
        item.status
        for item in observations
        if item.branch == "fts" and item.chunk_id == "vector-only"
    ] == ["INELIGIBLE"]


def test_rrf_v2_uses_independent_branch_budgets_and_source_ordinal_order() -> None:
    workspace_id = f"rrf-v2-{uuid4()}"
    configuration = EmbeddingConfiguration.milestone_one_local()
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="RRF v2"))
    for ordinal in range(10):
        ingest(
            workspace_id,
            f"support/{ordinal:02d}",
            content=f"refund token {ordinal}".encode(),
        )
    query_vector = DeterministicEmbeddingProvider().embed(
        ["refund token"], configuration
    ).vectors[0]
    retrieval = RetrievalConfiguration.milestone_three_hybrid_v2(min_similarity=-1.0)
    with SessionFactory.begin() as session:
        session.add(
            RetrievalV2CutoverTable(
                workspace_id=workspace_id,
                embedding_configuration_id=configuration.id,
                population_digest="a" * 64,
                status="completed",
            )
        )

    candidates = PostgresAnsweringStore(SessionFactory).retrieve_candidates(
        workspace_id=workspace_id,
        query_text="the and what",
        query_vector=query_vector,
        embedding_configuration=configuration,
        retrieval_configuration=retrieval,
    )

    assert len(candidates) == 8
    assert all(candidate.fts_contribution is None for candidate in candidates)
    assert [candidate.fusion_score for candidate in candidates] == [
        1 / (60 + rank) for rank in range(1, 9)
    ]


def test_fts_m3_or_v2_empty_query_executes_no_sql_and_adversarial_inputs_are_bound() -> None:
    workspace_id = f"fts-v2-adversarial-{uuid4()}"
    configuration = EmbeddingConfiguration.milestone_one_local()
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="FTS v2 adversarial"))
    ingest(workspace_id, "support/refund", content=b"refund period is thirty days")
    retrieval = RetrievalConfiguration.milestone_three_hybrid_v2(min_similarity=-1.0)
    store = PostgresAnsweringStore(SessionFactory)
    statements: list[str] = []

    def capture(_connection, _cursor, statement, _parameters, _context, _many):
        statements.append(statement)

    engine = SessionFactory.kw["bind"]
    event.listen(engine, "before_cursor_execute", capture)
    try:
        assert store._fts_candidates(
            workspace_id=workspace_id,
            query_text="the and what",
            embedding_configuration=configuration,
            retrieval_configuration=retrieval,
        ) == ()
        assert statements == []

        operator_candidates = store._fts_candidates(
            workspace_id=workspace_id,
            query_text="' OR 1=1; refund refund",
            embedding_configuration=configuration,
            retrieval_configuration=retrieval,
        )
        long_token_candidates = store._fts_candidates(
            workspace_id=workspace_id,
            query_text="x" * 5000,
            embedding_configuration=configuration,
            retrieval_configuration=retrieval,
        )
    finally:
        event.remove(engine, "before_cursor_execute", capture)

    assert {candidate.source_key for candidate in operator_candidates} == {
        "support/refund"
    }
    assert long_token_candidates == ()
    assert len(statements) == 2
    assert all("%(to_tsquery_1)s" in statement for statement in statements)


def test_fts_filters_before_limit_and_breaks_equal_ranks_by_chunk_id() -> None:
    workspace_id = f"fts-owner-{uuid4()}"
    foreign_workspace_id = f"fts-foreign-{uuid4()}"
    configuration = EmbeddingConfiguration.milestone_one_local()
    other_configuration = EmbeddingConfiguration(
        id=f"fts-other-{uuid4()}",
        provider="deterministic-local",
        model="text-embedding-3-small",
        dimensions=1536,
        distance_metric="cosine",
    )
    with SessionFactory.begin() as session:
        session.add_all(
            [
                WorkspaceTable(id=workspace_id, name="FTS owner"),
                WorkspaceTable(id=foreign_workspace_id, name="FTS foreign"),
            ]
        )
    ingest(workspace_id, "fts/tie-a", content=b"token tie")
    ingest(workspace_id, "fts/tie-b", content=b"token tie")
    wrong_configuration = ingest(
        workspace_id,
        "fts/wrong-config",
        content=b"token token token token",
        configuration=other_configuration,
    )
    inactive = ingest(
        workspace_id, "fts/inactive", content=b"token token token token token"
    )
    ingest(
        foreign_workspace_id, "fts/foreign", content=b"token token token token token token"
    )
    with SessionFactory.begin() as session:
        session.execute(
            update(DocumentTable)
            .where(DocumentTable.id == inactive.document_id)
            .values(
                active_embedding_set_id=None,
                active_embedding_configuration_id=None,
            )
        )
    store = PostgresAnsweringStore(SessionFactory)
    retrieval_configuration = replace(
        RetrievalConfiguration.milestone_three_hybrid(), candidate_k=2
    )
    candidates = store._fts_candidates(
        workspace_id=workspace_id,
        query_text="token tie",
        embedding_configuration=configuration,
        retrieval_configuration=retrieval_configuration,
    )

    assert [candidate.chunk_id for candidate in candidates] == sorted(
        candidate.chunk_id for candidate in candidates
    )
    assert {candidate.source_key for candidate in candidates} == {"fts/tie-a", "fts/tie-b"}
    assert all(
        candidate.embedding_set_id != wrong_configuration.embedding_set_id
        for candidate in candidates
    )
    assert all(candidate.embedding_set_id != inactive.embedding_set_id for candidate in candidates)


@pytest.mark.asyncio
async def test_hybrid_persists_pre_selection_trace_provenance_without_sql_details() -> None:
    workspace_id = f"hybrid-trace-{uuid4()}"
    content = b"ZX-42 identifier is eligible for expedited refund processing."
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="Hybrid Trace"))
    ingest(workspace_id, "support/zx-42-trace", content=content)
    service = AnswerQuestion(
        embedding_provider=DeterministicEmbeddingProvider(),
        generation_provider=DeterministicGenerationProvider(),
        store=PostgresAnsweringStore(SessionFactory),
        embedding_configuration=EmbeddingConfiguration.milestone_one_local(),
        retrieval_configuration=replace(
            RetrievalConfiguration.milestone_three_hybrid(), min_similarity=0.0
        ),
    )

    result = await service.execute(
        QuestionCommand(workspace_id=workspace_id, question="ZX-42 identifier"),
        WorkspacePrincipal(workspace_id=workspace_id, key_id="test"),
    )

    with SessionFactory() as session:
        trace = session.get(QuestionTraceTable, result.trace_id)
    assert trace is not None
    assert trace.retrieval_configuration_id == "retrieval-m3-rrf-v1"
    assert trace.fusion_policy_version == "rrf-v1"
    assert trace.candidate_decisions[0]["final_rank"] == 1
    assert trace.candidate_decisions[0]["vector_contribution"] is not None
    assert trace.candidate_decisions[0]["fts_contribution"] is not None
    serialized = str(trace.candidate_decisions).casefold()
    assert "tsquery" not in serialized
    assert "tsvector" not in serialized
    assert "execution plan" not in serialized


def test_conversation_trace_is_idempotently_persisted_and_recovers_validated_citations() -> None:
    workspace_id = f"conversation-trace-{uuid4()}"
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="Conversation trace"))
    ingested = ingest(
        workspace_id,
        "guide/chapters",
        content=(
            b"# Chapters\n\n"
            b"The software project report is suggested to include seven chapters.\n"
        ),
    )
    with SessionFactory() as session:
        chunk = session.scalar(
            select(ChunkTable).where(ChunkTable.chunk_set_id == ingested.chunk_set_id)
        )
    assert chunk is not None

    conversation_store = PostgresConversationStore(SessionFactory)
    conversation = conversation_store.create(workspace_id, "create-conversation")
    admission = conversation_store.submit_turn(
        workspace_id,
        conversation.id,
        "turn-request-1",
        "How many chapters does the guide suggest?",
        "How many chapters does the guide suggest?",
        "a" * 64,
    )
    claim = conversation_store.claim_next_turn("worker-conversation-trace", workspace_id)
    assert claim is not None
    assert claim.turn.id == admission.turn.id

    trace_record = QuestionTraceRecord(
        workspace_id=workspace_id,
        question=admission.turn.question,
        retrieval_configuration_id="retrieval-m1-v1",
        embedding_configuration_id="embedding-local-m1-v2",
        candidate_decisions=(),
        retrieved_chunk_ids=(chunk.id,),
        embedding_set_ids=(ingested.embedding_set_id,),
        chunk_set_ids=(ingested.chunk_set_id,),
        decision="ANSWER",
        answer="The report is suggested to include seven chapters. [[E1]]",
        refusal_reason=None,
        generation_status="completed",
        alias_mapping={"E1": chunk.id},
        parsed_markers=("E1",),
        validation_outcome="valid",
        conversation_turn_id=admission.turn.id,
    )
    store = PostgresAnsweringStore(SessionFactory)

    trace_id = store.persist_trace(trace_record)
    replayed_trace_id = store.persist_trace(trace_record)

    assert replayed_trace_id == trace_id
    read_result = getattr(store, "read_conversation_result", lambda *_: None)
    recovered = read_result(workspace_id, admission.turn.id)
    assert recovered is not None
    assert recovered.trace_id == trace_id
    assert recovered.workspace_id == workspace_id
    assert recovered.decision == "ANSWER"
    assert recovered.answer == trace_record.answer
    assert len(recovered.citations) == 1
    citation = recovered.citations[0]
    assert citation.evidence_id == "E1"
    assert citation.document_id == ingested.document_id
    assert citation.document_version_id == ingested.document_version_id
    assert citation.source_key == "guide/chapters"
    assert citation.source_name == "refunds.md"
    assert citation.excerpt == chunk.content[:500]
    assert citation.content_checksum == chunk.content_checksum
    assert read_result("another-workspace", admission.turn.id) is None

    with SessionFactory.begin() as session:
        row = session.get(QuestionTraceTable, trace_id)
        row.alias_mapping = {"E1": str(uuid4())}
    assert read_result(workspace_id, admission.turn.id) is None

    with SessionFactory.begin() as session:
        row = session.get(QuestionTraceTable, trace_id)
        row.alias_mapping = {"E1": chunk.id}
        row.validation_outcome = "invalid"
    assert read_result(workspace_id, admission.turn.id) is None


def test_conversation_result_reader_recovers_a_valid_no_evidence_refusal() -> None:
    workspace_id = f"conversation-refusal-trace-{uuid4()}"
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="Conversation refusal"))
    conversation_store = PostgresConversationStore(SessionFactory)
    conversation = conversation_store.create(workspace_id, "create-refusal-conversation")
    admission = conversation_store.submit_turn(
        workspace_id,
        conversation.id,
        "refusal-turn-request-1",
        "Which planet is made of cheese?",
        "Which planet is made of cheese?",
        "b" * 64,
    )
    claim = conversation_store.claim_next_turn("worker-conversation-refusal", workspace_id)
    assert claim is not None
    assert claim.turn.id == admission.turn.id
    store = PostgresAnsweringStore(SessionFactory)
    trace_id = store.persist_trace(
        QuestionTraceRecord(
            workspace_id=workspace_id,
            question=admission.turn.question,
            retrieval_configuration_id="retrieval-m1-v1",
            embedding_configuration_id="embedding-local-m1-v2",
            candidate_decisions=(),
            retrieved_chunk_ids=(),
            embedding_set_ids=(),
            chunk_set_ids=(),
            decision="REFUSAL",
            answer=None,
            refusal_reason="INSUFFICIENT_EVIDENCE",
            generation_status="not_called",
            validation_outcome="not_applicable",
            conversation_turn_id=admission.turn.id,
        )
    )

    recovered = store.read_conversation_result(workspace_id, admission.turn.id)

    assert recovered == QuestionResult(
        decision="REFUSAL",
        answer=None,
        citations=(),
        refusal_reason="INSUFFICIENT_EVIDENCE",
        trace_id=trace_id,
        workspace_id=workspace_id,
    )
