"""Owned PostgreSQL projection proof; synthetic receipt, no native/application E2E claim."""

from dataclasses import replace
from uuid import uuid4

from test_s2_lexical_retrieval import _structural_population
from test_s2_two_job_transactions import extraction_job as extraction_job

from knora.adapters.http.routes import _job_status_payload
from knora.adapters.postgres.database import SessionFactory
from knora.adapters.postgres.ingestion_job_store import PostgresIngestionJobStore
from knora.adapters.postgres.search_index_store import PostgresSearchIndexStore
from knora.answering.stores import RetrievalConfiguration
from knora.ingestion.job_processing import (
    AttemptTimingV1,
    ClaimedAttempt,
    ClaimOperationId,
    FinalizationApplied,
    TransitionOperationId,
)
from knora.ingestion.search_indexing import LexicalIndexSuccess, StageReceipt


def test_parent_poll_tracks_its_child_and_authoritative_serving_through_revoke(extraction_job):
    store, parent, success = extraction_job
    result = store.finalize_success(
        operation_id=TransitionOperationId(uuid4().hex), claim=parent, success=success
    )
    assert isinstance(result, FinalizationApplied)
    child = store.claim_next_attempt(
        operation_id=ClaimOperationId(uuid4().hex),
        worker_id="s2-status",
        timing=AttemptTimingV1.standard(),
    )
    assert isinstance(child, ClaimedAttempt)
    authority = PostgresSearchIndexStore(SessionFactory)
    generation = authority.load_generation(child.work).generation
    reader = PostgresIngestionJobStore(
        SessionFactory,
        retrieval_configuration=replace(
            RetrievalConfiguration.bm25_diagnostic_v1(),
            lexical_policy_id=generation.lexical_profile.id,
        ),
        lexical_population=_structural_population(generation),
    )

    def read():
        status = reader.get_job_status(
            workspace_id=parent.work.workspace_id, ingestion_job_id=parent.token.job_id
        )
        assert status.ingestion_job_id == parent.token.job_id
        assert status.status == "succeeded"
        assert status.derivation_kind == "pdf_extraction"
        assert status.indexing_job_id == child.token.job_id
        assert status.desired_lexical_generation_id == generation.generation_id
        return status

    pending = read()
    assert pending.indexing_status == "processing"
    assert pending.served_document_version_id is None
    assert pending.lexical_readiness == "not_indexed"
    assert _job_status_payload(pending)["poll_after_seconds"] == 5
    assert isinstance(
        store.finalize_success(
            operation_id=TransitionOperationId(uuid4().hex),
            claim=child,
            success=LexicalIndexSuccess(
                generation,
                StageReceipt(
                    generation.generation_id, len(generation.chunks), generation.content_digest()
                ),
            ),
        ),
        FinalizationApplied,
    )
    ready = read()
    assert ready.indexing_status == "succeeded"
    assert ready.served_document_version_id == generation.document_version_id
    assert ready.lexical_readiness == "ready"
    assert _job_status_payload(ready)["poll_after_seconds"] == 0
    authority.revoke(workspace_id=generation.workspace_id, document_id=generation.document_id)
    revoked = reader.get_job_status(
        workspace_id=parent.work.workspace_id, ingestion_job_id=parent.token.job_id
    )
    assert revoked.indexing_status == "succeeded"
    assert revoked.served_document_version_id is None
    assert revoked.lexical_readiness != "ready"
