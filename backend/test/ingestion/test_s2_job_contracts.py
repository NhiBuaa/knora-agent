from dataclasses import replace
from hashlib import sha256
from io import BytesIO
from unittest.mock import Mock

import pytest
from backend.test.fixtures.issue_18_acceptance import pdf_extraction, pdf_metadata, work_for

from knora.ingestion.job_processing import (
    Cancellation,
    HandlerFailureKindV1,
    IngestionWork,
    PdfDerivationHandler,
    WorkFailed,
    WorkSucceeded,
)
from knora.ingestion.lexical_population import VerifiedLexicalPopulation
from knora.ingestion.pdf import PdfExtractionConfiguration
from knora.ingestion.search_indexing import LexicalProfile


def lexical_profile() -> LexicalProfile:
    return LexicalProfile("lexical-1", "word", "native-v1", 1.2, 0.75, 10.0, "stats-1")


@pytest.mark.parametrize("kind", ["dense", "pdf_extraction", "lexical_index"])
def test_worker_dispatches_only_the_claimed_derivation_kind(kind):
    from knora.ingestion.search_indexing import DerivationJobHandler

    class Handler:
        def __init__(self, outcome):
            self.outcome = outcome
            self.calls = []

        def execute(self, work, cancellation):
            self.calls.append((work, cancellation))
            return self.outcome

    pdf = Handler(WorkFailed(HandlerFailureKindV1.INVALID_INPUT, "invalid_input"))
    index = Handler(WorkFailed(HandlerFailureKindV1.STORAGE_TRANSIENT, "storage_transient"))
    handler = DerivationJobHandler(pdf_handler=pdf, index_handler=index)
    work = (
        work_for(pdf_metadata())
        if kind == "dense"
        else replace(
            extraction_work(),
            derivation_kind=kind,
            lexical_generation_id="generation-1" if kind == "lexical_index" else None,
        )
    )
    cancellation = Cancellation()
    cancellation.cancel()
    chosen, other = (index, pdf) if kind == "lexical_index" else (pdf, index)

    assert handler.execute(work, cancellation) is chosen.outcome
    assert chosen.calls == [(work, cancellation)]
    assert other.calls == []


def extraction_work() -> IngestionWork:
    return IngestionWork(
        workspace_id="workspace-1",
        document_id="document-1",
        document_version_id="version-1",
        source_object_id="source-1",
        source_object_key="object-1",
        source_media_type="application/pdf",
        parser_configuration_id="parser-1",
        normalizer_configuration_id="pdf-normalizer-m2-v1",
        chunking_configuration_id="chunks-1",
        embedding_configuration_id=None,
        source_sha256=sha256(b"pdf").hexdigest(),
        source_byte_size=3,
        derivation_kind="pdf_extraction",
        lexical_profile_digest=lexical_profile().digest(),
        source_revision=0,
        workspace_revision=2,
    )


def test_extraction_corrupt_persisted_profile_is_terminal_configuration() -> None:
    from knora.ingestion.job_processing import CoordinationInvariantError

    def corrupt_profile(work):
        raise CoordinationInvariantError("persisted profile digest differs")

    handler = PdfDerivationHandler(
        object_store=object(),
        extractor=object(),
        profile_resolver=corrupt_profile,
    )
    assert handler.execute(extraction_work(), Cancellation()) == WorkFailed(
        HandlerFailureKindV1.CONFIGURATION_INVALID,
        "configuration_invalid",
    )


