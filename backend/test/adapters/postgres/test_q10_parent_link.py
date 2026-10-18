from types import SimpleNamespace

from knora.adapters.postgres.document_reader import PostgresDocumentReader


def test_document_projection_links_indexing_status_to_latest_upload_parent():
    reader = PostgresDocumentReader(None)
    reader._answer_availability = lambda *_: "unavailable"
    row = SimpleNamespace(
        id="document",
        workspace_id="workspace",
        source_key="source",
        source_name="pdf",
        archived=False,
        revision=1,
        current_document_version_id="version",
        active_embedding_set_id=None,
    )
    upload = SimpleNamespace(id="new-upload", status="succeeded", derivation_kind="pdf_extraction")
    linked = SimpleNamespace(id="index-for-new-upload", status="retry_scheduled")
    captured = []

    def scalar(query):
        statement = str(query)
        captured.append(query)
        if (
            "FROM ingestion_jobs" in statement
            and "WHERE ingestion_jobs.parent_ingestion_job_id" in statement
        ):
            return linked
        if "FROM ingestion_jobs" in statement:
            return upload
        if "FROM workspaces" in statement:
            return False
        return None

    session = SimpleNamespace(
        execute=lambda query: SimpleNamespace(first=lambda: None),
        scalar=scalar,
    )
    projection = reader._projection(session, row)
    assert projection.ingestion_job_id == "new-upload"
    assert projection.indexing_job_id == "index-for-new-upload"
    assert projection.indexing_status == "retry_scheduled"
    assert any(
        "WHERE ingestion_jobs.parent_ingestion_job_id" in str(query)
        and "new-upload" in query.compile().params.values()
        for query in captured
    )


def test_document_projection_has_no_indexing_job_without_parent_link():
    reader = PostgresDocumentReader(None)
    reader._answer_availability = lambda *_: "unavailable"
    row = SimpleNamespace(
        id="document",
        workspace_id="workspace",
        source_key="source",
        source_name="pdf",
        archived=False,
        revision=1,
        current_document_version_id="version",
        active_embedding_set_id=None,
    )
    upload = SimpleNamespace(id="new-upload", status="queued", derivation_kind="pdf_extraction")

    def scalar(query):
        statement = str(query)
        if (
            "FROM ingestion_jobs" in statement
            and "WHERE ingestion_jobs.parent_ingestion_job_id" in statement
        ):
            return None
        if "FROM ingestion_jobs" in statement:
            return upload
        if "FROM workspaces" in statement:
            return False
        return None

    session = SimpleNamespace(
        execute=lambda query: SimpleNamespace(first=lambda: None), scalar=scalar
    )
    projection = reader._projection(session, row)
    assert projection.ingestion_job_id == "new-upload"
    assert projection.indexing_job_id is None
    assert projection.indexing_status is None
