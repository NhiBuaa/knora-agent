from dataclasses import dataclass, field

import pytest

from knora.domain.access import WorkspacePrincipal
from knora.domain.errors import KnoraError
from knora.ingestion.interface import IngestDocumentCommand, IngestionResult
from knora.ingestion.module import IngestDocument
from knora.ingestion.processing import ChunkingConfiguration, DocumentProcessor
from knora.ingestion.store import DocumentHead, PreparedDerivation
from knora.providers.deterministic.embedding import DeterministicEmbeddingProvider
from knora.providers.embedding import EmbeddingBatch, EmbeddingConfiguration


@dataclass
class RecordingIngestionStore:
    result: IngestionResult
    head: DocumentHead | None = None
    commits: list[tuple[PreparedDerivation, int]] = field(default_factory=list)

    def authorize_workspace(self, *, workspace_id: str) -> None:
        return None

    def read_document_head(self, *, workspace_id: str, source_key: str) -> DocumentHead | None:
        return self.head

    def commit_derivation(
        self, *, prepared: PreparedDerivation, expected_revision: int
    ) -> IngestionResult:
        self.commits.append((prepared, expected_revision))
        return self.result


@dataclass
class RejectingAuthorizationStore(RecordingIngestionStore):
    def authorize_workspace(self, *, workspace_id: str) -> None:
        raise KnoraError("WORKSPACE_ACCESS_DENIED")

    def read_document_head(self, *, workspace_id: str, source_key: str) -> DocumentHead | None:
        raise AssertionError("resource lookup must not occur before authorization")


@dataclass
class RecordingEmbeddingProvider:
    dimensions: int = 1536
    calls: int = 0

    def embed(
        self, texts: list[str], configuration: EmbeddingConfiguration
    ) -> EmbeddingBatch:
        self.calls += 1
        vector = tuple(0.0 for _ in range(self.dimensions))
        return EmbeddingBatch(
            vectors=tuple(vector for _ in texts),
            provider="recording",
            model="recording-v1",
        )


@dataclass
class MismatchedEmbeddingProvider(RecordingEmbeddingProvider):
    def embed(
        self, texts: list[str], configuration: EmbeddingConfiguration
    ) -> EmbeddingBatch:
        batch = super().embed(texts, configuration)
        return EmbeddingBatch(
            vectors=batch.vectors, provider="wrong-provider", model="wrong-model"
        )


def command_for(raw_content: bytes, configuration: ChunkingConfiguration | None = None):
    return IngestDocumentCommand(
        workspace_id="demo",
        source_key="support/refund-policy",
        source_name="refund-policy.md",
        media_type="text/markdown",
        raw_content=raw_content,
        chunking_configuration=configuration or ChunkingConfiguration.milestone_one(),
        embedding_configuration=EmbeddingConfiguration.milestone_one_local(),
    )


def expected_result() -> IngestionResult:
    return IngestionResult(
        outcome="created",
        activation_changed=True,
        document_id="document-1",
        document_version_id="version-1",
        chunk_set_id="chunk-set-1",
        embedding_set_id="embedding-set-1",
        chunking_configuration_id="chunking-m1-v1",
        embedding_configuration_id="embedding-local-m1-v2",
        chunk_count=1,
    )


def test_ingest_document_prepares_and_commits_a_new_derivation() -> None:
    expected = expected_result()
    store = RecordingIngestionStore(result=expected)
    use_case = IngestDocument(
        processor=DocumentProcessor(),
        embedding_provider=DeterministicEmbeddingProvider(),
        store=store,
    )

    result = use_case.execute(
        IngestDocumentCommand(
            workspace_id="demo",
            source_key="support/refund-policy",
            source_name="refund-policy.md",
            media_type="text/markdown",
            raw_content=b"# Refund\n\nRefunds are available for 30 days.\n",
            chunking_configuration=ChunkingConfiguration.milestone_one(),
            embedding_configuration=EmbeddingConfiguration.milestone_one_local(),
        ),
        WorkspacePrincipal(workspace_id="demo", key_id="cli"),
    )

    assert result == expected
    assert len(store.commits) == 1
    prepared, expected_revision = store.commits[0]
    assert expected_revision == 0
    assert prepared.source_key == "support/refund-policy"
    assert prepared.processed.chunks[0].heading_path == ("Refund",)
    assert len(prepared.embedding_batch.vectors[0]) == 1536


def test_ingest_document_authorizes_workspace_before_lookup_or_provider() -> None:
    provider = RecordingEmbeddingProvider()
    use_case = IngestDocument(
        processor=DocumentProcessor(),
        embedding_provider=provider,
        store=RejectingAuthorizationStore(result=expected_result()),
    )

    with pytest.raises(KnoraError, match="WORKSPACE_ACCESS_DENIED"):
        use_case.execute(
            command_for(b"# Refund\n\nRefunds are available for 30 days.\n"),
            WorkspacePrincipal(workspace_id="demo", key_id="cli"),
        )

    assert provider.calls == 0


