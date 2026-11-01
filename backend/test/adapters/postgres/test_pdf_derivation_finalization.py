from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from io import BytesIO
from uuid import uuid4

import pytest
from sqlalchemy import select, text

from knora.adapters.postgres.database import SessionFactory
from knora.adapters.postgres.ingestion_job_store import PostgresIngestionJobStore
from knora.adapters.postgres.tables import (
    ChunkSetTable,
    ChunkTable,
    DocumentTable,
    DocumentVersionTable,
    EmbeddingSetTable,
    IngestionJobAttemptTable,
    IngestionJobTable,
    WorkspaceTable,
)
from knora.ingestion.job_processing import (
    AttemptTimingV1,
    ClaimedAttempt,
    ClaimOperationId,
    CoordinationInvariantError,
    FinalizationApplied,
    PdfDerivationHandler,
    PdfDerivationProfile,
    PdfDerivationSuccess,
    PdfExtractionSuccess,
    ProcessIngestionJob,
    RetryPolicyV1,
    Succeeded,
    SystemRandomSource,
    TransitionOperationId,
    UuidOperationIds,
)
from knora.ingestion.jobs import (
    PdfExtractionSubmissionConfiguration,
    PdfSubmissionConfiguration,
    PreparedPdfSubmission,
)
from knora.ingestion.object_store import ObjectMetadata
from knora.ingestion.pdf import (
    NormalizedPdfPage,
    PdfExtractionConfiguration,
    PdfExtractionResult,
    PreparedPdfChunk,
)
from knora.ingestion.pdf_structure import (
    BlockType,
    CanonicalBlock,
    CanonicalDocument,
    CanonicalPage,
    PageCompleteness,
)
from knora.ingestion.search_indexing import LexicalProfile
from knora.providers.embedding import EmbeddingBatch, EmbeddingConfiguration


def _submit_job() -> tuple[PostgresIngestionJobStore, str, PdfSubmissionConfiguration]:
    with SessionFactory.begin() as session:
        session.execute(
            text(
                "TRUNCATE TABLE workspace_admissions, "
                "reprocess_audit_records, idempotency_records, "
                "ingestion_job_attempts, ingestion_jobs"
            )
        )
    workspace_id = f"pdf-finalization-{uuid4()}"
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="PDF finalization"))
    configuration = PdfSubmissionConfiguration.milestone_two(
        embedding_configuration=EmbeddingConfiguration.milestone_one_local()
    )
    raw = b"%PDF-1.7\nfixture"
    source_object = ObjectMetadata(
        workspace_id=workspace_id,
        object_key=uuid4().hex,
        sha256=hashlib.sha256(raw).hexdigest(),
        byte_size=len(raw),
        media_type="application/pdf",
    )
    prepared = PreparedPdfSubmission(
        workspace_id=workspace_id,
        source_key="support/fixture",
        source_name="fixture.pdf",
        source_object=source_object,
        content_fingerprint="\n".join(
            (
                workspace_id,
                "support/fixture",
                source_object.sha256,
                configuration.parser_configuration_id,
                configuration.normalizer_configuration_id,
                configuration.chunking_configuration.id,
                configuration.embedding_configuration.id,
            )
        ),
        idempotency_operation="submit_pdf",
        idempotency_key=uuid4().hex,
        idempotency_expires_at=datetime.now(UTC) + timedelta(hours=24),
        configuration=configuration,
    )
    store = PostgresIngestionJobStore(SessionFactory)
    return store, store.commit_pdf_submission(prepared).ingestion_job_id, configuration


def _success(configuration: PdfSubmissionConfiguration) -> PdfDerivationSuccess:
    extraction_configuration = PdfExtractionConfiguration.milestone_two()
    content = "A short PDF paragraph."
    page = NormalizedPdfPage(
        page_number=1,
        text=content,
        content_checksum=hashlib.sha256(content.encode()).hexdigest(),
    )
    return PdfDerivationSuccess(
        extraction=PdfExtractionResult(
            pages=(page,),
            chunks=(
                PreparedPdfChunk(
                    ordinal=0,
                    page_number=1,
                    page_start=1,
                    page_end=1,
                    start_offset=0,
                    end_offset=len(content),
                    content=content,
                    content_checksum=page.content_checksum,
                    token_count=5,
                ),
            ),
            parser_version=extraction_configuration.parser_version,
            extraction_options_version=extraction_configuration.extraction_options_version,
            normalizer_version=extraction_configuration.normalizer_version,
            tokenizer_name=extraction_configuration.tokenizer_name,
            tokenizer_version=extraction_configuration.tokenizer_version,
            chunking_policy_version=extraction_configuration.chunking_policy_version,
            derivation_identity=extraction_configuration.derivation_identity,
        ),
        vectors=(tuple(0.1 for _ in range(configuration.embedding_configuration.dimensions)),),
        embedding_provider=configuration.embedding_configuration.provider,
        embedding_model=configuration.embedding_configuration.model,
    )


