import hashlib
import json
import math

import pytest

from knora.answering.retrieval_configuration import (
    CALIBRATED_M3_VECTOR_MIN_SIMILARITY,
    DeploymentRetrievalConfigurationResolver,
    resolve_qwen_retrieval_configuration,
    resolve_retrieval_configuration,
    retrieval_configuration_for_id,
)


def test_deployment_resolver_returns_pinned_hybrid_configuration_for_any_workspace() -> None:
    resolver = DeploymentRetrievalConfigurationResolver(
        retrieval_configuration_for_id("retrieval-m3-rrf-v1")
    )

    configuration = resolver.resolve(workspace_id="evaluation-m3-v1")

    assert configuration.id == "retrieval-m3-rrf-v1"
    assert configuration.strategy == "hybrid"


def test_resolver_rejects_unknown_configuration_and_blank_workspace() -> None:
    with pytest.raises(ValueError, match="unsupported retrieval configuration"):
        retrieval_configuration_for_id("evaluation-override")
    with pytest.raises(ValueError, match="workspace_id"):
        DeploymentRetrievalConfigurationResolver(
            retrieval_configuration_for_id("retrieval-m1-v1")
        ).resolve(workspace_id="")


def test_v2_resolver_fails_closed_without_calibrated_threshold() -> None:
    with pytest.raises(ValueError, match="exact calibrated numeric threshold"):
        resolve_retrieval_configuration("retrieval-m3-rrf-v2", vector_min_similarity=None)


def test_v2_resolver_builds_exact_paired_configuration() -> None:
    result = resolve_retrieval_configuration(
        "retrieval-m3-rrf-v2",
        vector_min_similarity=CALIBRATED_M3_VECTOR_MIN_SIMILARITY,
    )

    assert result.id == "retrieval-m3-rrf-v2"
    assert result.min_similarity == 0.657410732025
    assert result.fusion_policy_id == "rrf-v2"


def test_v2_resolver_rejects_guessed_or_inherited_numeric_threshold() -> None:
    with pytest.raises(ValueError, match="exact calibrated numeric threshold"):
        resolve_retrieval_configuration("retrieval-m3-vector-v2", vector_min_similarity=0.65)