def test_ingest_document_rejects_principal_command_workspace_mismatch() -> None:
    provider = RecordingEmbeddingProvider()
    store = RecordingIngestionStore(result=expected_result())
    use_case = IngestDocument(
        processor=DocumentProcessor(), embedding_provider=provider, store=store
    )

    with pytest.raises(KnoraError, match="WORKSPACE_ACCESS_DENIED"):
        use_case.execute(
            command_for(b"# Refund\n\nRefunds are available for 30 days.\n"),
            WorkspacePrincipal(workspace_id="other-workspace", key_id="cli"),
        )

    assert provider.calls == 0
    assert store.commits == []


@pytest.mark.parametrize(
    ("raw_content", "configuration"),
    [
        (b"x" * (1024 * 1024 + 1), ChunkingConfiguration.milestone_one()),
        (("word " * 50_001).encode(), ChunkingConfiguration.milestone_one()),
        (
            ("\n\n".join(f"paragraph {index}" for index in range(101))).encode(),
            ChunkingConfiguration(
                id="chunking-boundary-test",
                parser_version="markdown-text-v1",
                chunker_version="heading-paragraph-v1",
                tokenizer_name="cl100k_base",
                tokenizer_version="tiktoken-0.12.0",
                target_tokens=500,
                overlap_tokens=75,
                max_tokens=650,
            ),
        ),
    ],
    ids=["raw-byte-limit", "normalized-token-limit", "chunk-count-limit"],
)
def test_ingest_document_rejects_sync_limits_before_embedding(
    raw_content: bytes, configuration: ChunkingConfiguration
) -> None:
    provider = RecordingEmbeddingProvider()
    store = RecordingIngestionStore(result=expected_result())
    use_case = IngestDocument(
        processor=DocumentProcessor(), embedding_provider=provider, store=store
    )

    with pytest.raises(KnoraError, match="DOCUMENT_TOO_LARGE_FOR_SYNC_INGESTION"):
        use_case.execute(
            command_for(raw_content, configuration),
            WorkspacePrincipal(workspace_id="demo", key_id="cli"),
        )

    assert provider.calls == 0
    assert store.commits == []


def test_ingest_document_rejects_embedding_dimension_mismatch_before_commit() -> None:
    provider = RecordingEmbeddingProvider(dimensions=1535)
    store = RecordingIngestionStore(result=expected_result())
    use_case = IngestDocument(
        processor=DocumentProcessor(), embedding_provider=provider, store=store
    )

    with pytest.raises(KnoraError, match="EMBEDDING_DIMENSION_MISMATCH"):
        use_case.execute(
            command_for(b"# Refund\n\nRefunds are available for 30 days.\n"),
            WorkspacePrincipal(workspace_id="demo", key_id="cli"),
        )

    assert provider.calls == 1
    assert store.commits == []


def test_ingest_document_rejects_embedding_configuration_mismatch_before_commit() -> None:
    provider = MismatchedEmbeddingProvider()
    store = RecordingIngestionStore(result=expected_result())
    use_case = IngestDocument(
        processor=DocumentProcessor(), embedding_provider=provider, store=store
    )

    with pytest.raises(KnoraError, match="EMBEDDING_CONFIGURATION_MISMATCH"):
        use_case.execute(
            command_for(b"# Refund\n\nRefunds are available for 30 days.\n"),
            WorkspacePrincipal(workspace_id="demo", key_id="cli"),
        )

    assert store.commits == []


@pytest.mark.parametrize(
    "source_key", ["", "  support/refund  ", "/etc/passwd", r"C:\\secret.txt", "a/../b"]
)
def test_ingest_document_rejects_non_logical_source_keys(source_key: str) -> None:
    provider = RecordingEmbeddingProvider()
    store = RecordingIngestionStore(result=expected_result())
    use_case = IngestDocument(
        processor=DocumentProcessor(), embedding_provider=provider, store=store
    )

    with pytest.raises(KnoraError, match="INVALID_SOURCE_KEY"):
        use_case.execute(
            command_for(b"# Refund\n\nRefunds are available for 30 days.\n")
            .__class__(
                workspace_id="demo",
                source_key=source_key,
                source_name="refund-policy.md",
                media_type="text/markdown",
                raw_content=b"# Refund\n\nRefunds are available for 30 days.\n",
                chunking_configuration=ChunkingConfiguration.milestone_one(),
                embedding_configuration=EmbeddingConfiguration.milestone_one_local(),
            ),
            WorkspacePrincipal(workspace_id="demo", key_id="cli"),
        )

    assert provider.calls == 0
