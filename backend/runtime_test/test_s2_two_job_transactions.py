"""Two-job persistence proofs in the owned database; projection I/O is separate."""

import hashlib
from dataclasses import replace
from uuid import uuid4

import pytest
from backend.runtime_test.s2_runtime_guard import require_owned_s2_database
from backend.test.adapters.postgres.test_ingestion_jobs import prepared_submission
from backend.test.fixtures.issue_18_acceptance import pdf_extraction
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from knora.adapters.postgres.database import SessionFactory
from knora.adapters.postgres.ingestion_job_store import PostgresIngestionJobStore
from knora.adapters.postgres.search_index_store import PostgresSearchIndexStore
from knora.adapters.postgres.tables import (
    ChunkSetTable,
    DocumentTable,
    EmbeddingSetTable,
    IngestionJobTable,
    LexicalGenerationTable,
    LexicalHeadTable,
    WorkspaceTable,
)
from knora.ingestion.job_processing import (
    AttemptTimingV1,
    ClaimedAttempt,
    ClaimOperationId,
    Fenced,
    FinalizationApplied,
    PdfExtractionSuccess,
    TransitionOperationId,
)
from knora.ingestion.jobs import PdfExtractionSubmissionConfiguration, PdfSubmissionConfiguration
from knora.ingestion.search_indexing import LexicalIndexSuccess, LexicalProfile, StageReceipt
from knora.providers.embedding import EmbeddingConfiguration


@pytest.fixture
def extraction_job():
    require_owned_s2_database(SessionFactory.kw["bind"].url)
    workspace_id = str(uuid4())
    with SessionFactory.begin() as session:
        # A contaminated queue is a fixture failure, never repaired by mutating other jobs.
        assert (
            session.scalar(
                select(func.count())
                .select_from(IngestionJobTable)
                .where(IngestionJobTable.status.in_(("queued", "retry_scheduled")))
            )
            == 0
        )
        session.add(WorkspaceTable(id=workspace_id, name="S2 transaction proof"))
    prepared = prepared_submission(workspace_id, idempotency_key=uuid4().hex)
    dense = PdfSubmissionConfiguration.milestone_two(
        embedding_configuration=EmbeddingConfiguration.milestone_one_local()
    )
    profile = LexicalProfile("transaction-fixture", "word", "1.19.2", 1.2, 0.75, 3, "fixture")
    configuration = PdfExtractionSubmissionConfiguration(
        dense.parser_configuration_id,
        dense.normalizer_configuration_id,
        dense.chunking_configuration,
        profile,
    )
    store = PostgresIngestionJobStore(SessionFactory)
    result = store.commit_pdf_submission(replace(prepared, configuration=configuration))
    claim = store.claim_next_attempt(
        operation_id=ClaimOperationId(uuid4().hex),
        worker_id="s2-transaction",
        timing=AttemptTimingV1.standard(),
    )
    assert isinstance(claim, ClaimedAttempt) and claim.token.job_id == result.ingestion_job_id
    # Use the approved extraction adapter's immutable result shape; this is not a parser proof.
    success = PdfExtractionSuccess(pdf_extraction(page_texts=("Hạn mức 42.",)), profile)
    assert (
        success.extraction.chunks[0].content_checksum
        == hashlib.sha256("Hạn mức 42.".encode()).hexdigest()
    )
    return store, claim, success


