"""Workspace-scoped PDF drafts and local source preparation for the workbench."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from io import BytesIO
from typing import BinaryIO, Literal, Protocol

from knora.access.identity import Identity
from knora.domain.access import WorkspacePrincipal
from knora.domain.errors import KnoraError
from knora.evaluation.access import authorize_evaluation
from knora.evaluation.contracts import (
    Case,
    DatasetIdentity,
    DatasetReference,
    FreezeApproval,
    FrozenDataset,
    GoldDataset,
    PdfSource,
    digest_json,
    freeze_dataset,
)
from knora.ingestion.object_store import ObjectMetadata, ObjectStore
from knora.ingestion.pdf import (
    NormalizedPdfPage,
    PdfExtractionConfiguration,
    PdfExtractionError,
    PdfExtractionResult,
    PdfTextExtractor,
)


@dataclass(frozen=True, slots=True)
class CaseReview:
    case_id: str
    case_digest: str
    decision: Literal["ACCEPTED", "REJECTED"]
    owner_issuer: str
    owner_subject: str
    note: str
    reviewed_at: str


@dataclass(frozen=True, slots=True)
class Dataset:
    id: str
    workspace_id: str
    name: str
    status: Literal["DRAFT", "FROZEN"]
    revision: int = 0
    cases: tuple[Case, ...] = ()
    reviews: tuple[CaseReview, ...] = ()
    reference: DatasetReference | None = None


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
        self, workspace_id: str, dataset_id: str, source_id: str, snapshot_id: str | None = None
    ) -> ExtractionSnapshot | None: ...

    def save_cases(
        self,
        workspace_id: str,
        dataset_id: str,
        cases: tuple[Case, ...],
        reviews: tuple[CaseReview, ...],
        expected_revision: int,
    ) -> Dataset: ...

    def persist_frozen(
        self,
        workspace_id: str,
        dataset_id: str,
        frozen: FrozenDataset,
        expected_revision: int,
    ) -> Dataset: ...

    def get_frozen(
        self, workspace_id: str, dataset_id: str, version: int | None = None
    ) -> FrozenDataset | None: ...

    def reopen_dataset(
        self, workspace_id: str, dataset_id: str, expected_revision: int
    ) -> Dataset: ...


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
        dataset = self.get_dataset(workspace_id, dataset_id, principal)
        if dataset.status == "FROZEN":
            raise KnoraError("EVALUATION_DATASET_FROZEN")
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

    @staticmethod
    def _editable(dataset: Dataset, expected_revision: int) -> None:
        if dataset.status == "FROZEN":
            raise KnoraError("EVALUATION_DATASET_FROZEN")
        if type(expected_revision) is not int or dataset.revision != expected_revision:
            raise KnoraError("EVALUATION_DATASET_REVISION_CONFLICT")

    @staticmethod
    def _actor(principal: WorkspacePrincipal, identity: Identity) -> None:
        if identity.subject != principal.subject:
            raise KnoraError("WORKSPACE_ACCESS_DENIED")

    def _gold(
        self,
        workspace_id: str,
        dataset: Dataset,
        cases: tuple[Case, ...],
        sources: tuple[DatasetSource, ...],
        version: int,
    ) -> GoldDataset:
        if not sources or not cases:
            raise KnoraError("EVALUATION_GOLD_NOT_READY")
        source_by_version = {source.document_version_id: source for source in sources}
        for case in cases:
            anchors = [anchor for group in case.evidence_groups for anchor in group.alternatives]
            if case.no_answer_scope:
                for document_version_id in case.no_answer_scope.checked_document_version_ids:
                    if document_version_id not in source_by_version:
                        raise KnoraError("EVALUATION_GOLD_NOT_READY")
            for anchor in anchors:
                source = source_by_version.get(anchor.document_version_id)
                if source is None:
                    raise KnoraError("EVALUATION_GOLD_NOT_READY")
                if anchor.extraction_snapshot_id is not None:
                    snapshot = self._store.get_snapshot(
                        workspace_id, dataset.id, source.id, anchor.extraction_snapshot_id
                    )
                    if snapshot is None or snapshot.extraction_sha256 != anchor.extraction_sha256:
                        raise KnoraError("EVALUATION_GOLD_NOT_READY")
                    page = next(
                        (p for p in snapshot.pages if p.page_number == anchor.physical_page), None
                    )
                    if page is None or (
                        anchor.start_offset is not None
                        and (
                            anchor.end_offset > len(page.text)
                            or page.text[anchor.start_offset : anchor.end_offset] != anchor.quote
                        )
                    ):
                        raise KnoraError("EVALUATION_GOLD_NOT_READY")
        try:
            return GoldDataset(
                DatasetIdentity(dataset.id, version, workspace_id, "pdf-gold-v1", "pdf-metrics-v1"),
                tuple(
                    PdfSource(s.document_id, s.document_version_id, s.raw_sha256) for s in sources
                ),
                cases,
            )
        except ValueError as error:
            raise KnoraError("EVALUATION_CASE_INVALID") from error

    def save_case(
        self,
        workspace_id: str,
        dataset_id: str,
        case: Case,
        expected_revision: int,
        principal: WorkspacePrincipal,
    ) -> Dataset:
        authorize_evaluation(workspace_id=workspace_id, principal=principal, action="write")
        dataset = self.get_dataset(workspace_id, dataset_id, principal)
        self._editable(dataset, expected_revision)
        cases = tuple(case if c.case_id == case.case_id else c for c in dataset.cases)
        if case.case_id not in {c.case_id for c in dataset.cases}:
            cases += (case,)
        self._gold(
            workspace_id, dataset, cases, self.list_sources(workspace_id, dataset_id, principal), 1
        )
        return self._store.save_cases(workspace_id, dataset_id, cases, (), expected_revision)

    def delete_case(
        self,
        workspace_id: str,
        dataset_id: str,
        case_id: str,
        expected_revision: int,
        principal: WorkspacePrincipal,
    ) -> Dataset:
        authorize_evaluation(workspace_id=workspace_id, principal=principal, action="write")
        dataset = self.get_dataset(workspace_id, dataset_id, principal)
        self._editable(dataset, expected_revision)
        if case_id not in {case.case_id for case in dataset.cases}:
            raise KnoraError("EVALUATION_CASE_NOT_FOUND")
        cases = tuple(case for case in dataset.cases if case.case_id != case_id)
        if cases:
            self._gold(
                workspace_id,
                dataset,
                cases,
                self.list_sources(workspace_id, dataset_id, principal),
                1,
            )
        return self._store.save_cases(workspace_id, dataset_id, cases, (), expected_revision)

    def review_case(
        self,
        workspace_id: str,
        dataset_id: str,
        case_id: str,
        decision: Literal["ACCEPTED", "REJECTED"],
        expected_revision: int,
        principal: WorkspacePrincipal,
        *,
        identity: Identity,
        note: str,
    ) -> Dataset:
        authorize_evaluation(workspace_id=workspace_id, principal=principal, action="approve")
        self._actor(principal, identity)
        authorize_evaluation(workspace_id=workspace_id, principal=principal, action="read_source")
        dataset = self.get_dataset(workspace_id, dataset_id, principal)
        self._editable(dataset, expected_revision)
        if case_id not in {case.case_id for case in dataset.cases}:
            raise KnoraError("EVALUATION_CASE_NOT_FOUND")
        if decision not in ("ACCEPTED", "REJECTED"):
            raise KnoraError("EVALUATION_REVIEW_DECISION_INVALID")
        if not note.strip() or len(note) > 2000:
            raise KnoraError("EVALUATION_REVIEW_DECISION_INVALID")
        if decision == "ACCEPTED":
            self._gold(
                workspace_id,
                dataset,
                dataset.cases,
                self.list_sources(workspace_id, dataset_id, principal),
                1,
            )
        case = next(c for c in dataset.cases if c.case_id == case_id)
        review = CaseReview(
            case_id,
            digest_json(asdict(case)),
            decision,
            identity.issuer,
            identity.subject,
            note.strip(),
            datetime.now(UTC).isoformat(),
        )
        reviews = tuple(r for r in dataset.reviews if r.case_id != case_id) + (review,)
        return self._store.save_cases(
            workspace_id, dataset_id, dataset.cases, reviews, expected_revision
        )

    def preview_gold(
        self, workspace_id: str, dataset_id: str, principal: WorkspacePrincipal
    ) -> GoldDataset:
        dataset = self.get_dataset(workspace_id, dataset_id, principal)
        reviews = {r.case_id: r for r in dataset.reviews}
        if not dataset.cases or any(
            c.case_id not in reviews or reviews[c.case_id].case_digest != digest_json(asdict(c))
            for c in dataset.cases
        ):
            raise KnoraError("EVALUATION_GOLD_NOT_READY")
        accepted = tuple(c for c in dataset.cases if reviews[c.case_id].decision == "ACCEPTED")
        latest = self._store.get_frozen(workspace_id, dataset_id)
        version = latest.reference.version + 1 if latest else 1
        return self._gold(
            workspace_id,
            dataset,
            accepted,
            self.list_sources(workspace_id, dataset_id, principal),
            version,
        )

    def freeze_dataset(
        self,
        workspace_id: str,
        dataset_id: str,
        expected_revision: int,
        principal: WorkspacePrincipal,
        *,
        identity: Identity,
        gold_digest: str,
    ) -> FrozenDataset:
        authorize_evaluation(workspace_id=workspace_id, principal=principal, action="approve")
        self._actor(principal, identity)
        dataset = self.get_dataset(workspace_id, dataset_id, principal)
        self._editable(dataset, expected_revision)
        gold = self.preview_gold(workspace_id, dataset_id, principal)
        if gold.digest != gold_digest:
            raise KnoraError("EVALUATION_GOLD_DIGEST_CONFLICT")
        for source in self.list_sources(workspace_id, dataset_id, principal):
            metadata = self._object_store.head(
                workspace_id=workspace_id, object_key=source.object_key
            )
            if metadata.sha256 != source.raw_sha256 or metadata.byte_size != source.byte_size:
                raise KnoraError("SOURCE_IDENTITY_MISMATCH")
        frozen = freeze_dataset(
            gold, FreezeApproval(identity.issuer, identity.subject, gold.digest)
        )
        self._store.persist_frozen(workspace_id, dataset_id, frozen, expected_revision)
        return frozen

    def get_frozen_dataset(
        self,
        workspace_id: str,
        dataset_id: str,
        principal: WorkspacePrincipal,
        *,
        version: int | None = None,
    ) -> FrozenDataset:
        authorize_evaluation(workspace_id=workspace_id, principal=principal, action="read")
        self.get_dataset(workspace_id, dataset_id, principal)
        frozen = self._store.get_frozen(workspace_id, dataset_id, version)
        if frozen is None:
            raise KnoraError("EVALUATION_GOLD_VERSION_NOT_FOUND")
        return frozen

    def reopen_dataset(
        self,
        workspace_id: str,
        dataset_id: str,
        expected_revision: int,
        principal: WorkspacePrincipal,
    ) -> Dataset:
        authorize_evaluation(workspace_id=workspace_id, principal=principal, action="write")
        self.get_dataset(workspace_id, dataset_id, principal)
        return self._store.reopen_dataset(workspace_id, dataset_id, expected_revision)

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