def test_pdf_success_finalization_commits_complete_derivation_and_activation() -> None:
    store, job_id, configuration = _submit_job()
    claim = store.claim_next_attempt(
        operation_id=ClaimOperationId(uuid4().hex),
        worker_id="worker-pdf",
        timing=AttemptTimingV1.standard(),
    )
    assert isinstance(claim, ClaimedAttempt)

    result = store.finalize_success(
        operation_id=TransitionOperationId(uuid4().hex),
        claim=claim,
        success=_success(configuration),
    )

    assert isinstance(result, FinalizationApplied)
    with SessionFactory() as session:
        job = session.get(IngestionJobTable, job_id)
        attempt = session.get(IngestionJobAttemptTable, (job_id, 1))
        document = session.get(DocumentTable, claim.work.document_id)
        chunk_set = session.scalar(
            select(ChunkSetTable).where(
                ChunkSetTable.document_version_id == claim.work.document_version_id,
                ChunkSetTable.parser_configuration_id == claim.work.parser_configuration_id,
                ChunkSetTable.normalizer_configuration_id == claim.work.normalizer_configuration_id,
                ChunkSetTable.chunking_configuration_id == claim.work.chunking_configuration_id,
            )
        )
        embedding_set = session.scalar(
            select(EmbeddingSetTable).where(EmbeddingSetTable.chunk_set_id == chunk_set.id)
        )
        assert job.status == "succeeded"
        assert attempt.disposition == "succeeded"
        assert document.active_embedding_set_id == embedding_set.id
        assert chunk_set.status == "completed"
        assert embedding_set.status == "completed"


def test_pdf_success_finalization_persists_history_but_supersedes_stale_target() -> None:
    store, job_id, configuration = _submit_job()
    claim = store.claim_next_attempt(
        operation_id=ClaimOperationId(uuid4().hex),
        worker_id="worker-pdf",
        timing=AttemptTimingV1.standard(),
    )
    assert isinstance(claim, ClaimedAttempt)

    replacement_version_id = str(uuid4())
    with SessionFactory.begin() as session:
        document = session.get(DocumentTable, claim.work.document_id)
        session.add(
            DocumentVersionTable(
                id=replacement_version_id,
                document_id=document.id,
                normalized_content=None,
                normalized_content_checksum=None,
                raw_sha256=hashlib.sha256(b"new-pdf").hexdigest(),
                media_type="application/pdf",
                version_number=2,
            )
        )
        session.flush()
        document.current_document_version_id = replacement_version_id

    result = store.finalize_success(
        operation_id=TransitionOperationId(uuid4().hex),
        claim=claim,
        success=_success(configuration),
    )

    assert isinstance(result, FinalizationApplied)
    assert result.outcome == "superseded"
    assert result.replacement_document_version_id == replacement_version_id
    with SessionFactory() as session:
        job = session.get(IngestionJobTable, job_id)
        attempt = session.get(IngestionJobAttemptTable, (job_id, 1))
        document = session.get(DocumentTable, claim.work.document_id)
        assert job.status == "superseded"
        assert attempt.disposition == "superseded"
        assert document.current_document_version_id == replacement_version_id
        assert document.active_embedding_set_id is None


def test_pdf_success_finalization_replays_one_operation_without_duplicate_rows() -> None:
    store, job_id, configuration = _submit_job()
    claim = store.claim_next_attempt(
        operation_id=ClaimOperationId(uuid4().hex),
        worker_id="worker-pdf",
        timing=AttemptTimingV1.standard(),
    )
    assert isinstance(claim, ClaimedAttempt)
    operation_id = TransitionOperationId(uuid4().hex)
    success = _success(configuration)

    first = store.finalize_success(
        operation_id=operation_id,
        claim=claim,
        success=success,
    )
    replay = store.finalize_success(
        operation_id=operation_id,
        claim=claim,
        success=success,
    )

    assert isinstance(first, FinalizationApplied)
    assert replay == first
    with SessionFactory() as session:
        assert (
            session.scalar(
                select(ChunkSetTable).where(
                    ChunkSetTable.document_version_id == claim.work.document_version_id,
                    ChunkSetTable.parser_configuration_id == claim.work.parser_configuration_id,
                    ChunkSetTable.normalizer_configuration_id
                    == claim.work.normalizer_configuration_id,
                )
            )
            is not None
        )
        job = session.get(IngestionJobTable, job_id)
        assert job.status == "succeeded"


