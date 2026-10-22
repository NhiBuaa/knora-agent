"""Owned PostgreSQL reader proof with a stub projection; no native or upload E2E claim."""

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest
from test_s2_search_index_store import lexical_generation as lexical_generation

from knora.adapters.postgres.answering_store import PostgresAnsweringStore
from knora.adapters.postgres.database import SessionFactory
from knora.adapters.postgres.evaluation_reader import PostgresEvaluationReader
from knora.adapters.postgres.operator_reader import PostgresOperatorReader
from knora.adapters.postgres.search_index_store import PostgresSearchIndexStore
from knora.adapters.postgres.tables import ChunkTable, DocumentTable, DocumentVersionTable
from knora.answering.interface import QuestionCommand
from knora.answering.module import AnswerQuestion
from knora.answering.stores import RetrievalConfiguration
from knora.domain.access import WorkspacePrincipal
from knora.ingestion.lexical_population import VerifiedLexicalPopulation
from knora.ingestion.search_indexing import StageReceipt
from knora.providers.deterministic.generation import DeterministicGenerationProvider


@pytest.mark.asyncio
@pytest.mark.parametrize("change", [None, "archive", "source", "revoke"])
async def test_postgres_bm25_trace_and_pdf_binding_are_authoritative(lexical_generation, change):
    population = VerifiedLexicalPopulation.from_mapping(
        json.loads(
            Path("evals/fixtures/pdf_retrieval_v3_s2/upload-lexical-population-v1.json").read_text()
        )
    )
    content = "Refund requests are accepted within 30 days."
    checksum = hashlib.sha256(content.encode()).hexdigest()
    generation = replace(
        lexical_generation,
        lexical_profile=population.profile,
        chunks=(replace(lexical_generation.chunks[0], content_checksum=checksum),),
    )
    with SessionFactory.begin() as session:
        version = session.get(DocumentVersionTable, generation.document_version_id)
        version.raw_sha256 = population.documents[0].source_sha256
        version.media_type = "application/pdf"
        chunk = session.get(ChunkTable, generation.chunks[0].chunk_id)
        chunk.content, chunk.content_checksum, chunk.token_count = content, checksum, 8
        chunk.page_start = chunk.page_end = 1
        chunk.start_offset, chunk.end_offset = 0, len(content)
    authority = PostgresSearchIndexStore(SessionFactory)
    authority.request_generation(generation, expected_revision=0)
    authority.activate_ready(
        generation, StageReceipt(generation.generation_id, 1, generation.content_digest())
    )

    class StubProjection:
        calls = 0

        def query(self, snapshot, query, *, limit):
            assert limit == 200
            self.calls += 1
            return (
                {
                    "generation_id": generation.generation_id,
                    "chunk_id": generation.chunks[0].chunk_id,
                    "score": 1.5,
                    "rank": 1,
                    "score_policy_digest": population.profile.digest(),
                },
            )

    projection = StubProjection()
    service = AnswerQuestion(
        embedding_provider=None,
        embedding_configuration=None,
        generation_provider=DeterministicGenerationProvider(),
        store=PostgresAnsweringStore(
            SessionFactory, lexical_index=projection, lexical_population=population
        ),
        retrieval_configuration=RetrievalConfiguration.bm25_upload_fixture_top8_v1(),
    )
    result = await service.execute(
        QuestionCommand(workspace_id=generation.workspace_id, question="Refund?"),
        WorkspacePrincipal(workspace_id=generation.workspace_id, key_id="s2"),
    )
    assert projection.calls == 1
    reader = PostgresEvaluationReader(SessionFactory, lexical_population=population)
    trace = reader.read_trace(trace_id=result.trace_id, workspace_id=generation.workspace_id)
    assert trace.embedding_configuration_id is None
    assert trace.candidates[0].content == content
    assert trace.candidates[0].bm25_contribution["raw_score"] == 1.5
    assert reader.read_pdf_chunks(workspace_id=generation.workspace_id)[0].chunk_id == (
        generation.chunks[0].chunk_id
    )
    operator = PostgresOperatorReader(SessionFactory, lexical_population=population)
    assert (
        operator.read_trace(trace_id=result.trace_id, workspace_id=generation.workspace_id) == trace
    )
    if change == "archive":
        with SessionFactory.begin() as session:
            document = session.get(DocumentTable, generation.document_id)
            document.archived, document.revision = True, document.revision + 1
    elif change == "source":
        with SessionFactory.begin() as session:
            session.get(DocumentVersionTable, generation.document_version_id).raw_sha256 = "0" * 64
    elif change == "revoke":
        authority.revoke(workspace_id=generation.workspace_id, document_id=generation.document_id)
    if change:
        with pytest.raises(LookupError, match="lexical"):
            reader.read_trace(trace_id=result.trace_id, workspace_id=generation.workspace_id)
        with pytest.raises(LookupError, match="lexical"):
            reader.read_pdf_chunks(workspace_id=generation.workspace_id)
