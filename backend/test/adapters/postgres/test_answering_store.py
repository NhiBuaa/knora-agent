from dataclasses import replace
from uuid import uuid4

import pytest
from sqlalchemy import select, update

from knora.adapters.postgres.answering_store import PostgresAnsweringStore
from knora.adapters.postgres.database import SessionFactory
from knora.adapters.postgres.ingestion_store import PostgresIngestionStore
from knora.adapters.postgres.tables import (
    ChunkEmbeddingTable,
    DocumentTable,
    EmbeddingSetTable,
    QuestionTraceTable,
    WorkspaceTable,
)
from knora.answering.interface import QuestionCommand
from knora.answering.module import AnswerQuestion
from knora.answering.stores import RetrievalConfiguration
from knora.domain.access import WorkspacePrincipal
from knora.ingestion.interface import IngestDocumentCommand
from knora.ingestion.module import IngestDocument
from knora.ingestion.processing import ChunkingConfiguration, DocumentProcessor
from knora.providers.deterministic.embedding import DeterministicEmbeddingProvider
from knora.providers.deterministic.generation import DeterministicGenerationProvider
from knora.providers.embedding import EmbeddingConfiguration


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
    ingest(
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
