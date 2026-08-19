from evals.runners.milestone_3 import HttpEvaluationExecutor, ProductionM3Executor


def test_m3_executor_uses_one_canonical_class_with_compatibility_alias() -> None:
    assert ProductionM3Executor is HttpEvaluationExecutor
