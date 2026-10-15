"""Workspace-scoped PDF drafts and local source preparation for the workbench."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from io import BytesIO
from typing import BinaryIO, Literal, Protocol

from knora.domain.access import WorkspacePrincipal
from knora.domain.errors import KnoraError
from knora.evaluation.access import authorize_evaluation
from knora.ingestion.object_store import ObjectMetadata, ObjectStore
from knora.ingestion.pdf import (
    NormalizedPdfPage,
    PdfExtractionConfiguration,
    PdfExtractionError,
    PdfExtractionResult,
    PdfTextExtractor,
)


@dataclass(frozen=True, slots=True)
class Dataset:
    id: str
    workspace_id: str
    name: str
    status: Literal["DRAFT"]


@dataclass(frozen=True, slots=True)
class DatasetSource:
    id: str
    dataset_id: str
    document_id: str
    document_version_id: str
    filename: str
    raw_sha256: str
    byte_size: int
    object_key: str
    idempotency_key: str
    status: Literal["PROCESSING", "READY", "FAILED"]
    failure_code: str | None
    snapshot_id: str | None


@dataclass(frozen=True, slots=True)
class ExtractionSnapshot:
    id: str
    source_id: str
    configuration_sha256: str
    extraction_sha256: str
    pages: tuple[NormalizedPdfPage, ...]


def extraction_checksum(pages: tuple[NormalizedPdfPage, ...]) -> str:
    payload = [{"page_number": page.page_number, "text": page.text} for page in pages]
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


class DatasetStore(Protocol):
    def create_dataset(self, workspace_id: str, name: str) -> Dataset: ...

    def list_datasets(self, workspace_id: str) -> tuple[Dataset, ...]: ...

    def get_dataset(self, workspace_id: str, dataset_id: str) -> Dataset | None: ...

    def find_upload(
        self, workspace_id: str, dataset_id: str, idempotency_key: str
    ) -> DatasetSource | None: ...

    def add_source(
        self,
        workspace_id: str,
        dataset_id: str,
        name: str,
        metadata: ObjectMetadata,
        idempotency_key: str,
    ) -> tuple[DatasetSource, bool]: ...

    def get_source(
        self, workspace_id: str, dataset_id: str, source_id: str
    ) -> DatasetSource | None: ...

    def list_sources(self, workspace_id: str, dataset_id: str) -> tuple[DatasetSource, ...]: ...

    def record_extraction(
        self, source: DatasetSource, result: PdfExtractionResult | None, failure: str | None
    ) -> DatasetSource: ...

    def get_snapshot(
        self, workspace_id: str, dataset_id: str, source_id: str
    ) -> ExtractionSnapshot | None: ...


class DatasetService:
    def __init__(
        self,
        store: DatasetStore,
        object_store: ObjectStore,
        extractor: PdfTextExtractor,
        configuration: PdfExtractionConfiguration,
    ) -> None:
        self._store = store
        self._object_store = object_store
        self._extractor = extractor
        self._configuration = configuration

    def create_dataset(
        self, workspace_id: str, name: str, principal: WorkspacePrincipal
    ) -> Dataset:
        authorize_evaluation(workspace_id=workspace_id, principal=principal, action="write")
        if not name.strip() or len(name) > 200:
            raise KnoraError("INVALID_DATASET_NAME")
        return self._store.create_dataset(workspace_id, name.strip())

    def list_datasets(
        self, workspace_id: str, principal: WorkspacePrincipal
    ) -> tuple[Dataset, ...]:
        authorize_evaluation(workspace_id=workspace_id, principal=principal, action="read")
        return self._store.list_datasets(workspace_id)

    def get_dataset(
        self, workspace_id: str, dataset_id: str, principal: WorkspacePrincipal
    ) -> Dataset:
        authorize_evaluation(workspace_id=workspace_id, principal=principal, action="read")
        dataset = self._store.get_dataset(workspace_id, dataset_id)
        if dataset is None:
            raise KnoraError("DATASET_NOT_FOUND")
        return dataset

    def upload_source(
        self,
        workspace_id: str,
        dataset_id: str,
        filename: str,
        media_type: str,
        stream: BinaryIO,
        idempotency_key: str,
        principal: WorkspacePrincipal,
    ) -> DatasetSource:
        authorize_evaluation(workspace_id=workspace_id, principal=principal, action="upload")
        self.get_dataset(workspace_id, dataset_id, principal)
        if not idempotency_key or len(idempotency_key) > 255:
            raise KnoraError("INVALID_IDEMPOTENCY_KEY")
        safe_name = filename.replace("\\", "/").rsplit("/", 1)[-1]
        if not safe_name or len(safe_name) > 255 or not safe_name.lower().endswith(".pdf"):
            raise KnoraError("UNSUPPORTED_DOCUMENT_TYPE")
        if media_type.split(";", 1)[0].lower() != "application/pdf":
            raise KnoraError("UNSUPPORTED_DOCUMENT_TYPE")
        raw = stream.read(self._configuration.max_raw_bytes + 1)
        if len(raw) > self._configuration.max_raw_bytes:
            raise KnoraError("PDF_RESOURCE_LIMIT_EXCEEDED")
        if not raw.startswith(b"%PDF-"):
            raise KnoraError("INVALID_PDF_SIGNATURE")
        digest = hashlib.sha256(raw).hexdigest()
        existing = self._store.find_upload(workspace_id, dataset_id, idempotency_key)
        if existing is not None:
            if existing.raw_sha256 != digest:
                raise KnoraError("IDEMPOTENCY_KEY_CONFLICT")
            return existing
        metadata = self._object_store.put_stream(
            workspace_id=workspace_id,
            stream=BytesIO(raw),
            media_type="application/pdf",
        )
        if (
            metadata.workspace_id != workspace_id
            or metadata.sha256 != digest
            or metadata.byte_size != len(raw)
            or metadata.media_type != "application/pdf"
        ):
            raise KnoraError("OBJECT_STORE_METADATA_INVALID")
        source, created = self._store.add_source(
            workspace_id, dataset_id, safe_name, metadata, idempotency_key
        )
        if not created:
            if metadata.object_key != source.object_key:
                self._object_store.delete(workspace_id=workspace_id, object_key=metadata.object_key)
            if source.raw_sha256 != digest:
                raise KnoraError("IDEMPOTENCY_KEY_CONFLICT")
            return source
        return self._prepare(workspace_id, source)

    def retry_extraction(
        self, workspace_id: str, dataset_id: str, source_id: str, principal: WorkspacePrincipal
    ) -> DatasetSource:
        authorize_evaluation(workspace_id=workspace_id, principal=principal, action="upload")
        source = self.get_source(workspace_id, dataset_id, source_id, principal)
        if source.status == "READY":
            raise KnoraError("SOURCE_NOT_RETRYABLE")
        return self._prepare(workspace_id, source)

    def _prepare(self, workspace_id: str, source: DatasetSource) -> DatasetSource:
        try:
            metadata = self._object_store.head(
                workspace_id=workspace_id, object_key=source.object_key
            )
            if metadata.sha256 != source.raw_sha256 or metadata.byte_size != source.byte_size:
                raise KnoraError("SOURCE_IDENTITY_MISMATCH")
            with self._object_store.open_read(
                workspace_id=metadata.workspace_id, object_key=source.object_key
            ) as stream:
                raw = stream.read(self._configuration.max_raw_bytes + 1)
            if len(raw) != source.byte_size or hashlib.sha256(raw).hexdigest() != source.raw_sha256:
                raise KnoraError("SOURCE_IDENTITY_MISMATCH")
            result = self._extractor.extract(BytesIO(raw), self._configuration)
            if result.derivation_identity != self._configuration.derivation_identity:
                raise KnoraError("SOURCE_EXTRACTION_MISMATCH")
            return self._store.record_extraction(source, result, None)
        except PdfExtractionError as error:
            return self._store.record_extraction(source, None, error.code)
        except KnoraError as error:
            return self._store.record_extraction(source, None, error.code)
        except Exception:
            return self._store.record_extraction(source, None, "PDF_EXTRACTOR_UNAVAILABLE")

    def list_sources(
        self, workspace_id: str, dataset_id: str, principal: WorkspacePrincipal
    ) -> tuple[DatasetSource, ...]:
        self.get_dataset(workspace_id, dataset_id, principal)
        return self._store.list_sources(workspace_id, dataset_id)

    def get_source(
        self, workspace_id: str, dataset_id: str, source_id: str, principal: WorkspacePrincipal
    ) -> DatasetSource:
        self.get_dataset(workspace_id, dataset_id, principal)
        source = self._store.get_source(workspace_id, dataset_id, source_id)
        if source is None:
            raise KnoraError("SOURCE_NOT_FOUND")
        return source

    def get_snapshot(
        self, workspace_id: str, dataset_id: str, source_id: str, principal: WorkspacePrincipal
    ) -> ExtractionSnapshot | None:
        authorize_evaluation(workspace_id=workspace_id, principal=principal, action="read_source")
        self.get_source(workspace_id, dataset_id, source_id, principal)
        return self._store.get_snapshot(workspace_id, dataset_id, source_id)

    def read_original(
        self, workspace_id: str, dataset_id: str, source_id: str, principal: WorkspacePrincipal
    ) -> bytes:
        authorize_evaluation(workspace_id=workspace_id, principal=principal, action="read_source")
        source = self.get_source(workspace_id, dataset_id, source_id, principal)
        metadata = self._object_store.head(workspace_id=workspace_id, object_key=source.object_key)
        if metadata.sha256 != source.raw_sha256 or metadata.byte_size != source.byte_size:
            raise KnoraError("SOURCE_IDENTITY_MISMATCH")
        with self._object_store.open_read(
            workspace_id=workspace_id, object_key=source.object_key
        ) as stream:
            raw = stream.read(self._configuration.max_raw_bytes + 1)
        if len(raw) != source.byte_size or hashlib.sha256(raw).hexdigest() != source.raw_sha256:
            raise KnoraError("SOURCE_IDENTITY_MISMATCH")
        return raw
