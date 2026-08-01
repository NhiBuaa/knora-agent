from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import sys
from decimal import Decimal
from pathlib import Path
from time import perf_counter
from typing import Protocol

import httpx
from evals.runners.evaluation import (
    EvaluationCase,
    EvaluationObservation,
    EvaluationProvenance,
    build_report,
    load_corpus_manifest,
    load_dataset,
    load_dataset_manifest,
    validate_mode,
    validate_relevance_references,
    verify_active_corpus,
    write_report_atomic,
)

from knora.adapters.postgres.database import SessionFactory
from knora.adapters.postgres.evaluation_reader import PostgresEvaluationReader
from knora.infrastructure.settings import settings

MARKER_PATTERN = re.compile(r"\[\[(E[1-9][0-9]*)\]\]")


class TraceReader(Protocol):
    def read_trace(self, *, trace_id: str, workspace_id: str): ...


class HttpEvaluationExecutor:
    def __init__(
        self,
        *,
        endpoint: str,
        api_key: str,
        trace_reader: TraceReader,
        client: httpx.AsyncClient,
    ) -> None:
        self._endpoint = endpoint
        self._api_key = api_key
        self._trace_reader = trace_reader
        self._client = client

    async def execute(self, case: EvaluationCase) -> EvaluationObservation:
        started = perf_counter()
        try:
            response = await self._client.post(
                self._endpoint,
                headers={"X-API-Key": self._api_key},
                json={"workspace_id": case.workspace_id, "question": case.question},
            )
            response.raise_for_status()
            payload = response.json()
            trace = self._trace_reader.read_trace(
                trace_id=payload["trace_id"], workspace_id=case.workspace_id
            )
        except (httpx.HTTPError, KeyError, TypeError, ValueError, LookupError) as error:
            return EvaluationObservation(
                case_id=case.id,
                retrieved_chunks=(),
                retrieval_latency_ms=0.0,
                decision="ERROR",
                refusal_reason=None,
                end_to_end_latency_ms=(perf_counter() - started) * 1000,
                provider_error=type(error).__name__,
            )

        references_by_id = {
            candidate.chunk_id: f"{candidate.source_key}#{candidate.chunk_ordinal}"
            for candidate in trace.candidates
        }
        citation_ids = tuple(item["evidence_id"] for item in payload["citations"])
        cited_chunks = tuple(
            references_by_id[trace.alias_mapping[evidence_id]]
            for evidence_id in citation_ids
            if evidence_id in trace.alias_mapping
            and trace.alias_mapping[evidence_id] in references_by_id
        )
        usage, cost = _system_observations(trace.provider_metadata)
        generation = trace.provider_metadata.get("generation", {})
        if not isinstance(generation, dict):
            generation = {}
        embedding = trace.provider_metadata.get("embedding", {})
        if not isinstance(embedding, dict):
            embedding = {}
        return EvaluationObservation(
            case_id=case.id,
            retrieved_chunks=tuple(
                references_by_id[candidate.chunk_id] for candidate in trace.candidates
            ),
            retrieval_latency_ms=trace.retrieval_latency_ms,
            decision=payload["decision"],
            answer=payload["answer"],
            refusal_reason=payload["refusal_reason"],
            cited_chunks=cited_chunks,
            citation_evidence_ids=citation_ids,
            answer_marker_ids=tuple(MARKER_PATTERN.findall(payload["answer"])),
            candidate_workspaces=tuple(
                candidate.workspace_id for candidate in trace.candidates
            ),
            trace_id=payload["trace_id"],
            end_to_end_latency_ms=(perf_counter() - started) * 1000,
            token_usage=usage,
            cost_usd=cost,
            retrieval_configuration_id=trace.retrieval_configuration_id,
            embedding_configuration_id=trace.embedding_configuration_id,
            embedding_provider=str(embedding.get("provider", "")),
            generation_provider=str(generation.get("provider", "")),
            generation_model=str(generation.get("model", "")),
            generation_prompt_version=str(generation.get("prompt_version", "")),
        )


def _system_observations(
    provider_metadata: dict[str, object],
) -> tuple[dict[str, int], str | None]:
    usage: dict[str, int] = {}
    total_cost = Decimal("0")
    has_cost = False
    for provider in provider_metadata.values():
        if not isinstance(provider, dict):
            continue
        raw_usage = provider.get("usage", {})
        if isinstance(raw_usage, dict):
            for name, value in raw_usage.items():
                if isinstance(value, int):
                    usage[name] = usage.get(name, 0) + value
        cost = provider.get("cost", {})
        if isinstance(cost, dict) and cost.get("amount_usd") is not None:
            total_cost += Decimal(str(cost["amount_usd"]))
            has_cost = True
    return usage, format(total_cost, "f") if has_cost else None


