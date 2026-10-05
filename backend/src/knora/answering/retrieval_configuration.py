"""Production retrieval configuration resolution.

The resolver is intentionally a composition seam: HTTP requests never select retrieval strategy.
"""

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Protocol

from knora.answering.stores import RetrievalConfiguration


class RetrievalConfigurationResolver(Protocol):
    def resolve(self, *, workspace_id: str) -> RetrievalConfiguration: ...


@dataclass(frozen=True, slots=True)
class DeploymentRetrievalConfigurationResolver:
    """Resolve one immutable deployment configuration for every production Workspace."""

    configuration: RetrievalConfiguration

    def resolve(self, *, workspace_id: str) -> RetrievalConfiguration:
        if not workspace_id:
            raise ValueError("workspace_id must not be blank")
        return self.configuration


def retrieval_configuration_for_id(configuration_id: str) -> RetrievalConfiguration:
    configurations = {
        "retrieval-m1-v1": RetrievalConfiguration.milestone_one(),
        "retrieval-evidence-containment-v1": RetrievalConfiguration.evidence_containment_v1(),
        "retrieval-m3-rrf-v1": RetrievalConfiguration.milestone_three_hybrid(),
    }
    try:
        return configurations[configuration_id]
    except KeyError as error:
        raise ValueError("unsupported retrieval configuration") from error


CALIBRATED_M3_VECTOR_MIN_SIMILARITY = 0.657410732025


def _valid_calibration_rate(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and 0 <= value <= 1
    )


def resolve_retrieval_configuration(
    configuration_id: str, *, vector_min_similarity: float | None
) -> RetrievalConfiguration:
    """Resolve the immutable deployment configuration, including calibrated v2 variants."""
    if configuration_id in {
        "retrieval-m1-v1",
        "retrieval-m3-rrf-v1",
        "retrieval-evidence-containment-v1",
    }:
        return retrieval_configuration_for_id(configuration_id)
    if configuration_id not in {"retrieval-m3-vector-v2", "retrieval-m3-rrf-v2"}:
        raise ValueError("unsupported retrieval configuration")
    if vector_min_similarity != CALIBRATED_M3_VECTOR_MIN_SIMILARITY:
        raise ValueError("v2 retrieval requires the exact calibrated numeric threshold")
    if configuration_id == "retrieval-m3-vector-v2":
        return RetrievalConfiguration.milestone_three_vector_v2(
            min_similarity=vector_min_similarity
        )
    return RetrievalConfiguration.milestone_three_hybrid_v2(min_similarity=vector_min_similarity)


def resolve_qwen_retrieval_configuration(
    sealed_artifact: dict[str, object],
    *,
    profile_id: str,
    model_digest: str,
    dataset_sha256: str,
    corpus_sha256: str,
    chunk_set_ids: tuple[str, ...],
) -> RetrievalConfiguration:
    """Resolve the Qwen policy only from a matching, passing calibration artifact."""
    if sealed_artifact.get("artifact_sha256") is None:
        raise ValueError("calibration artifact is unsealed")
    payload = {key: value for key, value in sealed_artifact.items() if key != "artifact_sha256"}
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    if sealed_artifact["artifact_sha256"] != digest:
        raise ValueError("calibration artifact checksum mismatch")
    threshold = sealed_artifact.get("threshold")
    hit_at_5 = sealed_artifact.get("held_out_hit_at_5")
    false_insufficient = sealed_artifact.get("held_out_false_insufficient_evidence_rate")
    negative_refusal = sealed_artifact.get("held_out_negative_refusal_rate")
    if (
        sealed_artifact.get("schema_version") != 1
        or sealed_artifact.get("status") != "PASSED"
        or sealed_artifact.get("profile_id") != profile_id
        or sealed_artifact.get("model_digest") != model_digest
        or sealed_artifact.get("dataset_sha256") != dataset_sha256
        or sealed_artifact.get("corpus_sha256") != corpus_sha256
        or sealed_artifact.get("chunk_set_ids") != list(chunk_set_ids)
        or sealed_artifact.get("policy_id") != "qwen-vietnamese-evidence-v1"
        or not isinstance(threshold, (int, float))
        or isinstance(threshold, bool)
        or not math.isfinite(threshold)
        or not -1 <= threshold <= 1
        or not _valid_calibration_rate(hit_at_5)
        or hit_at_5 < 0.80
        or not _valid_calibration_rate(false_insufficient)
        or false_insufficient > 0.10
        or not _valid_calibration_rate(negative_refusal)
        or negative_refusal != 1.0
        or sealed_artifact.get("regression_case_passed") is not True
    ):
        raise ValueError("calibration artifact does not satisfy Qwen evidence policy")
    return RetrievalConfiguration.qwen_vietnamese_v1(
        min_similarity=threshold, artifact_sha256=digest
    )
