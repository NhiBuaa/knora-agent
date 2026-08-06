from io import BytesIO

import pytest

from knora.adapters.object_store.filesystem import FileSystemObjectStore
from knora.domain.errors import KnoraError


class StreamingOnly(BytesIO):
    def read(self, size: int = -1) -> bytes:
        if size < 0:
            raise AssertionError("whole-object reads are forbidden")
        return super().read(size)


def test_filesystem_object_store_streams_immutable_workspace_scoped_objects(tmp_path) -> None:
    store = FileSystemObjectStore(tmp_path, max_bytes=64)
    content = b"%PDF-1.7\nsmall fixture"

    metadata = store.put_stream(
        workspace_id="workspace-a",
        stream=StreamingOnly(content),
        media_type="application/pdf",
    )

    assert metadata.workspace_id == "workspace-a"
    assert metadata.byte_size == len(content)
    assert metadata.sha256 == "79c6a101650ef352a7dacc99e21965cc204e80717683d4216a21b7af7798c0d9"
    assert "workspace-a" not in metadata.object_key
    assert store.head(workspace_id="workspace-a", object_key=metadata.object_key) == metadata
    with store.open_read(workspace_id="workspace-a", object_key=metadata.object_key) as source:
        assert source.read() == content

    with pytest.raises(KnoraError, match="OBJECT_NOT_FOUND"):
        store.head(workspace_id="workspace-b", object_key=metadata.object_key)


def test_filesystem_object_store_enforces_streaming_size_limit_and_idempotent_delete(
    tmp_path,
) -> None:
    store = FileSystemObjectStore(tmp_path, max_bytes=8)

    with pytest.raises(KnoraError, match="PDF_RESOURCE_LIMIT_EXCEEDED"):
        store.put_stream(
            workspace_id="workspace-a",
            stream=StreamingOnly(b"123456789"),
            media_type="application/pdf",
        )

    assert list(tmp_path.rglob("*.*")) == []
    store.delete(workspace_id="workspace-a", object_key="missing-object")