async def _execute_cases(
    cases: tuple[EvaluationCase, ...], executor: HttpEvaluationExecutor
) -> tuple[EvaluationObservation, ...]:
    return tuple([await executor.execute(case) for case in sorted(cases, key=lambda item: item.id)])


def _manifest_checksum(path: Path) -> str:
    normalized = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return "sha256:" + hashlib.sha256(normalized).hexdigest()


def _runtime_versions(
    observations: tuple[EvaluationObservation, ...], expected_embedding: str
) -> tuple[str, str, str]:
    retrieval = {item.retrieval_configuration_id for item in observations if item.trace_id}
    embedding = {item.embedding_configuration_id for item in observations if item.trace_id}
    embedding_providers = {item.embedding_provider for item in observations if item.trace_id}
    generation = {
        (item.generation_provider, item.generation_model, item.generation_prompt_version)
        for item in observations
        if item.generation_provider
    }
    if len(retrieval) != 1:
        raise ValueError("evaluation traces disagree on retrieval configuration")
    if embedding != {expected_embedding}:
        raise ValueError("evaluation traces disagree on embedding configuration")
    if embedding_providers != {"deterministic-local"}:
        raise ValueError("local evaluation requires observed deterministic embedding provenance")
    if len(generation) != 1 or next(iter(generation))[0] != "deterministic-local":
        raise ValueError("local evaluation requires observed deterministic generation provenance")
    provider, model, prompt = next(iter(generation))
    return next(iter(retrieval)), expected_embedding, f"{provider}:{model}:{prompt}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the Milestone 1 HTTP structural and retrieval evaluation"
    )
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--dataset-manifest", type=Path, required=True)
    parser.add_argument("--corpus-manifest", type=Path, required=True)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument(
        "--mode",
        choices=("deterministic-local", "model-backed"),
        default="deterministic-local",
    )
    parser.add_argument("--scorer-version")
    parser.add_argument("--api-key-env", default="KNORA_EVALUATION_API_KEY")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        validate_mode(
            args.mode,
            provider_mode=settings.provider_mode,
            scorer_version=args.scorer_version,
        )
        api_key = os.environ.get(args.api_key_env)
        if not api_key:
            raise ValueError(f"missing evaluation API key environment variable: {args.api_key_env}")
        dataset_identity = load_dataset_manifest(args.dataset_manifest, args.dataset)
        dataset = load_dataset(args.dataset)
        manifest = load_corpus_manifest(args.corpus_manifest)
        validate_relevance_references(dataset, manifest)
        if {case.workspace_id for case in dataset.cases} != {manifest.workspace_id}:
            raise ValueError("dataset Workspaces do not match corpus manifest")
        reader = PostgresEvaluationReader(SessionFactory)
        active_corpus = reader.read_active_corpus(workspace_id=manifest.workspace_id)
        verify_active_corpus(manifest, active_corpus)

        async def execute() -> tuple[EvaluationObservation, ...]:
            async with httpx.AsyncClient(timeout=60.0) as client:
                executor = HttpEvaluationExecutor(
                    endpoint=args.endpoint,
                    api_key=api_key,
                    trace_reader=reader,
                    client=client,
                )
                return await _execute_cases(dataset.cases, executor)

        observations = asyncio.run(execute())
        retrieval_version, embedding_version, generation_version = _runtime_versions(
            observations, manifest.embedding_configuration_id
        )
        report = build_report(
            dataset,
            observations,
            provenance=EvaluationProvenance(
                dataset_version=dataset_identity.version,
                dataset_checksum=dataset_identity.checksum,
                corpus_version=manifest.version,
                corpus_checksum=_manifest_checksum(args.corpus_manifest),
                chunking_version=manifest.chunking_configuration_id,
                embedding_version=embedding_version,
                retrieval_version=retrieval_version,
                generation_version=generation_version,
                scorer_version=args.scorer_version or "not-run",
            ),
            mode=args.mode,
        )
        write_report_atomic(args.report, report)
    except (
        FileExistsError,
        OSError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
    ) as error:
        print(json.dumps({"error": str(error)}), file=sys.stderr)
        return 2
    print(
        f"{report['structural']['passed']}/{report['structural']['denominator']} "
        f"structural cases passed; report={args.report}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
