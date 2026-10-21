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
    assert (
        RetrievalConfiguration.qwen_vietnamese_v1(
            min_similarity=0.51, artifact_sha256="f" * 64
        ).overlap_policy
        == "adjacent-token-overlap-v1"
    )
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


def test_v3_dense_and_hybrid_configuration_registration() -> None:
    from knora.answering.retrieval_configuration import (
        resolve_retrieval_configuration,
        retrieval_configuration_for_id,
    )

    dense = retrieval_configuration_for_id("retrieval-dense-top8-v3")
    assert dense.id == "retrieval-dense-top8-v3"
    assert dense.strategy == "dense-only"
    assert dense.candidate_k == 8
    assert dense.vector_candidate_k == 200
    assert dense.min_similarity == 0.65
    assert dense.lexical_policy_id is None
    assert dense.fusion_policy_id is None
    assert dense.overlap_policy == "adjacent-content-containment-v1"

    hybrid = retrieval_configuration_for_id("retrieval-hybrid-top8-v3")
    assert hybrid.id == "retrieval-hybrid-top8-v3"
    assert hybrid.strategy == "hybrid"
    assert hybrid.candidate_k == 8
    assert hybrid.vector_candidate_k == 200
    assert hybrid.fts_candidate_k == 200
    assert hybrid.min_similarity == 0.65
    assert hybrid.lexical_policy_id == "bm25-word-frozen47-population-v1"
    assert hybrid.fusion_policy_id == "dbsf-v1"
    assert hybrid.overlap_policy == "adjacent-content-containment-v1"

    assert (
        resolve_retrieval_configuration("retrieval-dense-top8-v3", vector_min_similarity=None)
        == dense
    )
    assert (
        resolve_retrieval_configuration("retrieval-hybrid-top8-v3", vector_min_similarity=None)
        == hybrid
    )


def test_v3_retrieval_embedding_compatibility_validation() -> None:
    from knora.answering.retrieval_configuration import validate_retrieval_embedding_compatibility
    from knora.answering.stores import RetrievalConfiguration
    from knora.providers.embedding import EmbeddingConfiguration

    bm25 = RetrievalConfiguration.bm25_top8_v1()
    dense = RetrievalConfiguration.dense_top8_v3()
    hybrid = RetrievalConfiguration.hybrid_top8_v3()
    cf_embedding = EmbeddingConfiguration.cloudflare_qwen3_06b()

    # Sparse-only requires no embedding configuration
    validate_retrieval_embedding_compatibility(bm25, None)
    validate_retrieval_embedding_compatibility(bm25, cf_embedding)

    # Dense and hybrid require a valid embedding configuration
    validate_retrieval_embedding_compatibility(dense, cf_embedding)
    validate_retrieval_embedding_compatibility(hybrid, cf_embedding)

    with pytest.raises(ValueError, match="requires an embedding configuration"):
        validate_retrieval_embedding_compatibility(dense, None)

    with pytest.raises(ValueError, match="requires an embedding configuration"):
        validate_retrieval_embedding_compatibility(hybrid, None)

    invalid_dims = EmbeddingConfiguration(
        id="invalid-dims",
        provider="cloudflare-workers-ai",
        model="@cf/qwen/qwen3-embedding-0.6b",
        dimensions=0,
        distance_metric="cosine",
    )
    with pytest.raises(ValueError, match="dimensions"):
        validate_retrieval_embedding_compatibility(dense, invalid_dims)

    invalid_metric = EmbeddingConfiguration(
        id="invalid-metric",
        provider="cloudflare-workers-ai",
        model="@cf/qwen/qwen3-embedding-0.6b",
        dimensions=1024,
        distance_metric="euclidean",
    )
    with pytest.raises(ValueError, match="unsupported distance metric"):
        validate_retrieval_embedding_compatibility(dense, invalid_metric)


