"""Offline provenance checks before a lexical generation can reach projection I/O."""

import json
from contextlib import nullcontext
from dataclasses import asdict, replace
from datetime import UTC, datetime
from hashlib import sha256
from types import SimpleNamespace

import pytest

from knora.adapters.postgres.search_index_store import PostgresSearchIndexStore
from knora.adapters.postgres.tables import (
    ChunkingConfigurationTable,
    ChunkSetTable,
    ChunkTable,
    DocumentTable,
    DocumentVersionTable,
    IngestionJobTable,
    LexicalGenerationTable,
    LexicalHeadTable,
    OriginalSourceObjectTable,
    WorkspaceTable,
)
from knora.ingestion.job_processing import (
    Cancellation,
    HandlerFailureKindV1,
    IngestionWork,
    WorkFailed,
    WorkSuperseded,
)
from knora.ingestion.search_indexing import (
    LexicalChunk,
    LexicalGeneration,
    LexicalGenerationError,
    LexicalIndexHandler,
    LexicalProfile,
    StaleGenerationError,
)


class _Session:
    def __init__(self, rows):
        self.rows = {(type(row), row.id): row for row in rows if hasattr(row, "id")}
        self.head = next(row for row in rows if isinstance(row, LexicalHeadTable))

    def get(self, model, identity):
        if model is LexicalHeadTable:
            return self.head if self.head.document_id == identity else None
        return self.rows.get((model, identity))

    def scalar(self, statement):
        model = statement.column_descriptions[0]["entity"]
        params = statement.compile().params
        row = self.get(model, params["id_1"])
        if row is not None and model is DocumentTable:
            return row if row.workspace_id == params["workspace_id_1"] else None
        return row

    def scalars(self, statement):
        assert statement.column_descriptions[0]["entity"] is ChunkTable
        chunk_set_id = statement.compile().params["chunk_set_id_1"]
        rows = sorted(
            (
                row
                for (model, _), row in self.rows.items()
                if model is ChunkTable and row.chunk_set_id == chunk_set_id
            ),
            key=lambda row: row.ordinal,
        )
        return SimpleNamespace(all=lambda: rows)


@pytest.fixture
def snapshot():
    text = "Retained source text."
    checksum = sha256(text.encode()).hexdigest()
    profile = LexicalProfile("profile", "word", "1", 1.2, 0.75, 4, "statistics")
    generation = LexicalGeneration(
        "generation",
        "workspace",
        "document",
        "version",
        "chunks",
        profile,
        2,
        (LexicalChunk("chunk", 0, checksum),),
    )
    rows = SimpleNamespace(
        workspace=WorkspaceTable(id="workspace", archived=False, revision=3),
        document=DocumentTable(
            id="document",
            workspace_id="workspace",
            archived=False,
            revision=4,
            current_document_version_id="version",
        ),
        version=DocumentVersionTable(
            id="version",
            document_id="document",
            raw_sha256="a" * 64,
            media_type="application/pdf",
        ),
        source=OriginalSourceObjectTable(
            id="source",
            workspace_id="workspace",
            document_version_id="version",
            object_key="retained-key",
            raw_sha256="a" * 64,
            byte_size=123,
            media_type="application/pdf",
            deleted_at=None,
        ),
        job=IngestionJobTable(
            id="job",
            workspace_id="workspace",
            document_id="document",
            target_document_version_id="version",
            source_object_id="source",
            derivation_kind="lexical_index",
            operation="lexical_index",
            parser_configuration_id="parser",
            normalizer_configuration_id="normalizer",
            chunking_configuration_id="chunking",
            embedding_configuration_id=None,
            lexical_profile=None,
            lexical_generation_id="generation",
            source_revision=4,
            workspace_revision=3,
            status="processing",
        ),
        chunking=ChunkingConfigurationTable(id="chunking"),
        chunk_set=ChunkSetTable(
            id="chunks",
            document_version_id="version",
            status="completed",
            parser_configuration_id="parser",
            normalizer_configuration_id="normalizer",
            chunking_configuration_id="chunking",
        ),
        chunk=ChunkTable(
            id="chunk",
            chunk_set_id="chunks",
            ordinal=0,
            content=text,
            content_checksum=checksum,
        ),
        generation=LexicalGenerationTable(
            id="generation",
            workspace_id="workspace",
            document_id="document",
            document_version_id="version",
            chunk_set_id="chunks",
            revision=2,
            source_revision=4,
            workspace_revision=3,
            profile_digest=profile.digest(),
            content_digest=generation.content_digest(),
            expected_count=1,
            manifest=json.loads(json.dumps(asdict(generation))),
            status="requested",
        ),
        head=LexicalHeadTable(
            document_id="document",
            revision=2,
            desired_generation_id="generation",
            active_generation_id=None,
        ),
    )
    work = IngestionWork(
        workspace_id="workspace",
        document_id="document",
        document_version_id="version",
        source_object_id="source",
        source_object_key="retained-key",
        source_media_type="application/pdf",
        source_sha256="a" * 64,
        source_byte_size=123,
        parser_configuration_id="parser",
        normalizer_configuration_id="normalizer",
        chunking_configuration_id="chunking",
        embedding_configuration_id=None,
        derivation_kind="lexical_index",
        lexical_generation_id="generation",
        source_revision=4,
        workspace_revision=3,
        ingestion_job_id="job",
    )
    session = _Session(vars(rows).values())
    store = PostgresSearchIndexStore(SimpleNamespace(begin=lambda: nullcontext(session)))
    return SimpleNamespace(rows=rows, session=session, work=work, store=store)


