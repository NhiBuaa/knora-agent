from io import BytesIO

import pytest

from knora.adapters.object_store.s3 import (
    AuditedS3CapabilityClient,
    BotoS3CapabilityClient,
    S3ObjectStore,
)
from knora.domain.errors import KnoraError
from knora.ingestion.object_store import ObjectMetadata


class Audit:
    def __init__(self) -> None:
        self.operations: list[str] = []

    def record(self, operation: str) -> None:
        self.operations.append(operation)


class Client:
    def __init__(self) -> None:
        self.metadata = ObjectMetadata("w1", "k1", "a" * 64, 1, "application/pdf")

    def put_stream(self, *, bucket, workspace_id, stream, media_type):
        del bucket, workspace_id, stream, media_type
        return self.metadata

    def open_read(self, *, bucket, object_key):
        del bucket, object_key
        return BytesIO(b"x")

    def head(self, *, bucket, object_key):
        del bucket, object_key
        return self.metadata

    def delete(self, *, bucket, object_key):
        del bucket, object_key


class MissingClient(Client):
    def head(self, *, bucket, object_key):
        del bucket, object_key
        raise KnoraError("OBJECT_NOT_FOUND")


class MalformedMetadataClient(Client):
    def head(self, *, bucket, object_key):
        del bucket, object_key
        return ObjectMetadata("w1", "k1", "not-a-sha256", -1, "application/pdf")


class NonMetadataClient(Client):
    def head(self, *, bucket, object_key):
        del bucket, object_key
        return {"workspace_id": "w1"}


def test_s3_capability_audit_records_only_approved_operations() -> None:
    audit = Audit()
    store = S3ObjectStore(
        client=AuditedS3CapabilityClient(delegate=Client(), audit=audit), bucket="b"
    )

    store.put_stream(workspace_id="w1", stream=BytesIO(b"x"), media_type="application/pdf")
    store.open_read(workspace_id="w1", object_key="k1")
    store.head(workspace_id="w1", object_key="k1")
    store.delete(workspace_id="w1", object_key="k1")

    assert audit.operations == ["put_stream", "head", "open_read", "head", "head", "delete"]


def test_s3_delete_is_idempotent_when_object_is_already_absent() -> None:
    S3ObjectStore(client=MissingClient(), bucket="b").delete(
        workspace_id="w1", object_key="missing"
    )


def test_s3_rejects_malformed_provider_metadata() -> None:
    with pytest.raises(KnoraError, match="OBJECT_STORE_METADATA_INVALID"):
        S3ObjectStore(client=MalformedMetadataClient(), bucket="b").head(
            workspace_id="w1", object_key="k1"
        )


def test_s3_rejects_non_metadata_provider_result() -> None:
    with pytest.raises(KnoraError, match="OBJECT_STORE_METADATA_INVALID"):
        S3ObjectStore(client=NonMetadataClient(), bucket="b").head(
            workspace_id="w1", object_key="k1"
        )


def test_boto_s3_bootstrap_uses_path_style_for_s3_compatible_endpoints(monkeypatch) -> None:
    import sys
    import types

    captured = {}

    class Config:
        def __init__(self, *, signature_version, s3):
            self.signature_version = signature_version
            self.s3 = s3

    def fake_client(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return object()

    fake_boto3 = types.ModuleType("boto3")
    fake_boto3.client = fake_client
    fake_botocore_config = types.ModuleType("botocore.config")
    fake_botocore_config.Config = Config
    fake_botocore = types.ModuleType("botocore")
    fake_botocore.config = fake_botocore_config
    monkeypatch.setitem(sys.modules, "boto3", fake_boto3)
    monkeypatch.setitem(sys.modules, "botocore", fake_botocore)
    monkeypatch.setitem(sys.modules, "botocore.config", fake_botocore_config)
    BotoS3CapabilityClient(
        endpoint_url="http://minio:9000",
        region_name="us-east-1",
        access_key="access",
        secret_key="secret",
    )

    config = captured["kwargs"]["config"]
    assert config.signature_version == "s3v4"
    assert config.s3["addressing_style"] == "path"
