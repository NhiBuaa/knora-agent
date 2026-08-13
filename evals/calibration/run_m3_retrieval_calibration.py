import hashlib
import json
import math
import os
import sys
from math import ceil
from pathlib import Path
from typing import Any

from knora.answering.calibration_v2 import (
    CalibrationCaseObservation,
    CalibrationPolicy,
    CalibrationSnapshot,
    select_calibrated_threshold,
)
from knora.providers.embedding import EmbeddingConfiguration
from knora.providers.gemini.embedding import GeminiEmbeddingProvider


def canonical_json(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode()


def sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def cosine(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    numerator = math.fsum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(math.fsum(value * value for value in left))
    right_norm = math.sqrt(math.fsum(value * value for value in right))
    if left_norm == 0.0 or right_norm == 0.0:
        raise ValueError("provider returned a zero vector")
    return numerator / (left_norm * right_norm)


def load_inputs(base: Path) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    manifest = json.loads((base / "manifest.json").read_text(encoding="utf-8"))
    documents = []
    for member in manifest["files"]:
        if member["path"].startswith("corpus/"):
            documents.append(
                {
                    "chunk_id": f"calibration/{Path(member['path']).stem}#0",
                    "content": (base / member["path"]).read_text(encoding="utf-8"),
                }
            )
    cases = [
        json.loads(line)
        for line in (base / "cases.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    return sorted(documents, key=lambda item: item["chunk_id"]), cases


def metrics(
    snapshot_cases: list[CalibrationCaseObservation],
    hard_negative_similarities: list[float],
) -> dict[str, Any]:
    recalls = []
    first_gold_scores = []
    top_two_hits = 0
    for case in snapshot_cases:
        gold = set(case.gold_chunk_ids)
        ranked_gold = [
            score
            for chunk_id, score in zip(
                case.top_chunk_ids, case.top_similarities, strict=True
            )
            if chunk_id in gold
        ]
        recalls.append(len(ranked_gold) / len(gold))
        if ranked_gold:
            first_gold_scores.append(max(ranked_gold))
        top_two_hits += bool(gold.intersection(case.top_chunk_ids[:2]))
    ordered_first_gold = sorted(first_gold_scores)
    p10_index = max(0, ceil(0.10 * len(ordered_first_gold)) - 1)
    hard_max = max(hard_negative_similarities, default=float("-inf"))
    boundaries = sorted(
        {
            round(score, 12)
            for case in snapshot_cases
            for score in case.top_similarities
        },
        reverse=True,
    )
    max_observed = max(boundaries)
    empty_boundary = math.nextafter(max_observed, math.inf)
    return {
        "applicable_case_count": len(snapshot_cases),
        "mean_recall_at_8": format(math.fsum(recalls) / len(recalls), ".12f"),
        "top_two_gold_rate": format(top_two_hits / len(snapshot_cases), ".12f"),
        "first_gold_similarities": [format(value, ".12f") for value in first_gold_scores],
        "p10_first_gold_similarity": format(ordered_first_gold[p10_index], ".12f"),
        "hard_negative_max_similarity": format(hard_max, ".12f"),
        "observed_boundaries": [format(value, ".12f") for value in boundaries],
        "empty_above_max_boundary": format(empty_boundary, ".12f"),
        "score_precision_decimals": 12,
        "percentile_method": "nearest-rank",
        "boundary_inclusion": "similarity >= threshold",
    }


def execute(base: Path, run_manifest_path: Path, output_path: Path) -> None:
    run_manifest_bytes = run_manifest_path.read_bytes()
    run_manifest = json.loads(run_manifest_bytes)
    frozen_digest = sha256((base / "manifest.json").read_bytes())
    if run_manifest["frozen_calibration_sha256"] != frozen_digest:
        raise ValueError("first-run manifest is not bound to frozen calibration")
    if run_manifest["execution_status"] != "authorized-before-first-execution":
        raise ValueError("first-run manifest is not pre-authorized")
    configuration = EmbeddingConfiguration.gemini_m3()
    if run_manifest["embedding_configuration"] != {
        "id": configuration.id,
        "provider": configuration.provider,
        "deployment_identity": configuration.deployment_identity,
        "api_contract_version": configuration.api_contract_version,
        "model": configuration.model,
        "dimensions": configuration.dimensions,
        "input_normalization": configuration.input_normalization,
        "input_policy_id": configuration.input_policy_id,
        "output_dimensionality": configuration.output_dimensionality,
        "vector_normalization": configuration.vector_normalization,
        "distance_metric": configuration.distance_metric,
    }:
        raise ValueError("first-run manifest embedding configuration mismatch")
    api_key = os.environ.get("KNORA_GEMINI_API_KEY")
    if not api_key:
        raise ValueError("runtime Gemini credential is absent")
    documents, cases = load_inputs(base)
    provider = GeminiEmbeddingProvider(api_key=api_key)
    try:
        document_batch = provider.embed_documents(
            [document["content"] for document in documents], configuration
        )
        observations: list[dict[str, Any]] = []
        snapshot_cases: list[CalibrationCaseObservation] = []
        hard_negative_similarities: list[float] = []
        for case in cases:
            query_vector = provider.embed_queries(
                [case["question"]], configuration
            ).vectors[0]
            ranked = sorted(
                (
                    {
                        "chunk_id": document["chunk_id"],
                        "similarity": cosine(query_vector, vector),
                    }
                    for document, vector in zip(
                        documents, document_batch.vectors, strict=True
                    )
                ),
                key=lambda item: (-item["similarity"], item["chunk_id"]),
            )[:8]
            observed = {
                "case_id": case["id"],
                "applicable": case["applicable"],
                "gold_chunk_ids": case["gold_chunk_refs"],
                "candidates": [
                    {
                        "rank": rank,
                        "chunk_id": item["chunk_id"],
                        "similarity": format(item["similarity"], ".12f"),
                    }
                    for rank, item in enumerate(ranked, start=1)
                ],
            }
            observations.append(observed)
            if case["applicable"]:
                snapshot_cases.append(
                    CalibrationCaseObservation(
                        case_id=case["id"],
                        top_similarities=tuple(item["similarity"] for item in ranked),
                        gold_chunk_ids=tuple(case["gold_chunk_refs"]),
                        top_chunk_ids=tuple(item["chunk_id"] for item in ranked),
                    )
                )
            else:
                hard_negative_similarities.extend(
                    item["similarity"] for item in ranked
                )
    finally:
        provider.close()
        api_key = ""
    observed_table = {
        "schema_version": 1,
        "run_id": run_manifest["run_id"],
        "frozen_calibration_sha256": frozen_digest,
        "first_run_manifest_sha256": sha256(run_manifest_bytes),
        "embedding_configuration_id": configuration.id,
        "vector_candidate_k": 8,
        "threshold_applied": False,
        "observations": observations,
    }
    observed_table_bytes = canonical_json(observed_table)
    observed_digest = sha256(observed_table_bytes)
    snapshot = CalibrationSnapshot(
        artifact_id="m3-retrieval-calibration-v1",
        artifact_sha256=frozen_digest,
        observed_table_sha256=observed_digest,
        cases=tuple(snapshot_cases),
        hard_negative_similarities=tuple(hard_negative_similarities),
    )
    first = select_calibrated_threshold(snapshot, CalibrationPolicy.r9())
    second = select_calibrated_threshold(snapshot, CalibrationPolicy.r9())
    if first != second:
        raise ValueError("threshold selection is not deterministic on sealed observations")
    result = {
        "schema_version": 1,
        "run_id": run_manifest["run_id"],
        "frozen_calibration_sha256": frozen_digest,
        "first_run_manifest_sha256": sha256(run_manifest_bytes),
        "observed_table_sha256": observed_digest,
        "observed_table": observed_table,
        "metrics_and_boundaries": metrics(
            snapshot_cases, hard_negative_similarities
        ),
        "selection_repeated_on_same_table": True,
        "calibration_status": first.status.value,
        "gate_results": {
            "mean_recall_at_8": first.gate_results[0],
            "top_two_gold_rate": first.gate_results[1],
            "hard_negative_below_p10_first_gold": first.gate_results[2],
            "preserving_observed_boundary_exists": first.gate_results[3],
        },
        "vector_min_similarity": (
            format(first.vector_min_similarity, ".12f")
            if first.vector_min_similarity is not None
            else None
        ),
        "credential_retained": False,
        "provider_vectors_retained": False,
        "provider_payloads_retained": False,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(canonical_json(result))
    print(
        json.dumps(
            {
                "calibration_status": result["calibration_status"],
                "gate_results": result["gate_results"],
                "observed_table_sha256": observed_digest,
                "result_sha256": sha256(output_path.read_bytes()),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    execute(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))
