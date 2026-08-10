from __future__ import annotations

import hashlib
from dataclasses import replace
from io import BytesIO

from knora.ingestion.job_processing import (
    Cancellation,
    HandlerFailureKindV1,
    IngestionWork,
    PdfDerivationHandler,
    PdfDerivationProfile,
    WorkFailed,
    WorkSucceeded,
)
from knora.ingestion.object_store import ObjectMetadata
from knora.ingestion.pdf import (
    NormalizedPdfPage,
    PdfExtractionConfiguration,
    PdfExtractionResult,
    PreparedPdfChunk,
)
from knora.providers.embedding import EmbeddingBatch, EmbeddingConfiguration


class RecordingObjectStore:
    def __init__(self, metadata: ObjectMetadata) -> None:
        self.metadata = metadata
        self.head_calls: list[tuple[str, str]] = []
        self.open_calls: list[tuple[str, str]] = []

    def head(self, *, workspace_id: str, object_key: str) -> ObjectMetadata:
        self.head_calls.append((workspace_id, object_key))
        return self.metadata

    def open_read(self, *, workspace_id: str, object_key: str) -> BytesIO:
        self.open_calls.append((workspace_id, object_key))
        return BytesIO(b"pdf")


class FixedExtractor:
    def __init__(self, result: PdfExtractionResult) -> None:
        self.result = result
        self.calls: list[PdfExtractionConfiguration] = []

    def extract(self, stream, configuration: PdfExtractionConfiguration) -> PdfExtractionResult:
        self.calls.append(configuration)
        assert stream.read() == b"pdf"
        return self.result


class RecordingEmbeddingProvider:
    def __init__(self, configuration: EmbeddingConfiguration) -> None:
        self.configuration = configuration
        self.texts: list[str] | None = None

    def embed(self, texts: list[str], configuration: EmbeddingConfiguration) -> EmbeddingBatch:
        self.texts = texts
        assert configuration == self.configuration
        return EmbeddingBatch(
            vectors=(tuple(0.1 for _ in range(configuration.dimensions)),),
            provider=configuration.provider,
            model=configuration.model,
        )


def test_pdf_handler_produces_immutable_success_from_verified_streamed_source() -> None:
    extraction_configuration = PdfExtractionConfiguration.milestone_two()
    embedding_configuration = EmbeddingConfiguration.milestone_one_local()
    content = "A short PDF paragraph."
    page = NormalizedPdfPage(
        page_number=1,
        text=content,
        content_checksum=hashlib.sha256(content.encode()).hexdigest(),
    )
    chunk = PreparedPdfChunk(
        ordinal=0,
        page_number=1,
        page_start=1,
        page_end=1,
        start_offset=0,
        end_offset=len(content),
        content=content,
        content_checksum=page.content_checksum,
        token_count=5,
    )
    extraction = PdfExtractionResult(
        pages=(page,),
        chunks=(chunk,),
        parser_version=extraction_configuration.parser_version,
        extraction_options_version=extraction_configuration.extraction_options_version,
        normalizer_version=extraction_configuration.normalizer_version,
        tokenizer_name=extraction_configuration.tokenizer_name,
        tokenizer_version=extraction_configuration.tokenizer_version,
        chunking_policy_version=extraction_configuration.chunking_policy_version,
        derivation_identity=extraction_configuration.derivation_identity,
    )
    raw = b"pdf"
    metadata = ObjectMetadata(
        workspace_id="workspace-1",
        object_key="object-1",
        sha256=hashlib.sha256(raw).hexdigest(),
        byte_size=len(raw),
        media_type="application/pdf",
    )
    object_store = RecordingObjectStore(metadata)
    extractor = FixedExtractor(extraction)
    provider = RecordingEmbeddingProvider(embedding_configuration)
    handler = PdfDerivationHandler(
        object_store=object_store,
        extractor=extractor,
        embedding_provider=provider,
        profile=PdfDerivationProfile(
            parser_configuration_id="pdf-parser-pypdf-6-14-2-plain-layout-v1",
            normalizer_configuration_id=extraction_configuration.normalizer_version,
            chunking_configuration_id="chunking-m2-pdf-pypdf-6-14-2-v1",
            extraction_configuration=extraction_configuration,
            embedding_configuration=embedding_configuration,
        ),
    )

    outcome = handler.execute(
        IngestionWork(
            workspace_id="workspace-1",
            document_id="document-1",
            document_version_id="version-1",
            source_object_id="source-1",
            source_object_key="object-1",
            source_media_type="application/pdf",
            source_sha256=metadata.sha256,
            source_byte_size=metadata.byte_size,
            parser_configuration_id="pdf-parser-pypdf-6-14-2-plain-layout-v1",
            normalizer_configuration_id=extraction_configuration.normalizer_version,
            chunking_configuration_id="chunking-m2-pdf-pypdf-6-14-2-v1",
            embedding_configuration_id=embedding_configuration.id,
        ),
        Cancellation(),
    )

    assert isinstance(outcome, WorkSucceeded)
    assert outcome.payload.extraction == extraction
    assert outcome.payload.vectors == (tuple(0.1 for _ in range(1536)),)
    assert outcome.payload.embedding_provider == embedding_configuration.provider
    assert outcome.payload.embedding_model == embedding_configuration.model
    assert object_store.head_calls == [("workspace-1", "object-1")]
    assert object_store.open_calls == [("workspace-1", "object-1")]
    assert provider.texts == [content]


