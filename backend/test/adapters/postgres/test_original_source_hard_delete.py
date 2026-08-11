from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import delete, update

from knora.adapters.postgres.database import SessionFactory
from knora.adapters.postgres.ingestion_job_store import PostgresIngestionJobStore
from knora.adapters.postgres.tables import (
    ChunkingConfigurationTable,
    ChunkSetTable,
    ChunkTable,
    DocumentTable,
    DocumentVersionTable,
    EmbeddingConfigurationTable,
    EmbeddingSetTable,
    OriginalSourceObjectTable,
    QuestionTraceTable,
    WorkspaceTable,
)
from knora.ingestion.object_lifecycle import ObjectLifecycleRetryPolicyV1, ObjectLifecycleWorker


@pytest.fixture
def hard_delete_fixture():
    workspace_id = f"hard-delete-{uuid4()}"
    document_id = str(uuid4())
    version_id = str(uuid4())
    source_id = str(uuid4())
    object_key = uuid4().hex
    chunk_set_id = str(uuid4())
    chunk_id = str(uuid4())
    configuration_id = str(uuid4())
    embedding_configuration_id = str(uuid4())
    embedding_set_id = str(uuid4())
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="hard delete"))
        session.flush()
        session.add(
            DocumentTable(
                id=document_id,
                workspace_id=workspace_id,
                source_key=f"source-{uuid4()}",
                source_name="source.pdf",
                revision=0,
            )
        )
        session.add(
            DocumentVersionTable(
                id=version_id,
                document_id=document_id,
                raw_sha256="a" * 64,
                media_type="application/pdf",
                version_number=1,
            )
        )
        session.flush()
        session.add(
            OriginalSourceObjectTable(
                id=source_id,
                workspace_id=workspace_id,
                document_version_id=version_id,
                object_key=object_key,
                raw_sha256="a" * 64,
                byte_size=1,
                media_type="application/pdf",
            )
        )
        session.add(
            ChunkingConfigurationTable(
                id=configuration_id,
                parser_version="parser-v1",
                chunker_version="chunker-v1",
                tokenizer_name="tokenizer",
                tokenizer_version="v1",
                target_tokens=500,
                overlap_tokens=75,
                max_tokens=650,
            )
        )
        session.flush()
        session.add(
            ChunkSetTable(
                id=chunk_set_id,
                document_version_id=version_id,
                chunking_configuration_id=configuration_id,
                status="completed",
            )
        )
        session.add(
            ChunkTable(
                id=chunk_id,
                chunk_set_id=chunk_set_id,
                ordinal=0,
                heading_path=[],
                start_line=1,
                end_line=1,
                content="retained source",
                content_checksum="b" * 64,
                token_count=2,
            )
        )
        session.add(
            EmbeddingConfigurationTable(
                id=embedding_configuration_id,
                provider="deterministic-local",
                model="embedding-v1",
                dimensions=1536,
                distance_metric="cosine",
            )
        )
        session.flush()
        session.add(
            EmbeddingSetTable(
                id=embedding_set_id,
                chunk_set_id=chunk_set_id,
                embedding_configuration_id=embedding_configuration_id,
                status="completed",
            )
        )
    try:
        yield {
            "workspace_id": workspace_id,
            "document_id": document_id,
            "version_id": version_id,
            "source_id": source_id,
            "object_key": object_key,
            "chunk_id": chunk_id,
            "embedding_configuration_id": embedding_configuration_id,
            "embedding_set_id": embedding_set_id,
        }
    finally:
        with SessionFactory.begin() as session:
            session.execute(
                delete(QuestionTraceTable).where(QuestionTraceTable.workspace_id == workspace_id)
            )
            session.execute(
                update(DocumentTable)
                .where(DocumentTable.id == document_id)
                .values(
                    current_document_version_id=None,
                    active_embedding_set_id=None,
                    active_embedding_configuration_id=None,
                )
            )
            session.execute(delete(ChunkTable).where(ChunkTable.chunk_set_id == chunk_set_id))
            session.execute(
                delete(EmbeddingSetTable).where(EmbeddingSetTable.id == embedding_set_id)
            )
            session.execute(delete(ChunkSetTable).where(ChunkSetTable.id == chunk_set_id))
            session.execute(
                delete(EmbeddingConfigurationTable).where(
                    EmbeddingConfigurationTable.id == embedding_configuration_id
                )
            )
            session.execute(
                delete(ChunkingConfigurationTable).where(
                    ChunkingConfigurationTable.id == configuration_id
                )
            )
            session.execute(
                delete(OriginalSourceObjectTable).where(OriginalSourceObjectTable.id == source_id)
            )
            session.execute(
                delete(DocumentVersionTable).where(DocumentVersionTable.id == version_id)
            )
            session.execute(delete(DocumentTable).where(DocumentTable.id == document_id))
            session.execute(delete(WorkspaceTable).where(WorkspaceTable.id == workspace_id))


