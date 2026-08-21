from copy import deepcopy
from uuid import uuid4

import pytest
from sqlalchemy import select

from knora.adapters.postgres.answering_store import PostgresAnsweringStore
from knora.adapters.postgres.database import SessionFactory
from knora.adapters.postgres.evaluation_reader import (
    PostgresEvaluationReader,
    _ordered_candidate_ids,
)
from knora.adapters.postgres.ingestion_store import PostgresIngestionStore
from knora.adapters.postgres.tables import (
    ChunkSetTable,
    ChunkTable,
    DocumentTable,
    DocumentVersionTable,
    EmbeddingSetTable,
    QuestionTraceTable,
    WorkspaceTable,
)
from knora.answering.interface import QuestionCommand
from knora.answering.module import AnswerQuestion
from knora.domain.access import WorkspacePrincipal
from knora.ingestion.interface import IngestDocumentCommand
from knora.ingestion.module import IngestDocument
from knora.ingestion.processing import ChunkingConfiguration, DocumentProcessor
from knora.providers.deterministic.embedding import DeterministicEmbeddingProvider
from knora.providers.deterministic.generation import DeterministicGenerationProvider
from knora.providers.embedding import EmbeddingConfiguration


def _budget_provider_metadata() -> dict[str, object]:
    return {
        "retrieval": {"latency_ms": 1.0},
        "timing": {
            "clock_resolution_ms": 0.001,
            "phases": {
                "query_embedding": {"start_tick": 0.0, "end_tick": 0.0, "duration_ms": 0.0},
                "candidate_retrieval": {
                    "start_tick": 0.0,
                    "end_tick": 0.001,
                    "duration_ms": 1.0,
                },
                "evidence_selection": {
                    "start_tick": 0.001,
                    "end_tick": 0.001,
                    "duration_ms": 0.0,
                },
                "generation": {
                    "start_tick": 0.001,
                    "end_tick": 0.001,
                    "duration_ms": 0.0,
                },
            },
        },
    }


def _persist_budget_trace(
    *,
    workspace_id: str,
    embedding_set_id: str,
    chunk_set_id: str,
    chunk_ids: list[str],
    token_counts: list[int],
    decision_reason: str,
    mutation: dict[str, int] | None = None,
) -> str:
    decisions: list[dict[str, object]] = []
    branch_observations: list[dict[str, object]] = []
    selected_token_count = 0
    for rank, (chunk_id, token_count) in enumerate(
        zip(chunk_ids, token_counts, strict=True), start=1
    ):
        branch_observations.append(
            {
                "schema_version": 1,
                "branch": "vector",
                "status": "ELIGIBLE",
                "chunk_id": chunk_id,
                "branch_rank": rank,
                "cosine_distance": 0.1,
                "similarity": 0.9,
                "native_rank": None,
                "lexical_policy_id": None,
                "normalized_lexemes": [],
                "omitted_lexemes": [],
            }
        )
        is_budget_candidate = (
            decision_reason == "TOKEN_BUDGET" and rank == 1
        ) or (decision_reason == "CHUNK_COUNT_LIMIT" and rank == len(chunk_ids))
        evidence = None
        final_decision = "SELECTED"
        reason = None
        if is_budget_candidate:
            final_decision = "BUDGET_EXCEEDED"
            reason = decision_reason
            evidence = {
                "max_evidence_chunks": 5,
                "max_evidence_tokens": 3000,
                "selected_chunk_count": rank - 1,
                "selected_token_count": selected_token_count,
                "candidate_token_count": token_count,
                "token_total": selected_token_count + token_count,
            }
            if mutation:
                evidence.update(mutation)
        else:
            selected_token_count += token_count
        decisions.append(
            {
                "chunk_id": chunk_id,
                "final_rank": rank,
                "fusion_score": 1 / (60 + rank),
                "final_decision": final_decision,
                "decision_reason": reason,
                "budget_evidence": evidence,
                "vector_contribution": {
                    "branch_rank": rank,
                    "cosine_distance": 0.1,
                    "similarity": 0.9,
                },
                "fts_contribution": None,
            }
        )
    trace_id = str(uuid4())
    with SessionFactory.begin() as session:
        session.add(
            QuestionTraceTable(
                id=trace_id,
                workspace_id=workspace_id,
                question="budget evidence",
                retrieval_configuration_id="retrieval-m1-v1",
                fusion_policy_version=None,
                embedding_configuration_id="embedding-local-m1-v2",
                embedding_set_ids=[embedding_set_id],
                chunk_set_ids=[chunk_set_id],
                retrieved_chunk_ids=chunk_ids,
                candidate_decisions=decisions,
                branch_observations=branch_observations,
                decision="ANSWER",
                answer="budget evidence",
                refused=False,
                refusal_reason=None,
                generation_status="completed",
                alias_mapping={"E1": chunk_ids[0]},
                parsed_markers=["E1"],
                validation_outcome="valid",
                provider_metadata=_budget_provider_metadata(),
                latency_ms=1.0,
            )
        )
    return trace_id