def test_v3_dense_hybrid_configuration_validation_rules() -> None:
    from knora.answering.stores import RetrievalConfiguration

    # Dense-only cannot have lexical policy or fusion policy
    with pytest.raises(ValueError, match="dense-only retrieval requires no lexical policy"):
        RetrievalConfiguration(
            id="test-dense-bad",
            candidate_k=8,
            min_similarity=0.65,
            max_evidence_chunks=5,
            max_evidence_tokens=3000,
            overlap_policy="adjacent-content-containment-v1",
            strategy="dense-only",
            lexical_policy_id="bm25-word-frozen47-population-v1",
        )

    # Dense-only requires min_similarity
    with pytest.raises(ValueError, match="dense/hybrid retrieval requires its vector threshold"):
        RetrievalConfiguration(
            id="test-dense-no-sim",
            candidate_k=8,
            min_similarity=None,
            max_evidence_chunks=5,
            max_evidence_tokens=3000,
            overlap_policy="adjacent-content-containment-v1",
            strategy="dense-only",
        )

    # Hybrid requires lexical policy and fusion policy
    with pytest.raises(ValueError, match="hybrid retrieval requires a lexical policy"):
        RetrievalConfiguration(
            id="test-hybrid-no-lex",
            candidate_k=8,
            min_similarity=0.65,
            max_evidence_chunks=5,
            max_evidence_tokens=3000,
            overlap_policy="adjacent-content-containment-v1",
            strategy="hybrid",
            fusion_policy_id="dbsf-v1",
        )

    with pytest.raises(ValueError, match="hybrid retrieval requires a fusion policy"):
        RetrievalConfiguration(
            id="test-hybrid-no-fusion",
            candidate_k=8,
            min_similarity=0.65,
            max_evidence_chunks=5,
            max_evidence_tokens=3000,
            overlap_policy="adjacent-content-containment-v1",
            strategy="hybrid",
            lexical_policy_id="bm25-word-frozen47-population-v1",
        )


def test_v3_branch_observation_dense_branch_mapping() -> None:
    from knora.answering.stores import BranchObservation

    obs = BranchObservation(
        branch="dense",
        status="ELIGIBLE",
        chunk_id="chunk-1",
        branch_rank=1,
        similarity=0.88,
        cosine_distance=0.12,
        raw_score=0.88,
        score_kind="cosine_similarity",
        index_generation_id="gen-1",
        decision_reason="scored",
    )
    mapping = obs.as_mapping()
    assert mapping["schema_version"] == 2
    assert mapping["branch"] == "dense"
    assert mapping["status"] == "ELIGIBLE"
    assert mapping["chunk_id"] == "chunk-1"
    assert mapping["branch_rank"] == 1
    assert mapping["raw_score"] == 0.88
    assert mapping["score_kind"] == "cosine_similarity"
    assert mapping["index_generation_id"] == "gen-1"
    assert mapping["decision_reason"] == "scored"
    # Ensure no external SDK object is exposed
    assert all(isinstance(v, (str, int, float, list, type(None))) for v in mapping.values())


def test_candidate_locator_parity_across_bm25_dense_hybrid_modes() -> None:
    from knora.answering.stores import RetrievalCandidate

    common_locators = {
        "document_id": "doc-test",
        "document_version_id": "ver-test",
        "source_key": "policy",
        "source_name": "policy.pdf",
        "chunk_set_id": "set-1",
        "chunk_id": "chunk-1",
        "chunk_ordinal": 0,
        "heading_path": ("Ch 1", "Sec A"),
        "start_line": 5,
        "end_line": 15,
        "content": "Policy text content.",
        "content_checksum": "hash123",
        "token_count": 8,
        "page_start": 2,
        "page_end": 2,
        "start_offset": 50,
        "end_offset": 120,
        "index_generation_id": "gen-1",
    }

    bm25_candidate = RetrievalCandidate(
        **common_locators,
        embedding_set_id=None,
        embedding_configuration_id=None,
        cosine_distance=None,
        similarity=None,
        bm25_score=14.5,
        bm25_rank=1,
    )

    dense_candidate = RetrievalCandidate(
        **common_locators,
        embedding_set_id="emb-set-1",
        embedding_configuration_id="embedding-cloudflare-qwen3-06b-v1",
        cosine_distance=0.15,
        similarity=0.85,
        vector_contribution={"similarity": 0.85, "cosine_distance": 0.15},
    )

    hybrid_candidate = RetrievalCandidate(
        **common_locators,
        embedding_set_id="emb-set-1",
        embedding_configuration_id="embedding-cloudflare-qwen3-06b-v1",
        cosine_distance=0.15,
        similarity=0.85,
        bm25_score=14.5,
        bm25_rank=1,
        fusion_score=0.92,
        vector_contribution={"similarity": 0.85},
        fts_contribution={"bm25_score": 14.5},
    )

    # Locators must be identical across all three modes
    for loc_key, loc_val in common_locators.items():
        assert getattr(bm25_candidate, loc_key) == loc_val
        assert getattr(dense_candidate, loc_key) == loc_val
        assert getattr(hybrid_candidate, loc_key) == loc_val
