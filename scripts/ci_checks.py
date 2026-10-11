"""Fail CI when required jobs or JUnit reports lack passing execution evidence."""

import argparse
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

REQUIRED_JOBS = {"format", "frontend", "backend", "database", "keycloak"}


def _safe_identity(case: ET.Element) -> str:
    identity = f"{case.get('classname', '')}.{case.get('name', '')}"
    return re.sub(r"[^a-zA-Z0-9_./:\[\] -]", "?", identity)[:160]


def validate_reports(paths: list[Path]) -> int:
    if not paths:
        raise ValueError("missing report")
    identities: set[tuple[str, str]] = set()
    total = 0
    for path in paths:
        if not path.is_file():
            raise ValueError("missing report")
        try:
            root = ET.parse(path).getroot()
        except (ET.ParseError, OSError) as exc:
            raise ValueError("malformed report") from exc
        if root.tag not in {"testsuite", "testsuites"}:
            raise ValueError("malformed report")
        cases = root.findall(".//testcase")
        if not cases:
            raise ValueError("zero test cases")
        suites = [root, *root.findall(".//testsuite")]
        for suite in suites:
            suite_cases = suite.findall(".//testcase")
            for key, tag in (
                ("tests", None),
                ("failures", "failure"),
                ("errors", "error"),
                ("skipped", "skipped"),
            ):
                value = suite.get(key)
                if value is None:
                    continue
                try:
                    declared = int(value)
                except ValueError as exc:
                    raise ValueError("malformed report") from exc
                actual = (
                    len(suite_cases)
                    if tag is None
                    else sum(c.find(tag) is not None for c in suite_cases)
                )
                if declared < 0 or declared != actual:
                    raise ValueError("inconsistent counts")
        for case in cases:
            identity = (case.get("classname", ""), case.get("name", ""))
            if not identity[1]:
                raise ValueError("malformed report")
            if identity in identities:
                raise ValueError(f"duplicate test case: {_safe_identity(case)}")
            identities.add(identity)
            for outcome in ("failure", "error", "skipped"):
                if case.find(outcome) is not None:
                    raise ValueError(f"{outcome}: {_safe_identity(case)}")
        total += len(cases)
    return total


def report_identities(paths: list[Path]) -> list[str]:
    """Return only sanitized case identities for human-readable CI evidence."""
    return [
        _safe_identity(case)
        for path in paths
        for case in ET.parse(path).getroot().findall(".//testcase")
    ]


def required_jobs_succeeded(needs: object) -> bool:
    return (
        isinstance(needs, dict)
        and needs.keys() == REQUIRED_JOBS
        and all(isinstance(job, dict) and job.get("result") == "success" for job in needs.values())
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    reports = commands.add_parser("reports")
    reports.add_argument("paths", nargs="+", type=Path)
    commands.add_parser("jobs")
    args = parser.parse_args()
    try:
        if args.command == "reports":
            count = validate_reports(args.paths)
            print(f"{count} passing test cases")
            for identity in report_identities(args.paths):
                print(f"CASE {identity}")
        else:
            try:
                needs = json.loads(os.environ["CI_NEEDS"])
            except (KeyError, json.JSONDecodeError) as exc:
                raise ValueError("invalid CI_NEEDS") from exc
            if not required_jobs_succeeded(needs):
                raise ValueError("required job missing or unsuccessful")
            print("all required jobs succeeded")
    except ValueError as exc:
        print(f"CI check failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