def test_qwen_configuration_requires_a_sealed_matching_artifact() -> None:
    artifact = {
        "schema_version": 1,
        "status": "PASSED",
        "profile_id": "embedding-ollama-qwen3-test",
        "model_digest": "sha256:" + "e" * 64,
        "dataset_sha256": "a" * 64,
        "corpus_sha256": "b" * 64,
        "chunk_set_ids": ["chunk-set-1"],
        "policy_id": "qwen-vietnamese-evidence-v1",
        "threshold": 0.72,
        "held_out_hit_at_5": 1.0,
        "held_out_false_insufficient_evidence_rate": 0.0,
        "held_out_negative_refusal_rate": 1.0,
        "regression_case_passed": True,
    }
    artifact["artifact_sha256"] = hashlib.sha256(
        json.dumps(artifact, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    configuration = resolve_qwen_retrieval_configuration(
        artifact,
        profile_id="embedding-ollama-qwen3-test",
        model_digest="sha256:" + "e" * 64,
        dataset_sha256="a" * 64,
        corpus_sha256="b" * 64,
        chunk_set_ids=("chunk-set-1",),
    )
    assert configuration.candidate_k == 16
    assert configuration.max_evidence_chunks == 5
    assert configuration.min_similarity == 0.72
    with pytest.raises(ValueError, match="calibration"):
        resolve_qwen_retrieval_configuration(
            {**artifact, "threshold": 0.60},
            profile_id="embedding-ollama-qwen3-test",
            model_digest="sha256:" + "e" * 64,
            dataset_sha256="a" * 64,
            corpus_sha256="b" * 64,
            chunk_set_ids=("chunk-set-1",),
        )
    for mismatched in (
        {"profile_id": "another-profile"},
        {"dataset_sha256": "c" * 64},
        {"corpus_sha256": "d" * 64},
        {"model_digest": "sha256:" + "f" * 64},
        {"chunk_set_ids": ("chunk-set-2",)},
    ):
        with pytest.raises(ValueError, match="calibration"):
            resolve_qwen_retrieval_configuration(
                artifact,
                profile_id=mismatched.get("profile_id", "embedding-ollama-qwen3-test"),
                model_digest=mismatched.get("model_digest", "sha256:" + "e" * 64),
                dataset_sha256=mismatched.get("dataset_sha256", "a" * 64),
                corpus_sha256=mismatched.get("corpus_sha256", "b" * 64),
                chunk_set_ids=mismatched.get("chunk_set_ids", ("chunk-set-1",)),
            )
    another = {**artifact, "threshold": 0.73}
    another["artifact_sha256"] = hashlib.sha256(
        json.dumps(
            {key: value for key, value in another.items() if key != "artifact_sha256"},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    other_configuration = resolve_qwen_retrieval_configuration(
        another,
        profile_id="embedding-ollama-qwen3-test",
        model_digest="sha256:" + "e" * 64,
        dataset_sha256="a" * 64,
        corpus_sha256="b" * 64,
        chunk_set_ids=("chunk-set-1",),
    )
    assert other_configuration.id != configuration.id
    invalid_metric = {**artifact, "held_out_hit_at_5": math.nan}
    invalid_metric["artifact_sha256"] = hashlib.sha256(
        json.dumps(
            {key: value for key, value in invalid_metric.items() if key != "artifact_sha256"},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    with pytest.raises(ValueError, match="calibration"):
        resolve_qwen_retrieval_configuration(
            invalid_metric,
            profile_id="embedding-ollama-qwen3-test",
            model_digest="sha256:" + "e" * 64,
            dataset_sha256="a" * 64,
            corpus_sha256="b" * 64,
            chunk_set_ids=("chunk-set-1",),
        )


def test_qwen_configuration_rejects_failed_artifact() -> None:
    with pytest.raises(ValueError, match="calibration"):
        resolve_qwen_retrieval_configuration(
            {"status": "FAILED"},
            profile_id="profile",
            model_digest="sha256:" + "e" * 64,
            dataset_sha256="a" * 64,
            corpus_sha256="b" * 64,
            chunk_set_ids=("chunk-set-1",),
        )


def test_containment_configuration_changes_only_identity_and_overlap():
    from dataclasses import replace

    from knora.answering.retrieval_configuration import resolve_retrieval_configuration
    from knora.answering.stores import RetrievalConfiguration

    actual = resolve_retrieval_configuration(
        "retrieval-evidence-containment-v1", vector_min_similarity=None
    )
    assert actual == replace(
        RetrievalConfiguration.milestone_one(),
        id="retrieval-evidence-containment-v1",
        overlap_policy="adjacent-content-containment-v1",
    )


def test_qwen_containment_candidate_preserves_existing_deployment_policies():
    from knora.answering.stores import RetrievalConfiguration

    candidate = RetrievalConfiguration.qwen_containment_candidate_v2(
        min_similarity=0.51, provenance_sha256="f" * 64
    )
    assert candidate.candidate_k == candidate.vector_candidate_k == 16
    assert candidate.min_similarity == 0.51
    assert candidate.max_evidence_chunks == 5
    assert candidate.max_evidence_tokens == 3000
    assert candidate.overlap_policy == "adjacent-content-containment-v1"
    assert candidate.id == "retrieval-qwen-containment-candidate-v2-" + "f" * 24
    assert RetrievalConfiguration.milestone_one().min_similarity == 0.65
    assert RetrievalConfiguration.qwen_vietnamese_v1(
        min_similarity=0.51, artifact_sha256="f" * 64
    ).overlap_policy == "adjacent-token-overlap-v1"
    with pytest.raises(ValueError, match="unsupported"):
        retrieval_configuration_for_id(candidate.id)


@pytest.mark.parametrize("threshold", [float("nan"), float("inf"), True, -1.1, 1.1])
def test_qwen_candidate_rejects_invalid_threshold(threshold):
    from knora.answering.stores import RetrievalConfiguration

    with pytest.raises(ValueError, match="candidate"):
        RetrievalConfiguration.qwen_containment_candidate_v2(
            min_similarity=threshold, provenance_sha256="f" * 64
        )


@pytest.mark.parametrize("digest", ["", "diagnostic-unsealed", "a" * 63, "z" * 64])
def test_qwen_candidate_requires_complete_provenance_digest(digest):
    from knora.answering.stores import RetrievalConfiguration

    with pytest.raises(ValueError, match="candidate"):
        RetrievalConfiguration.qwen_containment_candidate_v2(
            min_similarity=0.5, provenance_sha256=digest
        )
