"""Pre-start control-plane contracts for canonical M3 evaluation runs."""

from __future__ import annotations

import json
import os
import secrets
import socket
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from evals.datasets.milestone_3 import Milestone3CorpusManifest
from evals.runners.milestone_3 import (
    EvaluationEnvironmentBinding,
    EvaluationEnvironmentSeal,
    ObservationFailure,
    SourceBinding,
)


class EvaluationWorkspaceGateway(Protocol):
    """Application/control-plane seam for idempotent evaluation Workspace ownership."""

    def provision_or_reuse(self, *, workspace_id: str, name: str) -> str: ...


class CorpusIngestionGateway(Protocol):
    def ingest(self, *, workspace_id: str, source_key: str, source_name: str,
               media_type: str, raw_content: bytes) -> object: ...


class EvaluationWorkspaceProvisioner(Protocol):
    def provision_or_reuse(self, *, workspace_id: str, name: str) -> str: ...

    def materialize_corpus(
        self, *, workspace_id: str, manifest: Milestone3CorpusManifest
    ) -> None: ...


@dataclass(slots=True)
class ProductionEvaluationWorkspaceProvisioner:
    """Concrete orchestrator over application seams; it never reaches into the database."""

    workspace_gateway: EvaluationWorkspaceGateway
    ingestion_gateway: CorpusIngestionGateway
    corpus_root: Path

    def provision_or_reuse(self, *, workspace_id: str, name: str = "Milestone 3 evaluation") -> str:
        return self.workspace_gateway.provision_or_reuse(
            workspace_id=workspace_id, name=name
        )

    def materialize_corpus(
        self, *, workspace_id: str, manifest: Milestone3CorpusManifest
    ) -> None:
        if manifest.workspace_id != workspace_id:
            raise ObservationFailure("CORPUS_WORKSPACE_MISMATCH")
        manifest_path = self.corpus_root / "manifest.json"
        import json as _json

        documents = _json.loads(manifest_path.read_text(encoding="utf-8"))["documents"]
        for document in documents:
            path = self.corpus_root / str(document["path"])
            self.ingestion_gateway.ingest(
                workspace_id=workspace_id,
                source_key=f"support/{path.stem}",
                source_name=path.name,
                media_type="text/plain",
                raw_content=path.read_bytes(),
            )


def ephemeral_minio_runtime() -> dict[str, str]:
    """Generate isolated MinIO credentials for an evaluation-owned topology."""
    return {
        "KNORA_CANONICAL_MINIO_ACCESS_KEY": f"m3-{secrets.token_urlsafe(18)}",
        "KNORA_CANONICAL_MINIO_SECRET_KEY": secrets.token_urlsafe(40),
    }


def inject_minio_runtime(values: dict[str, str]) -> None:
    required = {"KNORA_CANONICAL_MINIO_ACCESS_KEY", "KNORA_CANONICAL_MINIO_SECRET_KEY"}
    if set(values) != required or any(not value for value in values.values()):
        raise ValueError("invalid ephemeral MinIO runtime configuration")
    os.environ.update(values)


def choose_free_loopback_ports() -> dict[str, str]:
    """Reserve no sockets; return currently free loopback ports for Compose host bindings."""
    ports: dict[str, str] = {}
    for name in ("KNORA_EVAL_POSTGRES_HOST_PORT", "KNORA_EVAL_MINIO_HOST_PORT",
                 "KNORA_EVAL_MINIO_CONSOLE_PORT", "KNORA_EVAL_API_HOST_PORT"):
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            ports[name] = str(probe.getsockname()[1])
    os.environ.update(ports)
    return ports


class EphemeralCredentialIssuer(Protocol):
    def issue(self, *, workspace_id: str, key_id: str) -> str: ...


class ActiveCorpusReader(Protocol):
    def read_active_corpus(self, *, workspace_id: str) -> object: ...


@dataclass(frozen=True, slots=True)
class EphemeralEvaluationCredential:
    workspace_id: str
    key_id: str
    raw_key: str

    def startup_config(self) -> str:
        from knora.access.api_keys import hash_api_key

        return json.dumps(
            [
                {
                    "key_id": self.key_id,
                    "key_hash": hash_api_key(self.raw_key),
                    "workspace_id": self.workspace_id,
                    "enabled": True,
                }
            ],
            separators=(",", ":"),
        )


@dataclass(frozen=True, slots=True)
class BootstrapResult:
    binding: EvaluationEnvironmentBinding
    credential: EphemeralEvaluationCredential
    endpoint: str


