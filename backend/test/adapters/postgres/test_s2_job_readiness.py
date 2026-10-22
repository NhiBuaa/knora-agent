"""Offline public job polling: exact parent linkage and strategy-aware serving."""

from contextlib import contextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from knora.adapters.http.routes import _job_status_payload
from knora.adapters.http.schemas import DocumentResponse, IngestionJobStatusResponse
from knora.adapters.postgres import document_reader
from knora.adapters.postgres.ingestion_jobs.submission import PostgresPdfSubmissionStore
from knora.answering.stores import RetrievalConfiguration
from knora.ingestion.documents import DocumentProjection


@pytest.mark.parametrize("kind", ["pdf_extraction", "lexical_index", "dense"])
def test_job_poll_preserves_requested_identity_and_links_only_its_child(monkeypatch, kind):
    now = datetime.now(UTC)
    job = SimpleNamespace(
        id="requested-old-job",
        status="succeeded",
        derivation_kind=kind,
        attempt_count=1,
        max_attempts=3,
        next_attempt_at=None,
        created_at=now,
        started_at=now,
        updated_at=now,
        terminal_at=now,
        target_document_version_id="old-version",
        failure_reason=None,
        safe_failure_code=None,
        replacement_document_version_id=None,
        replacement_ingestion_job_id=None,
        reprocess_of_job_id=None,
    )
    document = SimpleNamespace(id="document", current_document_version_id="version")
    statements = []
    events = []
    child = SimpleNamespace(id="explicit-child", status="retry_scheduled")
    session = Mock()
    session.get.return_value = SimpleNamespace(revision=7)
    session.execute.side_effect = lambda query: (
        events.append("query") or SimpleNamespace(first=lambda: (job, document, None, None, None))
    )
    session.scalar.side_effect = lambda query: statements.append(query) or child

    @contextmanager
    def sessions():
        yield session

    projected = DocumentProjection(
        "document",
        "workspace",
        "pdf",
        "pdf",
        False,
        1,
        served_document_version_id="version",
        serving_state="current",
        lexical_readiness="ready",
        desired_lexical_generation_id="desired-B",
    )
    projection = Mock(return_value=projected)
    monkeypatch.setattr(document_reader.PostgresDocumentReader, "_projection", projection)
    monkeypatch.setattr(
        document_reader.PostgresDocumentReader,
        "_begin_snapshot",
        staticmethod(lambda _: events.append("snapshot")),
    )
    store = PostgresPdfSubmissionStore(
        sessions, lambda _: now, RetrievalConfiguration.bm25_top8_v1()
    )
    status = store.get_job_status(workspace_id="workspace", ingestion_job_id=job.id)
    assert events == ["snapshot", "query"]
    assert status.ingestion_job_id == job.id
    assert status.status == "succeeded"
    assert status.target_document_version_id == "old-version"
    assert status.derivation_kind == kind
    assert status.served_document_version_id == "version"
    assert status.lexical_readiness == "ready"
    assert status.desired_lexical_generation_id == "desired-B"
    assert status.lexical_revision == 7
    if kind == "pdf_extraction":
        assert status.indexing_job_id == child.id
        assert status.indexing_status == "retry_scheduled"
        params = statements[0].compile().params.values()
        assert job.id in params and "workspace" in params and "document" in params
        assert "parent_ingestion_job_id" in str(statements[0])
    elif kind == "lexical_index":
        assert status.indexing_job_id == job.id
        assert status.indexing_status == job.status
        assert statements == []
    else:
        assert status.indexing_job_id is None
        assert statements == []
    payload = _job_status_payload(status)
    assert payload["derivation_kind"] == kind
    assert payload["indexing_job_id"] == status.indexing_job_id
    assert payload["lexical_readiness"] == "ready"
    assert payload["desired_lexical_generation_id"] == "desired-B"
    assert payload["lexical_revision"] == 7
    assert payload["poll_after_seconds"] == (5 if kind == "pdf_extraction" else 0)
    IngestionJobStatusResponse.model_validate(payload)


def test_document_contract_exposes_kind_and_desired_generation_without_fabricating_them():
    row = DocumentProjection("document", "workspace", "pdf", "pdf", False, 1)
    result = DocumentResponse.model_validate(row, from_attributes=True)
    assert result.derivation_kind is None
    assert result.desired_lexical_generation_id is None
