import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest
from evals.runners.evaluation_ownership import SqliteEvaluationOwnershipStore
from evals.runners.m3_bootstrap import (
    EphemeralEvaluationCredential,
    EvaluationEnvironmentBootstrap,
    ProductionEvaluationWorkspaceProvisioner,
    ephemeral_minio_runtime,
    inject_minio_runtime,
    inject_startup_auth,
    teardown_evaluation_runtime,
)
from evals.runners.milestone_3 import (
    EvaluationEnvironmentBinding,
    EvaluationEnvironmentSeal,
    ObservationFailure,
)


def _binding():
    from evals.runners.milestone_3 import EvaluationEnvironmentBinding, SourceBinding

    return EvaluationEnvironmentBinding(
        dataset_manifest_identity="m3-dataset-v1",
        corpus_manifest_identity="m3-corpus-v1",
        chunk_set_provenance_id="set-1",
        workspace_id="workspace",
        retrieval_configuration_id="retrieval-m3-rrf-v1",
        source_bindings=(SourceBinding("support/a", "version-1", "set-1"),),
    )


def _manifest():
    return SimpleNamespace(
        version="m3-corpus-v1", workspace_id="workspace", chunk_set_id="set-1",
        chunks=frozenset({"support/a#0"}),
    )


def _corpus():
    return SimpleNamespace(
        workspace_id="workspace",
        documents=(SimpleNamespace(
            source_key="support/a", document_version_id="version-1", chunk_set_id="set-1",
            chunk_references=("support/a#0",),
        ),),
    )


def test_credential_startup_config_contains_hash_only_and_not_raw_key(monkeypatch):
    credential = EphemeralEvaluationCredential("workspace", "key-1", "raw-secret")
    inject_startup_auth(credential)
    config = os.getenv("KNORA_API_CREDENTIALS_JSON")
    assert config is not None
    assert "raw-secret" not in config
    assert "sha256:" in config
    assert json.loads(config)[0]["workspace_id"] == "workspace"


def test_bootstrap_acquires_seal_before_authoritative_preflight(tmp_path: Path):
    events: list[str] = []
    seal = EvaluationEnvironmentSeal(
        ownership_store=SqliteEvaluationOwnershipStore(
            path=tmp_path / "ownership.sqlite3"
        ),
        owner_id="bootstrap",
    )
    bootstrap = EvaluationEnvironmentBootstrap(
        workspace_provisioner=SimpleNamespace(
            provision_or_reuse=lambda **kwargs: events.append("workspace") or "workspace",
            materialize_corpus=lambda **kwargs: None,
        ),
        corpus_reader=SimpleNamespace(
            read_active_corpus=lambda **kwargs: events.append("closure") or _corpus()
        ),
        seal=seal,
        endpoint="http://127.0.0.1:8000/v1/questions",
    )
    result = bootstrap.prepare(binding=_binding(), manifest=_manifest(), run_id="run-1")
    assert events == ["workspace", "closure"]
    assert seal.ownership_snapshot().owner_id == "bootstrap"
    assert result.endpoint.endswith("/v1/questions")
    seal.release()


def test_bootstrap_releases_ownership_when_binding_preflight_fails(tmp_path: Path):
    path = tmp_path / "ownership.sqlite3"
    seal = EvaluationEnvironmentSeal(
        ownership_store=SqliteEvaluationOwnershipStore(path=path), owner_id="first"
    )
    bootstrap = EvaluationEnvironmentBootstrap(
        workspace_provisioner=SimpleNamespace(
            provision_or_reuse=lambda **kwargs: "workspace",
            materialize_corpus=lambda **kwargs: None,
        ),
        corpus_reader=SimpleNamespace(read_active_corpus=lambda **kwargs: _corpus()),
        seal=seal,
        endpoint="http://127.0.0.1:8000/v1/questions",
    )
    mismatched = EvaluationEnvironmentBinding(
        dataset_manifest_identity="m3-dataset-v1",
        corpus_manifest_identity="wrong-corpus",
        chunk_set_provenance_id="set-1",
        workspace_id="workspace",
        retrieval_configuration_id="retrieval-m3-rrf-v1",
        source_bindings=(),
    )

    with pytest.raises(ObservationFailure, match="CORPUS_CLOSURE_MISMATCH"):
        bootstrap.prepare(binding=mismatched, manifest=_manifest(), run_id="run-1")

    second = EvaluationEnvironmentSeal(
        ownership_store=SqliteEvaluationOwnershipStore(path=path), owner_id="second"
    )
    capability = second.acquire(run_id="run-1")
    assert capability.fencing_version == 2
    second.release()


def test_production_provisioner_materializes_every_manifest_document(tmp_path: Path):
    (tmp_path / "manifest.json").write_text(json.dumps({"documents": [
        {"path": "refund-policy.txt"}, {"path": "shipping-policy.txt"}
    ]}), encoding="utf-8")
    (tmp_path / "refund-policy.txt").write_text("refund", encoding="utf-8")
    (tmp_path / "shipping-policy.txt").write_text("shipping", encoding="utf-8")
    calls: list[tuple[str, str]] = []
    provisioner = ProductionEvaluationWorkspaceProvisioner(
        workspace_gateway=SimpleNamespace(
            provision_or_reuse=lambda **kwargs: kwargs["workspace_id"]
        ),
        ingestion_gateway=SimpleNamespace(
            ingest=lambda **kwargs: calls.append((kwargs["source_key"], kwargs["media_type"]))
        ),
        corpus_root=tmp_path,
    )
    provisioner.materialize_corpus(workspace_id="workspace", manifest=_manifest())
    assert calls == [
        ("support/refund-policy", "text/plain"),
        ("support/shipping-policy", "text/plain"),
    ]
    teardown_evaluation_runtime()


def test_minio_runtime_is_ephemeral_and_injected(monkeypatch):
    values = ephemeral_minio_runtime()
    inject_minio_runtime(values)
    assert os.environ["KNORA_CANONICAL_MINIO_ACCESS_KEY"] == values[
        "KNORA_CANONICAL_MINIO_ACCESS_KEY"
    ]
    assert len(values["KNORA_CANONICAL_MINIO_SECRET_KEY"]) >= 40
    teardown_evaluation_runtime()
