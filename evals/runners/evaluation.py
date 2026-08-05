from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass, field
from decimal import Decimal
from pathlib import Path
from uuid import uuid4


class DatasetValidationError(ValueError):
    pass


REQUIRED_CATEGORIES = {
    "answerable",
    "unanswerable",
    "ambiguous",
    "adversarial_near_miss",
}
REQUIRED_CASE_FIELDS = (
    "id",
    "category",
    "workspace_id",
    "question",
    "expected_behavior",
    "expected_source_documents",
    "acceptable_relevant_chunks",
)
REFUSAL_MESSAGE = "Tôi không tìm thấy đủ thông tin trong knowledge base để trả lời câu hỏi này."
SEMANTIC_METRICS = (
    "citation_entailment",
    "faithfulness",
    "answer_relevance",
    "refusal_correctness",
)


@dataclass(frozen=True, slots=True)
class EvaluationCase:
    id: str
    category: str
    workspace_id: str
    question: str
    expected_behavior: str
    expected_source_documents: tuple[str, ...]
    acceptable_relevant_chunks: tuple[str, ...]
    required_facts: tuple[str, ...]
    reference_answer: str | None


@dataclass(frozen=True, slots=True)
class EvaluationDataset:
    cases: tuple[EvaluationCase, ...]


