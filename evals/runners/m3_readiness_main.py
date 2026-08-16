"""Executable composition root for the canonical M3 readiness smoke."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from dataclasses import dataclass, replace
from pathlib import Path

import httpx

_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
_WORKTREE_BACKEND_SOURCE = _REPOSITORY_ROOT / "backend" / "src"
for _source_path in (_REPOSITORY_ROOT, _WORKTREE_BACKEND_SOURCE):
    if _source_path.is_dir() and str(_source_path) not in sys.path:
        sys.path.insert(0, str(_source_path))

from evals.datasets.milestone_3 import (  # noqa: E402, I001
    Milestone3Case,
    load_milestone_3_corpus_manifest,
    load_milestone_3_dataset,
)
from evals.runners.m3_bootstrap import (  # noqa: E402
    ProductionApiProcessLauncher,
    ProductionEvaluationWorkspaceProvisioner,
    choose_free_loopback_ports,
    ephemeral_minio_runtime,
)
from evals.runners.m3_readiness import ReadinessFailure, run_readiness  # noqa: E402
from evals.runners.milestone_3 import EvaluationEnvironmentBinding, EvaluationEnvironmentSeal  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from knora.adapters.postgres.evaluation_reader import PostgresEvaluationReader  # noqa: E402
from knora.adapters.postgres.ingestion_store import PostgresIngestionStore  # noqa: E402
from knora.answering.retrieval_configuration import CALIBRATED_M3_VECTOR_MIN_SIMILARITY  # noqa: E402
from knora.application.evaluation_environment import (  # noqa: E402
    ApplicationEvaluationCorpusGateway,
    PostgresEvaluationWorkspaceGateway,
)
from knora.bootstrap import build_provider_selection  # noqa: E402
from knora.ingestion.module import IngestDocument  # noqa: E402
from knora.ingestion.processing import DocumentProcessor  # noqa: E402


def current_source_pythonpath() -> str:
    """Pin production subprocess imports to this worktree's source tree."""
    inherited = os.environ.get("PYTHONPATH")
    paths = [str(_WORKTREE_BACKEND_SOURCE)]
    if inherited:
        paths.append(inherited)
    return os.pathsep.join(paths)


@dataclass(frozen=True, slots=True)
class RuntimeTopology:
    project: str
    database_url: str
    api_endpoint: str
    minio_endpoint: str


@dataclass(frozen=True, slots=True)
class DiagnosticCase:
    """Non-scoring readiness input; it is not a Milestone 3 dataset case."""

    id: str
    workspace_id: str
    question: str
    expected_behavior: str
    refusal_expectation: str | None


class TraceFaultInjectingReader:
    """Acceptance-only fault seam that preserves the real trace reader boundary."""

    _MODES = {
        "none",
        "missing",
        "response-trace-id-mismatch",
        "workspace-mismatch",
        "unauthorized",
    }

    def __init__(self, reader, *, mode: str = "none") -> None:
        if mode not in self._MODES:
            raise ValueError("unsupported trace fault mode")
        self._reader = reader
        self._mode = mode

    def read_trace(self, *, trace_id: str, workspace_id: str):
        if self._mode == "missing":
            raise LookupError("injected missing evaluation trace")
        if self._mode == "unauthorized":
            return self._reader.read_trace(
                trace_id=trace_id, workspace_id=f"unauthorized-{workspace_id}"
            )
        trace = self._reader.read_trace(trace_id=trace_id, workspace_id=workspace_id)
        if self._mode == "response-trace-id-mismatch":
            return replace(trace, trace_id=f"mismatched-{trace_id}")
        if self._mode == "workspace-mismatch":
            return replace(trace, workspace_id=f"mismatched-{workspace_id}")
        return trace


class ResponseFaultInjectingPost:
    """Acceptance-only response fault seam at the normal HTTP client boundary."""

    _MODES = {"none", "malformed-refusal"}

    def __init__(self, post, *, mode: str = "none") -> None:
        if mode not in self._MODES:
            raise ValueError("unsupported response fault mode")
        self._post = post
        self._mode = mode

    def __call__(self, url: str, **kwargs: object) -> httpx.Response:
        response = self._post(url, **kwargs)
        if self._mode == "none":
            return response
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("response fault requires a JSON object")
        malformed = {
            **payload,
            "decision": "REFUSAL",
            "answer": "malformed",
            "citations": [],
            "refusal_reason": "INSUFFICIENT_EVIDENCE",
        }
        return httpx.Response(
            response.status_code,
            headers=response.headers,
            json=malformed,
            request=response.request,
        )