def test_extraction_submission_has_distinct_profile_bound_fingerprint() -> None:
    from knora.ingestion.jobs import (
        IngestionJobs,
        PdfExtractionSubmissionConfiguration,
        PdfSubmissionCommand,
        PdfSubmissionConfiguration,
    )
    from knora.ingestion.processing import ChunkingConfiguration
    from knora.providers.embedding import EmbeddingConfiguration

    chunking = ChunkingConfiguration("chunks-1", "parser-v1", "chunker-v1", "tokens", "v1", 5, 1, 6)
    config = PdfExtractionSubmissionConfiguration(
        "parser-1", "normalizer-1", chunking, lexical_profile()
    )
    command = PdfSubmissionCommand(
        "workspace-1", "source", "source.pdf", "application/pdf", BytesIO(b"pdf"), "request", config
    )

    assert IngestionJobs._content_fingerprint(command, "raw-sha") == (
        "pdf-extraction-v1\npdf_extraction\nworkspace-1\nsource\nraw-sha\nparser-1\nnormalizer-1\nchunks-1\n"
        + lexical_profile().digest()
    )
    changed = replace(
        command,
        configuration=replace(config, lexical_profile=replace(lexical_profile(), avg_len=11.0)),
    )
    assert IngestionJobs._content_fingerprint(
        changed, "raw-sha"
    ) != IngestionJobs._content_fingerprint(command, "raw-sha")
    dense = replace(
        command,
        configuration=PdfSubmissionConfiguration(
            "parser-1", "normalizer-1", chunking, EmbeddingConfiguration.milestone_one_local()
        ),
    )
    assert (
        IngestionJobs._content_fingerprint(dense, "raw-sha").encode()
        == b"workspace-1\nsource\nraw-sha\nparser-1\nnormalizer-1\nchunks-1\nembedding-local-m1-v2"
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"derivation_kind": "dense"},
        {"embedding_configuration_id": "embedding-1"},
        {"derivation_kind": "unknown"},
        {"lexical_generation_id": "generation-1"},
        {"lexical_profile_digest": None},
        {"derivation_kind": "lexical_index", "lexical_generation_id": None},
        {"source_revision": None},
        {"workspace_revision": None},
        {"source_revision": -1},
        {"workspace_revision": True},
        {"lexical_profile_digest": 123},
    ],
)
def test_work_rejects_invalid_explicit_kind_bindings(changes: dict) -> None:
    with pytest.raises(ValueError):
        replace(extraction_work(), **changes)


def test_extraction_handler_validates_source_and_profile_without_embedding_provider() -> None:
    from knora.ingestion.job_processing import PdfExtractionProfile, PdfExtractionSuccess
    from knora.ingestion.object_store import ObjectMetadata

    work = extraction_work()
    extraction = pdf_extraction()

    class Source:
        opens = 0
        metadata = ObjectMetadata(
            "workspace-1", "object-1", work.source_sha256, 3, "application/pdf"
        )

        def head(self, **kwargs):
            return self.metadata

        def open_read(self, **kwargs):
            self.opens += 1
            return BytesIO(b"pdf")

    class Extractor:
        calls = 0

        def extract(self, stream, configuration):
            self.calls += 1
            assert stream.read() == b"pdf"
            return extraction

    profile = PdfExtractionProfile(
        "parser-1",
        "pdf-normalizer-m2-v1",
        "chunks-1",
        PdfExtractionConfiguration.milestone_two(),
        lexical_profile(),
    )
    source, extractor = Source(), Extractor()
    handler = PdfDerivationHandler(
        object_store=source,
        extractor=extractor,
        profile=profile,
        lexical_population=Mock(spec=VerifiedLexicalPopulation),
    )

    outcome = handler.execute(work, Cancellation())
    assert outcome == WorkSucceeded(PdfExtractionSuccess(extraction, lexical_profile()))
    assert source.opens == extractor.calls == 1
    assert not hasattr(outcome.payload, "vectors")

    source.metadata = replace(source.metadata, workspace_id="foreign")
    assert handler.execute(work, Cancellation()) == WorkFailed(
        HandlerFailureKindV1.INVALID_INPUT, "invalid_input"
    )
    assert source.opens == extractor.calls == 1

    stale = replace(profile, lexical_profile=replace(lexical_profile(), avg_len=11.0))
    invalid_handler = PdfDerivationHandler(object_store=source, extractor=extractor, profile=stale)
    assert invalid_handler.execute(work, Cancellation()) == WorkFailed(
        HandlerFailureKindV1.CONFIGURATION_INVALID, "configuration_invalid"
    )


