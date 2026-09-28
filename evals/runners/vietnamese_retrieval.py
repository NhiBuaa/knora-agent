"""Provenance-checked Vietnamese retrieval measurements."""

import argparse
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import fmean
from time import perf_counter
from uuid import uuid4

import httpx
from evals.datasets.vietnamese_rag_v1 import VietnameseDataset, load_vietnamese_dataset
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from knora.adapters.postgres.answering_store import PostgresAnsweringStore
from knora.adapters.postgres.tables import (
    ChunkSetTable,
    ChunkTable,
    DocumentTable,
    DocumentVersionTable,
    EmbeddingSetTable,
)
from knora.answering.stores import RetrievalConfiguration
from knora.providers.ollama.embedding import (
    OllamaEmbeddingProvider,
    resolve_ollama_embedding_configuration,
)


@dataclass(frozen=True, slots=True)
class ActiveChunkBinding:
    source_key: str
    source_sha256: str
    chunk_set_id: str
    profile_id: str
    page_start: int | None
    checksum: str


def validate_active_corpus(
    dataset: VietnameseDataset, chunks: tuple[ActiveChunkBinding, ...]
) -> None:
    if not chunks:
        raise ValueError("active corpus is empty")
    if {item.profile_id for item in chunks} != {dataset.profile_id}:
        raise ValueError("active profile mismatch")
    if {item.source_sha256 for item in chunks} != {dataset.corpus_sha256}:
        raise ValueError("active corpus mismatch")
    if {item.chunk_set_id for item in chunks} != set(dataset.chunk_set_ids):
        raise ValueError("active chunk set mismatch")
    bound = {(item.source_key, item.page_start, item.checksum) for item in chunks}
    for case in dataset.cases:
        if case.expected_behavior == "ANSWER" and not any(
            (case.source_key, case.page_start, checksum) in bound
            for checksum in case.acceptable_chunk_checksums
        ):
            raise ValueError(f"case {case.id} label is absent from active corpus")


@dataclass(frozen=True, slots=True)
class CandidateObservation:
    source_key: str
    page_start: int | None
    checksum: str
    similarity: float


@dataclass(frozen=True, slots=True)
class RetrievalObservation:
    case_id: str
    observation_id: str
    source: str
    profile_id: str
    corpus_sha256: str
    retrieval_configuration_id: str
    chunk_set_ids: tuple[str, ...]
    candidates: tuple[CandidateObservation, ...]
    insufficient_evidence: bool
    latency_ms: float


@dataclass(frozen=True, slots=True)
class CaseResult:
    case_id: str
    split: str
    expected_behavior: str
    observation_id: str
    observation_source: str
    expected_source_key: str
    expected_page_start: int | None
    expected_chunk_checksums: tuple[str, ...]
    selected_provenance: tuple[tuple[str, int | None, str], ...]
    first_relevant_rank: int | None
    insufficient_evidence: bool
    latency_ms: float


@dataclass(frozen=True, slots=True)
class RetrievalReport:
    dataset_sha256: str
    profile_id: str
    corpus_sha256: str
    retrieval_configuration_id: str
    hit_at_1: float
    hit_at_5: float
    mrr: float
    false_insufficient_evidence_count: int | None
    negative_refusal_rate: float | None
    mean_latency_ms: float
    cases: tuple[CaseResult, ...]

    def as_mapping(self) -> dict[str, object]:
        return asdict(self)


def evaluate_retrieval(
    dataset: VietnameseDataset,
    observations: tuple[RetrievalObservation, ...] | list[RetrievalObservation],
) -> RetrievalReport:
    by_id = {}
    observation_ids = set()
    for observation in observations:
        if not observation.observation_id or observation.observation_id in observation_ids:
            raise ValueError("missing or duplicate observation ID")
        observation_ids.add(observation.observation_id)
        if observation.case_id in by_id:
            raise ValueError("duplicate case observation")
        if observation.profile_id != dataset.profile_id:
            raise ValueError("profile mismatch")
        if observation.corpus_sha256 != dataset.corpus_sha256:
            raise ValueError("corpus mismatch")
        if observation.retrieval_configuration_id != dataset.retrieval_configuration_id:
            raise ValueError("retrieval configuration mismatch")
        if set(observation.chunk_set_ids) != set(dataset.chunk_set_ids):
            raise ValueError("chunk set mismatch")
        if observation.source not in {"production_trace", "answering_store_diagnostic"}:
            raise ValueError("unknown observation source")
        if observation.latency_ms < 0:
            raise ValueError("negative latency")
        by_id[observation.case_id] = observation
    case_ids = {case.id for case in dataset.cases}
    if case_ids != set(by_id):
        raise ValueError("missing or unexpected case observation")
    results = []
    for case in dataset.cases:
        observation = by_id[case.id]
        relevant = set(case.acceptable_chunk_checksums)
        first_rank = next(
            (
                rank
                for rank, candidate in enumerate(observation.candidates, 1)
                if candidate.source_key == case.source_key
                and candidate.page_start == case.page_start
                and candidate.checksum in relevant
            ),
            None,
        )
        results.append(
            CaseResult(
                case.id,
                case.split,
                case.expected_behavior,
                observation.observation_id,
                observation.source,
                case.source_key,
                case.page_start,
                case.acceptable_chunk_checksums,
                tuple(
                    (candidate.source_key, candidate.page_start, candidate.checksum)
                    for candidate in observation.candidates[:5]
                ),
                first_rank,
                observation.insufficient_evidence,
                observation.latency_ms,
            )
        )
    positives = [item for item in results if item.expected_behavior == "ANSWER"]
    negatives = [item for item in results if item.expected_behavior == "REFUSAL"]
    if not positives or not negatives:
        raise ValueError("answer and refusal observations are both required")
    thresholded_trace = all(item.source == "production_trace" for item in observations)
    return RetrievalReport(
        dataset.dataset_sha256,
        dataset.profile_id,
        dataset.corpus_sha256,
        dataset.retrieval_configuration_id,
        fmean(item.first_relevant_rank == 1 for item in positives),
        fmean(
            item.first_relevant_rank is not None and item.first_relevant_rank <= 5
            for item in positives
        ),
        fmean(
            1 / item.first_relevant_rank if item.first_relevant_rank else 0 for item in positives
        ),
        sum(item.insufficient_evidence for item in positives) if thresholded_trace else None,
        fmean(item.insufficient_evidence for item in negatives) if thresholded_trace else None,
        fmean(item.latency_ms for item in results),
        tuple(results),
    )