class PostgresEvaluationOwnershipProbe:
    """Hold a PostgreSQL session-level advisory lock for one evaluation run."""

    def __init__(self, engine) -> None:
        self._engine = engine
        self._connection = None
        self._lock_key: int | None = None

    def __call__(self, run_id: str) -> bool:
        if not run_id or self._connection is not None:
            return False
        connection = self._engine.connect()
        lock_key = int.from_bytes(
            hashlib.sha256(b"knora-m3-evaluation-seal").digest()[:8],
            byteorder="big",
            signed=True,
        )
        try:
            acquired = bool(
                connection.execute(
                    text("SELECT pg_try_advisory_lock(:lock_key)"),
                    {"lock_key": lock_key},
                ).scalar()
            )
            connection.commit()
        except Exception:
            connection.close()
            raise
        if not acquired:
            connection.close()
            return False
        self._connection = connection
        self._lock_key = lock_key
        return True

    def release(self) -> None:
        connection = self._connection
        self._connection = None
        lock_key = self._lock_key
        self._lock_key = None
        if connection is None:
            return
        try:
            connection.execute(
                text("SELECT pg_advisory_unlock(:lock_key)"),
                {"lock_key": lock_key},
            )
            connection.commit()
        finally:
            connection.close()


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


def build_diagnostic_case(
    *, workspace_id: str, case_id: str, question: str, behavior: str
) -> DiagnosticCase:
    if not case_id or not question:
        raise ValueError("diagnostic case id and question must be non-empty")
    if behavior not in {"ANSWER", "REFUSAL"}:
        raise ValueError("diagnostic behavior must be ANSWER or REFUSAL")
    return DiagnosticCase(
        id=case_id,
        workspace_id=workspace_id,
        question=question,
        expected_behavior=behavior,
        refusal_expectation=(None if behavior == "ANSWER" else "INSUFFICIENT_EVIDENCE"),
    )


