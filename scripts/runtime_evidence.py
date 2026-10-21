"""Create and validate sanitized, commit-bound runtime verification evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ci_checks import validate_reports

SCHEMA = "knora-runtime-verification-v1"
PROFILES = {
    "application": ("identity", "documents", "conversations", "operator", "workspace"),
    "otp": ("storage", "native"),
    "retrieval-v3": ("dense_hybrid", "reranking", "query_understanding", "recovery"),
}
EXCLUDED_SCENARIOS = {
    "application": (
        {
            "scenario": "controller-pdf-turn",
            "limitation": (
                "Requires fresh controller processing and artifacts in a separate acceptance scope."
            ),
        },
        {
            "scenario": "fault-injection",
            "limitation": (
                "Outage, crash, activation and commit-reply cases require separate "
                "acceptance evidence."
            ),
        },
    ),
    "otp": (
        {
            "scenario": "fault-injection",
            "limitation": (
                "Outage, crash, activation and commit-reply cases require separate "
                "acceptance evidence."
            ),
        },
    ),
    "retrieval-v3": (
        {
            "scenario": "local-ai-weights",
            "limitation": (
                "Cloudflare-only AI; local model weights are intentionally excluded ($0 AI budget)."
            ),
        },
    ),
}
SHA_RE = r"^[0-9a-f]{40}$"


def _sha(value: str, label: str) -> str:
    import re

    if not isinstance(value, str) or not re.fullmatch(SHA_RE, value):
        raise ValueError(f"{label} must be a full 40-character SHA")
    return value


def _junit(path: Path) -> tuple[str, int]:
    try:
        count = validate_reports([path])
    except ValueError as exc:
        raise ValueError(f"report is invalid: {path}") from exc
    return hashlib.sha256(path.read_bytes()).hexdigest(), count


def _sanitize_junit(source: Path, destination: Path, scenario: str) -> tuple[str, int]:
    _source_hash, count = _junit(source)
    root = ET.Element(
        "testsuite",
        {"name": scenario, "tests": str(count), "failures": "0", "errors": "0", "skipped": "0"},
    )
    for index in range(count):
        ET.SubElement(root, "testcase", {"classname": "runtime", "name": f"{scenario}-{index + 1}"})
    destination.write_bytes(ET.tostring(root, encoding="utf-8", xml_declaration=True))
    return hashlib.sha256(destination.read_bytes()).hexdigest(), count


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def create_evidence(
    *,
    subject_sha: str,
    actual_sha: str,
    workflow_sha: str,
    run_id: str,
    run_attempt: str,
    profile: str,
    reports: dict[str, Path],
    output_dir: Path,
    started_at: str,
    tool_identities: dict[str, str],
    image_identities: dict[str, str],
    completed_at: str | None = None,
) -> Path:
    subject = _sha(subject_sha, "subject SHA")
    if _sha(actual_sha, "actual SHA") != subject:
        raise ValueError("actual checkout SHA does not match subject SHA")
    workflow = _sha(workflow_sha, "workflow source SHA")
    if profile not in PROFILES:
        raise ValueError(f"unknown profile: {profile}")
    expected = PROFILES[profile]
    if set(reports) != set(expected):
        raise ValueError(f"selected scenarios for {profile} must be exactly {expected}")

    output_dir.mkdir(parents=True, exist_ok=True)
    report_dir = output_dir / "reports"
    report_dir.mkdir(exist_ok=True)
    hashes: dict[str, str] = {}
    counts: dict[str, int] = {}
    report_paths: dict[str, str] = {}
    for scenario in expected:
        source = Path(reports[scenario])
        destination = report_dir / f"{scenario}.xml"
        hashes[scenario], counts[scenario] = _sanitize_junit(source, destination, scenario)
        report_paths[scenario] = destination.relative_to(output_dir).as_posix()

    data: dict[str, Any] = {
        "schema": SCHEMA,
        "subject_sha": subject,
        "workflow_source_sha": workflow,
        "run_id": str(run_id),
        "run_attempt": str(run_attempt),
        "profile": profile,
        "selected_scenarios": list(expected),
        "executed_scenarios": list(expected),
        "scenario_counts": counts,
        "excluded_scenarios": [dict(item) for item in EXCLUDED_SCENARIOS[profile]],
        "tool_identities": dict(tool_identities),
        "image_identities": dict(image_identities),
        "started_at": started_at,
        "completed_at": completed_at or _now(),
        "report_paths": report_paths,
        "report_hashes": hashes,
        "outcome": "success",
    }
    evidence = output_dir / "evidence.json"
    evidence.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return evidence


def _load_evidence(path: Path, candidate_sha: str) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"evidence is unreadable: {path}") from exc
    if data.get("schema") != SCHEMA:
        raise ValueError("evidence schema mismatch")
    required_provenance = (
        "workflow_source_sha",
        "run_id",
        "run_attempt",
        "started_at",
        "completed_at",
        "tool_identities",
        "image_identities",
    )
    if any(field not in data or data[field] in (None, "", {}) for field in required_provenance):
        raise ValueError("evidence provenance is incomplete")
    if data.get("subject_sha") != candidate_sha:
        raise ValueError("evidence subject SHA mismatch")
    profile = data.get("profile")
    if profile not in PROFILES:
        raise ValueError("evidence profile is invalid")
    if data.get("outcome") != "success":
        raise ValueError("evidence outcome is not success")
    expected = list(PROFILES[profile])
    if data.get("selected_scenarios") != expected or data.get("executed_scenarios") != expected:
        raise ValueError("evidence scenario selection is incomplete")
    if data.get("excluded_scenarios") != [dict(item) for item in EXCLUDED_SCENARIOS[profile]]:
        raise ValueError("evidence scenario exclusions are incomplete")
    counts = data.get("scenario_counts")
    if not isinstance(counts, dict) or set(counts) != set(expected):
        raise ValueError("evidence scenario counts are incomplete")
    paths = data.get("report_paths")
    hashes = data.get("report_hashes")
    if not isinstance(paths, dict) or not isinstance(hashes, dict) or set(paths) != set(expected):
        raise ValueError("evidence reports are incomplete")
    for scenario in expected:
        report = (path.parent / paths[scenario]).resolve()
        if path.parent.resolve() not in report.parents:
            raise ValueError("evidence report path escapes evidence directory")
        report_hash, report_count = _junit(report)
        if report_hash != hashes.get(scenario):
            raise ValueError("evidence report hash mismatch")
        if counts[scenario] != report_count:
            raise ValueError("evidence scenario count mismatch")
    return data


def validate_release(
    candidate_sha: str, evidence_files: list[Path], applicable_profiles: list[str]
) -> None:
    candidate = _sha(candidate_sha, "candidate SHA")
    if not applicable_profiles or any(profile not in PROFILES for profile in applicable_profiles):
        raise ValueError("applicable profiles are invalid")
    if len(evidence_files) != len(set(evidence_files)):
        raise ValueError("duplicate evidence file")
    found: dict[str, dict[str, Any]] = {}
    for path in evidence_files:
        data = _load_evidence(Path(path), candidate)
        profile = data["profile"]
        if profile in found:
            raise ValueError(f"duplicate evidence profile: {profile}")
        found[profile] = data
    if set(found) != set(applicable_profiles):
        missing = sorted(set(applicable_profiles) - set(found))
        raise ValueError(f"missing evidence profile: {', '.join(missing)}")


def _pairs(values: list[str]) -> dict[str, str]:
    result = {}
    for value in values:
        if "=" not in value:
            raise ValueError("metadata must use key=value")
        key, item = value.split("=", 1)
        if not key or not item:
            raise ValueError("metadata must use key=value")
        result[key] = item
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate")
    validate.add_argument("candidate_sha")
    validate.add_argument("evidence", nargs="+")
    validate.add_argument("--profile", action="append", dest="profiles", required=True)
    create = subparsers.add_parser("create")
    create.add_argument("--subject-sha", required=True)
    create.add_argument("--actual-sha", required=True)
    create.add_argument("--workflow-sha", required=True)
    create.add_argument("--run-id", required=True)
    create.add_argument("--run-attempt", required=True)
    create.add_argument("--profile", required=True)
    create.add_argument("--output-dir", type=Path, required=True)
    create.add_argument("--started-at", required=True)
    create.add_argument("--report", action="append", required=True)
    create.add_argument("--tool", action="append", default=[])
    create.add_argument("--image", action="append", default=[])
    args = parser.parse_args()
    try:
        if args.command == "validate":
            validate_release(
                args.candidate_sha, [Path(path) for path in args.evidence], args.profiles
            )
        else:
            reports = {}
            for pair in args.report:
                if "=" not in pair:
                    raise ValueError("reports must use scenario=path")
                scenario, path = pair.split("=", 1)
                reports[scenario] = Path(path)
            evidence = create_evidence(
                subject_sha=args.subject_sha,
                actual_sha=args.actual_sha,
                workflow_sha=args.workflow_sha,
                run_id=args.run_id,
                run_attempt=args.run_attempt,
                profile=args.profile,
                reports=reports,
                output_dir=args.output_dir,
                started_at=args.started_at,
                tool_identities=_pairs(args.tool),
                image_identities=_pairs(args.image),
            )
            print(evidence)
    except ValueError as exc:
        parser.error(str(exc))
    if args.command == "validate":
        print("runtime evidence valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
