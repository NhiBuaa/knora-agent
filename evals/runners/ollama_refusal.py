"""Workspace-scoped model refusal diagnostics; never seals a Conversation gate."""

import argparse
import asyncio
import json
import math
import os
from dataclasses import asdict
from pathlib import Path

import httpx
from evals.datasets.vietnamese_rag_v1 import load_vietnamese_dataset
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from knora.answering.evidence import select_evidence
from knora.answering.generation_validation import validate_generation
from knora.answering.stores import RetrievalCandidate, RetrievalConfiguration
from knora.domain.errors import KnoraError
from knora.providers.generation import GenerationEvidence, GenerationProvider
from knora.providers.ollama.embedding import (
    OllamaEmbeddingProvider,
    resolve_ollama_embedding_configuration,
)
from knora.providers.ollama.generation import OLLAMA_PROMPT_VERSION, OllamaGenerationProvider


async def evaluate_case(
    *,
    case_id: str,
    question: str,
    candidates: tuple[RetrievalCandidate, ...],
    configuration: RetrievalConfiguration,
    provider: GenerationProvider,
) -> dict[str, object]:
    threshold = configuration.min_similarity
    if not math.isfinite(threshold) or not -1 <= threshold <= 1:
        raise ValueError("invalid diagnostic threshold")
    eligible = tuple(
        item for item in candidates if item.similarity is not None and item.similarity >= threshold
    )
    selection = select_evidence(eligible, configuration)
    evidence = tuple(
        GenerationEvidence(f"E{index}", item.candidate.content)
        for index, item in enumerate(selection.selected, 1)
    )
    row = {
        "case_id": case_id,
        "generation_called": bool(evidence),
        "evidence_checksums": [item.candidate.content_checksum for item in selection.selected],
        "outcome": "PRE_GENERATION_REFUSAL",
    }
    if not evidence:
        return row
    try:
        result = await provider.generate(question=question, evidence=evidence)
    except KnoraError as error:
        row["outcome"] = (
            "INVALID_OUTPUT" if error.code == "GENERATION_OUTPUT_INVALID" else "PROVIDER_ERROR"
        )
        return row
    except Exception:
        # Provider exceptions can contain prompts, credentials, or HTTP response bodies.
        row["outcome"] = "PROVIDER_ERROR"
        return row
    try:
        validate_generation(
            result, available_evidence_ids=tuple(item.evidence_id for item in evidence)
        )
    except KnoraError:
        row["outcome"] = "INVALID_OUTPUT"
    else:
        row["outcome"] = "MODEL_REFUSAL" if result.decision == "REFUSAL" else "UNEXPECTED_ANSWER"
    return row


def summarize(rows: list[dict[str, object]]) -> dict[str, object]:
    if not rows:
        raise ValueError("empty refusal evaluation")
    generated = sum(bool(row["generation_called"]) for row in rows)
    refused = sum(row["outcome"] == "MODEL_REFUSAL" for row in rows)
    return {
        "schema_version": 1,
        "scope": "model_refusal_diagnostic",
        "conversation_gate": "NOT_EVALUATED",
        "sealed_artifact_sha256": None,
        "case_count": len(rows),
        "generation_count": generated,
        "pre_generation_refusal_count": len(rows) - generated,
        "model_refusal_rate": refused / generated if generated else None,
        "cases": rows,
    }


async def collect_live(
    dataset,
    *,
    workspace_id,
    session_factory,
    ollama_url,
    embedding_model,
    generation_model,
    generation_digest,
    configuration,
):
    # Import database adapters only inside the CLI's sanitized error boundary.
    from evals.runners.vietnamese_retrieval import load_active_bindings, validate_active_corpus

    from knora.adapters.postgres.answering_store import PostgresAnsweringStore

    validate_active_corpus(dataset, load_active_bindings(session_factory, workspace_id))
    provider = OllamaGenerationProvider(
        base_url=ollama_url,
        model=generation_model,
        expected_digest=generation_digest,
    )
    try:
        with httpx.Client(base_url=ollama_url, timeout=120) as client:
            profile = resolve_ollama_embedding_configuration(client, embedding_model)
            if profile.id != dataset.profile_id or not profile.deployment_identity.endswith(
                dataset.model_digest
            ):
                raise ValueError("deployed Qwen profile differs from dataset")
            embedding = OllamaEmbeddingProvider(client=client)
            store = PostgresAnsweringStore(session_factory)
            rows = []
            for case in dataset.cases:
                if case.expected_behavior != "REFUSAL":
                    continue
                vector = embedding.embed_queries([case.question], profile).vectors[0]
                retrieved = store.retrieve_candidates(
                    workspace_id=workspace_id,
                    query_text=case.question,
                    query_vector=vector,
                    embedding_configuration=profile,
                    retrieval_configuration=configuration,
                )
                if set(retrieved.chunk_set_ids) != set(dataset.chunk_set_ids):
                    raise ValueError("retrieval chunk set differs from dataset")
                rows.append(
                    await evaluate_case(
                        case_id=case.id,
                        question=case.question,
                        candidates=retrieved.candidates,
                        configuration=configuration,
                        provider=provider,
                    )
                )
            report = summarize(rows)
            report.update(
                {
                    "workspace_id": workspace_id,
                    "dataset_sha256": dataset.dataset_sha256,
                    "corpus_sha256": dataset.corpus_sha256,
                    "chunk_set_ids": dataset.chunk_set_ids,
                    "embedding_profile_id": profile.id,
                    "embedding_model_digest": dataset.model_digest,
                    "generation_model": generation_model,
                    "generation_expected_digest": generation_digest,
                    "prompt_version": OLLAMA_PROMPT_VERSION,
                    "retrieval_configuration": asdict(configuration),
                }
            )
            return report
    finally:
        await provider.aclose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--workspace-id", required=True)
    parser.add_argument("--threshold", type=float, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    configuration = RetrievalConfiguration.qwen_vietnamese_v1(
        min_similarity=args.threshold,
        artifact_sha256="diagnostic-unsealed",
    )
    dataset = load_vietnamese_dataset(args.dataset, args.manifest)
    engine = create_engine(os.environ["KNORA_DATABASE_URL"])
    try:
        report = asyncio.run(
            collect_live(
                dataset,
                workspace_id=args.workspace_id,
                session_factory=sessionmaker(engine),
                ollama_url=os.environ.get("KNORA_OLLAMA_BASE_URL", "http://127.0.0.1:11435"),
                embedding_model=os.environ.get(
                    "KNORA_OLLAMA_EMBEDDING_MODEL", "qwen3-embedding:0.6b"
                ),
                generation_model=os.environ.get("KNORA_OLLAMA_GENERATION_MODEL", "qwen3:8b"),
                generation_digest=os.environ["KNORA_EXPECTED_GENERATION_MODEL_DIGEST"],
                configuration=configuration,
            )
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
        print(
            json.dumps(
                {
                    key: report[key]
                    for key in (
                        "case_count",
                        "generation_count",
                        "model_refusal_rate",
                        "conversation_gate",
                    )
                }
            )
        )
    finally:
        engine.dispose()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit("Refusal diagnostic failed; no complete report was produced.") from None
