from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import BinaryIO
from uuid import uuid4

from knora.domain.errors import KnoraError
from knora.ingestion.object_store import ObjectMetadata

DEFAULT_MAX_PDF_BYTES = 25 * 1024 * 1024
STREAM_CHUNK_BYTES = 1024 * 1024
_OPAQUE_KEY = re.compile(r"^[0-9a-f]{32}$")


class FileSystemObjectStore:
    """A durable local ObjectStore adapter for development and tests.

    The application sees only opaque keys. Workspace names never participate in paths.
    """

    def __init__(self, root: str | Path, *, max_bytes: int = DEFAULT_MAX_PDF_BYTES) -> None:
        self._root = Path(root).resolve()
        self._max_bytes = max_bytes

    def put_stream(
        self,
        *,
        workspace_id: str,
        stream: BinaryIO,
        media_type: str,
    ) -> ObjectMetadata:
        bucket = self._workspace_directory(workspace_id)
        bucket.mkdir(parents=True, exist_ok=True)
        object_key = uuid4().hex
        data_path, metadata_path = self._paths(workspace_id, object_key)
        temporary_data = data_path.with_suffix(".data.tmp")
        temporary_metadata = metadata_path.with_suffix(".json.tmp")
        digest = hashlib.sha256()
        byte_size = 0
        try:
            with temporary_data.open("xb") as destination:
                while chunk := stream.read(STREAM_CHUNK_BYTES):
                    byte_size += len(chunk)
                    if byte_size > self._max_bytes:
                        raise KnoraError("PDF_RESOURCE_LIMIT_EXCEEDED")
                    digest.update(chunk)
                    destination.write(chunk)
                destination.flush()
                os.fsync(destination.fileno())
            metadata = ObjectMetadata(
                workspace_id=workspace_id,
                object_key=object_key,
                sha256=digest.hexdigest(),
                byte_size=byte_size,
                media_type=media_type,
            )
            os.replace(temporary_data, data_path)
            with temporary_metadata.open("x", encoding="utf-8") as destination:
                json.dump(
                    {
                        "workspace_id": metadata.workspace_id,
                        "object_key": metadata.object_key,
                        "sha256": metadata.sha256,
                        "byte_size": metadata.byte_size,
                        "media_type": metadata.media_type,
                    },
                    destination,
                    sort_keys=True,
                )
                destination.flush()
                os.fsync(destination.fileno())
            os.replace(temporary_metadata, metadata_path)
            return metadata
        except Exception:
            temporary_data.unlink(missing_ok=True)
            temporary_metadata.unlink(missing_ok=True)
            data_path.unlink(missing_ok=True)
            metadata_path.unlink(missing_ok=True)
            raise

    def open_read(self, *, workspace_id: str, object_key: str) -> BinaryIO:
        self.head(workspace_id=workspace_id, object_key=object_key)
        data_path, _ = self._paths(workspace_id, object_key)
        return data_path.open("rb")

    def head(self, *, workspace_id: str, object_key: str) -> ObjectMetadata:
        if not _OPAQUE_KEY.fullmatch(object_key):
            raise KnoraError("OBJECT_NOT_FOUND")
        data_path, metadata_path = self._paths(workspace_id, object_key)
        try:
            payload = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata = ObjectMetadata(**payload)
        except (FileNotFoundError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise KnoraError("OBJECT_NOT_FOUND") from error
        if (
            not data_path.is_file()
            or metadata.workspace_id != workspace_id
            or metadata.object_key != object_key
        ):
            raise KnoraError("OBJECT_NOT_FOUND")
        return metadata

    def delete(self, *, workspace_id: str, object_key: str) -> None:
        if not _OPAQUE_KEY.fullmatch(object_key):
            return
        data_path, metadata_path = self._paths(workspace_id, object_key)
        data_path.unlink(missing_ok=True)
        metadata_path.unlink(missing_ok=True)

    def _workspace_directory(self, workspace_id: str) -> Path:
        bucket = hashlib.sha256(workspace_id.encode("utf-8")).hexdigest()
        return self._root / bucket

    def _paths(self, workspace_id: str, object_key: str) -> tuple[Path, Path]:
        bucket = self._workspace_directory(workspace_id)
        return bucket / f"{object_key}.data", bucket / f"{object_key}.json"