class EvaluationEnvironmentBootstrap:
    """Prepare a sealed environment before the normal API process starts."""

    def __init__(
        self,
        *,
        workspace_provisioner: EvaluationWorkspaceProvisioner,
        corpus_reader: ActiveCorpusReader,
        seal: EvaluationEnvironmentSeal,
        endpoint: str,
        credential_issuer: EphemeralCredentialIssuer | None = None,
    ) -> None:
        self._workspace_provisioner = workspace_provisioner
        self._corpus_reader = corpus_reader
        self._seal = seal
        self._endpoint = endpoint
        self._credential_issuer = credential_issuer

    def prepare(
        self,
        *,
        binding: EvaluationEnvironmentBinding,
        manifest: Milestone3CorpusManifest,
        run_id: str,
    ) -> BootstrapResult:
        workspace_id = self._workspace_provisioner.provision_or_reuse(
            workspace_id=binding.workspace_id, name="Milestone 3 evaluation"
        )
        if workspace_id != binding.workspace_id:
            raise ObservationFailure("EVALUATION_WORKSPACE_BINDING_MISMATCH")
        self._workspace_provisioner.materialize_corpus(
            workspace_id=workspace_id, manifest=manifest
        )
        self._seal.acquire(run_id=run_id)
        corpus = self._corpus_reader.read_active_corpus(workspace_id=workspace_id)
        if not binding.source_bindings:
            expected_sources = {reference.rsplit("#", 1)[0] for reference in manifest.chunks}
            documents = getattr(corpus, "documents", ())
            if {getattr(item, "source_key", None) for item in documents} != expected_sources:
                raise ObservationFailure("CORPUS_CLOSURE_MISMATCH")
            binding = EvaluationEnvironmentBinding(
                dataset_manifest_identity=binding.dataset_manifest_identity,
                corpus_manifest_identity=binding.corpus_manifest_identity,
                chunk_set_provenance_id=binding.chunk_set_provenance_id,
                workspace_id=binding.workspace_id,
                retrieval_configuration_id=binding.retrieval_configuration_id,
                source_bindings=tuple(
                    SourceBinding(
                        source_key=item.source_key,
                        production_document_version_id=item.document_version_id,
                        production_chunk_set_id=item.chunk_set_id,
                    )
                    for item in sorted(documents, key=lambda value: value.source_key)
                ),
            )
        self._seal.capture_preflight(binding=binding, corpus=corpus, manifest=manifest)
        key_id = f"m3-{run_id}"
        raw_key = (
            self._credential_issuer.issue(workspace_id=workspace_id, key_id=key_id)
            if self._credential_issuer is not None
            else secrets.token_urlsafe(32)
        )
        credential = EphemeralEvaluationCredential(
            workspace_id=workspace_id, key_id=key_id, raw_key=raw_key
        )
        return BootstrapResult(binding=binding, credential=credential, endpoint=self._endpoint)


class ProductionRuntimeLauncher(Protocol):
    def start(self, *, startup_auth_config: str, endpoint: str) -> object: ...


@dataclass(slots=True)
class ProductionApiProcessLauncher:
    """Starts the normal uvicorn production entrypoint with startup-only auth config."""

    command: tuple[str, ...] = (
        "uvicorn", "knora.main:app", "--host", "127.0.0.1", "--port", "8000"
    )
    process: Any = None
    environment: dict[str, str] | None = None

    def start(self, *, startup_auth_config: str, endpoint: str) -> subprocess.Popen[bytes]:
        del endpoint
        env = os.environ.copy()
        env["KNORA_API_CREDENTIALS_JSON"] = startup_auth_config
        if self.environment:
            env.update(self.environment)
        self.process = subprocess.Popen(self.command, env=env)
        return self.process

    def stop(self) -> None:
        if self.process is not None:
            self.process.terminate()
            self.process.wait(timeout=30)
            self.process = None


def inject_startup_auth(credential: EphemeralEvaluationCredential) -> None:
    """Inject only the normal hash-bearing startup setting; raw key is never serialized."""
    os.environ["KNORA_API_CREDENTIALS_JSON"] = credential.startup_config()


def inject_evaluation_runtime(credential: EphemeralEvaluationCredential, endpoint: str) -> None:
    """Set ephemeral evaluator handoff and production endpoint without persisting secrets."""
    inject_startup_auth(credential)
    os.environ["KNORA_EVALUATION_API_KEY"] = credential.raw_key
    os.environ["KNORA_EVALUATION_ENDPOINT"] = endpoint


def teardown_evaluation_runtime() -> None:
    os.environ.pop("KNORA_API_CREDENTIALS_JSON", None)
    os.environ.pop("KNORA_EVALUATION_API_KEY", None)
    os.environ.pop("KNORA_EVALUATION_ENDPOINT", None)
    os.environ.pop("KNORA_CANONICAL_MINIO_ACCESS_KEY", None)
    os.environ.pop("KNORA_CANONICAL_MINIO_SECRET_KEY", None)