def test_loads_exact_retained_job_generation_and_authoritative_text(snapshot):
    loaded = snapshot.store.load_generation(snapshot.work)
    assert loaded.generation.generation_id == "generation"
    assert loaded.generation.chunk_set_id == "chunks"
    assert loaded.generation.lexical_profile.tokenizer == "word"
    assert loaded.chunk_texts == (("chunk", "Retained source text."),)


def test_transaction_loader_reuses_caller_session_without_opening_another(snapshot):
    expected = snapshot.store.load_generation(snapshot.work)

    def forbidden_begin():
        pytest.fail("transaction loader opened a nested session")

    store = PostgresSearchIndexStore(SimpleNamespace(begin=forbidden_begin))
    assert store.load_generation_in_transaction(snapshot.session, snapshot.work) == expected


@pytest.mark.parametrize(
    ("row", "field", "value"),
    [
        ("workspace", "archived", True),
        ("document", "archived", True),
        ("workspace", "revision", 5),
        ("document", "revision", 6),
        ("document", "current_document_version_id", "new-version"),
        ("head", "desired_generation_id", "new-generation"),
        ("generation", "status", "revoked"),
    ],
)
def test_changed_or_unavailable_snapshot_is_stale(snapshot, row, field, value):
    setattr(getattr(snapshot.rows, row), field, value)
    with pytest.raises(StaleGenerationError):
        snapshot.store.load_generation(snapshot.work)


@pytest.mark.parametrize(
    ("row", "field", "value"),
    [
        ("job", "workspace_id", "another-workspace"),
        ("job", "document_id", "another-document"),
        ("job", "target_document_version_id", "another-version"),
        ("job", "source_object_id", "another-source"),
        ("job", "derivation_kind", "dense"),
        ("job", "lexical_generation_id", "another-generation"),
        ("job", "parser_configuration_id", "another-parser"),
        ("job", "normalizer_configuration_id", "another-normalizer"),
        ("job", "chunking_configuration_id", "another-chunking"),
        ("job", "embedding_configuration_id", "dense-profile"),
        ("job", "lexical_profile", {}),
        ("job", "source_revision", 2),
        ("job", "workspace_revision", 2),
        ("head", "revision", 3),
        ("generation", "source_revision", 2),
        ("generation", "workspace_revision", 2),
        ("generation", "workspace_id", "another-workspace"),
        ("generation", "document_id", "another-document"),
        ("generation", "profile_digest", "corrupt"),
        ("generation", "content_digest", "corrupt"),
        ("generation", "expected_count", 2),
        ("generation", "manifest", None),
        ("generation", "manifest", {}),
        ("generation", "status", "unknown"),
        ("version", "document_id", "another-document"),
        ("version", "raw_sha256", "b" * 64),
        ("version", "media_type", "text/plain"),
        ("source", "workspace_id", "another-workspace"),
        ("source", "document_version_id", "another-version"),
        ("source", "object_key", "another-key"),
        ("source", "raw_sha256", "b" * 64),
        ("source", "byte_size", 124),
        ("source", "media_type", "text/plain"),
        ("source", "deleted_at", datetime(2026, 10, 16, tzinfo=UTC)),
        ("chunk_set", "status", "pending"),
        ("chunk_set", "document_version_id", "another-version"),
        ("chunk_set", "parser_configuration_id", "another-parser"),
        ("chunk_set", "normalizer_configuration_id", "another-normalizer"),
        ("chunk_set", "chunking_configuration_id", "another-chunking"),
        ("chunk", "content_checksum", "corrupt"),
        ("chunk", "ordinal", 1),
        ("chunk", "content", "Changed text."),
        ("chunk", "content", ""),
    ],
)
def test_corrupt_persisted_provenance_is_configuration_failure(snapshot, row, field, value):
    setattr(getattr(snapshot.rows, row), field, value)
    with pytest.raises(LexicalGenerationError) as error:
        snapshot.store.load_generation(snapshot.work)
    assert type(error.value) is LexicalGenerationError


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("ingestion_job_id", None),
        ("ingestion_job_id", "another-job"),
        ("lexical_profile_digest", "wrong-profile"),
        ("source_sha256", ""),
        ("source_byte_size", 0),
    ],
)
def test_rejects_unbound_claimed_work(snapshot, field, value):
    with pytest.raises(LexicalGenerationError) as error:
        snapshot.store.load_generation(replace(snapshot.work, **{field: value}))
    assert type(error.value) is LexicalGenerationError


