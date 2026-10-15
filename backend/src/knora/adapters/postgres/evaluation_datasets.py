"""PostgreSQL persistence for local PDF dataset drafts and retained source evidence."""

from __future__ import annotations

from dataclasses import asdict
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from knora.adapters.postgres.evaluation_datasets_tables import (
    DatasetDraftTable,
    DatasetSourceTable,
    EvaluationGoldVersionTable,
    ExtractionSnapshotTable,
)
from knora.adapters.postgres.tables import (
    DocumentTable,
    DocumentVersionTable,
    OriginalSourceObjectTable,
    WorkspaceTable,
)
from knora.domain.errors import KnoraError
from knora.evaluation.contracts import Case, FrozenDataset
from knora.evaluation.datasets import (
    CaseReview,
    Dataset,
    DatasetSource,
    ExtractionSnapshot,
    extraction_checksum,
)
from knora.ingestion.object_store import ObjectMetadata
from knora.ingestion.pdf import NormalizedPdfPage, PdfExtractionResult


def _dataset(row: DatasetDraftTable) -> Dataset:
    from knora.evaluation.contracts import DatasetReference

    reviews = tuple(CaseReview(**item) for item in (row.reviews or []))
    return Dataset(
        row.id,
        row.workspace_id,
        row.name,
        row.status,
        row.revision,
        tuple(Case.from_dict(case) for case in (row.cases or [])),
        reviews,
        DatasetReference.from_dict(row.reference) if row.reference else None,
    )


def _source(row: DatasetSourceTable) -> DatasetSource:
    return DatasetSource(
        row.id,
        row.dataset_id,
        row.document_id,
        row.document_version_id,
        row.filename,
        row.raw_sha256,
        row.byte_size,
        row.object_key,
        row.idempotency_key,
        row.status,
        row.failure_code,
        row.snapshot_id,
    )


