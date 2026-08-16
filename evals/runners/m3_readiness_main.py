"""Executable composition root for the canonical M3 readiness smoke."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from evals.datasets.milestone_3 import (
    load_milestone_3_corpus_manifest,
    load_milestone_3_dataset,
)
from evals.runners.evaluation_ownership import SqliteEvaluationOwnershipStore
from evals.runners.m3_bootstrap import (
    ProductionApiProcessLauncher,
    ProductionEvaluationWorkspaceProvisioner,
    choose_free_loopback_ports,
    ephemeral_minio_runtime,
)
from evals.runners.m3_readiness import run_readiness
from evals.runners.milestone_3 import EvaluationEnvironmentBinding, EvaluationEnvironmentSeal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from knora.adapters.postgres.evaluation_reader import PostgresEvaluationReader
from knora.adapters.postgres.ingestion_store import PostgresIngestionStore
from knora.application.evaluation_environment import (
    ApplicationEvaluationCorpusGateway,
    PostgresEvaluationWorkspaceGateway,
)
from knora.bootstrap import build_provider_selection
from knora.ingestion.module import IngestDocument
from knora.ingestion.processing import DocumentProcessor


@dataclass(frozen=True, slots=True)
class RuntimeTopology:
    project: str
    database_url: str
    api_endpoint: str
    minio_endpoint: str


def _migration(topology: RuntimeTopology) -> None:
    env = os.environ.copy()
    env["KNORA_DATABASE_URL"] = topology.database_url
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"],
        env=env,
        cwd="backend",
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        raise RuntimeError("alembic migration failed")


def build_topology(project: str) -> RuntimeTopology:
    ports = choose_free_loopback_ports()
    postgres = ports["KNORA_EVAL_POSTGRES_HOST_PORT"]
    minio = ports["KNORA_EVAL_MINIO_HOST_PORT"]
    api = ports["KNORA_EVAL_API_HOST_PORT"]
    return RuntimeTopology(
        project=project,
        database_url=f"postgresql+psycopg://knora:knora@127.0.0.1:{postgres}/knora",
        api_endpoint=f"http://127.0.0.1:{api}/v1/questions",
        minio_endpoint=f"http://127.0.0.1:{minio}",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", default="issue51-m3")
    args = parser.parse_args()
    topology = build_topology(args.project)
    compose_env = os.environ.copy()
    compose_env.update({
        "KNORA_DATABASE_URL": topology.database_url,
        "KNORA_EVAL_POSTGRES_HOST_PORT": topology.database_url.rsplit(":", 1)[1].split("/", 1)[0],
        "KNORA_EVAL_MINIO_HOST_PORT": topology.minio_endpoint.rsplit(":", 1)[1],
        "KNORA_EVAL_API_HOST_PORT": topology.api_endpoint.split(":", 2)[2].split("/", 1)[0],
        "KNORA_OBJECT_STORE_S3_ENDPOINT": topology.minio_endpoint,
        **ephemeral_minio_runtime(),
    })
    subprocess.run(
        [
            "docker", "compose", "-p", topology.project,
            "up", "-d", "postgres", "minio", "minio-init",
        ],
        env=compose_env,
        check=True,
    )
    try:
        _migration(topology)
        from knora.infrastructure.settings import Settings
        runtime_settings = Settings(_env_file=None, database_url=topology.database_url)
        providers = build_provider_selection(runtime_settings)
        session_factory = sessionmaker(
            bind=create_engine(topology.database_url, pool_pre_ping=True), expire_on_commit=False
        )
        ingestion = IngestDocument(
            processor=DocumentProcessor(), embedding_provider=providers.embedding_provider,
            store=PostgresIngestionStore(session_factory),
        )
        gateway = ProductionEvaluationWorkspaceProvisioner(
            workspace_gateway=PostgresEvaluationWorkspaceGateway(session_factory),
            ingestion_gateway=ApplicationEvaluationCorpusGateway(
                ingestion, providers.embedding_configuration
            ),
            corpus_root=Path("evals/corpora/milestone_3"),
        )
        manifest = load_milestone_3_corpus_manifest(Path("evals/corpora/milestone_3/manifest.json"))
        dataset = load_milestone_3_dataset(Path("evals/datasets/milestone_3.jsonl"))
        cases = [item for item in dataset.cases if item.expected_behavior == "ANSWER"]
        if os.environ.get("KNORA_M3_DIAGNOSTIC_CASE"):
            cases = [item for item in cases if item.id == os.environ["KNORA_M3_DIAGNOSTIC_CASE"]]
        if not cases:
            raise RuntimeError("diagnostic case selection is empty")
        case = cases[0]
        binding = EvaluationEnvironmentBinding(
            dataset_manifest_identity="m3-dataset-v1", corpus_manifest_identity=manifest.version,
            chunk_set_provenance_id=manifest.chunk_set_id, workspace_id=manifest.workspace_id,
            retrieval_configuration_id="retrieval-m3-rrf-v1",
        )
        reader = PostgresEvaluationReader(session_factory)
        ownership_path = Path(
            os.environ.get(
                "KNORA_M3_OWNERSHIP_STORE",
                str(Path(tempfile.gettempdir()) / f"{args.project}-ownership.sqlite3"),
            )
        )
        seal = EvaluationEnvironmentSeal(
            ownership_store=SqliteEvaluationOwnershipStore(path=ownership_path)
        )
        from evals.runners.m3_bootstrap import EvaluationEnvironmentBootstrap
        bootstrap = EvaluationEnvironmentBootstrap(
            workspace_provisioner=gateway, corpus_reader=reader, seal=seal,
            endpoint=topology.api_endpoint,
        )
        evidence = run_readiness(
            bootstrap=bootstrap, binding=binding, manifest=manifest, case=case,
            trace_reader=reader, seal=seal,
            launcher=ProductionApiProcessLauncher(
                command=(sys.executable, "-m", "uvicorn", "knora.main:app", "--host", "127.0.0.1",
                         "--port", topology.api_endpoint.rsplit(":", 1)[1].split("/", 1)[0]),
                environment={
                    "KNORA_DATABASE_URL": topology.database_url,
                    "KNORA_OBJECT_STORE_BACKEND": "s3_compatible",
                    "KNORA_OBJECT_STORE_S3_ENDPOINT": topology.minio_endpoint,
                    "KNORA_OBJECT_STORE_S3_BUCKET": "knora",
                    "KNORA_CANONICAL_MINIO_ACCESS_KEY": compose_env[
                        "KNORA_CANONICAL_MINIO_ACCESS_KEY"
                    ],
                    "KNORA_CANONICAL_MINIO_SECRET_KEY": compose_env[
                        "KNORA_CANONICAL_MINIO_SECRET_KEY"
                    ],
                    "KNORA_OBJECT_STORE_S3_ACCESS_KEY": compose_env[
                        "KNORA_CANONICAL_MINIO_ACCESS_KEY"
                    ],
                    "KNORA_OBJECT_STORE_S3_SECRET_KEY": compose_env[
                        "KNORA_CANONICAL_MINIO_SECRET_KEY"
                    ],
                    "KNORA_RETRIEVAL_CONFIGURATION_ID": "retrieval-m3-rrf-v1",
                },
            ),
        )
        print(json.dumps({
            "phases": evidence.phases,
            "workspace_id": evidence.workspace_id,
            "trace_id": evidence.trace_id,
            "candidate_count": evidence.candidate_count,
            "retrieval_configuration_id": evidence.retrieval_configuration_id,
            "source_bindings_verified": evidence.source_bindings_verified,
            "retrieval_latency_ms": evidence.retrieval_latency_ms,
            "end_to_end_latency_ms": evidence.end_to_end_latency_ms,
            "candidate_triples": evidence.candidate_triples,
            "citation_matrix": evidence.citation_matrix,
            "semantic_input": evidence.semantic_input,
            "retrieval_provenance": evidence.retrieval_provenance,
            "active_corpus": evidence.active_corpus,
        }, ensure_ascii=True))
        return 0
    finally:
        subprocess.run(
            ["docker", "compose", "-p", topology.project, "down", "--remove-orphans"],
            env=compose_env,
            check=False,
        )


if __name__ == "__main__":
    raise SystemExit(main())