@dataclass(frozen=True, slots=True)
class EvaluationObservation:
    case_id: str
    retrieved_chunks: tuple[str, ...]
    retrieval_latency_ms: float
    decision: str = "REFUSAL"
    answer: str | None = None
    refusal_reason: str | None = "INSUFFICIENT_EVIDENCE"
    cited_chunks: tuple[str, ...] = ()
    citation_evidence_ids: tuple[str, ...] = ()
    answer_marker_ids: tuple[str, ...] = ()
    candidate_workspaces: tuple[str, ...] = ()
    trace_id: str | None = None
    end_to_end_latency_ms: float = 0.0
    token_usage: dict[str, int] = field(default_factory=dict)
    cost_usd: str | None = None
    provider_error: str | None = None
    retrieval_configuration_id: str = ""
    embedding_configuration_id: str = ""
    embedding_provider: str = ""
    generation_provider: str = ""
    generation_model: str = ""
    generation_prompt_version: str = ""
    evidence: tuple[tuple[str, str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class SemanticEvaluation:
    case_id: str
    scores: dict[str, float] = field(default_factory=dict)
    rationales: dict[str, str] = field(default_factory=dict)
    provider: str = ""
    model: str = ""
    scorer_version: str = ""
    measurement_method: str = ""
    prompt_version: str = ""
    pricing_version: str | None = None
    provider_request_id: str | None = None
    token_usage: dict[str, int] = field(default_factory=dict)
    cost_usd: str | None = None
    latency_ms: float = 0.0
    error: str | None = None


@dataclass(frozen=True, slots=True)
class EvaluationProvenance:
    dataset_version: str
    dataset_checksum: str
    corpus_version: str
    corpus_checksum: str
    chunking_version: str
    embedding_version: str
    retrieval_version: str
    generation_version: str
    scorer_version: str
    scorer_method: str = ""


@dataclass(frozen=True, slots=True)
class CorpusDocument:
    path: Path
    source_key: str
    normalized_content_sha256: str
    expected_chunk_references: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CorpusManifest:
    version: str
    workspace_id: str
    chunking_configuration_id: str
    embedding_configuration_id: str
    documents: tuple[CorpusDocument, ...]


@dataclass(frozen=True, slots=True)
class DatasetIdentity:
    version: str
    checksum: str


def load_dataset(path: Path) -> EvaluationDataset:
    records = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]
    parsed_cases = []
    for index, record in enumerate(records, start=1):
        label = record.get("id", f"line-{index}")
        missing = next((field for field in REQUIRED_CASE_FIELDS if field not in record), None)
        if missing is not None:
            raise DatasetValidationError(f"case {label} missing field: {missing}")
        parsed_cases.append(
            EvaluationCase(
                id=record["id"],
                category=record["category"],
                workspace_id=record["workspace_id"],
                question=record["question"],
                expected_behavior=record["expected_behavior"],
                expected_source_documents=tuple(record["expected_source_documents"]),
                acceptable_relevant_chunks=tuple(record["acceptable_relevant_chunks"]),
                required_facts=tuple(record.get("required_facts", [])),
                reference_answer=record.get("reference_answer"),
            )
        )
    cases = tuple(parsed_cases)
    if not 20 <= len(cases) <= 25:
        raise DatasetValidationError("dataset must contain 20 to 25 cases")
    seen: set[str] = set()
    for case in cases:
        if case.id in seen:
            raise DatasetValidationError(f"duplicate case id: {case.id}")
        seen.add(case.id)
        if case.category not in REQUIRED_CATEGORIES:
            raise DatasetValidationError(f"unknown category: {case.category}")
        if case.expected_behavior not in {"ANSWER", "REFUSAL"}:
            raise DatasetValidationError(
                f"unknown expected behavior: {case.expected_behavior}"
            )
        if case.expected_behavior == "ANSWER" and (
            not case.expected_source_documents or not case.acceptable_relevant_chunks
        ):
            raise DatasetValidationError(
                f"ANSWER case {case.id} requires relevant sources and chunks"
            )
    missing_categories = REQUIRED_CATEGORIES - {case.category for case in cases}
    if missing_categories:
        raise DatasetValidationError(
            "dataset missing categories: " + ", ".join(sorted(missing_categories))
        )
    return EvaluationDataset(cases=cases)


def load_corpus_manifest(path: Path) -> CorpusManifest:
    payload = json.loads(path.read_text(encoding="utf-8"))
    root = path.parent.resolve()
    documents = []
    seen_paths: set[Path] = set()
    seen_source_keys: set[str] = set()
    for record in payload["documents"]:
        document_path = (root / record["path"]).resolve()
        if document_path.parent != root:
            raise ValueError("corpus document must be inside the manifest directory")
        if document_path in seen_paths or record["source_key"] in seen_source_keys:
            raise ValueError("corpus paths and source keys must be unique")
        seen_paths.add(document_path)
        seen_source_keys.add(record["source_key"])
        normalized = (
            document_path.read_text(encoding="utf-8")
            .replace("\r\n", "\n")
            .replace("\r", "\n")
        )
        actual = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        if actual != record["normalized_content_sha256"]:
            raise ValueError(f"corpus checksum mismatch: {record['path']}")
        documents.append(
            CorpusDocument(
                path=document_path,
                source_key=record["source_key"],
                normalized_content_sha256=actual,
                expected_chunk_references=tuple(record["expected_chunk_references"]),
            )
        )
    return CorpusManifest(
        version=payload["version"],
        workspace_id=payload["workspace_id"],
        chunking_configuration_id=payload["chunking_configuration_id"],
        embedding_configuration_id=payload["embedding_configuration_id"],
        documents=tuple(documents),
    )


def load_dataset_manifest(path: Path, dataset_path: Path) -> DatasetIdentity:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if Path(payload["path"]).name != dataset_path.name:
        raise ValueError("dataset path does not match manifest")
    normalized = dataset_path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    actual = hashlib.sha256(normalized).hexdigest()
    if actual != payload["sha256"]:
        raise ValueError("dataset checksum mismatch")
    return DatasetIdentity(version=payload["version"], checksum=f"sha256:{actual}")


def validate_relevance_references(
    dataset: EvaluationDataset, manifest: CorpusManifest
) -> None:
    available = {
        reference
        for document in manifest.documents
        for reference in document.expected_chunk_references
    }
    for case in dataset.cases:
        missing = set(case.acceptable_relevant_chunks) - available
        if missing:
            raise DatasetValidationError(
                f"case {case.id} references unknown relevant chunks: "
                + ", ".join(sorted(missing))
            )


def verify_active_corpus(manifest: CorpusManifest, active: object) -> None:
    if getattr(active, "workspace_id", None) != manifest.workspace_id:
        raise ValueError("active corpus does not match manifest Workspace")
    expected = {document.source_key: document for document in manifest.documents}
    actual_documents = getattr(active, "documents", ())
    actual = {document.source_key: document for document in actual_documents}
    if set(actual) != set(expected):
        raise ValueError("active corpus does not match manifest source keys")
    for source_key, document in expected.items():
        projection = actual[source_key]
        if (
            projection.normalized_content_checksum
            != document.normalized_content_sha256
            or projection.chunking_configuration_id
            != manifest.chunking_configuration_id
            or projection.embedding_configuration_id
            != manifest.embedding_configuration_id
            or tuple(projection.chunk_references)
            != document.expected_chunk_references
        ):
            raise ValueError(f"active corpus does not match manifest: {source_key}")


def score_retrieval(
    cases: tuple[EvaluationCase, ...],
    observations: tuple[EvaluationObservation, ...],
    *,
    candidate_k: int,
) -> dict[str, object]:
    by_case = {observation.case_id: observation for observation in observations}
    eligible = [case for case in cases if case.acceptable_relevant_chunks]
    recalls: list[float] = []
    reciprocal_ranks: list[float] = []
    hits: list[float] = []
    latencies: list[float] = []
    case_results: list[dict[str, object]] = []
    for case in sorted(eligible, key=lambda item: item.id):
        observation = by_case[case.id]
        ranked = observation.retrieved_chunks[:candidate_k]
        relevant = set(case.acceptable_relevant_chunks)
        matched = relevant.intersection(ranked)
        recalls.append(len(matched) / len(relevant))
        first_rank = next(
            (index for index, chunk in enumerate(ranked, start=1) if chunk in relevant),
            None,
        )
        reciprocal_ranks.append(0.0 if first_rank is None else 1.0 / first_rank)
        hits.append(float(first_rank is not None))
        latencies.append(observation.retrieval_latency_ms)
        case_results.append(
            {
                "id": case.id,
                "hit": first_rank is not None,
                "recall_at_8": recalls[-1],
                "reciprocal_rank": reciprocal_ranks[-1],
                "retrieved_chunks": list(ranked),
            }
        )
    denominator = len(eligible)
    return {
        "candidate_k": candidate_k,
        "denominator": denominator,
        "recall_at_8": sum(recalls) / denominator,
        "mrr": sum(reciprocal_ranks) / denominator,
        "hit_rate": sum(hits) / denominator,
        "cases": case_results,
        "latency_ms": {
            "mean": sum(latencies) / denominator,
            "min": min(latencies),
            "max": max(latencies),
        },
    }


def _structural_checks(
    case: EvaluationCase, observation: EvaluationObservation
) -> dict[str, bool]:
    if observation.decision == "ANSWER":
        decision_contract = bool(observation.answer) and (
            observation.refusal_reason is None
            and bool(observation.citation_evidence_ids)
            and observation.answer_marker_ids == observation.citation_evidence_ids
            and len(set(observation.citation_evidence_ids))
            == len(observation.citation_evidence_ids)
            and len(observation.cited_chunks)
            == len(observation.citation_evidence_ids)
        )
    elif observation.decision == "REFUSAL":
        decision_contract = (
            observation.refusal_reason == "INSUFFICIENT_EVIDENCE"
            and observation.answer == REFUSAL_MESSAGE
            and not observation.cited_chunks
            and not observation.citation_evidence_ids
            and not observation.answer_marker_ids
        )
    else:
        decision_contract = False
    cited_source_documents = {
        reference.rsplit("#", 1)[0] for reference in observation.cited_chunks
    }
    expected_sources = set(case.expected_source_documents)
    source_documents_match = (
        not observation.cited_chunks
        if observation.decision == "REFUSAL"
        else bool(cited_source_documents)
        and cited_source_documents.issubset(expected_sources)
    )
    return {
        "decision_contract": decision_contract,
        "expected_source_documents": source_documents_match,
        "citation_in_evidence_set": set(observation.cited_chunks).issubset(
            observation.retrieved_chunks
        ),
        "workspace_isolation": all(
            workspace == case.workspace_id
            for workspace in observation.candidate_workspaces
        ),
        "trace_persisted": bool(observation.trace_id),
    }


def _build_semantic_report(
    dataset: EvaluationDataset,
    evaluations: tuple[SemanticEvaluation, ...],
    *,
    provenance: EvaluationProvenance,
    measurement_method: str,
) -> dict[str, object]:
    by_case = {evaluation.case_id: evaluation for evaluation in evaluations}
    if len(by_case) != len(evaluations) or set(by_case) != {
        case.id for case in dataset.cases
    }:
        raise ValueError("semantic evaluations must contain exactly one result for every case")
    case_results: list[dict[str, object]] = []
    metric_cases: dict[str, list[dict[str, object]]] = {metric: [] for metric in SEMANTIC_METRICS}
    providers: set[str] = set()
    models: set[str] = set()
    prompt_versions: set[str] = set()
    errors = 0
    for case in sorted(dataset.cases, key=lambda item: item.id):
        evaluation = by_case[case.id]
        if evaluation.provider:
            providers.add(evaluation.provider)
        if evaluation.model:
            models.add(evaluation.model)
        if evaluation.prompt_version:
            prompt_versions.add(evaluation.prompt_version)
        if evaluation.error is not None:
            errors += 1
        missing_metrics = set(SEMANTIC_METRICS) - set(evaluation.scores)
        if evaluation.error is None and missing_metrics:
            raise ValueError(
                f"semantic evaluation missing metrics: {case.id}/"
                + ",".join(sorted(missing_metrics))
            )
        for metric in SEMANTIC_METRICS:
            score = evaluation.scores.get(metric)
            if score is not None:
                if isinstance(score, bool) or not isinstance(score, (int, float)):
                    raise ValueError(f"semantic score must be numeric: {case.id}/{metric}")
                if not 0.0 <= float(score) <= 1.0:
                    raise ValueError(f"semantic score must be between 0 and 1: {case.id}/{metric}")
                metric_cases[metric].append({"id": case.id, "score": float(score)})
        case_results.append(
            {
                "id": case.id,
                "scores": {
                    metric: float(evaluation.scores[metric])
                    for metric in SEMANTIC_METRICS
                    if metric in evaluation.scores
                },
                "rationales": dict(sorted(evaluation.rationales.items())),
                "provider_request_id": evaluation.provider_request_id,
                "error": evaluation.error,
            }
        )
    metrics: dict[str, object] = {}
    for metric, cases in metric_cases.items():
        metrics[metric] = {
            "denominator": len(cases),
            "mean": sum(item["score"] for item in cases) / len(cases) if cases else None,
            "cases": cases,
        }
    return {
        "status": "completed" if errors == 0 else "completed_with_errors",
        "scorer": {
            "provider": next(iter(providers)) if len(providers) == 1 else "mixed",
            "model": next(iter(models)) if len(models) == 1 else "mixed",
            "version": provenance.scorer_version,
            "measurement_method": measurement_method,
            "prompt_versions": sorted(prompt_versions),
            "pricing_versions": sorted(
                {
                    evaluation.pricing_version
                    for evaluation in evaluations
                    if evaluation.pricing_version
                }
            ),
        },
        "metrics": metrics,
        "cases": case_results,
        "errors": errors,
    }


def build_report(
    dataset: EvaluationDataset,
    observations: tuple[EvaluationObservation, ...],
    *,
    provenance: EvaluationProvenance,
    mode: str,
    semantic_evaluations: tuple[SemanticEvaluation, ...] = (),
    scorer_method: str | None = None,
) -> dict[str, object]:
    by_case = {observation.case_id: observation for observation in observations}
    if len(by_case) != len(observations) or set(by_case) != {
        case.id for case in dataset.cases
    }:
        raise ValueError("observations must contain exactly one result for every case")
    ordered_cases = sorted(dataset.cases, key=lambda case: case.id)
    structural_cases = []
    for case in ordered_cases:
        checks = _structural_checks(case, by_case[case.id])
        structural_cases.append(
            {
                "id": case.id,
                "passed": all(checks.values()),
                "expected_behavior_match": by_case[case.id].decision
                == case.expected_behavior,
                "checks": checks,
            }
        )
    passed = sum(item["passed"] for item in structural_cases)
    token_usage: dict[str, int] = {}
    total_cost = Decimal("0")
    cost_observed = False
    provider_errors = 0
    end_to_end_latencies = []
    for observation in observations:
        for name, value in observation.token_usage.items():
            token_usage[name] = token_usage.get(name, 0) + value
        if observation.cost_usd is not None:
            total_cost += Decimal(observation.cost_usd)
            cost_observed = True
        provider_errors += int(observation.provider_error is not None)
        end_to_end_latencies.append(observation.end_to_end_latency_ms)
    scorer_usage: dict[str, int] = {}
    scorer_total_cost = Decimal("0")
    scorer_cost_observed = False
    scorer_latencies: list[float] = []
    scorer_errors = 0
    for evaluation in semantic_evaluations:
        for name, value in evaluation.token_usage.items():
            scorer_usage[name] = scorer_usage.get(name, 0) + value
        if evaluation.cost_usd is not None:
            scorer_total_cost += Decimal(evaluation.cost_usd)
            scorer_cost_observed = True
        scorer_latencies.append(evaluation.latency_ms)
        scorer_errors += int(evaluation.error is not None)
    if mode == "model-backed":
        if not scorer_method:
            raise ValueError("model-backed report requires scorer measurement method")
        semantic = _build_semantic_report(
            dataset,
            semantic_evaluations,
            provenance=provenance,
            measurement_method=scorer_method,
        )
    else:
        if semantic_evaluations:
            raise ValueError("deterministic-local report cannot contain semantic evaluations")
        semantic = {
            "status": "not_run",
            "reason": "model_backed_required",
        }
    return {
        "schema_version": 1,
        "mode": mode,
        "provenance": asdict(provenance),
        "structural": {
            "denominator": len(structural_cases),
            "passed": passed,
            "pass_rate": passed / len(structural_cases),
            "hard_gate_passed": passed == len(structural_cases),
            "cases": structural_cases,
        },
        "retrieval": score_retrieval(
            dataset.cases, observations, candidate_k=8
        ),
        "semantic": semantic,
        "system": {
            "end_to_end_latency_ms": {
                "mean": sum(end_to_end_latencies) / len(end_to_end_latencies),
                "min": min(end_to_end_latencies),
                "max": max(end_to_end_latencies),
            },
            "token_usage": dict(sorted(token_usage.items())),
            "usage_status": (
                "observed"
                if token_usage
                else "zero_by_contract"
                if mode == "deterministic-local"
                else "unavailable"
            ),
            "cost_usd": format(total_cost, "f") if cost_observed else None,
            "cost_status": (
                "observed"
                if cost_observed
                else "zero_by_contract"
                if mode == "deterministic-local"
                else "unavailable"
            ),
            "provider_errors": provider_errors,
            "semantic_scorer": {
                "latency_ms": {
                    "mean": sum(scorer_latencies) / len(scorer_latencies)
                    if scorer_latencies
                    else None,
                    "min": min(scorer_latencies) if scorer_latencies else None,
                    "max": max(scorer_latencies) if scorer_latencies else None,
                },
                "token_usage": dict(sorted(scorer_usage.items())),
                "usage_status": (
                    "observed"
                    if scorer_usage
                    else "unavailable"
                    if mode == "model-backed"
                    else "not_applicable"
                ),
                "cost_usd": (
                    format(scorer_total_cost, "f") if scorer_cost_observed else None
                ),
                "cost_status": (
                    "observed"
                    if scorer_cost_observed
                    else "unavailable"
                    if mode == "model-backed"
                    else "not_applicable"
                ),
                "provider_errors": scorer_errors,
            },
        },
    }


def validate_mode(
    mode: str,
    *,
    provider_mode: str,
    scorer_version: str | None,
    scorer_method: str | None = None,
) -> None:
    if mode == "deterministic-local":
        if provider_mode != "deterministic-local":
            raise ValueError(
                "deterministic-local mode requires deterministic-local provider"
            )
        return
    if mode != "model-backed":
        raise ValueError(f"unsupported evaluation mode: {mode}")
    missing = []
    if provider_mode != "openai-compatible":
        missing.append("openai-compatible provider")
    if not scorer_version:
        missing.append("scorer version")
    if not scorer_method:
        missing.append("scorer measurement method")
    if missing:
        raise ValueError("model-backed mode requires " + " and ".join(missing))


def write_report_atomic(path: Path, report: dict[str, object]) -> None:
    if path.exists():
        raise FileExistsError(f"report already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            raise FileExistsError(f"report already exists: {path}") from None
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def normalize_report(report: dict[str, object]) -> dict[str, object]:
    normalized = json.loads(json.dumps(report))
    normalized.get("retrieval", {}).pop("latency_ms", None)
    normalized.get("system", {}).pop("end_to_end_latency_ms", None)
    normalized.get("system", {}).get("semantic_scorer", {}).pop("latency_ms", None)
    return normalized