def test_hard_delete_requires_authoritative_no_blocker_and_is_idempotent(hard_delete_fixture):
    store = PostgresIngestionJobStore(SessionFactory)
    fixture = hard_delete_fixture
    with SessionFactory.begin() as session:
        session.execute(
            update(DocumentTable)
            .where(DocumentTable.id == fixture["document_id"])
            .values(current_document_version_id=fixture["version_id"])
        )

    with pytest.raises(PermissionError, match="retention|ownership"):
        store.prepare_original_source_hard_delete(
            workspace_id=fixture["workspace_id"], object_key=fixture["object_key"]
        )

    with SessionFactory.begin() as session:
        session.execute(
            update(DocumentTable)
            .where(DocumentTable.id == fixture["document_id"])
            .values(current_document_version_id=None)
        )

    capability = store.prepare_original_source_hard_delete(
        workspace_id=fixture["workspace_id"], object_key=fixture["object_key"]
    )
    assert capability.object_key == fixture["object_key"]
    assert store.complete_original_source_hard_delete(capability=capability)
    assert store.complete_original_source_hard_delete(capability=capability)

    with SessionFactory() as session:
        source = session.get(OriginalSourceObjectTable, fixture["source_id"])
        assert source is not None
        assert isinstance(source.deleted_at, datetime)
        assert source.deleted_at.tzinfo is not None


def test_hard_delete_treats_trace_chunk_reference_as_retention_blocker(hard_delete_fixture):
    store = PostgresIngestionJobStore(SessionFactory)
    fixture = hard_delete_fixture
    now = datetime.now(UTC)
    with SessionFactory.begin() as session:
        session.add(
            QuestionTraceTable(
                id=str(uuid4()),
                workspace_id=fixture["workspace_id"],
                question="retention trace",
                retrieved_chunk_ids=[fixture["chunk_id"]],
                candidate_decisions=[],
                embedding_set_ids=[],
                chunk_set_ids=[],
                decision="ANSWER",
                answer="answer",
                refused=False,
                generation_status="completed",
                alias_mapping={"E1": fixture["chunk_id"]},
                parsed_markers=["E1"],
                validation_outcome="valid",
                provider_metadata={},
                created_at=now,
            )
        )

    with pytest.raises(PermissionError, match="retention|trace"):
        store.prepare_original_source_hard_delete(
            workspace_id=fixture["workspace_id"], object_key=fixture["object_key"]
        )


def test_hard_delete_rechecks_retention_after_capability_preparation(hard_delete_fixture):
    store = PostgresIngestionJobStore(SessionFactory)
    fixture = hard_delete_fixture
    capability = store.prepare_original_source_hard_delete(
        workspace_id=fixture["workspace_id"], object_key=fixture["object_key"]
    )
    with SessionFactory.begin() as session:
        session.add(
            QuestionTraceTable(
                id=str(uuid4()),
                workspace_id=fixture["workspace_id"],
                question="late retention trace",
                retrieved_chunk_ids=[fixture["chunk_id"]],
                candidate_decisions=[],
                embedding_set_ids=[],
                chunk_set_ids=[],
                decision="ANSWER",
                answer="answer",
                refused=False,
                generation_status="completed",
                alias_mapping={},
                parsed_markers=[],
                validation_outcome="valid",
                provider_metadata={},
            )
        )

    with pytest.raises(PermissionError, match="retention|trace"):
        store.revalidate_original_source_hard_delete(capability=capability)

    with SessionFactory.begin() as session:
        session.execute(
            delete(QuestionTraceTable).where(
                QuestionTraceTable.workspace_id == fixture["workspace_id"]
            )
        )
    assert store.complete_original_source_hard_delete(capability=capability)


