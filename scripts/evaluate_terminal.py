"""Evaluate mutually exclusive terminal states for refactoring."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def evaluate(state: dict[str, Any]) -> dict[str, Any]:
    baseline = state.get("baseline_guardrail")
    post = state.get("post_guardrail")
    implementation = state.get("implementation")
    review = state.get("review")
    suspension = state.get("suspension")
    failure = state.get("failure")
    completed = (
        isinstance(baseline, dict) and baseline.get("status") == "passed"
        and isinstance(post, dict) and post.get("status") == "passed"
        and state.get("behavior_drift") is False
        and isinstance(implementation, dict)
        and implementation.get("status") == "completed"
        and implementation.get("all_tests_green") is True
        and isinstance(review, dict)
        and review.get("status") == "completed"
        and review.get("pass") is True
        and review.get("verdict") == "APPROVE"
        and review.get("critical_count") == 0
        and review.get("major_count") == 0
    )
    suspended = (
        state.get("context_expiring") is True
        and isinstance(suspension, dict)
        and suspension.get("status") == "suspended"
        and bool(suspension.get("artifact_path"))
        and suspension.get("resumable") is True
    )
    dependency_failed = state.get("dependencies_reachable") is False
    behavior_changed = state.get("behavior_drift") is True
    terminal_failed = isinstance(failure, dict) and bool(failure.get("reason"))
    terminals = [completed, suspended, dependency_failed or behavior_changed or terminal_failed]
    if sum(terminals) > 1:
        raise ValueError("terminal state collision")
    if completed:
        return {"status": "completed"}
    if suspended:
        return {"status": "suspended", "artifact_path": suspension["artifact_path"]}
    if dependency_failed:
        return {"status": "failed", "reason": "dependency_unreachable"}
    if behavior_changed:
        return {"status": "failed", "reason": "behavior_change_detected"}
    if terminal_failed:
        return {"status": "failed", "reason": failure["reason"]}
    return {"status": "continue"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, required=True)
    args = parser.parse_args()
    state = json.loads(args.state.read_text(encoding="utf-8"))
    if not isinstance(state, dict):
        parser.error("state must be a JSON object")
    print(json.dumps(evaluate(state), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