def test_deployed_reprocess_does_not_convert_extraction_to_dense() -> None:
    from knora.domain.access import WorkspacePrincipal
    from knora.domain.errors import KnoraError
    from knora.ingestion.jobs import (
        IngestionJobs,
        PdfExtractionSubmissionConfiguration,
        ReprocessContext,
        ReprocessDocumentVersionCommand,
    )
    from knora.ingestion.object_store import ObjectMetadata
    from knora.ingestion.processing import ChunkingConfiguration
    from knora.providers.embedding import EmbeddingConfiguration

    class Store:
        def authorize_workspace(self, **kwargs):
            pass

        def read_reprocess_context(self, **kwargs):
            return ReprocessContext(
                "workspace-1",
                "document-1",
                "version-1",
                ObjectMetadata("workspace-1", "object-1", "a" * 64, 3, "application/pdf"),
                PdfExtractionSubmissionConfiguration(
                    "parser-1",
                    "normalizer-1",
                    ChunkingConfiguration(
                        "chunks-1", "parser-v1", "chunker-v1", "tokens", "v1", 5, 1, 6
                    ),
                    lexical_profile(),
                ),
                None,
                "job-1",
            )

    service = IngestionJobs(
        object_store=object(),
        store=Store(),
        deployed_embedding_configuration=EmbeddingConfiguration.milestone_one_local(),
    )
    with pytest.raises(KnoraError, match="CONFIGURATION_NOT_AVAILABLE"):
        service.reprocess_document_version(
            ReprocessDocumentVersionCommand(
                "workspace-1", "version-1", "deployed", None, "request"
            ),
            WorkspacePrincipal("workspace-1", "key-1"),
        )


def index_input():
    from knora.ingestion.search_indexing import LexicalChunk, LexicalGeneration, LexicalIndexInput

    generation = LexicalGeneration(
        "generation-1",
        "workspace-1",
        "document-1",
        "version-1",
        "chunk-set-1",
        lexical_profile(),
        1,
        (LexicalChunk("chunk-1", 0, sha256(b"text").hexdigest()),),
    )
    return LexicalIndexInput(generation, (("chunk-1", "text"),))


class IndexStore:
    def __init__(self, loaded):
        self.loaded = loaded

    def load_generation(self, work):
        return self.loaded


class Projection:
    def __init__(self, receipt=None, error=None):
        self.receipt = receipt
        self.error = error
        self.calls = []

    def stage_generation(self, generation, chunk_texts):
        self.calls.append((generation, chunk_texts))
        if self.error:
            raise self.error
        return self.receipt


def test_index_handler_replays_same_generation_and_returns_verified_receipt_only() -> None:
    from knora.ingestion.search_indexing import (
        LexicalIndexHandler,
        LexicalIndexSuccess,
        StageReceipt,
    )

    loaded = index_input()
    receipt = StageReceipt("generation-1", 1, loaded.generation.content_digest())
    projection = Projection(receipt)
    handler = LexicalIndexHandler(
        lexical_population=Mock(spec=VerifiedLexicalPopulation),
        store=IndexStore(loaded),
        index=projection,
    )
    work = replace(
        extraction_work(), derivation_kind="lexical_index", lexical_generation_id="generation-1"
    )

    assert handler.execute(work, Cancellation()) == WorkSucceeded(
        LexicalIndexSuccess(loaded.generation, receipt)
    )
    assert handler.execute(work, Cancellation()) == WorkSucceeded(
        LexicalIndexSuccess(loaded.generation, receipt)
    )
    assert projection.calls == [(loaded.generation, {"chunk-1": "text"})] * 2


@pytest.mark.parametrize(
    "changes",
    [
        {"workspace_id": "foreign"},
        {"document_id": "foreign"},
        {"document_version_id": "foreign"},
        {"lexical_generation_id": "other"},
        {"lexical_profile_digest": "other"},
    ],
)
def test_index_handler_rejects_foreign_generation_before_projection(changes: dict) -> None:
    from knora.ingestion.search_indexing import LexicalIndexHandler

    projection = Projection()
    handler = LexicalIndexHandler(
        lexical_population=Mock(spec=VerifiedLexicalPopulation),
        store=IndexStore(index_input()),
        index=projection,
    )
    work = replace(
        extraction_work(), derivation_kind="lexical_index", lexical_generation_id="generation-1"
    )
    work = replace(work, **changes)
    assert handler.execute(work, Cancellation()) == WorkFailed(
        HandlerFailureKindV1.CONFIGURATION_INVALID, "configuration_invalid"
    )
    assert projection.calls == []


@pytest.mark.parametrize(
    "texts",
    [
        (),
        (("chunk-1", "changed"),),
        (("foreign", "text"),),
        (("chunk-1", "text"), ("chunk-1", "text")),
    ],
)
def test_index_handler_rejects_incomplete_or_corrupt_authoritative_text(texts) -> None:
    from knora.ingestion.search_indexing import LexicalIndexHandler

    projection = Projection()
    handler = LexicalIndexHandler(
        lexical_population=Mock(spec=VerifiedLexicalPopulation),
        store=IndexStore(replace(index_input(), chunk_texts=texts)),
        index=projection,
    )
    work = replace(
        extraction_work(), derivation_kind="lexical_index", lexical_generation_id="generation-1"
    )
    assert handler.execute(work, Cancellation()) == WorkFailed(
        HandlerFailureKindV1.CONFIGURATION_INVALID, "configuration_invalid"
    )
    assert projection.calls == []


