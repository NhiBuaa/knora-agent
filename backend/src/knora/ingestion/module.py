from knora.domain.access import WorkspacePrincipal
from knora.domain.errors import KnoraError
from knora.ingestion.interface import IngestDocumentCommand, IngestionResult
from knora.ingestion.processing import DocumentProcessor
from knora.ingestion.store import IngestionStore, PreparedDerivation
from knora.providers.embedding import EmbeddingProvider

MAX_RAW_BYTES = 1024 * 1024
MAX_NORMALIZED_TOKENS = 50_000
MAX_CHUNKS = 100


def _validate_source_key(source_key: str) -> None:
    import ntpath

    if not source_key or source_key != source_key.strip():
        raise KnoraError("INVALID_SOURCE_KEY")
    if source_key.startswith(("/", "\\")) or ntpath.splitdrive(source_key)[0]:
        raise KnoraError("INVALID_SOURCE_KEY")
    if any(part == ".." for part in source_key.replace("\\", "/").split("/")):
        raise KnoraError("INVALID_SOURCE_KEY")


class IngestDocument:
    def __init__(
        self,
        *,
        processor: DocumentProcessor,
        embedding_provider: EmbeddingProvider,
        store: IngestionStore,
    ) -> None:
        self._processor = processor
        self._embedding_provider = embedding_provider
        self._store = store

    def execute(
        self,
        command: IngestDocumentCommand,
        principal: WorkspacePrincipal,
    ) -> IngestionResult:
        if principal.workspace_id != command.workspace_id:
            raise KnoraError("WORKSPACE_ACCESS_DENIED")
        self._store.authorize_workspace(workspace_id=command.workspace_id)
        _validate_source_key(command.source_key)
        if len(command.raw_content) > MAX_RAW_BYTES:
            raise KnoraError("DOCUMENT_TOO_LARGE_FOR_SYNC_INGESTION")

        head = self._store.read_document_head(
            workspace_id=command.workspace_id,
            source_key=command.source_key,
        )
        try:
            processed = self._processor.process(
                raw_content=command.raw_content,
                media_type=command.media_type,
                configuration=command.chunking_configuration,
            )
        except UnicodeDecodeError as error:
            raise KnoraError("INVALID_DOCUMENT_ENCODING") from error
        if (
            processed.normalized_token_count > MAX_NORMALIZED_TOKENS
            or len(processed.chunks) > MAX_CHUNKS
        ):
            raise KnoraError("DOCUMENT_TOO_LARGE_FOR_SYNC_INGESTION")

        embed_documents = getattr(
            self._embedding_provider, "embed_documents", self._embedding_provider.embed
        )
        embedding_batch = embed_documents(
            [chunk.content for chunk in processed.chunks],
            command.embedding_configuration,
        )
        expected_dimensions = command.embedding_configuration.dimensions
        if len(embedding_batch.vectors) != len(processed.chunks) or any(
            len(vector) != expected_dimensions for vector in embedding_batch.vectors
        ):
            raise KnoraError("EMBEDDING_DIMENSION_MISMATCH")
        if (
            embedding_batch.provider != command.embedding_configuration.provider
            or embedding_batch.model != command.embedding_configuration.model
        ):
            raise KnoraError("EMBEDDING_CONFIGURATION_MISMATCH")

        return self._store.commit_derivation(
            prepared=PreparedDerivation(
                workspace_id=command.workspace_id,
                source_key=command.source_key,
                source_name=command.source_name,
                processed=processed,
                chunking_configuration=command.chunking_configuration,
                embedding_configuration=command.embedding_configuration,
                embedding_batch=embedding_batch,
            ),
            expected_revision=head.revision if head is not None else 0,
        )