def select_diagnostic_case(
    cases: tuple[Milestone3Case, ...] | list[Milestone3Case],
    *,
    workspace_id: str,
    case_id: str | None,
    question: str | None,
    behavior: str,
) -> Milestone3Case | DiagnosticCase:
    if question is not None:
        return build_diagnostic_case(
            workspace_id=workspace_id,
            case_id=case_id or "diagnostic",
            question=question,
            behavior=behavior,
        )
    if case_id:
        for case in cases:
            if case.id == case_id:
                return case
        raise ValueError("diagnostic case selection is empty")
    try:
        return next(case for case in cases if case.expected_behavior == behavior)
    except StopIteration as error:
        raise ValueError("diagnostic case selection is empty") from error


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", default="issue51-m3")
    parser.add_argument(
        "--retrieval-configuration",
        default=os.environ.get("KNORA_M3_RETRIEVAL_CONFIGURATION", "retrieval-m3-rrf-v1"),
    )
    parser.add_argument(
        "--diagnostic-case",
        default=os.environ.get("KNORA_M3_DIAGNOSTIC_CASE"),
    )
    parser.add_argument(
        "--diagnostic-question",
        default=os.environ.get("KNORA_M3_DIAGNOSTIC_QUESTION"),
    )
    parser.add_argument(
        "--diagnostic-behavior",
        choices=("ANSWER", "REFUSAL"),
        default=os.environ.get("KNORA_M3_DIAGNOSTIC_BEHAVIOR", "ANSWER"),
    )
    parser.add_argument(
        "--trace-fault",
        choices=(
            "none",
            "missing",
            "response-trace-id-mismatch",
            "workspace-mismatch",
            "unauthorized",
        ),
        default="none",
    )
    parser.add_argument(
        "--response-fault",
        choices=("none", "malformed-refusal"),
        default="none",
    )
    args = parser.parse_args()
    runtime_overrides = {
        "KNORA_RETRIEVAL_CONFIGURATION_ID": args.retrieval_configuration,
    }
    if args.retrieval_configuration in {"retrieval-m3-vector-v2", "retrieval-m3-rrf-v2"}:
        runtime_overrides["KNORA_VECTOR_MIN_SIMILARITY"] = str(
            CALIBRATED_M3_VECTOR_MIN_SIMILARITY
        )
    topology = build_topology(args.project)
    compose_env = os.environ.copy()
    compose_env.update({
        "KNORA_DATABASE_URL": topology.database_url,
        "KNORA_EVAL_POSTGRES_HOST_PORT": topology.database_url.rsplit(":", 1)[1].split("/", 1)[0],
        "KNORA_EVAL_MINIO_HOST_PORT": topology.minio_endpoint.rsplit(":", 1)[1],
        "KNORA_EVAL_API_HOST_PORT": topology.api_endpoint.split(":", 2)[2].split("/", 1)[0],
        "KNORA_OBJECT_STORE_S3_ENDPOINT": topology.minio_endpoint,
        **runtime_overrides,
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
        previous_runtime = {
            name: os.environ.get(name) for name in runtime_overrides
        }
        os.environ.update(runtime_overrides)
        _migration(topology)
        from knora.infrastructure.settings import Settings
        runtime_settings = Settings(_env_file=None, database_url=topology.database_url)
        providers = build_provider_selection(runtime_settings)
        engine = create_engine(topology.database_url, pool_pre_ping=True)
        session_factory = sessionmaker(bind=engine, expire_on_commit=False)
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
        case = select_diagnostic_case(
            dataset.cases,
            workspace_id=manifest.workspace_id,
            case_id=args.diagnostic_case,
            question=args.diagnostic_question,
            behavior=args.diagnostic_behavior,
        )
        binding = EvaluationEnvironmentBinding(
            dataset_manifest_identity="m3-dataset-v1", corpus_manifest_identity=manifest.version,
            chunk_set_provenance_id=manifest.chunk_set_id, workspace_id=manifest.workspace_id,
            retrieval_configuration_id=args.retrieval_configuration,
            embedding_configuration_id=providers.embedding_configuration.id,
        )
        reader = PostgresEvaluationReader(session_factory)
        seal = EvaluationEnvironmentSeal(ownership_probe=PostgresEvaluationOwnershipProbe(engine))
        from evals.runners.m3_bootstrap import EvaluationEnvironmentBootstrap
        bootstrap = EvaluationEnvironmentBootstrap(
            workspace_provisioner=gateway, corpus_reader=reader, seal=seal,
            endpoint=topology.api_endpoint,
        )
        trace_reader = TraceFaultInjectingReader(reader, mode=args.trace_fault)
        try:
            evidence = run_readiness(
                bootstrap=bootstrap, binding=binding, manifest=manifest, case=case,
                trace_reader=trace_reader, seal=seal,
                post_question=ResponseFaultInjectingPost(
                    httpx.post, mode=args.response_fault
                ),
                launcher=ProductionApiProcessLauncher(
                command=(sys.executable, "-m", "uvicorn", "knora.main:app", "--host", "127.0.0.1",
                         "--port", topology.api_endpoint.rsplit(":", 1)[1].split("/", 1)[0]),
                environment={
                    "PYTHONPATH": current_source_pythonpath(),
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
                    **runtime_overrides,
                },
                ),
            )
        except ReadinessFailure as error:
            if args.trace_fault == "none" and args.response_fault == "none":
                raise
            print(json.dumps({
                "status": "EXPECTED_OBSERVATION_FAILURE",
                "trace_fault": args.trace_fault,
                "response_fault": args.response_fault,
                "phase": error.phase,
                "reason": error.reason,
            }, ensure_ascii=True))
            return 0
        print(json.dumps({
            "phases": evidence.phases,
            "workspace_id": evidence.workspace_id,
            "trace_id": evidence.trace_id,
            "diagnostic_case_id": case.id,
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
            "candidate_decisions": evidence.candidate_decisions,
            "branch_observations": evidence.branch_observations,
            "decision": evidence.decision,
            "answer": evidence.answer,
            "refusal_reason": evidence.refusal_reason,
            "parsed_markers": evidence.parsed_markers,
        }, ensure_ascii=True))
        return 0
    finally:
        for name, value in previous_runtime.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        subprocess.run(
            ["docker", "compose", "-p", topology.project, "down", "--remove-orphans"],
            env=compose_env,
            check=False,
        )


if __name__ == "__main__":
    raise SystemExit(main())
