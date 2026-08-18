from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
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
    SemanticEvaluation,
    build_report,
    load_corpus_manifest,
    load_dataset,
    load_dataset_manifest,
    validate_mode,
    validate_relevance_references,
    verify_active_corpus,
    write_report_atomic,
)
from evals.runners.milestone_3 import (
    ObservationFailure,
    validate_public_citations_against_trace,
    validate_public_response,
)
from evals.scorers.openai_compatible import (
    OpenAICompatibleSemanticScorer,
    SemanticScorerConfiguration,
)

from knora.adapters.postgres.database import SessionFactory
from knora.adapters.postgres.evaluation_reader import PostgresEvaluationReader
from knora.infrastructure.settings import settings


class TraceReader(Protocol):
    def read_trace(self, *, trace_id: str, workspace_id: str): ...


class SemanticScorer(Protocol):
    async def score(
        self, *, case: EvaluationCase, observation: EvaluationObservation
    ) -> SemanticEvaluation: ...

    async def aclose(self) -> None: ...


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
            public = validate_public_response(payload)
            trace = self._trace_reader.read_trace(
                trace_id=payload["trace_id"], workspace_id=case.workspace_id
            )
        except (
            httpx.HTTPError,
            KeyError,
            TypeError,
            ValueError,
            LookupError,
            ObservationFailure,
        ) as error:
            return EvaluationObservation(
                case_id=case.id,
                retrieved_chunks=(),
                retrieval_latency_ms=0.0,
                decision="ERROR",
                refusal_reason=None,
                end_to_end_latency_ms=(perf_counter() - started) * 1000,
                provider_error=type(error).__name__,
            )

        try:
            references_by_id = {
                candidate.chunk_id: f"{candidate.source_key}#{candidate.chunk_ordinal}"
                for candidate in trace.candidates
            }
            candidates_by_id = {candidate.chunk_id: candidate for candidate in trace.candidates}
            selected_candidate_ids = {
                candidate.chunk_id
                for candidate in trace.candidates
                if getattr(candidate, "final_decision", None) == "SELECTED"
            }
            citation_ids = public.citation_evidence_ids
            validate_public_citations_against_trace(
                citations=public.citations,
                alias_mapping=trace.alias_mapping,
                candidates=trace.candidates,
            )
            public_citations = tuple(
                (
                    citation.evidence_id,
                    citation.excerpt,
                    citation.source_locator,
                )
                for citation in public.citations
            )
            alias_mapping = trace.alias_mapping
            if not isinstance(alias_mapping, dict) or any(
                evidence_id not in alias_mapping
                or alias_mapping[evidence_id] not in selected_candidate_ids
                for evidence_id in citation_ids
            ) or len(
                {alias_mapping[evidence_id] for evidence_id in citation_ids}
            ) != len(citation_ids):
                raise ValueError("PUBLIC_CITATION_ALIAS_INVALID")
            cited_chunks = tuple(
                references_by_id[alias_mapping[evidence_id]] for evidence_id in citation_ids
            )
            usage, cost = _system_observations(trace.provider_metadata)
            generation = trace.provider_metadata.get("generation", {})
            if not isinstance(generation, dict):
                generation = {}
            embedding = trace.provider_metadata.get("embedding", {})
            if not isinstance(embedding, dict):
                embedding = {}
            evidence = tuple(
                (
                    evidence_id,
                    references_by_id[chunk_id],
                    getattr(candidates_by_id[chunk_id], "content", ""),
                )
                for evidence_id, chunk_id in alias_mapping.items()
                if chunk_id in references_by_id
            )
        except (KeyError, TypeError, ValueError, AttributeError) as error:
            return EvaluationObservation(
                case_id=case.id,
                retrieved_chunks=(),
                retrieval_latency_ms=0.0,
                decision="ERROR",
                refusal_reason=None,
                end_to_end_latency_ms=(perf_counter() - started) * 1000,
                provider_error=type(error).__name__,
            )
        return EvaluationObservation(
            case_id=case.id,
            retrieved_chunks=tuple(
                references_by_id[candidate.chunk_id] for candidate in trace.candidates
            ),
            retrieval_latency_ms=trace.retrieval_latency_ms,
            decision=public.decision,
            answer=public.answer,
            refusal_reason=public.refusal_reason,
            cited_chunks=cited_chunks,
            citation_evidence_ids=citation_ids,
            answer_marker_ids=public.answer_marker_ids,
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
            public_citations=public_citations,
            evidence=evidence,
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


async def _score_cases(
    cases: tuple[EvaluationCase, ...],
    observations: tuple[EvaluationObservation, ...],
    scorer: SemanticScorer,
) -> tuple[SemanticEvaluation, ...]:
    by_case = {observation.case_id: observation for observation in observations}
    results: list[SemanticEvaluation] = []
    for case in sorted(cases, key=lambda item: item.id):
        observation = by_case[case.id]
        if observation.provider_error is not None:
            results.append(
                SemanticEvaluation(
                    case_id=case.id,
                    error="QUESTION_PROVIDER_ERROR",
                )
            )
            continue
        try:
            results.append(await scorer.score(case=case, observation=observation))
        except ValueError as error:
            results.append(
                SemanticEvaluation(
                    case_id=case.id,
                    error=str(error),
                )
            )
    return tuple(results)


def _manifest_checksum(path: Path) -> str:
    normalized = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return "sha256:" + hashlib.sha256(normalized).hexdigest()


def _runtime_versions(
    observations: tuple[EvaluationObservation, ...],
    expected_embedding: str,
    *,
    mode: str,
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
    expected_provider = (
        "deterministic-local" if mode == "deterministic-local" else "openai-compatible"
    )
    if embedding_providers != {expected_provider}:
        raise ValueError(
            f"{mode} evaluation requires observed {expected_provider} embedding provenance"
        )
    if len(generation) != 1 or next(iter(generation))[0] != expected_provider:
        raise ValueError(
            f"{mode} evaluation requires observed {expected_provider} generation provenance"
        )
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
    parser.add_argument("--scorer-method")
    parser.add_argument("--scorer-base-url-env", default="KNORA_SEMANTIC_SCORER_BASE_URL")
    parser.add_argument("--scorer-api-key-env", default="KNORA_SEMANTIC_SCORER_API_KEY")
    parser.add_argument("--scorer-model-env", default="KNORA_SEMANTIC_SCORER_MODEL")
    parser.add_argument("--api-key-env", default="KNORA_EVALUATION_API_KEY")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        validate_mode(
            args.mode,
            provider_mode=settings.provider_mode,
            scorer_version=args.scorer_version,
            scorer_method=args.scorer_method,
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
        scorer: SemanticScorer | None = None
        if args.mode == "model-backed":
            scorer = OpenAICompatibleSemanticScorer(
                SemanticScorerConfiguration.from_environment(
                    version=args.scorer_version,
                    measurement_method=args.scorer_method,
                    base_url_env=args.scorer_base_url_env,
                    api_key_env=args.scorer_api_key_env,
                    model_env=args.scorer_model_env,
                )
            )

        async def execute() -> tuple[
            tuple[EvaluationObservation, ...], tuple[SemanticEvaluation, ...]
        ]:
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    executor = HttpEvaluationExecutor(
                        endpoint=args.endpoint,
                        api_key=api_key,
                        trace_reader=reader,
                        client=client,
                    )
                    observations = await _execute_cases(dataset.cases, executor)
                semantic_evaluations = (
                    await _score_cases(dataset.cases, observations, scorer)
                    if scorer is not None
                    else ()
                )
                return observations, semantic_evaluations
            finally:
                if scorer is not None:
                    await scorer.aclose()

        observations, semantic_evaluations = asyncio.run(execute())
        retrieval_version, embedding_version, generation_version = _runtime_versions(
            observations,
            manifest.embedding_configuration_id,
            mode=args.mode,
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
                scorer_method=args.scorer_method or "",
            ),
            mode=args.mode,
            semantic_evaluations=semantic_evaluations,
            scorer_method=args.scorer_method,
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