def test_index_handler_classifies_only_typed_transport_failure_as_storage_retry() -> None:
    from knora.ingestion.job_processing import (
        CauseMappingV1,
        FailureCauseV1,
        RetryExhausted,
        RetryPolicyV1,
        ScheduleRetry,
    )
    from knora.ingestion.search_indexing import LexicalIndexHandler, LexicalProjectionUnavailable

    projection = Projection(error=LexicalProjectionUnavailable("sanitized transport failure"))
    handler = LexicalIndexHandler(
        lexical_population=Mock(spec=VerifiedLexicalPopulation),
        store=IndexStore(index_input()),
        index=projection,
    )
    work = replace(
        extraction_work(), derivation_kind="lexical_index", lexical_generation_id="generation-1"
    )
    outcome = handler.execute(work, Cancellation())
    assert outcome == WorkFailed(HandlerFailureKindV1.STORAGE_TRANSIENT, "storage_transient")
    assert CauseMappingV1.map(outcome).cause == FailureCauseV1.STORAGE_TRANSIENT

    class ZeroRandom:
        def next_int_inclusive(self, upper_bound_microseconds):
            return 0

    retry = RetryPolicyV1(ZeroRandom())
    assert isinstance(retry.decide(CauseMappingV1.map(outcome).cause, 1, 4), ScheduleRetry)
    assert isinstance(retry.decide(CauseMappingV1.map(outcome).cause, 4, 4), RetryExhausted)
    projection.error = OSError("invalid local configuration")
    with pytest.raises(OSError):
        handler.execute(work, Cancellation())


@pytest.mark.parametrize("mutation", ["missing", "count", "digest", "generation"])
def test_index_handler_never_succeeds_on_malformed_receipt(mutation: str) -> None:
    from knora.ingestion.search_indexing import LexicalIndexHandler, StageReceipt

    loaded = index_input()
    receipt = StageReceipt("generation-1", 1, loaded.generation.content_digest())
    if mutation == "missing":
        receipt = None
    elif mutation == "count":
        receipt = replace(receipt, point_count=0)
    elif mutation == "digest":
        receipt = replace(receipt, content_digest="other")
    else:
        receipt = replace(receipt, generation_id="other")
    handler = LexicalIndexHandler(
        lexical_population=Mock(spec=VerifiedLexicalPopulation),
        store=IndexStore(loaded),
        index=Projection(receipt),
    )
    work = replace(
        extraction_work(), derivation_kind="lexical_index", lexical_generation_id="generation-1"
    )
    assert handler.execute(work, Cancellation()) == WorkFailed(
        HandlerFailureKindV1.CONFIGURATION_INVALID, "configuration_invalid"
    )


def test_index_handler_reports_stale_snapshot_as_superseded_before_projection() -> None:
    from knora.ingestion.job_processing import WorkSuperseded
    from knora.ingestion.search_indexing import LexicalIndexHandler, StaleGenerationError

    class StaleStore:
        def load_generation(self, work):
            raise StaleGenerationError("source revision changed")

    projection = Projection()
    handler = LexicalIndexHandler(
        lexical_population=Mock(spec=VerifiedLexicalPopulation),
        store=StaleStore(),
        index=projection,
    )
    work = replace(
        extraction_work(), derivation_kind="lexical_index", lexical_generation_id="generation-1"
    )
    assert handler.execute(work, Cancellation()) == WorkSuperseded(
        terminal_outcome_code="stale_derivation_snapshot"
    )
    assert projection.calls == []


