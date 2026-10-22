"""Offline secrets shadow over explicit saved Knora artifacts; no runtime integration."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any

from evals.runners.evaluation import write_report_atomic
from evals.scorers.security_shadow import APPROVED_PACKAGES

IDENTITY_FIELDS = (
    "run_id",
    "attempt",
    "attempt_id",
    "trace_id",
    "workspace_id",
    "conversation_id",
    "turn_id",
    "dataset_id",
    "dataset_version",
    "dataset_sha256",
    "corpus_sha256",
    "derivation_sha256",
    "response_sha256",
    "failure_code",
    "observation_failure_code",
    "decision",
    "retrieval_configuration_id",
    "chunk_set_provenance_id",
    "source_bindings",
    "dataset_digest",
    "corpus_id",
    "corpus_digest",
    "chunk_set_id",
    "chunk_set_digest",
    "dataset_manifest_identity",
    "corpus_manifest_identity",
    "workspace",
    "source_commit",
    "evaluation_commit",
    "error_code",
    "answer_sha256",
)
STATUSES = {"detected", "clear", "unknown", "error", "timeout", "unavailable"}
SCOPES = {"source_page", "retrieved_candidate", "generation_evidence", "output"}
SAFE_ERRORS = {
    "missing_text",
    "validator_error",
    "validator_timeout",
    "invalid_text",
    "worker_error",
    "network_attempt",
    "invalid_result",
    "dependency_unavailable",
    "dependency_version_mismatch",
}


def _identity(*sources: dict) -> dict:
    identity = {}
    for source in sources:
        if not isinstance(source, dict):
            raise ValueError("INVALID_IDENTITY")
        for key in IDENTITY_FIELDS:
            if key not in source or source[key] is None:
                continue
            value = source[key]
            if key == "source_bindings":
                fields = ("source_key", "production_document_version_id", "production_chunk_set_id")
                if not isinstance(value, list) or any(
                    not isinstance(item, dict)
                    or any(not isinstance(item.get(k), str) for k in fields)
                    for item in value
                ):
                    raise ValueError("INVALID_IDENTITY")
                value = [{k: item[k] for k in fields} for item in value]
            elif not isinstance(value, (str, int)):
                raise ValueError("INVALID_IDENTITY")
            if key in identity and identity[key] != value:
                raise ValueError("IDENTITY_MISMATCH")
            identity[key] = value
    return identity


def digest_bytes(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _records(value: Any) -> list[dict[str, Any]]:
    records = (
        value.get("observations")
        if isinstance(value, dict) and "observations" in value
        else ([value] if isinstance(value, dict) else value)
    )
    if not isinstance(records, list) or any(not isinstance(item, dict) for item in records):
        raise ValueError("INVALID_CAPTURE")
    ids = [item.get("case_id") for item in records]
    if any(not isinstance(case_id, str) or not case_id for case_id in ids) or len(set(ids)) != len(
        ids
    ):
        raise ValueError("INVALID_CASE_IDENTITIES")
    return records


def load_capture_units(path: Path, *, expected_digest: str | None = None) -> list[dict[str, Any]]:
    raw = path.read_bytes()
    artifact_digest = digest_bytes(raw)
    if expected_digest is not None and artifact_digest != expected_digest:
        raise ValueError("ARTIFACT_DIGEST_MISMATCH")
    value = json.loads(raw.decode("utf-8-sig"))
    root = value if isinstance(value, dict) and "observations" in value else {}
    units = []
    for record in _records(value):
        response = record.get("public_response", record)
        if not isinstance(response, dict):
            raise ValueError("INVALID_PUBLIC_RESPONSE")
        identity = _identity(root, root.get("provenance", {}), record, response)
        base = {
            **identity,
            "case_id": record["case_id"],
            "observation_status": record.get("status", "unavailable"),
            "source_artifact_sha256": artifact_digest,
            "language": record.get("language", "unknown"),
        }
        output = response.get("answer", response.get("public_answer"))
        if (
            response.get("decision") == "REFUSAL"
            or not isinstance(output, str)
            or not output.strip()
        ):
            output = response.get("refusal_reason")
        units.append(
            {
                **base,
                "scope": "output",
                "text": output if isinstance(output, str) and output.strip() else None,
            }
        )
        evidence = record.get("generation_evidence")
        exact = record.get("generation_evidence_status") == "exact"
        text = None
        if exact:
            if not isinstance(evidence, list) or any(
                not isinstance(item, dict) or not isinstance(item.get("content"), str)
                for item in evidence
            ):
                raise ValueError("INVALID_GENERATION_EVIDENCE")
            # Concatenated prompt evidence is one scan unit, never a whole-PDF claim.
            joined = "\n".join(item["content"] for item in evidence)
            text = joined if joined.strip() else None
        units.append(
            {
                **base,
                "scope": "generation_evidence",
                "text": text,
                "evidence_status": "exact" if text is not None else "unavailable",
            }
        )
    return units


def _metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {"tp": 0, "fp": 0, "tn": 0, "fn": 0}
    for row in rows:
        if row["label"] not in {"positive", "negative"} or row["status"] not in {
            "detected",
            "clear",
        }:
            continue
        key = {
            ("positive", "detected"): "tp",
            ("positive", "clear"): "fn",
            ("negative", "detected"): "fp",
            ("negative", "clear"): "tn",
        }[(row["label"], row["status"])]
        counts[key] += 1
    tp, fp, tn, fn = (counts[k] for k in ("tp", "fp", "tn", "fn"))
    return {
        **counts,
        "precision": tp / (tp + fp) if tp + fp else None,
        "recall": tp / (tp + fn) if tp + fn else None,
        "false_positive_rate": fp / (fp + tn) if fp + tn else None,
    }


def _population(rows: list[dict[str, Any]]) -> dict[str, int]:
    statuses = Counter(row["status"] for row in rows)
    reviewed = sum(row["label"] in {"positive", "negative"} for row in rows)
    return {
        "total": len(rows),
        "reviewed": reviewed,
        "unreviewed": len(rows) - reviewed,
        "evaluable": sum(_metrics(rows)[k] for k in ("tp", "fp", "tn", "fn")),
        "unavailable": statuses["unavailable"],
        "errors": statuses["error"],
        "timeouts": statuses["timeout"],
        "unknown": statuses["unknown"],
    }


def evaluate_cases(
    cases: list[dict[str, Any]], scan: Callable[[str], dict[str, Any]]
) -> dict[str, Any]:
    if not isinstance(cases, list) or any(not isinstance(case, dict) for case in cases):
        raise ValueError("INVALID_SCAN_UNITS")
    seen = set()
    for case in cases:
        key = (case.get("case_id"), case.get("scope", "output"))
        if not isinstance(key[0], str) or not key[0] or key in seen or key[1] not in SCOPES:
            raise ValueError("INVALID_SCAN_UNIT_IDENTITY")
        seen.add(key)
    rows = []
    for case in cases:
        text = case.get("text")
        if text is not None and not isinstance(text, str):
            raise ValueError("INVALID_TEXT")
        result = scan(text) if text is not None else {"status": "unavailable"}
        status = result.get("status") if isinstance(result, dict) else "unknown"
        if status not in STATUSES:
            status = "unknown"
        diagnostic = result.get("diagnostics", {}) if isinstance(result, dict) else {}
        diagnostic = diagnostic if isinstance(diagnostic, dict) else {}
        error = diagnostic.get("error")
        label = case.get("label")
        row = {
            **_identity(case),
            **{
                key: case[key]
                for key in ("source_artifact_sha256", "observation_status", "evidence_status")
                if key in case
            },
            "case_id": case["case_id"],
            "scope": case.get("scope", "output"),
            "language": case.get("language", "unknown"),
            "label": label if label in {"positive", "negative"} else "unreviewed",
            "status": status,
            "finding_type": "secrets_present" if status == "detected" else None,
            "input_sha256": digest_bytes(text.encode("utf-8")) if text is not None else None,
            "diagnostics": {"error": error} if error in SAFE_ERRORS else {},
        }
        if isinstance(result, dict):
            packages = result.get("packages")
            if packages is not None:
                row["packages"] = {
                    k: packages[k]
                    for k in APPROVED_PACKAGES
                    if isinstance(packages, dict) and isinstance(packages.get(k), str)
                }
                if packages != APPROVED_PACKAGES:
                    row.update(status="error", finding_type=None)
                    row["diagnostics"]["error"] = "dependency_version_mismatch"
            elapsed = result.get("elapsed_ms")
            if isinstance(elapsed, (int, float)) and elapsed >= 0:
                row["elapsed_ms"] = elapsed
            blocked = diagnostic.get("blocked_network_attempts")
            if type(blocked) is int and blocked >= 0:
                row["diagnostics"]["blocked_network_attempts"] = blocked
        rows.append(row)
    groups = []
    for language, scope in sorted({(r["language"], r["scope"]) for r in rows}):
        group = [r for r in rows if r["language"] == language and r["scope"] == scope]
        groups.append(
            {
                "language": language,
                "scope": scope,
                "metrics": _metrics(group),
                "population": _population(group),
            }
        )
    return {
        "metrics": _metrics(rows),
        "population": _population(rows),
        "groups": groups,
        "cases": rows,
        "case_count": len({r["case_id"] for r in rows}),
        "not_run": ["prompt_injection", "pii", "dangerous_output"],
    }


def write_shadow_report(
    path: Path, report: dict[str, Any], *, source_digest: str
) -> dict[str, Any]:
    payload = {
        **report,
        "schema_version": 1,
        "source_digest": source_digest,
        "detector": "secrets_present",
        "enforcement": "off",
        "release_gate": False,
        "detector_configuration": {
            "approved_packages": APPROVED_PACKAGES,
            "use_local": True,
            "on_fail": "noop",
            "timeout_seconds": 30,
            "plugins": "detect-secrets default_settings; no verification",
        },
    }
    payload["report_digest"] = digest_bytes(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    )
    write_report_atomic(path, payload)
    return payload


def apply_review(cases: list[dict], review: dict, source_digest: str) -> list[dict]:
    if (
        not isinstance(review, dict)
        or review.get("artifact_sha256") != source_digest
        or not isinstance(review.get("reviewed_by"), str)
        or not review["reviewed_by"]
        or not isinstance(review.get("decision_ref"), str)
        or not review["decision_ref"].startswith(
            "https://github.com/NhiBuaa/knora-agent/issues/188#issuecomment-"
        )
        or any(case.get("proposed_label") not in {"positive", "negative"} for case in cases)
    ):
        raise ValueError("INVALID_LABEL_REVIEW")
    return [{**case, "label": case["proposed_label"]} for case in cases]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--cases", type=Path)
    inputs.add_argument("--capture", type=Path)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--label-review", type=Path)
    parser.add_argument("--execute", action="store_true", help="Run the approved local validator")
    args = parser.parse_args()
    from evals.scorers.security_shadow import scan_local

    try:
        if args.output.exists():
            raise ValueError("OUTPUT_EXISTS")
        source = args.cases or args.capture
        raw = source.read_bytes()
        source_digest = digest_bytes(raw)
        if source_digest != args.expected_sha256:
            raise ValueError("ARTIFACT_DIGEST_MISMATCH")
        cases = (
            json.loads(raw.decode("utf-8-sig"))
            if args.cases
            else load_capture_units(args.capture, expected_digest=source_digest)
        )
        # File labels are proposals until an owner-approved exact artifact review is supplied.
        if args.cases:
            if not isinstance(cases, list) or any(not isinstance(case, dict) for case in cases):
                raise ValueError("INVALID_CASES")
            cases = [{**case, "label": "unreviewed"} for case in cases]
            if args.label_review:
                review = json.loads(args.label_review.read_text(encoding="utf-8-sig"))
                cases = apply_review(cases, review, source_digest)
        elif args.label_review:
            raise ValueError("CAPTURE_LABEL_REVIEW_UNSUPPORTED")
        scanner = scan_local if args.execute else lambda text: {"status": "unavailable"}
        report = evaluate_cases(cases, scanner)
        import importlib.metadata
        import platform
        from datetime import UTC, datetime

        from evals.scorers import security_shadow

        report["execution"] = "local_validator" if args.execute else "not_run"
        report["created_at"] = datetime.now(UTC).isoformat()
        report["runtime"] = {
            "python": platform.python_version(),
            "packages": {name: importlib.metadata.version(name) for name in APPROVED_PACKAGES},
            "implementation_sha256": {
                "runner": digest_bytes(Path(__file__).read_bytes()),
                "scorer": digest_bytes(Path(security_shadow.__file__).read_bytes()),
            },
        }
        if args.label_review:
            report["label_review_sha256"] = digest_bytes(args.label_review.read_bytes())
            report["label_review_ref"] = review["decision_ref"]
        write_shadow_report(args.output, report, source_digest=source_digest)
    except (ValueError, OSError, TypeError):
        parser.exit(2, "SECURITY_SHADOW_INPUT_OR_PUBLICATION_ERROR\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