class _Permit:
    def release(self) -> None:
        return None


class _Runner:
    def try_reserve(self) -> _Permit:
        return _Permit()


class _Extractor:
    def __init__(self, success: PdfDerivationSuccess) -> None:
        self.success = success

    def extract(self, stream, configuration: PdfExtractionConfiguration):
        assert stream.read() == b"pdf"
        return self.success.extraction


class _EmbeddingProvider:
    def __init__(self, success: PdfDerivationSuccess) -> None:
        self.success = success

    def embed(self, texts, configuration: EmbeddingConfiguration) -> EmbeddingBatch:
        return EmbeddingBatch(
            vectors=self.success.vectors,
            provider=self.success.embedding_provider,
            model=self.success.embedding_model,
        )


class _ObjectStore:
    def __init__(self, metadata: ObjectMetadata) -> None:
        self.metadata = metadata

    def head(self, *, workspace_id: str, object_key: str) -> ObjectMetadata:
        return self.metadata

    def open_read(self, *, workspace_id: str, object_key: str) -> BytesIO:
        return BytesIO(b"pdf")


def test_process_ingestion_job_runs_concrete_pdf_handler_to_atomic_success() -> None:
    store, _, configuration = _submit_job()
    claim = store.claim_next_attempt(
        operation_id=ClaimOperationId(uuid4().hex),
        worker_id="setup-worker",
        timing=AttemptTimingV1.standard(),
    )
    assert isinstance(claim, ClaimedAttempt)
    # Return the queued state to let the processor own the claim in this end-to-end seam test.
    with SessionFactory.begin() as session:
        job = session.get(IngestionJobTable, claim.token.job_id)
        attempt = session.get(IngestionJobAttemptTable, (claim.token.job_id, 1))
        session.delete(attempt)
        job.status = "queued"
        job.attempt_count = 0
        job.started_at = None
        job.worker_id = None
        job.lease_expires_at = None
        job.current_attempt_number = None
        job.current_attempt_started_at = None
        job.current_attempt_deadline_at = None

    success = _success(configuration)
    metadata = ObjectMetadata(
        workspace_id=claim.work.workspace_id,
        object_key=claim.work.source_object_key,
        sha256=claim.work.source_sha256,
        byte_size=claim.work.source_byte_size,
        media_type=claim.work.source_media_type,
    )
    processor = ProcessIngestionJob(
        store=store,
        handler=PdfDerivationHandler(
            object_store=_ObjectStore(metadata),
            extractor=_Extractor(success),
            embedding_provider=_EmbeddingProvider(success),
            profile=PdfDerivationProfile.milestone_two(
                embedding_configuration=configuration.embedding_configuration
            ),
        ),
        operation_ids=UuidOperationIds(),
        timing=AttemptTimingV1.standard(),
        retry_policy=RetryPolicyV1(SystemRandomSource()),
        runner=_Runner(),
    )

    result = processor.run_once("worker-pdf")

    assert isinstance(result, Succeeded)


def _make_canonical_structure(
    raw_sha: str,
    page_text: str,
    *,
    is_complete: bool = True,
    heading_path: tuple[str, ...] = ("Chapter 1",),
) -> CanonicalDocument:
    return CanonicalDocument(
        raw_source_hash=raw_sha,
        derivation_identity=PdfExtractionConfiguration.milestone_two().derivation_identity,
        parser_version="pdf-pypdf-m2",
        pages=(
            CanonicalPage(
                page_number=1,
                text=page_text,
                content_checksum=hashlib.sha256(page_text.encode()).hexdigest(),
                blocks=(
                    CanonicalBlock(
                        block_id="b1",
                        page_number=1,
                        block_type=BlockType.PARAGRAPH,
                        start_offset=0,
                        end_offset=len(page_text),
                        text=page_text,
                        heading_path=heading_path,
                    ),
                ),
                completeness=PageCompleteness(is_complete=is_complete),
            ),
        ),
        is_complete=is_complete,
    )


