from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

SEVERITIES = {"critical", "major", "minor", "nit"}
FINDING_STRING_FIELDS = ("location", "evidence", "problem", "harm", "fix")


class ReviewAggregationError(RuntimeError):
    pass


def _validate_axis(value: Mapping[str, Any], expected_axis: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ReviewAggregationError(f"{expected_axis} result must be an object")
    if value.get("axis") != expected_axis:
        raise ReviewAggregationError(f"expected {expected_axis} axis result")
    status = value.get("status")
    if status not in {"completed", "skipped", "failed"}:
        raise ReviewAggregationError(f"invalid {expected_axis} axis status")
    if status == "skipped" and expected_axis != "spec":
        raise ReviewAggregationError("only the spec axis may be skipped")
    report = value.get("report")
    if not isinstance(report, str):
        raise ReviewAggregationError(f"{expected_axis} report must be a string")
    if status == "failed":
        if not isinstance(value.get("reason"), str) or not value["reason"].strip():
            raise ReviewAggregationError(f"{expected_axis} failure reason is required")
        if not isinstance(value.get("retryable"), bool):
            raise ReviewAggregationError(f"{expected_axis} failure retryable must be boolean")
    if status == "skipped" and (
        not isinstance(value.get("reason"), str) or not value["reason"].strip()
    ):
        raise ReviewAggregationError("spec skip reason is required")
    findings = value.get("findings", [])
    if not isinstance(findings, list) or not all(isinstance(item, dict) for item in findings):
        raise ReviewAggregationError(f"{expected_axis} findings must be an object array")
    for finding in findings:
        if finding.get("severity") not in SEVERITIES:
            raise ReviewAggregationError(f"invalid finding severity in {expected_axis}")
        for field in FINDING_STRING_FIELDS:
            if not isinstance(finding.get(field), str) or not finding[field].strip():
                raise ReviewAggregationError(
                    f"{expected_axis} finding field '{field}' must be a non-empty string"
                )
    if status != "completed" and findings:
        raise ReviewAggregationError(f"{expected_axis} {status} result must not contain findings")
    return dict(value)


def aggregate(standards: Mapping[str, Any], spec: Mapping[str, Any]) -> dict[str, Any]:
    raw_axes = {"standards": standards, "spec": spec}
    try:
        standards_result = _validate_axis(standards, "standards")
        spec_result = _validate_axis(spec, "spec")
    except ReviewAggregationError as exc:
        return {
            "status": "failed",
            "reason": str(exc),
            "retryable": True,
            "axes": raw_axes,
        }
    axes = {"standards": standards_result, "spec": spec_result}
    failed = [name for name, result in axes.items() if result["status"] == "failed"]
    if failed:
        return {
            "status": "failed",
            "reason": f"axis execution failed: {', '.join(failed)}",
            "retryable": True,
            "axes": axes,
        }

    findings = [
        {**finding, "axis": axis_name}
        for axis_name, result in axes.items()
        for finding in result["findings"]
    ]
    critical_count = sum(item["severity"] == "critical" for item in findings)
    major_count = sum(item["severity"] == "major" for item in findings)
    verdict = "BLOCK" if critical_count else "REQUEST_CHANGES" if major_count else "APPROVE"
    report = "\n\n".join(
        f"## {name.title()}\n\n{result.get('report', '').strip() or '_No findings._'}"
        for name, result in axes.items()
    )
    return {
        "status": "completed",
        "pass": verdict == "APPROVE",
        "verdict": verdict,
        "critical_count": critical_count,
        "major_count": major_count,
        "findings": findings,
        "axes": axes,
        "report": report,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Aggregate two code-review axis results.")
    parser.add_argument("--standards", type=Path, required=True)
    parser.add_argument("--spec", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        standards = json.loads(args.standards.read_text(encoding="utf-8"))
        spec = json.loads(args.spec.read_text(encoding="utf-8"))
        result = aggregate(standards, spec)
        print(json.dumps(result, indent=2))
        return 0 if result["status"] == "completed" else 1
    except (OSError, json.JSONDecodeError, ReviewAggregationError) as exc:
        print(json.dumps({"status": "failed", "reason": str(exc)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
