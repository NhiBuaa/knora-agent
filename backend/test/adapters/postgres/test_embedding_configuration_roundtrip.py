"""Persisted embedding identity must survive PDF job reconstruction."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from knora.adapters.postgres.database import SessionFactory
from knora.adapters.postgres.embedding_configuration import configuration_from_row
from knora.adapters.postgres.ingestion_job_store import PostgresIngestionJobStore
from knora.adapters.postgres.ingestion_jobs.submission import PostgresPdfSubmissionStore
from knora.adapters.postgres.tables import (
    ChunkSetTable,
    DocumentTable,
    EmbeddingConfigurationTable,
    EmbeddingSetTable,
    IngestionJobTable,
    WorkspaceTable,
)
from knora.domain.errors import KnoraError
from knora.ingestion.jobs import PdfSubmissionConfiguration, PreparedPdfSubmission
from knora.ingestion.object_store import ObjectMetadata
from knora.ingestion.processing import ChunkingConfiguration
from knora.providers.embedding import EmbeddingConfiguration


def _profile() -> EmbeddingConfiguration:
    return EmbeddingConfiguration(
        id=f"qwen3-ollama-{uuid4().hex}",
        provider="ollama",
        model="qwen3-embedding:0.6b",
        dimensions=1024,
        distance_metric="cosine",
        deployment_identity="ollama-digest-a",
        api_contract_version="ollama-api-embed-v1",
        input_normalization="utf8-nfkc-v1",
        input_policy_id="qwen3-qa-v1",
        output_dimensionality=1024,
        vector_normalization="provider-output-v1",
    )


def _submission(workspace_id: str, profile: EmbeddingConfiguration) -> PreparedPdfSubmission:
    configuration = PdfSubmissionConfiguration(
        parser_configuration_id="pdf-parser-pypdf-m2-v1",
        normalizer_configuration_id="pdf-normalizer-m2-v1",
        chunking_configuration=ChunkingConfiguration(
            id="chunking-m2-pdf-v1",
            parser_version="pypdf-baseline-v1",
            chunker_version="page-block-v1",
            tokenizer_name="cl100k_base",
            tokenizer_version="tiktoken-0.12.0",
            target_tokens=500,
            overlap_tokens=75,
            max_tokens=650,
        ),
        embedding_configuration=profile,
    )
    raw_sha256 = uuid4().hex + uuid4().hex
    return PreparedPdfSubmission(
        workspace_id=workspace_id,
        source_key=f"profile/{uuid4().hex}",
        source_name="profile.pdf",
        source_object=ObjectMetadata(
            workspace_id=workspace_id,
            object_key=uuid4().hex,
            sha256=raw_sha256,
            byte_size=123,
            media_type="application/pdf",
        ),
        content_fingerprint=uuid4().hex,
        idempotency_operation="submit_pdf",
        idempotency_key=uuid4().hex,
        idempotency_expires_at=datetime.now(UTC) + timedelta(hours=24),
        configuration=configuration,
    )


def test_persisted_profile_roundtrips_through_job_and_worker() -> None:
    workspace_id = f"profile-roundtrip-{uuid4().hex}"
    profile = _profile()
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="Profile roundtrip"))
    store = PostgresIngestionJobStore(SessionFactory)
    result = store.commit_pdf_submission(_submission(workspace_id, profile))

    with SessionFactory() as session:
        row = session.get(EmbeddingConfigurationTable, profile.id)
        job = session.get(IngestionJobTable, result.ingestion_job_id)
        assert configuration_from_row(row) == profile
        assert PostgresPdfSubmissionStore._configuration_from_job(
            session, job
        ).embedding_configuration == profile
        work = type("ClaimedWork", (), {
            "parser_configuration_id": job.parser_configuration_id,
            "normalizer_configuration_id": job.normalizer_configuration_id,
            "chunking_configuration_id": job.chunking_configuration_id,
            "embedding_configuration_id": job.embedding_configuration_id,
        })()

    assert store.pdf_profile_for_work(work).embedding_configuration == profile
    context = store.read_reprocess_context(
        workspace_id=workspace_id,
        document_version_id=result.document_version_id,
        config_mode="same_as_job",
        config_source_job_id=result.ingestion_job_id,
    )
    assert context.configuration.embedding_configuration == profile


def test_current_document_profile_retains_identity_without_matching_job() -> None:
    workspace_id = f"profile-active-{uuid4().hex}"
    profile = _profile()
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="Active profile"))
    store = PostgresIngestionJobStore(SessionFactory)
    result = store.commit_pdf_submission(_submission(workspace_id, profile))
    with SessionFactory.begin() as session:
        job = session.get(IngestionJobTable, result.ingestion_job_id)
        document = session.get(DocumentTable, result.document_id)
        chunk_set = ChunkSetTable(
            id=str(uuid4()),
            document_version_id=result.document_version_id,
            parser_configuration_id="alternate-parser-v1",
            normalizer_configuration_id=job.normalizer_configuration_id,
            chunking_configuration_id=job.chunking_configuration_id,
            status="completed",
        )
        session.add(chunk_set)
        session.flush()
        embedding_set = EmbeddingSetTable(
            id=str(uuid4()),
            chunk_set_id=chunk_set.id,
            embedding_configuration_id=profile.id,
            status="completed",
        )
        session.add(embedding_set)
        session.flush()
        document.active_embedding_set_id = embedding_set.id
        document.active_embedding_configuration_id = profile.id

    context = store.read_reprocess_context(
        workspace_id=workspace_id,
        document_version_id=result.document_version_id,
        config_mode="current",
        config_source_job_id=None,
    )
    assert context.configuration.embedding_configuration == profile


def test_same_id_with_changed_identity_is_rejected() -> None:
    workspace_id = f"profile-immutable-{uuid4().hex}"
    profile = _profile()
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="Profile immutable"))
    store = PostgresIngestionJobStore(SessionFactory)
    store.commit_pdf_submission(_submission(workspace_id, profile))

    with pytest.raises(KnoraError) as error:
        store.commit_pdf_submission(
            _submission(
                workspace_id,
                replace(profile, deployment_identity="ollama-digest-b"),
            )
        )
    assert error.value.code == "EMBEDDING_CONFIGURATION_IMMUTABLE"