def test_pdf_success_finalization_persists_heading_path_when_valid() -> None:
    store, job_id, configuration = _submit_job()
    claim = store.claim_next_attempt(
        operation_id=ClaimOperationId(uuid4().hex),
        worker_id="worker-pdf",
        timing=AttemptTimingV1.standard(),
    )
    assert isinstance(claim, ClaimedAttempt)

    raw_sha = hashlib.sha256(b"%PDF-1.7\nfixture").hexdigest()
    content = "A short PDF paragraph."
    structure = _make_canonical_structure(
        raw_sha, content, is_complete=True, heading_path=("Chapter 1", "Section A")
    )
    extraction_configuration = PdfExtractionConfiguration.milestone_two()
    page = NormalizedPdfPage(
        page_number=1,
        text=content,
        content_checksum=hashlib.sha256(content.encode()).hexdigest(),
    )
    success = PdfDerivationSuccess(
        extraction=PdfExtractionResult(
            pages=(page,),
            chunks=(
                PreparedPdfChunk(
                    ordinal=0,
                    page_number=1,
                    page_start=1,
                    page_end=1,
                    start_offset=0,
                    end_offset=len(content),
                    content=content,
                    content_checksum=page.content_checksum,
                    token_count=5,
                    heading_path=("Chapter 1", "Section A"),
                ),
            ),
            parser_version=extraction_configuration.parser_version,
            extraction_options_version=extraction_configuration.extraction_options_version,
            normalizer_version=extraction_configuration.normalizer_version,
            tokenizer_name=extraction_configuration.tokenizer_name,
            tokenizer_version=extraction_configuration.tokenizer_version,
            chunking_policy_version=extraction_configuration.chunking_policy_version,
            derivation_identity=extraction_configuration.derivation_identity,
            structure=structure,
        ),
        vectors=(tuple(0.1 for _ in range(configuration.embedding_configuration.dimensions)),),
        embedding_provider=configuration.embedding_configuration.provider,
        embedding_model=configuration.embedding_configuration.model,
    )

    result = store.finalize_success(
        operation_id=TransitionOperationId(uuid4().hex),
        claim=claim,
        success=success,
    )

    assert isinstance(result, FinalizationApplied)
    with SessionFactory() as session:
        chunk = session.scalar(
            select(ChunkTable)
            .join(ChunkSetTable)
            .where(ChunkSetTable.document_version_id == claim.work.document_version_id)
        )
        assert chunk is not None
        assert chunk.heading_path == ["Chapter 1", "Section A"]


def test_pdf_success_finalization_rejects_incomplete_canonical_structure() -> None:
    store, job_id, configuration = _submit_job()
    claim = store.claim_next_attempt(
        operation_id=ClaimOperationId(uuid4().hex),
        worker_id="worker-pdf",
        timing=AttemptTimingV1.standard(),
    )
    assert isinstance(claim, ClaimedAttempt)

    raw_sha = hashlib.sha256(b"%PDF-1.7\nfixture").hexdigest()
    content = "A short PDF paragraph."
    structure = _make_canonical_structure(raw_sha, content, is_complete=False)
    extraction_configuration = PdfExtractionConfiguration.milestone_two()
    page = NormalizedPdfPage(
        page_number=1,
        text=content,
        content_checksum=hashlib.sha256(content.encode()).hexdigest(),
    )
    success = PdfDerivationSuccess(
        extraction=PdfExtractionResult(
            pages=(page,),
            chunks=(
                PreparedPdfChunk(
                    ordinal=0,
                    page_number=1,
                    page_start=1,
                    page_end=1,
                    start_offset=0,
                    end_offset=len(content),
                    content=content,
                    content_checksum=page.content_checksum,
                    token_count=5,
                    heading_path=("Chapter 1",),
                ),
            ),
            parser_version=extraction_configuration.parser_version,
            extraction_options_version=extraction_configuration.extraction_options_version,
            normalizer_version=extraction_configuration.normalizer_version,
            tokenizer_name=extraction_configuration.tokenizer_name,
            tokenizer_version=extraction_configuration.tokenizer_version,
            chunking_policy_version=extraction_configuration.chunking_policy_version,
            derivation_identity=extraction_configuration.derivation_identity,
            structure=structure,
        ),
        vectors=(tuple(0.1 for _ in range(configuration.embedding_configuration.dimensions)),),
        embedding_provider=configuration.embedding_configuration.provider,
        embedding_model=configuration.embedding_configuration.model,
    )

    with pytest.raises(CoordinationInvariantError, match="canonical structure is incomplete"):
        store.finalize_success(
            operation_id=TransitionOperationId(uuid4().hex),
            claim=claim,
            success=success,
        )