def test_accepts_claimed_profile_digest_when_it_matches_generation(snapshot):
    work = replace(snapshot.work, lexical_profile_digest=snapshot.rows.generation.profile_digest)
    assert snapshot.store.load_generation(work).chunk_texts == (("chunk", "Retained source text."),)


@pytest.mark.parametrize(
    "model, identity",
    [
        (ChunkingConfigurationTable, "chunking"),
        (IngestionJobTable, "job"),
        (ChunkSetTable, "chunks"),
        (DocumentVersionTable, "version"),
        (OriginalSourceObjectTable, "source"),
        (LexicalGenerationTable, "generation"),
    ],
)
def test_missing_configuration_authority_is_terminal(snapshot, model, identity):
    del snapshot.session.rows[(model, identity)]
    with pytest.raises(LexicalGenerationError) as error:
        snapshot.store.load_generation(snapshot.work)
    assert type(error.value) is LexicalGenerationError


@pytest.mark.parametrize(
    "model, identity",
    [
        (WorkspaceTable, "workspace"),
        (DocumentTable, "document"),
    ],
)
def test_removed_workspace_or_document_is_stale(snapshot, model, identity):
    del snapshot.session.rows[(model, identity)]
    with pytest.raises(StaleGenerationError):
        snapshot.store.load_generation(snapshot.work)


def test_missing_head_with_unchanged_job_snapshot_is_terminal(snapshot):
    snapshot.session.head.document_id = "another-document"
    with pytest.raises(LexicalGenerationError) as error:
        snapshot.store.load_generation(snapshot.work)
    assert type(error.value) is LexicalGenerationError


@pytest.mark.parametrize("field", ["k1", "b", "avg_len"])
def test_profile_numeric_overflow_is_terminal_configuration_failure(snapshot, field):
    snapshot.rows.generation.manifest["lexical_profile"][field] = 10**1000
    with pytest.raises(LexicalGenerationError) as error:
        snapshot.store.load_generation(snapshot.work)
    assert type(error.value) is LexicalGenerationError


def test_loads_already_active_desired_generation_for_receipt_recovery(snapshot):
    snapshot.rows.generation.status = "active"
    snapshot.rows.head.active_generation_id = "generation"
    assert snapshot.store.load_generation(snapshot.work).chunk_texts == (
        ("chunk", "Retained source text."),
    )


@pytest.mark.parametrize(
    "corruption", ["invalid-profile", "invalid-chunk", "missing-chunk", "extra-chunk"]
)
def test_rejects_malformed_or_inexact_manifest(snapshot, corruption):
    manifest = snapshot.rows.generation.manifest
    if corruption == "invalid-profile":
        manifest["lexical_profile"]["k1"] = "invalid"
    elif corruption == "invalid-chunk":
        manifest["chunks"][0]["ordinal"] = True
    elif corruption == "missing-chunk":
        del snapshot.session.rows[(ChunkTable, "chunk")]
    else:
        snapshot.session.rows[(ChunkTable, "extra")] = ChunkTable(
            id="extra",
            chunk_set_id="chunks",
            ordinal=1,
            content="Extra.",
            content_checksum=sha256(b"Extra.").hexdigest(),
        )
    with pytest.raises(LexicalGenerationError) as error:
        snapshot.store.load_generation(snapshot.work)
    assert type(error.value) is LexicalGenerationError


@pytest.mark.parametrize("failure", ["stale", "ownership", "deleted-source", "incomplete-chunks"])
def test_handler_classifies_loader_failure_before_projection_io(snapshot, failure):
    if failure == "stale":
        snapshot.rows.head.desired_generation_id = "new-generation"
    elif failure == "deleted-source":
        snapshot.rows.source.deleted_at = datetime(2026, 10, 16, tzinfo=UTC)
    elif failure == "incomplete-chunks":
        snapshot.rows.chunk_set.status = "pending"
    else:
        snapshot.rows.source.workspace_id = "another-workspace"

    class NoProjectionIO:
        def stage_generation(self, *args):
            pytest.fail("invalid provenance reached projection I/O")

    outcome = LexicalIndexHandler(store=snapshot.store, index=NoProjectionIO()).execute(
        snapshot.work, Cancellation()
    )
    if failure == "stale":
        assert outcome == WorkSuperseded(terminal_outcome_code="stale_derivation_snapshot")
    else:
        assert outcome == WorkFailed(
            HandlerFailureKindV1.CONFIGURATION_INVALID, "configuration_invalid"
        )
