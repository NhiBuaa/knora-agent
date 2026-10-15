from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest

from knora.adapters.object_store.filesystem import FileSystemObjectStore
from knora.adapters.pdf.pypdf import PypdfTextExtractor
from knora.domain.access import WorkspacePrincipal
from knora.domain.errors import KnoraError
from knora.evaluation.datasets import DatasetService
from knora.ingestion.pdf import PdfExtractionConfiguration

PDF = Path(__file__).resolve().parents[3] / "docs/assets/readme/community-garden-guide.pdf"
OWNER = WorkspacePrincipal(
    "w1", "owner", ("operator:read", "evaluations:write", "documents:write", "documents:read")
)


class MemoryDatasetStore:
    def __init__(self):
        self.datasets = {}
        self.sources = {}
        self.snapshots = {}

    def create_dataset(self, workspace_id, name):
        from knora.evaluation.datasets import Dataset

        dataset = Dataset("d1", workspace_id, name, "DRAFT")
        self.datasets[dataset.id] = dataset
        return dataset

    def list_datasets(self, workspace_id):
        return tuple(d for d in self.datasets.values() if d.workspace_id == workspace_id)

    def get_dataset(self, workspace_id, dataset_id):
        dataset = self.datasets.get(dataset_id)
        return dataset if dataset and dataset.workspace_id == workspace_id else None

    def find_upload(self, workspace_id, dataset_id, idempotency_key):
        return next(
            (
                s
                for s in self.sources.values()
                if s.dataset_id == dataset_id and s.idempotency_key == idempotency_key
            ),
            None,
        )

    def add_source(self, workspace_id, dataset_id, name, metadata, idempotency_key):
        from knora.evaluation.datasets import DatasetSource

        source = DatasetSource(
            "s" + str(len(self.sources) + 1),
            dataset_id,
            "doc" + str(len(self.sources) + 1),
            "ver" + str(len(self.sources) + 1),
            name,
            metadata.sha256,
            metadata.byte_size,
            metadata.object_key,
            idempotency_key,
            "PROCESSING",
            None,
            None,
        )
        self.sources[source.id] = source
        return source, True

    def get_source(self, workspace_id, dataset_id, source_id):
        source = self.sources.get(source_id)
        return source if source and source.dataset_id == dataset_id else None

    def list_sources(self, workspace_id, dataset_id):
        return tuple(s for s in self.sources.values() if s.dataset_id == dataset_id)

    def record_extraction(self, source, result, failure):
        from dataclasses import replace

        from knora.evaluation.datasets import ExtractionSnapshot, extraction_checksum

        snapshot = None
        if result:
            snapshot = ExtractionSnapshot(
                "snap" + str(len(self.snapshots) + 1),
                source.id,
                result.derivation_identity,
                extraction_checksum(result.pages),
                result.pages,
            )
            self.snapshots[snapshot.id] = snapshot
        updated = replace(
            source,
            status="READY" if snapshot else "FAILED",
            failure_code=failure,
            snapshot_id=snapshot.id if snapshot else None,
        )
        self.sources[source.id] = updated
        return updated

    def get_snapshot(self, workspace_id, dataset_id, source_id):
        source = self.get_source(workspace_id, dataset_id, source_id)
        return self.snapshots.get(source.snapshot_id) if source and source.snapshot_id else None


@pytest.fixture
def service(tmp_path):
    return DatasetService(
        MemoryDatasetStore(),
        FileSystemObjectStore(tmp_path),
        PypdfTextExtractor(),
        PdfExtractionConfiguration.layout_preserving(),
    )


def test_upload_prepares_real_pdf_without_activation(service):
    dataset = service.create_dataset("w1", "Review", OWNER)
    data = PDF.read_bytes()
    source = service.upload_source(
        "w1", dataset.id, "guide.pdf", "application/pdf", BytesIO(data), "upload-1", OWNER
    )
    assert source.status == "READY"
    assert source.raw_sha256 == "91c195401b5201a2d77fa01fbc65c4eb819572f36d195a4c881f6ccc52388ee5"
    assert source.document_version_id
    snapshot = service.get_snapshot("w1", dataset.id, source.id, OWNER)
    assert (
        snapshot.configuration_sha256
        == PdfExtractionConfiguration.layout_preserving().derivation_identity
    )
    assert len(snapshot.extraction_sha256) == 64
    assert len(snapshot.pages) == 1
    assert "garden" in snapshot.pages[0].text.lower()
    assert service.read_original("w1", dataset.id, source.id, OWNER) == data


