import subprocess
from pathlib import Path

import pytest
from evals.runners.milestone_3 import HttpEvaluationExecutor, ProductionM3Executor
from evals.runners.milestone_3_comparison import (
    M3_POPULATION_SOURCE_COMMIT,
    ComparisonError,
    _validate_m3_manifest_source_commit,
    validate_m3_population_provenance,
)


def test_m3_executor_uses_one_canonical_class_with_compatibility_alias() -> None:
    assert ProductionM3Executor is HttpEvaluationExecutor


def test_m3_population_manifests_bind_to_immutable_source_commit() -> None:
    repository_root = Path(__file__).resolve().parents[2]
    assert M3_POPULATION_SOURCE_COMMIT == "2a6061ad38b3b3c4f06811c7ceb8bc26af39892"
    expected = {
        "evals/datasets/milestone_3.manifest.json": "08061b4a26b1d10b9720769828bb179264d99fec",
        "evals/corpora/milestone_3/manifest.json": "5b8ff82769239f253d31424606205a9e74828d71",
    }
    for path, blob in expected.items():
        actual = subprocess.run(
            ["git", "rev-parse", f"{M3_POPULATION_SOURCE_COMMIT}:{path}"],
            cwd=repository_root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        assert actual == blob

    with pytest.raises(ComparisonError, match="PROVENANCE_MISMATCH"):
        _validate_m3_manifest_source_commit(
            repository_root, "ab8abd88fdce0dccead869b27416fee260bc135e"
        )


def test_m3_population_provenance_binds_exact_manifest_and_source_set() -> None:
    report = {
        "provenance": {
            "dataset_version": "m3-dataset-v1",
            "dataset_digest": (
                "sha256:1830dd47863eae06927a4a6c2eb927b13899784ff94c83f522931ca6ec3ccc50"
            ),
            "corpus_id": "m3-corpus-v1",
            "corpus_digest": (
                "sha256:6b0daffe9acb7e541bb1621efb6880cd013d6af6e851f91867b36899d3eca326"
            ),
            "chunk_set_id": "chunk-set-m3-v1",
            "workspace": "evaluation-m3-v1",
        },
        "binding_v3": {
            "schema_version": 3,
            "dataset_manifest_identity": "m3-dataset-v1",
            "corpus_manifest_identity": "m3-corpus-v1",
            "chunk_set_provenance_id": "chunk-set-m3-v1",
            "workspace_id": "evaluation-m3-v1",
            "source_bindings": [
                {
                    "source_key": source_key,
                    "production_document_version_id": f"version-{index}",
                    "production_chunk_set_id": f"chunk-set-{index}",
                }
                for index, source_key in enumerate(
                    (
                        "support/account-security",
                        "support/billing-policy",
                        "support/refund-policy",
                        "support/shipping-policy",
                    ),
                    start=1,
                )
            ],
        },
    }

    validate_m3_population_provenance(
        report, repository_root=Path(__file__).resolve().parents[2]
    )