def test_evaluation_reader_rejects_inconsistent_fused_rank_provenance() -> None:
    with pytest.raises(LookupError, match="candidate ordering is invalid"):
        _ordered_candidate_ids(
            [
                {"chunk_id": "one", "final_rank": 1},
                {"chunk_id": "two", "final_rank": 3},
            ]
        )


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
    assert trace.candidates[0].document_version_id
    assert trace.candidates[0].chunk_set_id
    assert trace.candidates[0].source_key == "support/refund-policy"
    assert trace.candidates[0].chunk_ordinal == 0
    assert trace.candidates[0].content == content.decode()
    assert trace.retrieval_latency_ms >= 0
    assert corpus.documents[0].normalized_content_checksum
    assert corpus.documents[0].document_version_id
    assert corpus.documents[0].chunk_set_id
    assert corpus.documents[0].chunking_configuration_id == "chunking-m1-v1"
    assert corpus.documents[0].embedding_configuration_id == "embedding-local-m1-v2"
    assert corpus.documents[0].chunk_references == ("support/refund-policy#0",)

    with pytest.raises(LookupError, match="evaluation trace not found"):
        reader.read_trace(trace_id=result.trace_id, workspace_id="another-workspace")


def test_evaluation_reader_binds_persisted_budget_evidence_end_to_end() -> None:
    workspace_id = f"evaluation-reader-budget-{uuid4()}"
    content = ("policy evidence " * 4000).encode()
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="Evaluation Budget Reader"))
    IngestDocument(
        processor=DocumentProcessor(),
        embedding_provider=DeterministicEmbeddingProvider(),
        store=PostgresIngestionStore(SessionFactory),
    ).execute(
        IngestDocumentCommand(
            workspace_id=workspace_id,
            source_key="support/budget-policy",
            source_name="budget-policy.txt",
            media_type="text/plain",
            raw_content=content,
            chunking_configuration=ChunkingConfiguration.milestone_one(),
            embedding_configuration=EmbeddingConfiguration.milestone_one_local(),
        ),
        WorkspacePrincipal(workspace_id=workspace_id, key_id="test"),
    )

    with SessionFactory() as session:
        document, version, chunk_set, embedding_set = session.execute(
            select(DocumentTable, DocumentVersionTable, ChunkSetTable, EmbeddingSetTable)
            .join(DocumentVersionTable, DocumentVersionTable.document_id == DocumentTable.id)
            .join(ChunkSetTable, ChunkSetTable.document_version_id == DocumentVersionTable.id)
            .join(EmbeddingSetTable, EmbeddingSetTable.chunk_set_id == ChunkSetTable.id)
            .where(
                DocumentTable.workspace_id == workspace_id,
                DocumentTable.active_embedding_set_id == EmbeddingSetTable.id,
                EmbeddingSetTable.status == "completed",
            )
        ).one()
        chunks = session.scalars(
            select(ChunkTable)
            .where(ChunkTable.chunk_set_id == chunk_set.id)
            .order_by(ChunkTable.ordinal)
        ).all()
        chunk_ids = [chunk.id for chunk in chunks]
        token_counts = [chunk.token_count for chunk in chunks]

    assert document.workspace_id == workspace_id
    assert version.id == document.current_document_version_id
    assert len(chunks) >= 7

    chunk_count_trace_id = _persist_budget_trace(
        workspace_id=workspace_id,
        embedding_set_id=embedding_set.id,
        chunk_set_id=chunk_set.id,
        chunk_ids=chunk_ids[:6],
        token_counts=token_counts[:6],
        decision_reason="CHUNK_COUNT_LIMIT",
    )
    reader = PostgresEvaluationReader(SessionFactory)
    accepted_chunk_trace = reader.read_trace(
        trace_id=chunk_count_trace_id,
        workspace_id=workspace_id,
    )
    assert accepted_chunk_trace.candidates[-1].decision_reason == "CHUNK_COUNT_LIMIT"

    with SessionFactory.begin() as session:
        trace = session.get(QuestionTraceTable, chunk_count_trace_id)
        assert trace is not None
        decisions = deepcopy(trace.candidate_decisions)
        decisions[-1]["budget_evidence"]["selected_token_count"] += 1
        decisions[-1]["budget_evidence"]["token_total"] += 1
        trace.candidate_decisions = decisions
    with pytest.raises(LookupError, match="budget evidence is invalid"):
        reader.read_trace(trace_id=chunk_count_trace_id, workspace_id=workspace_id)

    token_chunk_id = chunk_ids[-1]
    with SessionFactory.begin() as session:
        chunk = session.get(ChunkTable, token_chunk_id)
        assert chunk is not None
        chunk.token_count = 3001
    token_trace_id = _persist_budget_trace(
        workspace_id=workspace_id,
        embedding_set_id=embedding_set.id,
        chunk_set_id=chunk_set.id,
        chunk_ids=[token_chunk_id],
        token_counts=[3001],
        decision_reason="TOKEN_BUDGET",
    )
    accepted_token_trace = reader.read_trace(
        trace_id=token_trace_id,
        workspace_id=workspace_id,
    )
    assert accepted_token_trace.candidates[0].decision_reason == "TOKEN_BUDGET"

    with SessionFactory.begin() as session:
        trace = session.get(QuestionTraceTable, token_trace_id)
        assert trace is not None
        decisions = deepcopy(trace.candidate_decisions)
        decisions[0]["budget_evidence"]["candidate_token_count"] = 3000
        decisions[0]["budget_evidence"]["token_total"] = 3000
        trace.candidate_decisions = decisions
    with pytest.raises(
        LookupError,
        match="evaluation candidate (?:budget evidence|decision) is invalid",
    ):
        reader.read_trace(trace_id=token_trace_id, workspace_id=workspace_id)