def test_upload_is_idempotent_and_rejects_changed_content(service):
    dataset = service.create_dataset("w1", "Review", OWNER)
    first = service.upload_source(
        "w1", dataset.id, "guide.pdf", "application/pdf", BytesIO(PDF.read_bytes()), "same", OWNER
    )
    replay = service.upload_source(
        "w1", dataset.id, "rename.pdf", "application/pdf", BytesIO(PDF.read_bytes()), "same", OWNER
    )
    assert replay == first
    assert len(service.list_sources("w1", dataset.id, OWNER)) == 1
    with pytest.raises(KnoraError, match="IDEMPOTENCY_KEY_CONFLICT"):
        service.upload_source(
            "w1",
            dataset.id,
            "bad.pdf",
            "application/pdf",
            BytesIO(b"%PDF-different"),
            "same",
            OWNER,
        )


def test_invalid_or_scanned_pdf_remains_explicit(service):
    dataset = service.create_dataset("w1", "Review", OWNER)
    with pytest.raises(KnoraError, match="INVALID_PDF_SIGNATURE"):
        service.upload_source(
            "w1", dataset.id, "bad.pdf", "application/pdf", BytesIO(b"bad"), "bad", OWNER
        )
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, NameObject

    blank = BytesIO()
    writer = PdfWriter()
    page = writer.add_blank_page(width=100, height=100)
    empty_stream = DecodedStreamObject()
    empty_stream.set_data(b"BT ET")
    page[NameObject("/Contents")] = writer._add_object(empty_stream)
    writer.write(blank)
    source = service.upload_source(
        "w1", dataset.id, "scan.pdf", "application/pdf", BytesIO(blank.getvalue()), "scan", OWNER
    )
    assert source.status == "FAILED"
    assert source.failure_code == "PDF_TEXT_INSUFFICIENT"
    assert service.get_snapshot("w1", dataset.id, source.id, OWNER) is None
    assert service.read_original("w1", dataset.id, source.id, OWNER) == blank.getvalue()


def test_auth_precedes_lookup_and_original_requires_documents_read(service):
    with pytest.raises(KnoraError, match="CAPABILITY_ACCESS_DENIED"):
        service.get_dataset("w1", "missing", WorkspacePrincipal("w1", "reader", ()))
    with pytest.raises(KnoraError, match="WORKSPACE_ACCESS_DENIED"):
        service.get_source("w2", "missing", "missing", OWNER)
    dataset = service.create_dataset("w1", "Review", OWNER)
    source = service.upload_source(
        "w1", dataset.id, "guide.pdf", "application/pdf", BytesIO(PDF.read_bytes()), "one", OWNER
    )
    with pytest.raises(KnoraError, match="CAPABILITY_ACCESS_DENIED"):
        service.read_original(
            "w1", dataset.id, source.id, WorkspacePrincipal("w1", "reader", ("operator:read",))
        )


def test_upload_limit_is_checked_before_storage(tmp_path):
    config = PdfExtractionConfiguration.layout_preserving()
    from dataclasses import replace

    service = DatasetService(
        MemoryDatasetStore(),
        FileSystemObjectStore(tmp_path),
        PypdfTextExtractor(),
        replace(config, max_raw_bytes=8),
    )
    dataset = service.create_dataset("w1", "Review", OWNER)
    with pytest.raises(KnoraError, match="PDF_RESOURCE_LIMIT_EXCEEDED"):
        service.upload_source(
            "w1",
            dataset.id,
            "guide.pdf",
            "application/pdf",
            BytesIO(PDF.read_bytes()),
            "too-big",
            OWNER,
        )
    assert service.list_sources("w1", dataset.id, OWNER) == ()


def test_stale_object_bytes_cannot_become_extraction_evidence(service):
    dataset = service.create_dataset("w1", "Review", OWNER)
    store = service._object_store
    original = store.open_read

    def stale_read(*, workspace_id, object_key):
        return BytesIO(b"%PDF-tampered")

    store.open_read = stale_read
    try:
        source = service.upload_source(
            "w1",
            dataset.id,
            "guide.pdf",
            "application/pdf",
            BytesIO(PDF.read_bytes()),
            "tampered",
            OWNER,
        )
    finally:
        store.open_read = original
    assert source.status == "FAILED"
    assert source.failure_code == "SOURCE_IDENTITY_MISMATCH"
    assert service.get_snapshot("w1", dataset.id, source.id, OWNER) is None


def test_processing_source_can_be_retried_after_interruption(service):
    dataset = service.create_dataset("w1", "Review", OWNER)
    original = service._prepare
    service._prepare = lambda workspace_id, source: source
    try:
        source = service.upload_source(
            "w1",
            dataset.id,
            "guide.pdf",
            "application/pdf",
            BytesIO(PDF.read_bytes()),
            "interrupt",
            OWNER,
        )
    finally:
        service._prepare = original
    assert source.status == "PROCESSING"
    resumed = service.retry_extraction("w1", dataset.id, source.id, OWNER)
    assert resumed.status == "READY"