def test_extraction_submission_uses_existing_authorization_and_source_commit_path() -> None:
    from knora.domain.access import WorkspacePrincipal
    from knora.ingestion.jobs import (
        IngestionJobs,
        PdfExtractionSubmissionConfiguration,
        PdfSubmissionCommand,
        PdfSubmissionResult,
    )
    from knora.ingestion.object_store import ObjectMetadata
    from knora.ingestion.processing import ChunkingConfiguration

    config = PdfExtractionSubmissionConfiguration(
        "parser-1",
        "normalizer-1",
        ChunkingConfiguration("chunks-1", "parser-v1", "chunker-v1", "tokens", "v1", 5, 1, 6),
        lexical_profile(),
    )
    content = b"%PDF-fixture"
    calls = []

    class Source:
        def put_stream(self, *, workspace_id, stream, media_type):
            calls.append("put")
            assert stream.read() == content
            return ObjectMetadata(
                workspace_id, "object-1", sha256(content).hexdigest(), len(content), media_type
            )

    class Store:
        prepared = None

        def authorize_workspace(self, *, workspace_id):
            assert workspace_id == "workspace-1"
            calls.append("authorize")

        def commit_pdf_submission(self, prepared):
            calls.append("commit")
            self.prepared = prepared
            return PdfSubmissionResult(
                "job-1", "created", "queued", "document-1", "version-1", "object-1"
            )

    store = Store()
    result = IngestionJobs(object_store=Source(), store=store).submit_pdf(
        PdfSubmissionCommand(
            "workspace-1",
            "source",
            "source.pdf",
            "application/pdf",
            BytesIO(content),
            "request",
            config,
        ),
        WorkspacePrincipal("workspace-1", "key-1"),
    )
    assert result.status == "queued"
    assert calls == ["authorize", "put", "commit"]
    assert store.prepared.configuration == config
    assert store.prepared.source_object.sha256 == sha256(content).hexdigest()


def test_dense_work_defaults_and_missing_provider_stay_fail_closed() -> None:
    from knora.ingestion.job_processing import PdfDerivationProfile
    from knora.providers.embedding import EmbeddingConfiguration

    config = EmbeddingConfiguration.milestone_one_local()
    dense = work_for(pdf_metadata())
    assert dense.derivation_kind == "dense"
    with pytest.raises(ValueError):
        replace(dense, embedding_configuration_id=None)
    handler = PdfDerivationHandler(
        object_store=object(),
        extractor=object(),
        profile=PdfDerivationProfile.milestone_two(embedding_configuration=config),
    )
    assert handler.execute(dense, Cancellation()) == WorkFailed(
        HandlerFailureKindV1.CONFIGURATION_INVALID, "configuration_invalid"
    )


def test_index_handler_rejects_wrong_kind_before_loading_generation() -> None:
    from knora.ingestion.search_indexing import LexicalIndexHandler

    handler = LexicalIndexHandler(
        lexical_population=Mock(spec=VerifiedLexicalPopulation), store=object(), index=object()
    )
    assert handler.execute(extraction_work(), Cancellation()) == WorkFailed(
        HandlerFailureKindV1.CONFIGURATION_INVALID, "configuration_invalid"
    )


def test_submission_store_reconstructs_lexical_profile_without_embedding() -> None:
    from types import SimpleNamespace

    from knora.adapters.postgres.ingestion_jobs.submission import PostgresPdfSubmissionStore
    from knora.adapters.postgres.tables import ChunkingConfigurationTable

    profile = lexical_profile()
    chunking = SimpleNamespace(
        id="chunks-1",
        parser_version="parser-v1",
        chunker_version="chunker-v1",
        tokenizer_name="tokens",
        tokenizer_version="v1",
        target_tokens=5,
        overlap_tokens=1,
        max_tokens=6,
    )
    job = SimpleNamespace(
        derivation_kind="pdf_extraction",
        parser_configuration_id="parser-1",
        normalizer_configuration_id="normalizer-1",
        chunking_configuration_id="chunks-1",
        embedding_configuration_id=None,
        lexical_profile=profile.__dict__
        if hasattr(profile, "__dict__")
        else {
            "id": profile.id,
            "tokenizer": profile.tokenizer,
            "tokenizer_version": profile.tokenizer_version,
            "k1": profile.k1,
            "b": profile.b,
            "avg_len": profile.avg_len,
            "statistics_digest": profile.statistics_digest,
            "digest": profile.digest(),
        },
    )

    class Session:
        def get(self, table, identity):
            assert table is ChunkingConfigurationTable
            assert identity == "chunks-1"
            return chunking

    result = PostgresPdfSubmissionStore._configuration_from_job(Session(), job)
    assert result.lexical_profile == profile
    assert result.chunking_configuration.id == "chunks-1"