def _finalize_extraction_and_index_with_replay(extraction_job):
    store, claim, success = extraction_job
    operation = TransitionOperationId(uuid4().hex)
    result = store.finalize_success(operation_id=operation, claim=claim, success=success)
    assert isinstance(result, FinalizationApplied)
    assert store.finalize_success(operation_id=operation, claim=claim, success=success) == result
    with SessionFactory() as session:
        jobs = session.scalars(
            select(IngestionJobTable).where(
                IngestionJobTable.workspace_id == claim.work.workspace_id
            )
        ).all()
        assert sorted((job.derivation_kind, job.status) for job in jobs) == [
            ("lexical_index", "queued"),
            ("pdf_extraction", "succeeded"),
        ]
        assert [
            job.parent_ingestion_job_id for job in jobs if job.derivation_kind == "lexical_index"
        ] == [claim.token.job_id]
        head = session.get(LexicalHeadTable, claim.work.document_id)
        assert head.desired_generation_id and head.active_generation_id is None
        assert session.get(DocumentTable, claim.work.document_id).active_embedding_set_id is None
    child = store.claim_next_attempt(
        operation_id=ClaimOperationId(uuid4().hex),
        worker_id="s2-index",
        timing=AttemptTimingV1.standard(),
    )
    assert isinstance(child, ClaimedAttempt) and child.work.derivation_kind == "lexical_index"
    loaded = PostgresSearchIndexStore(SessionFactory).load_generation(child.work)
    generation = loaded.generation
    index_success = LexicalIndexSuccess(
        generation,
        StageReceipt(generation.generation_id, len(generation.chunks), generation.content_digest()),
    )
    index_operation = TransitionOperationId(uuid4().hex)
    indexed = store.finalize_success(
        operation_id=index_operation, claim=child, success=index_success
    )
    assert isinstance(indexed, FinalizationApplied)
    assert (
        store.finalize_success(operation_id=index_operation, claim=child, success=index_success)
        == indexed
    )
    with SessionFactory() as session:
        assert (
            session.get(LexicalHeadTable, claim.work.document_id).active_generation_id
            == generation.generation_id
        )
        assert session.get(IngestionJobTable, child.token.job_id).status == "succeeded"
        assert (
            session.scalar(
                select(func.count())
                .select_from(EmbeddingSetTable)
                .where(EmbeddingSetTable.chunk_set_id == generation.chunk_set_id)
            )
            == 0
        )


def test_extraction_replay_creates_one_child_and_index_replay_activates_once(extraction_job):
    _finalize_extraction_and_index_with_replay(extraction_job)


def test_final_fence_loss_rolls_back_chunks_generation_and_child(extraction_job, monkeypatch):
    store, claim, success = extraction_job
    # Inject only the final guard failure; the transaction and all preceding writes are real.
    monkeypatch.setattr(
        store._coordination_store, "_finalize_pdf_job_if_current_and_live", lambda **kwargs: False
    )
    result = store.finalize_success(
        operation_id=TransitionOperationId(uuid4().hex), claim=claim, success=success
    )
    assert isinstance(result, Fenced)
    with SessionFactory() as session:
        assert session.get(IngestionJobTable, claim.token.job_id).status == "processing"
        assert session.get(LexicalHeadTable, claim.work.document_id) is None
        assert (
            session.scalar(
                select(func.count())
                .select_from(LexicalGenerationTable)
                .where(LexicalGenerationTable.document_id == claim.work.document_id)
            )
            == 0
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(ChunkSetTable)
                .where(ChunkSetTable.document_version_id == claim.work.document_version_id)
            )
            == 0
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(IngestionJobTable)
                .where(IngestionJobTable.parent_ingestion_job_id == claim.token.job_id)
            )
            == 0
        )


def test_parent_identity_cannot_change_after_linked_child_exists(extraction_job):
    _, claim, _ = extraction_job
    _finalize_extraction_and_index_with_replay(extraction_job)
    with (
        pytest.raises(IntegrityError, match="linked extraction identity is immutable"),
        SessionFactory.begin() as session,
    ):
        parent = session.get(IngestionJobTable, claim.token.job_id)
        parent.parser_configuration_id = "changed-parser"
    with SessionFactory() as session:
        assert session.get(IngestionJobTable, claim.token.job_id).parser_configuration_id == (
            claim.work.parser_configuration_id
        )
        children = session.scalars(
            select(IngestionJobTable).where(
                IngestionJobTable.parent_ingestion_job_id == claim.token.job_id
            )
        ).all()
        assert len(children) == 1
        assert children[0].parser_configuration_id == claim.work.parser_configuration_id