def test_pdf_success_finalization_rejects_source_hash_mismatch() -> None:
    store, job_id, configuration = _submit_job()
    claim = store.claim_next_attempt(
        operation_id=ClaimOperationId(uuid4().hex),
        worker_id="worker-pdf",
        timing=AttemptTimingV1.standard(),
    )
    assert isinstance(claim, ClaimedAttempt)

    content = "A short PDF paragraph."
    structure = _make_canonical_structure("0" * 64, content, is_complete=True)
    extraction_configuration = PdfExtractionConfiguration.milestone_two()
    page = NormalizedPdfPage(
        page_number=1,
        text=content,
        content_checksum=hashlib.sha256(content.encode()).hexdigest(),
    )
    success = PdfDerivationSuccess(
        extraction=PdfExtractionResult(
            pages=(page,),
            chunks=(
                PreparedPdfChunk(
                    ordinal=0,
                    page_number=1,
                    page_start=1,
                    page_end=1,
                    start_offset=0,
                    end_offset=len(content),
                    content=content,
                    content_checksum=page.content_checksum,
                    token_count=5,
                ),
            ),
            parser_version=extraction_configuration.parser_version,
            extraction_options_version=extraction_configuration.extraction_options_version,
            normalizer_version=extraction_configuration.normalizer_version,
            tokenizer_name=extraction_configuration.tokenizer_name,
            tokenizer_version=extraction_configuration.tokenizer_version,
            chunking_policy_version=extraction_configuration.chunking_policy_version,
            derivation_identity=extraction_configuration.derivation_identity,
            structure=structure,
        ),
        vectors=(tuple(0.1 for _ in range(configuration.embedding_configuration.dimensions)),),
        embedding_provider=configuration.embedding_configuration.provider,
        embedding_model=configuration.embedding_configuration.model,
    )

    with pytest.raises(CoordinationInvariantError, match="raw_source_hash does not match"):
        store.finalize_success(
            operation_id=TransitionOperationId(uuid4().hex),
            claim=claim,
            success=success,
        )


def test_pdf_success_finalization_rejects_invalid_heading_path() -> None:
    store, job_id, configuration = _submit_job()
    claim = store.claim_next_attempt(
        operation_id=ClaimOperationId(uuid4().hex),
        worker_id="worker-pdf",
        timing=AttemptTimingV1.standard(),
    )
    assert isinstance(claim, ClaimedAttempt)

    content = "A short PDF paragraph."
    extraction_configuration = PdfExtractionConfiguration.milestone_two()
    page = NormalizedPdfPage(
        page_number=1,
        text=content,
        content_checksum=hashlib.sha256(content.encode()).hexdigest(),
    )
    success = PdfDerivationSuccess(
        extraction=PdfExtractionResult(
            pages=(page,),
            chunks=(
                PreparedPdfChunk(
                    ordinal=0,
                    page_number=1,
                    page_start=1,
                    page_end=1,
                    start_offset=0,
                    end_offset=len(content),
                    content=content,
                    content_checksum=page.content_checksum,
                    token_count=5,
                    heading_path=("   ",),
                ),
            ),
            parser_version=extraction_configuration.parser_version,
            extraction_options_version=extraction_configuration.extraction_options_version,
            normalizer_version=extraction_configuration.normalizer_version,
            tokenizer_name=extraction_configuration.tokenizer_name,
            tokenizer_version=extraction_configuration.tokenizer_version,
            chunking_policy_version=extraction_configuration.chunking_policy_version,
            derivation_identity=extraction_configuration.derivation_identity,
        ),
        vectors=(tuple(0.1 for _ in range(configuration.embedding_configuration.dimensions)),),
        embedding_provider=configuration.embedding_configuration.provider,
        embedding_model=configuration.embedding_configuration.model,
    )

    with pytest.raises(CoordinationInvariantError, match="invalid chunk provenance"):
        store.finalize_success(
            operation_id=TransitionOperationId(uuid4().hex),
            claim=claim,
            success=success,
        )


