import pytest

from knora.answering.retrieval_configuration import (
    CALIBRATED_M3_VECTOR_MIN_SIMILARITY,
    resolve_retrieval_configuration,
)


def test_v2_resolver_fails_closed_without_calibrated_threshold() -> None:
    with pytest.raises(ValueError, match="exact calibrated numeric threshold"):
        resolve_retrieval_configuration(
            "retrieval-m3-rrf-v2", vector_min_similarity=None
        )


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
        resolve_retrieval_configuration(
            "retrieval-m3-vector-v2", vector_min_similarity=0.65
        )