class PostgresDatasetStore:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def create_dataset(self, workspace_id: str, name: str) -> Dataset:
        with self._session_factory.begin() as session:
            if session.get(WorkspaceTable, workspace_id) is None:
                raise KnoraError("WORKSPACE_ACCESS_DENIED")
            row = DatasetDraftTable(
                id=str(uuid4()), workspace_id=workspace_id, name=name, status="DRAFT"
            )
            session.add(row)
            session.flush()
            return _dataset(row)

    def list_datasets(self, workspace_id: str) -> tuple[Dataset, ...]:
        with self._session_factory() as session:
            rows = session.scalars(
                select(DatasetDraftTable)
                .where(DatasetDraftTable.workspace_id == workspace_id)
                .order_by(DatasetDraftTable.created_at.desc(), DatasetDraftTable.id)
            ).all()
            return tuple(_dataset(row) for row in rows)

    def get_dataset(self, workspace_id: str, dataset_id: str) -> Dataset | None:
        with self._session_factory() as session:
            row = session.scalar(
                select(DatasetDraftTable).where(
                    DatasetDraftTable.id == dataset_id,
                    DatasetDraftTable.workspace_id == workspace_id,
                )
            )
            return _dataset(row) if row is not None else None

    def find_upload(
        self, workspace_id: str, dataset_id: str, idempotency_key: str
    ) -> DatasetSource | None:
        with self._session_factory() as session:
            row = session.scalar(
                select(DatasetSourceTable).where(
                    DatasetSourceTable.workspace_id == workspace_id,
                    DatasetSourceTable.dataset_id == dataset_id,
                    DatasetSourceTable.idempotency_key == idempotency_key,
                )
            )
            return _source(row) if row is not None else None

    def add_source(
        self,
        workspace_id: str,
        dataset_id: str,
        name: str,
        metadata: ObjectMetadata,
        idempotency_key: str,
    ) -> tuple[DatasetSource, bool]:
        if metadata.workspace_id != workspace_id or metadata.media_type != "application/pdf":
            raise KnoraError("OBJECT_STORE_METADATA_INVALID")
        with self._session_factory.begin() as session:
            dataset = session.scalar(
                select(DatasetDraftTable)
                .where(
                    DatasetDraftTable.id == dataset_id,
                    DatasetDraftTable.workspace_id == workspace_id,
                )
                .with_for_update()
            )
            if dataset is None:
                raise KnoraError("DATASET_NOT_FOUND")
            if dataset.status == "FROZEN":
                raise KnoraError("EVALUATION_DATASET_FROZEN")
            replay = session.scalar(
                select(DatasetSourceTable).where(
                    DatasetSourceTable.dataset_id == dataset_id,
                    DatasetSourceTable.idempotency_key == idempotency_key,
                )
            )
            if replay is not None:
                return _source(replay), False
            dataset.revision += 1
            dataset.reviews = []
            source_id = str(uuid4())
            document = DocumentTable(
                id=str(uuid4()),
                workspace_id=workspace_id,
                source_key=f"evaluation/{dataset_id}/{source_id}",
                source_name=name,
                archived=False,
                revision=0,
            )
            session.add(document)
            session.flush()
            version = DocumentVersionTable(
                id=str(uuid4()),
                document_id=document.id,
                raw_sha256=metadata.sha256,
                media_type=metadata.media_type,
                version_number=1,
            )
            session.add(version)
            session.flush()
            original = OriginalSourceObjectTable(
                id=str(uuid4()),
                workspace_id=workspace_id,
                document_version_id=version.id,
                object_key=metadata.object_key,
                raw_sha256=metadata.sha256,
                byte_size=metadata.byte_size,
                media_type=metadata.media_type,
            )
            session.add(original)
            session.flush()
            row = DatasetSourceTable(
                id=source_id,
                workspace_id=workspace_id,
                dataset_id=dataset_id,
                document_id=document.id,
                document_version_id=version.id,
                original_source_object_id=original.id,
                filename=name,
                raw_sha256=metadata.sha256,
                byte_size=metadata.byte_size,
                object_key=metadata.object_key,
                idempotency_key=idempotency_key,
                status="PROCESSING",
            )
            session.add(row)
            session.flush()
            return _source(row), True

    def get_source(
        self, workspace_id: str, dataset_id: str, source_id: str
    ) -> DatasetSource | None:
        with self._session_factory() as session:
            row = session.scalar(
                select(DatasetSourceTable).where(
                    DatasetSourceTable.id == source_id,
                    DatasetSourceTable.dataset_id == dataset_id,
                    DatasetSourceTable.workspace_id == workspace_id,
                )
            )
            return _source(row) if row is not None else None

    def list_sources(self, workspace_id: str, dataset_id: str) -> tuple[DatasetSource, ...]:
        with self._session_factory() as session:
            rows = session.scalars(
                select(DatasetSourceTable)
                .where(
                    DatasetSourceTable.workspace_id == workspace_id,
                    DatasetSourceTable.dataset_id == dataset_id,
                )
                .order_by(DatasetSourceTable.created_at, DatasetSourceTable.id)
            ).all()
            return tuple(_source(row) for row in rows)

    def record_extraction(
        self, source: DatasetSource, result: PdfExtractionResult | None, failure: str | None
    ) -> DatasetSource:
        with self._session_factory.begin() as session:
            row = session.scalar(
                select(DatasetSourceTable)
                .where(DatasetSourceTable.id == source.id)
                .with_for_update()
            )
            if row is None or (
                row.dataset_id != source.dataset_id
                or row.document_version_id != source.document_version_id
                or row.raw_sha256 != source.raw_sha256
                or row.object_key != source.object_key
            ):
                raise KnoraError("SOURCE_IDENTITY_MISMATCH")
            original = session.scalar(
                select(OriginalSourceObjectTable)
                .where(OriginalSourceObjectTable.id == row.original_source_object_id)
                .with_for_update()
            )
            if original is None or original.deleted_at is not None:
                raise KnoraError("SOURCE_OBJECT_NOT_AVAILABLE")
            if row.status == "READY":
                return _source(row)
            if result is not None:
                digest = extraction_checksum(result.pages)
                snapshot = session.scalar(
                    select(ExtractionSnapshotTable).where(
                        ExtractionSnapshotTable.source_id == row.id,
                        ExtractionSnapshotTable.configuration_sha256 == result.derivation_identity,
                        ExtractionSnapshotTable.extraction_sha256 == digest,
                    )
                )
                if snapshot is None:
                    snapshot = ExtractionSnapshotTable(
                        id=str(uuid4()),
                        workspace_id=row.workspace_id,
                        source_id=row.id,
                        configuration_sha256=result.derivation_identity,
                        extraction_sha256=digest,
                        parser_version=result.parser_version,
                        extraction_options_version=result.extraction_options_version,
                        normalizer_version=result.normalizer_version,
                        pages=[
                            {
                                "page_number": page.page_number,
                                "text": page.text,
                                "content_checksum": page.content_checksum,
                            }
                            for page in result.pages
                        ],
                    )
                    session.add(snapshot)
                    session.flush()
                row.snapshot_id = snapshot.id
                row.status = "READY"
                row.failure_code = None
            else:
                row.status = "FAILED"
                row.failure_code = failure or "PDF_EXTRACTOR_UNAVAILABLE"
            session.flush()
            return _source(row)

    def get_snapshot(
        self, workspace_id: str, dataset_id: str, source_id: str, snapshot_id: str | None = None
    ) -> ExtractionSnapshot | None:
        with self._session_factory() as session:
            source = session.scalar(
                select(DatasetSourceTable).where(
                    DatasetSourceTable.id == source_id,
                    DatasetSourceTable.dataset_id == dataset_id,
                    DatasetSourceTable.workspace_id == workspace_id,
                )
            )
            if source is None or (snapshot_id is None and source.snapshot_id is None):
                return None
            row = session.scalar(
                select(ExtractionSnapshotTable).where(
                    ExtractionSnapshotTable.id == (snapshot_id or source.snapshot_id),
                    ExtractionSnapshotTable.source_id == source_id,
                    ExtractionSnapshotTable.workspace_id == workspace_id,
                )
            )
            if row is None:
                raise KnoraError("SOURCE_IDENTITY_MISMATCH")
            pages = tuple(NormalizedPdfPage(**page) for page in row.pages)
            return ExtractionSnapshot(
                row.id, source_id, row.configuration_sha256, row.extraction_sha256, pages
            )

    def save_cases(
        self,
        workspace_id: str,
        dataset_id: str,
        cases: tuple[Case, ...],
        reviews: tuple[CaseReview, ...],
        expected_revision: int,
    ) -> Dataset:
        with self._session_factory.begin() as session:
            row = session.scalar(
                select(DatasetDraftTable)
                .where(
                    DatasetDraftTable.id == dataset_id,
                    DatasetDraftTable.workspace_id == workspace_id,
                )
                .with_for_update()
            )
            if row is None:
                raise KnoraError("DATASET_NOT_FOUND")
            if row.status == "FROZEN":
                raise KnoraError("EVALUATION_DATASET_FROZEN")
            if row.revision != expected_revision:
                raise KnoraError("EVALUATION_DATASET_REVISION_CONFLICT")
            row.cases = [asdict(case) for case in cases]
            row.reviews = [asdict(review) for review in reviews]
            row.revision += 1
            session.flush()
            return _dataset(row)

    def persist_frozen(
        self,
        workspace_id: str,
        dataset_id: str,
        frozen: FrozenDataset,
        expected_revision: int,
    ) -> Dataset:
        with self._session_factory.begin() as session:
            row = session.scalar(
                select(DatasetDraftTable)
                .where(
                    DatasetDraftTable.id == dataset_id,
                    DatasetDraftTable.workspace_id == workspace_id,
                )
                .with_for_update()
            )
            if row is None:
                raise KnoraError("DATASET_NOT_FOUND")
            if row.status == "FROZEN":
                raise KnoraError("EVALUATION_DATASET_FROZEN")
            if row.revision != expected_revision:
                raise KnoraError("EVALUATION_DATASET_REVISION_CONFLICT")
            session.add(
                EvaluationGoldVersionTable(
                    id=str(uuid4()),
                    workspace_id=workspace_id,
                    dataset_id=dataset_id,
                    version=frozen.reference.version,
                    digest=frozen.reference.digest,
                    frozen_json=frozen.to_json(),
                    reviews=row.reviews,
                    draft_revision=row.revision,
                )
            )
            row.status = "FROZEN"
            row.reference = asdict(frozen.reference)
            row.revision += 1
            session.flush()
            return _dataset(row)

    def get_frozen(
        self, workspace_id: str, dataset_id: str, version: int | None = None
    ) -> FrozenDataset | None:
        with self._session_factory() as session:
            row = session.scalar(
                select(EvaluationGoldVersionTable)
                .where(
                    EvaluationGoldVersionTable.dataset_id == dataset_id,
                    EvaluationGoldVersionTable.workspace_id == workspace_id,
                    *(
                        [EvaluationGoldVersionTable.version == version]
                        if version is not None
                        else []
                    ),
                )
                .order_by(EvaluationGoldVersionTable.version.desc())
            )
            return FrozenDataset.from_json(row.frozen_json) if row is not None else None

    def reopen_dataset(self, workspace_id: str, dataset_id: str, expected_revision: int) -> Dataset:
        with self._session_factory.begin() as session:
            row = session.scalar(
                select(DatasetDraftTable)
                .where(
                    DatasetDraftTable.id == dataset_id,
                    DatasetDraftTable.workspace_id == workspace_id,
                )
                .with_for_update()
            )
            if row is None:
                raise KnoraError("DATASET_NOT_FOUND")
            if row.revision != expected_revision:
                raise KnoraError("EVALUATION_DATASET_REVISION_CONFLICT")
            if row.status != "FROZEN":
                raise KnoraError("EVALUATION_DATASET_REVISION_CONFLICT")
            frozen_row = session.scalar(
                select(EvaluationGoldVersionTable)
                .where(
                    EvaluationGoldVersionTable.dataset_id == dataset_id,
                    EvaluationGoldVersionTable.workspace_id == workspace_id,
                )
                .order_by(EvaluationGoldVersionTable.version.desc())
            )
            if frozen_row is None:
                raise KnoraError("EVALUATION_GOLD_VERSION_NOT_FOUND")
            frozen = FrozenDataset.from_json(frozen_row.frozen_json)
            row.status = "DRAFT"
            row.cases = [case for case in frozen.gold.to_dict()["cases"]]
            row.reviews = []
            row.revision += 1
            session.flush()
            return _dataset(row)