def test_pdf_extraction_only_persists_heading_path_and_validates_structure() -> None:
    with SessionFactory.begin() as session:
        session.execute(
            text(
                "TRUNCATE TABLE workspace_admissions, "
                "reprocess_audit_records, idempotency_records, "
                "ingestion_job_attempts, ingestion_jobs"
            )
        )
    workspace_id = f"pdf-extraction-{uuid4()}"
    with SessionFactory.begin() as session:
        session.add(WorkspaceTable(id=workspace_id, name="PDF extraction test"))

    profile = LexicalProfile(
        id="bm25-word-upload-fixture-population-v1",
        tokenizer="word",
        tokenizer_version="qdrant-1.19.2",
        k1=1.2,
        b=0.75,
        avg_len=7.0,
        statistics_digest="29452edc694c61c1f13ce8f519d0a192b926bf04ff354a42b7a5056fb7819d10",
    )
    base_config = PdfSubmissionConfiguration.milestone_two(
        embedding_configuration=EmbeddingConfiguration.milestone_one_local()
    )
    configuration = PdfExtractionSubmissionConfiguration(
        parser_configuration_id=base_config.parser_configuration_id,
        normalizer_configuration_id=base_config.normalizer_configuration_id,
        chunking_configuration=base_config.chunking_configuration,
        lexical_profile=profile,
    )
    raw = b"%PDF-1.7\nextraction-fixture"
    raw_sha = hashlib.sha256(raw).hexdigest()
    source_object = ObjectMetadata(
        workspace_id=workspace_id,
        object_key=uuid4().hex,
        sha256=raw_sha,
        byte_size=len(raw),
        media_type="application/pdf",
    )
    prepared = PreparedPdfSubmission(
        workspace_id=workspace_id,
        source_key="support/extraction-fixture",
        source_name="extraction.pdf",
        source_object=source_object,
        content_fingerprint="\n".join(
            (
                workspace_id,
                "support/extraction-fixture",
                source_object.sha256,
                configuration.parser_configuration_id,
                configuration.normalizer_configuration_id,
                configuration.chunking_configuration.id,
                configuration.lexical_profile.digest(),
            )
        ),
        idempotency_operation="submit_pdf_extraction",
        idempotency_key=uuid4().hex,
        idempotency_expires_at=datetime.now(UTC) + timedelta(hours=24),
        configuration=configuration,
    )
    store = PostgresIngestionJobStore(SessionFactory)
    store.commit_pdf_submission(prepared)

    claim = store.claim_next_attempt(
        operation_id=ClaimOperationId(uuid4().hex),
        worker_id="worker-extraction",
        timing=AttemptTimingV1.standard(),
    )
    assert isinstance(claim, ClaimedAttempt)

    content = "Extraction text content."
    structure = _make_canonical_structure(
        raw_sha, content, is_complete=True, heading_path=("Appendix A",)
    )
    extraction_configuration = PdfExtractionConfiguration.milestone_two()
    page = NormalizedPdfPage(
        page_number=1,
        text=content,
        content_checksum=hashlib.sha256(content.encode()).hexdigest(),
    )
    success = PdfExtractionSuccess(
        extraction=PdfExtractionResult(
            pages=(page,),
            chunks=(
                PreparedPdfChunk(
                    ordinal=0,
                    page_number=1,
                    page_start=1,
                    page_end=1,
                    start_offset=0,
                    end_offset=len(content),
                    content=content,
                    content_checksum=page.content_checksum,
                    token_count=3,
                    heading_path=("Appendix A",),
                ),
            ),
            parser_version=extraction_configuration.parser_version,
            extraction_options_version=extraction_configuration.extraction_options_version,
            normalizer_version=extraction_configuration.normalizer_version,
            tokenizer_name=extraction_configuration.tokenizer_name,
            tokenizer_version=extraction_configuration.tokenizer_version,
            chunking_policy_version=extraction_configuration.chunking_policy_version,
            derivation_identity=extraction_configuration.derivation_identity,
            structure=structure,
        ),
        lexical_profile=profile,
    )

    result = store.finalize_success(
        operation_id=TransitionOperationId(uuid4().hex),
        claim=claim,
        success=success,
    )
    assert isinstance(result, FinalizationApplied)

    with SessionFactory() as session:
        chunk = session.scalar(
            select(ChunkTable)
            .join(ChunkSetTable)
            .where(ChunkSetTable.document_version_id == claim.work.document_version_id)
        )
        assert chunk is not None
        assert chunk.heading_path == ["Appendix A"]
