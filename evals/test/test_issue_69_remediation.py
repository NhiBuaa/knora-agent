import subprocess
from pathlib import Path

from evals.runners.milestone_3 import HttpEvaluationExecutor, ProductionM3Executor
from evals.runners.milestone_3_comparison import _M3_MANIFEST_SOURCE_COMMIT


def test_m3_executor_uses_one_canonical_class_with_compatibility_alias() -> None:
    assert ProductionM3Executor is HttpEvaluationExecutor


def test_m3_population_manifests_bind_to_immutable_source_commit() -> None:
    repository_root = Path(__file__).resolve().parents[2]
    expected = {
        "evals/datasets/milestone_3.manifest.json": "08061b4a26b1d10b9720769828bb179264d99fec",
        "evals/corpora/milestone_3/manifest.json": "5b8ff82769239f253d31424606205a9e74828d71",
    }
    for path, blob in expected.items():
        actual = subprocess.run(
            ["git", "rev-parse", f"{_M3_MANIFEST_SOURCE_COMMIT}:{path}"],
            cwd=repository_root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        assert actual == blob