def test_pdf_handler_rejects_inconsistent_pinned_profile_before_object_access() -> None:
    extraction_configuration = PdfExtractionConfiguration.milestone_two()
    embedding_configuration = EmbeddingConfiguration.milestone_one_local()
    handler = PdfDerivationHandler(
        object_store=RecordingObjectStore(
            ObjectMetadata(
                workspace_id="workspace-1",
                object_key="object-1",
                sha256="0" * 64,
                byte_size=3,
                media_type="application/pdf",
            )
        ),
        extractor=FixedExtractor(
            PdfExtractionResult(
                pages=(),
                chunks=(),
                parser_version=extraction_configuration.parser_version,
                extraction_options_version=extraction_configuration.extraction_options_version,
                normalizer_version=extraction_configuration.normalizer_version,
                tokenizer_name=extraction_configuration.tokenizer_name,
                tokenizer_version=extraction_configuration.tokenizer_version,
                chunking_policy_version=extraction_configuration.chunking_policy_version,
                derivation_identity=extraction_configuration.derivation_identity,
            )
        ),
        embedding_provider=RecordingEmbeddingProvider(embedding_configuration),
        profile=PdfDerivationProfile(
            parser_configuration_id="pdf-parser-pypdf-6-14-2-plain-layout-v1",
            normalizer_configuration_id="pdf-normalizer-m2-v1",
            chunking_configuration_id="chunking-m2-pdf-pypdf-6-14-2-v1",
            extraction_configuration=replace(
                extraction_configuration,
                normalizer_version="pdf-normalizer-m2-v2",
            ),
            embedding_configuration=embedding_configuration,
        ),
    )

    outcome = handler.execute(
        IngestionWork(
            workspace_id="workspace-1",
            document_id="document-1",
            document_version_id="version-1",
            source_object_id="source-1",
            source_object_key="object-1",
            source_media_type="application/pdf",
            source_sha256="0" * 64,
            source_byte_size=3,
            parser_configuration_id="pdf-parser-pypdf-6-14-2-plain-layout-v1",
            normalizer_configuration_id="pdf-normalizer-m2-v1",
            chunking_configuration_id="chunking-m2-pdf-pypdf-6-14-2-v1",
            embedding_configuration_id=embedding_configuration.id,
        ),
        Cancellation(),
    )

    assert outcome == WorkFailed(
        HandlerFailureKindV1.CONFIGURATION_INVALID, "configuration_invalid"
    )


def test_pdf_handler_rejects_source_metadata_before_streaming_or_extraction() -> None:
    extraction_configuration = PdfExtractionConfiguration.milestone_two()
    embedding_configuration = EmbeddingConfiguration.milestone_one_local()
    object_store = RecordingObjectStore(
        ObjectMetadata(
            workspace_id="workspace-1",
            object_key="object-1",
            sha256="1" * 64,
            byte_size=3,
            media_type="application/pdf",
        )
    )
    extractor = FixedExtractor(
        PdfExtractionResult(
            pages=(),
            chunks=(),
            parser_version=extraction_configuration.parser_version,
            extraction_options_version=extraction_configuration.extraction_options_version,
            normalizer_version=extraction_configuration.normalizer_version,
            tokenizer_name=extraction_configuration.tokenizer_name,
            tokenizer_version=extraction_configuration.tokenizer_version,
            chunking_policy_version=extraction_configuration.chunking_policy_version,
            derivation_identity=extraction_configuration.derivation_identity,
        )
    )
    handler = PdfDerivationHandler(
        object_store=object_store,
        extractor=extractor,
        embedding_provider=RecordingEmbeddingProvider(embedding_configuration),
        profile=PdfDerivationProfile.milestone_two(
            embedding_configuration=embedding_configuration
        ),
    )

    outcome = handler.execute(
        IngestionWork(
            workspace_id="workspace-1",
            document_id="document-1",
            document_version_id="version-1",
            source_object_id="source-1",
            source_object_key="object-1",
            source_media_type="application/pdf",
            source_sha256="0" * 64,
            source_byte_size=3,
            parser_configuration_id="pdf-parser-pypdf-6-14-2-plain-layout-v1",
            normalizer_configuration_id=extraction_configuration.normalizer_version,
            chunking_configuration_id="chunking-m2-pdf-pypdf-6-14-2-v1",
            embedding_configuration_id=embedding_configuration.id,
        ),
        Cancellation(),
    )

    assert outcome == WorkFailed(HandlerFailureKindV1.INVALID_INPUT, "invalid_input")
    assert object_store.open_calls == []
    assert extractor.calls == []