@pytest.mark.asyncio
async def test_evaluation_reader_rejects_unresolvable_branch_observation_identity() -> None:
    workspace_id = f"evaluation-reader-branch-{uuid4()}"
    content = b"Refund requests are accepted within 30 days."
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="Evaluation Branch Reader"))
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

    with SessionFactory.begin() as session:
        trace = session.get(QuestionTraceTable, result.trace_id)
        assert trace is not None
        branch_observations = list(trace.branch_observations)
        branch_observations.append(
            {
                "schema_version": 1,
                "branch": "vector",
                "status": "NO_CONTRIBUTION",
                "chunk_id": "fabricated-branch-chunk",
                "branch_rank": None,
                "cosine_distance": None,
                "similarity": None,
                "native_rank": None,
                "lexical_policy_id": None,
                "normalized_lexemes": [],
                "omitted_lexemes": [],
            }
        )
        trace.branch_observations = branch_observations

    with pytest.raises(LookupError, match="evaluation branch candidate not found"):
        PostgresEvaluationReader(SessionFactory).read_trace(
            trace_id=result.trace_id,
            workspace_id=workspace_id,
        )


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
        branch_observations = list(foreign_trace.branch_observations)
        provider_metadata = dict(foreign_trace.provider_metadata)

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
                    provider_metadata=provider_metadata,
                    latency_ms=0,
                    branch_observations=branch_observations,
                )
        )

    with pytest.raises(LookupError, match="evaluation trace provenance is invalid"):
        PostgresEvaluationReader(SessionFactory).read_trace(
            trace_id=owner_trace_id,
            workspace_id=owner_workspace_id,
        )
