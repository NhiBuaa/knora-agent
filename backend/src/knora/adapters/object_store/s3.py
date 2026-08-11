"""S3-compatible ObjectStore adapter over the approved capability subset."""

from __future__ import annotations

import hashlib
import tempfile
from typing import BinaryIO, Protocol
from uuid import uuid4

from knora.domain.errors import KnoraError
from knora.ingestion.object_store import ObjectMetadata, ObjectStore


class S3CapabilityClient(Protocol):
    def put_stream(
        self, *, bucket: str, workspace_id: str, stream: BinaryIO, media_type: str
    ) -> ObjectMetadata: ...

    def open_read(self, *, bucket: str, object_key: str) -> BinaryIO: ...

    def head(self, *, bucket: str, object_key: str) -> ObjectMetadata: ...

    def delete(self, *, bucket: str, object_key: str) -> None: ...


class CapabilityAudit(Protocol):
    def record(self, operation: str) -> None: ...


class AuditedS3CapabilityClient:
    """Capability-boundary wrapper exposing only the approved provider operations."""

    def __init__(self, *, delegate: S3CapabilityClient, audit: CapabilityAudit) -> None:
        self._delegate = delegate
        self._audit = audit

    def put_stream(
        self, *, bucket: str, workspace_id: str, stream: BinaryIO, media_type: str
    ) -> ObjectMetadata:
        self._audit.record("put_stream")
        return self._delegate.put_stream(
            bucket=bucket, workspace_id=workspace_id, stream=stream, media_type=media_type
        )

    def open_read(self, *, bucket: str, object_key: str) -> BinaryIO:
        self._audit.record("open_read")
        return self._delegate.open_read(bucket=bucket, object_key=object_key)

    def head(self, *, bucket: str, object_key: str) -> ObjectMetadata:
        self._audit.record("head")
        return self._delegate.head(bucket=bucket, object_key=object_key)

    def delete(self, *, bucket: str, object_key: str) -> None:
        self._audit.record("delete")
        self._delegate.delete(bucket=bucket, object_key=object_key)


class S3ObjectStore(ObjectStore):
    def __init__(self, *, client: S3CapabilityClient, bucket: str) -> None:
        self._client = client
        self._bucket = bucket

    def put_stream(self, *, workspace_id: str, stream: BinaryIO, media_type: str) -> ObjectMetadata:
        metadata = self._client.put_stream(
            bucket=self._bucket,
            workspace_id=workspace_id,
            stream=stream,
            media_type=media_type,
        )
        self._validate_metadata(metadata, workspace_id=workspace_id)
        return metadata

    def open_read(self, *, workspace_id: str, object_key: str) -> BinaryIO:
        metadata = self.head(workspace_id=workspace_id, object_key=object_key)
        if metadata.workspace_id != workspace_id:
            raise ValueError("S3 object is outside the requested Workspace")
        return self._client.open_read(bucket=self._bucket, object_key=object_key)

    def head(self, *, workspace_id: str, object_key: str) -> ObjectMetadata:
        metadata = self._client.head(bucket=self._bucket, object_key=object_key)
        self._validate_metadata(metadata, workspace_id=workspace_id, object_key=object_key)
        return metadata

    def delete(self, *, workspace_id: str, object_key: str) -> None:
        try:
            metadata = self.head(workspace_id=workspace_id, object_key=object_key)
        except KnoraError as error:
            if error.code == "OBJECT_NOT_FOUND":
                return
            raise
        if metadata.workspace_id == workspace_id:
            self._client.delete(bucket=self._bucket, object_key=object_key)

    @staticmethod
    def _validate_metadata(
        metadata: ObjectMetadata, *, workspace_id: str, object_key: str | None = None
    ) -> None:
        if not isinstance(metadata, ObjectMetadata):
            raise KnoraError("OBJECT_STORE_METADATA_INVALID")
        if (
            not isinstance(metadata.workspace_id, str)
            or not metadata.workspace_id
            or not isinstance(metadata.object_key, str)
            or not metadata.object_key
            or metadata.workspace_id != workspace_id
            or (object_key is not None and metadata.object_key != object_key)
            or not isinstance(metadata.sha256, str)
            or len(metadata.sha256) != 64
            or any(character not in "0123456789abcdefABCDEF" for character in metadata.sha256)
            or isinstance(metadata.byte_size, bool)
            or not isinstance(metadata.byte_size, int)
            or metadata.byte_size < 0
            or not isinstance(metadata.media_type, str)
            or not metadata.media_type
        ):
            raise KnoraError("OBJECT_STORE_METADATA_INVALID")


class BotoS3CapabilityClient:
    """Production capability client; the boto SDK is loaded only for S3 wiring."""

    def __init__(
        self,
        *,
        endpoint_url: str | None,
        region_name: str | None,
        access_key: str,
        secret_key: str,
    ) -> None:
        import boto3
        from botocore.config import Config

        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            region_name=region_name,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        )

    def put_stream(
        self, *, bucket: str, workspace_id: str, stream: BinaryIO, media_type: str
    ) -> ObjectMetadata:
        object_key = uuid4().hex
        digest = hashlib.sha256()
        byte_size = 0
        with tempfile.TemporaryFile() as spool:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
                byte_size += len(chunk)
                spool.write(chunk)
            spool.seek(0)
            self._client.upload_fileobj(
                spool,
                bucket,
                object_key,
                ExtraArgs={
                    "ContentType": media_type,
                    "Metadata": {
                        "workspace-id": workspace_id,
                        "sha256": digest.hexdigest(),
                    },
                },
            )
        return ObjectMetadata(
            workspace_id=workspace_id,
            object_key=object_key,
            sha256=digest.hexdigest(),
            byte_size=byte_size,
            media_type=media_type,
        )

    def open_read(self, *, bucket: str, object_key: str) -> BinaryIO:
        return self._client.get_object(Bucket=bucket, Key=object_key)["Body"]

    def head(self, *, bucket: str, object_key: str) -> ObjectMetadata:
        try:
            response = self._client.head_object(Bucket=bucket, Key=object_key)
        except Exception as error:
            response_error = getattr(error, "response", {}).get("Error", {})
            if str(response_error.get("Code")) in {"404", "NoSuchKey", "NotFound"}:
                raise KnoraError("OBJECT_NOT_FOUND") from error
            raise
        metadata = response.get("Metadata", {})
        try:
            workspace_id = metadata["workspace-id"]
            sha256 = metadata["sha256"]
            byte_size = int(response["ContentLength"])
            media_type = response.get("ContentType", "application/octet-stream")
        except (KeyError, TypeError, ValueError) as error:
            raise KnoraError("OBJECT_STORE_METADATA_INVALID") from error
        if (
            not isinstance(workspace_id, str)
            or not workspace_id
            or not isinstance(sha256, str)
            or len(sha256) != 64
            or any(character not in "0123456789abcdefABCDEF" for character in sha256)
            or byte_size < 0
            or not isinstance(media_type, str)
            or not media_type
        ):
            raise KnoraError("OBJECT_STORE_METADATA_INVALID")
        return ObjectMetadata(
            workspace_id=workspace_id,
            object_key=object_key,
            sha256=sha256,
            byte_size=byte_size,
            media_type=media_type,
        )

    def delete(self, *, bucket: str, object_key: str) -> None:
        self._client.delete_object(Bucket=bucket, Key=object_key)