def load_active_bindings(
    session_factory: sessionmaker, workspace_id: str
) -> tuple[ActiveChunkBinding, ...]:
    statement = (
        select(
            DocumentTable.source_key,
            DocumentVersionTable.raw_sha256,
            ChunkSetTable.id,
            EmbeddingSetTable.embedding_configuration_id,
            ChunkTable.page_start,
            ChunkTable.content_checksum,
        )
        .join(EmbeddingSetTable, DocumentTable.active_embedding_set_id == EmbeddingSetTable.id)
        .join(ChunkSetTable, EmbeddingSetTable.chunk_set_id == ChunkSetTable.id)
        .join(DocumentVersionTable, ChunkSetTable.document_version_id == DocumentVersionTable.id)
        .join(ChunkTable, ChunkTable.chunk_set_id == ChunkSetTable.id)
        .where(
            DocumentTable.workspace_id == workspace_id,
            DocumentTable.archived.is_(False),
            EmbeddingSetTable.status == "completed",
        )
        .order_by(DocumentTable.id, ChunkTable.ordinal)
    )
    with session_factory() as session:
        return tuple(ActiveChunkBinding(*row) for row in session.execute(statement))


def collect_live_observations(
    dataset: VietnameseDataset,
    *,
    workspace_id: str,
    session_factory: sessionmaker,
    ollama_url: str,
    model: str,
) -> tuple[RetrievalObservation, ...]:
    validate_active_corpus(dataset, load_active_bindings(session_factory, workspace_id))
    with httpx.Client(base_url=ollama_url, timeout=60) as client:
        profile = resolve_ollama_embedding_configuration(client, model)
        if profile.id != dataset.profile_id or not profile.deployment_identity.endswith(
            dataset.model_digest
        ):
            raise ValueError("deployed Qwen profile differs from dataset")
        provider = OllamaEmbeddingProvider(client=client)
        store = PostgresAnsweringStore(session_factory)
        diagnostic = RetrievalConfiguration(
            id=dataset.retrieval_configuration_id,
            candidate_k=16,
            min_similarity=-1.0,
            max_evidence_chunks=5,
            max_evidence_tokens=3000,
            overlap_policy="adjacent-token-overlap-v1",
            vector_candidate_k=16,
        )
        observations = []
        for case in dataset.cases:
            query_vector = provider.embed_queries([case.question], profile).vectors[0]
            started = perf_counter()
            result = store.retrieve_candidates(
                workspace_id=workspace_id,
                query_text=case.question,
                query_vector=query_vector,
                embedding_configuration=profile,
                retrieval_configuration=diagnostic,
            )
            latency_ms = (perf_counter() - started) * 1000
            if set(result.chunk_set_ids) != set(dataset.chunk_set_ids):
                raise ValueError("retrieval chunk set differs from dataset")
            observations.append(
                RetrievalObservation(
                    case_id=case.id,
                    observation_id=f"store-diagnostic-{uuid4()}",
                    source="answering_store_diagnostic",
                    profile_id=profile.id,
                    corpus_sha256=dataset.corpus_sha256,
                    retrieval_configuration_id=diagnostic.id,
                    chunk_set_ids=result.chunk_set_ids,
                    candidates=tuple(
                        CandidateObservation(
                            source_key=item.source_key,
                            page_start=item.page_start,
                            checksum=item.content_checksum,
                            similarity=item.similarity,
                        )
                        for item in result.candidates
                    ),
                    insufficient_evidence=not bool(result.candidates),
                    latency_ms=latency_ms,
                )
            )
        return tuple(observations)


def main() -> None:
    parser = argparse.ArgumentParser(description="Measure Qwen retrieval on active Vietnamese PDF")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--workspace-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    database_url = os.environ.get("KNORA_DATABASE_URL")
    if not database_url:
        raise SystemExit("KNORA_DATABASE_URL is required")
    dataset = load_vietnamese_dataset(args.dataset, args.manifest)
    engine = create_engine(database_url)
    try:
        session_factory = sessionmaker(engine)
        observations = collect_live_observations(
            dataset,
            workspace_id=args.workspace_id,
            session_factory=session_factory,
            ollama_url=os.environ.get("KNORA_OLLAMA_BASE_URL", "http://localhost:11434"),
            model=os.environ.get("KNORA_OLLAMA_EMBEDDING_MODEL", "qwen3-embedding:0.6b"),
        )
        report = evaluate_retrieval(dataset, observations)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "threshold_applied": False,
                    "candidate_k": 16,
                    "report": report.as_mapping(),
                    "observations": [asdict(item) for item in observations],
                },
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(
            json.dumps(
                {"cases": len(observations), "hit_at_5": report.hit_at_5, "mrr": report.mrr},
                sort_keys=True,
            )
        )
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