def test_hard_delete_blocks_active_embedding_set_retention(hard_delete_fixture):
    store = PostgresIngestionJobStore(SessionFactory)
    fixture = hard_delete_fixture
    with SessionFactory.begin() as session:
        session.execute(
            update(DocumentTable)
            .where(DocumentTable.id == fixture["document_id"])
            .values(
                active_embedding_set_id=fixture["embedding_set_id"],
                active_embedding_configuration_id=fixture["embedding_configuration_id"],
            )
        )

    with pytest.raises(PermissionError, match="active"):
        store.prepare_original_source_hard_delete(
            workspace_id=fixture["workspace_id"], object_key=fixture["object_key"]
        )


class RecordingDeleteObjectStore:
    def __init__(self):
        self.deletes = []

    def delete(self, *, workspace_id: str, object_key: str) -> None:
        self.deletes.append((workspace_id, object_key))


class ZeroRandomSource:
    def sample(self, upper_bound_microseconds: int) -> int:
        del upper_bound_microseconds
        return 0


class LateTraceHardDeleteMaintenance:
    """Existing lifecycle port wrapped by a deterministic pre-delete race fixture."""

    def __init__(self, *, store: PostgresIngestionJobStore, fixture: dict[str, str]) -> None:
        self._store = store
        self._fixture = fixture

    def prepare_original_source_hard_delete(self, **kwargs):
        return self._store.prepare_original_source_hard_delete(**kwargs)

    def revalidate_original_source_hard_delete(self, **kwargs) -> None:
        with SessionFactory.begin() as session:
            session.add(
                QuestionTraceTable(
                    id=str(uuid4()),
                    workspace_id=self._fixture["workspace_id"],
                    question="hard delete race",
                    retrieved_chunk_ids=[self._fixture["chunk_id"]],
                    candidate_decisions=[],
                    embedding_set_ids=[],
                    chunk_set_ids=[],
                    decision="ANSWER",
                    answer="answer",
                    refused=False,
                    generation_status="completed",
                    alias_mapping={},
                    parsed_markers=[],
                    validation_outcome="valid",
                    provider_metadata={},
                )
            )
        self._store.revalidate_original_source_hard_delete(**kwargs)

    def complete_original_source_hard_delete(self, **kwargs):
        return self._store.complete_original_source_hard_delete(**kwargs)


def test_worker_hard_delete_path_revalidates_and_marks_tombstone(hard_delete_fixture):
    store = PostgresIngestionJobStore(SessionFactory)
    object_store = RecordingDeleteObjectStore()
    worker = ObjectLifecycleWorker(
        maintenance=store,
        object_store=object_store,
        retry_policy=ObjectLifecycleRetryPolicyV1(random_source=ZeroRandomSource()),
    )
    fixture = hard_delete_fixture

    assert worker.hard_delete_original_source(
        workspace_id=fixture["workspace_id"], object_key=fixture["object_key"]
    )
    assert worker.hard_delete_original_source(
        workspace_id=fixture["workspace_id"], object_key=fixture["object_key"]
    )
    assert object_store.deletes == [(fixture["workspace_id"], fixture["object_key"])]
    with SessionFactory() as session:
        source = session.get(OriginalSourceObjectTable, fixture["source_id"])
        assert source is not None and source.deleted_at is not None


def test_worker_hard_delete_suppresses_late_retention_before_object_store_delete(
    hard_delete_fixture,
):
    store = PostgresIngestionJobStore(SessionFactory)
    object_store = RecordingDeleteObjectStore()
    worker = ObjectLifecycleWorker(
        maintenance=LateTraceHardDeleteMaintenance(store=store, fixture=hard_delete_fixture),
        object_store=object_store,
        retry_policy=ObjectLifecycleRetryPolicyV1(random_source=ZeroRandomSource()),
    )

    with pytest.raises(PermissionError, match="retention|trace"):
        worker.hard_delete_original_source(
            workspace_id=hard_delete_fixture["workspace_id"],
            object_key=hard_delete_fixture["object_key"],
        )

    assert object_store.deletes == []
    with SessionFactory() as session:
        source = session.get(OriginalSourceObjectTable, hard_delete_fixture["source_id"])
        assert source is not None and source.deleted_at is None
