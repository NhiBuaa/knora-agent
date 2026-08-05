from uuid import uuid4

import pytest

from knora.adapters.postgres.answering_store import PostgresAnsweringStore
from knora.adapters.postgres.database import SessionFactory
from knora.adapters.postgres.evaluation_reader import PostgresEvaluationReader
from knora.adapters.postgres.ingestion_store import PostgresIngestionStore
from knora.adapters.postgres.tables import QuestionTraceTable, WorkspaceTable
from knora.answering.interface import QuestionCommand
from knora.answering.module import AnswerQuestion
from knora.domain.access import WorkspacePrincipal
from knora.ingestion.interface import IngestDocumentCommand
from knora.ingestion.module import IngestDocument
from knora.ingestion.processing import ChunkingConfiguration, DocumentProcessor
from knora.providers.deterministic.embedding import DeterministicEmbeddingProvider
from knora.providers.deterministic.generation import DeterministicGenerationProvider
from knora.providers.embedding import EmbeddingConfiguration


@pytest.mark.asyncio
async def test_evaluation_reader_resolves_real_candidate_ownership_and_active_corpus() -> None:
    workspace_id = f"evaluation-reader-{uuid4()}"
    content = b"Refund requests are accepted within 30 days."
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="Evaluation Reader"))
    IngestDocument(
        processor=DocumentProcessor(),
        embedding_provider=DeterministicEmbeddingProvider(),
        store=PostgresIngestionStore(SessionFactory),
    ).execute(
        IngestDocumentCommand(
            workspace_id=workspace_id,
            source_key="support/refund-policy",
            source_name="refund-policy.txt",
            media_type="text/plain",
            raw_content=content,
            chunking_configuration=ChunkingConfiguration.milestone_one(),
            embedding_configuration=EmbeddingConfiguration.milestone_one_local(),
        ),
        WorkspacePrincipal(workspace_id=workspace_id, key_id="test"),
    )
    result = await AnswerQuestion(
        embedding_provider=DeterministicEmbeddingProvider(),
        generation_provider=DeterministicGenerationProvider(),
        store=PostgresAnsweringStore(SessionFactory),
        embedding_configuration=EmbeddingConfiguration.milestone_one_local(),
    ).execute(
        QuestionCommand(workspace_id=workspace_id, question=content.decode()),
        WorkspacePrincipal(workspace_id=workspace_id, key_id="test"),
    )

    reader = PostgresEvaluationReader(SessionFactory)
    trace = reader.read_trace(trace_id=result.trace_id, workspace_id=workspace_id)
    corpus = reader.read_active_corpus(workspace_id=workspace_id)

    assert trace.candidates[0].workspace_id == workspace_id
    assert trace.candidates[0].source_key == "support/refund-policy"
    assert trace.candidates[0].chunk_ordinal == 0
    assert trace.candidates[0].content == content.decode()
    assert trace.retrieval_latency_ms >= 0
    assert corpus.documents[0].normalized_content_checksum
    assert corpus.documents[0].chunking_configuration_id == "chunking-m1-v1"
    assert corpus.documents[0].embedding_configuration_id == "embedding-local-m1-v2"
    assert corpus.documents[0].chunk_references == ("support/refund-policy#0",)

    with pytest.raises(LookupError, match="evaluation trace not found"):
        reader.read_trace(trace_id=result.trace_id, workspace_id="another-workspace")


@pytest.mark.asyncio
async def test_evaluation_reader_rejects_cross_workspace_candidate_reference() -> None:
    owner_workspace_id = f"evaluation-reader-owner-{uuid4()}"
    foreign_workspace_id = f"evaluation-reader-foreign-{uuid4()}"
    with SessionFactory.begin() as session:
        session.add_all(
            [
                WorkspaceTable(id=owner_workspace_id, name="Evaluation Reader Owner"),
                WorkspaceTable(id=foreign_workspace_id, name="Evaluation Reader Foreign"),
            ]
        )

    content = b"Refund requests are accepted within 30 days."
    IngestDocument(
        processor=DocumentProcessor(),
        embedding_provider=DeterministicEmbeddingProvider(),
        store=PostgresIngestionStore(SessionFactory),
    ).execute(
        IngestDocumentCommand(
            workspace_id=foreign_workspace_id,
            source_key="support/foreign-refund-policy",
            source_name="foreign-refund-policy.txt",
            media_type="text/plain",
            raw_content=content,
            chunking_configuration=ChunkingConfiguration.milestone_one(),
            embedding_configuration=EmbeddingConfiguration.milestone_one_local(),
        ),
        WorkspacePrincipal(workspace_id=foreign_workspace_id, key_id="test"),
    )
    foreign_question = await AnswerQuestion(
        embedding_provider=DeterministicEmbeddingProvider(),
        generation_provider=DeterministicGenerationProvider(),
        store=PostgresAnsweringStore(SessionFactory),
        embedding_configuration=EmbeddingConfiguration.milestone_one_local(),
    ).execute(
        QuestionCommand(workspace_id=foreign_workspace_id, question=content.decode()),
        WorkspacePrincipal(workspace_id=foreign_workspace_id, key_id="test"),
    )
    with SessionFactory() as session:
        foreign_trace = session.get(QuestionTraceTable, foreign_question.trace_id)
        assert foreign_trace is not None
        candidate_decisions = list(foreign_trace.candidate_decisions)
        embedding_set_ids = list(foreign_trace.embedding_set_ids)
        chunk_set_ids = list(foreign_trace.chunk_set_ids)
        retrieved_chunk_ids = list(foreign_trace.retrieved_chunk_ids)

    owner_trace_id = str(uuid4())
    with SessionFactory.begin() as session:
        session.add(
            QuestionTraceTable(
                id=owner_trace_id,
                workspace_id=owner_workspace_id,
                question="malicious cross-workspace trace",
                retrieval_configuration_id="retrieval-m1-v1",
                embedding_configuration_id="embedding-local-m1-v2",
                embedding_set_ids=embedding_set_ids,
                chunk_set_ids=chunk_set_ids,
                retrieved_chunk_ids=retrieved_chunk_ids,
                candidate_decisions=candidate_decisions,
                decision="ANSWER",
                answer="answer",
                refused=False,
                generation_status="completed",
                alias_mapping={},
                parsed_markers=[],
                validation_outcome="valid",
                provider_metadata={},
                latency_ms=0,
            )
        )

    with pytest.raises(LookupError, match="evaluation candidate not found"):
        PostgresEvaluationReader(SessionFactory).read_trace(
            trace_id=owner_trace_id,
            workspace_id=owner_workspace_id,
        )
