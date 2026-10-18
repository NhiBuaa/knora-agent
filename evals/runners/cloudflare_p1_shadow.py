"""Prepare P1 observations offline. No network transport or live execution is implemented."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from evals.runners.evaluation import write_report_atomic
from evals.runners.run_security_shadow import (
    IDENTITY_FIELDS,
    _metrics,
    _population,
    apply_review,
    digest_bytes,
    evaluate_cases,
    load_capture_units,
)

from knora.providers.generation import GenerationEvidence
from knora.providers.openai_compatible.generation import (
    CLOUDFLARE_PROMPT_VERSION,
    CLOUDFLARE_SYSTEM_PROMPT,
)
from knora.providers.structured_generation import user_message


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def configuration_digest() -> str:
    return digest_bytes(
        _canonical(
            {
                "detector": "cloudflare_p1",
                "mode": "offline",
                "prompt_version": CLOUDFLARE_PROMPT_VERSION,
                "system_prompt": CLOUDFLARE_SYSTEM_PROMPT,
                "contract": "hypothetical-p1-v1",
                "stream": False,
                "enforcement": "off",
            }
        )
    )


def load_units(
    path: Path, *, expected_digest: str, fixtures: bool = False, review: dict | None = None
) -> list[dict]:
    raw = path.read_bytes()
    if digest_bytes(raw) != expected_digest:
        raise ValueError("ARTIFACT_DIGEST_MISMATCH")
    value = json.loads(raw.decode("utf-8-sig"))
    # Reuse native capture identity/conflict/duplicate validation; never re-answer a capture.
    bases = [
        unit
        for unit in load_capture_units(path, expected_digest=expected_digest)
        if unit["scope"] == "generation_evidence"
    ]
    records = (
        value.get("observations")
        if isinstance(value, dict) and "observations" in value
        else (value if isinstance(value, list) else [value])
    )
    if review is not None and not fixtures:
        raise ValueError("CAPTURE_LABEL_REVIEW_UNSUPPORTED")
    reviewed = apply_review(records, review, expected_digest) if review is not None else records
    if fixtures and any(
        record.get("fixture_provenance") != "synthetic-development-control" for record in records
    ):
        raise ValueError("INVALID_FIXTURE_PROVENANCE")
    units = []
    for base, record in zip(bases, reviewed, strict=True):
        messages = None
        question = record.get("question")
        evidence = record.get("generation_evidence")
        if base["text"] is not None and isinstance(question, str) and question.strip():
            aliases = [item.get("alias", item.get("evidence_id")) for item in evidence]
            if any(
                not isinstance(alias, str) or not re.fullmatch(r"E[1-9][0-9]*", alias)
                for alias in aliases
            ) or len(set(aliases)) != len(aliases):
                raise ValueError("INVALID_GENERATION_EVIDENCE_ALIASES")
            messages = [
                {"role": "system", "content": CLOUDFLARE_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": user_message(
                        question,
                        tuple(
                            GenerationEvidence(evidence_id=alias, content=item["content"])
                            for alias, item in zip(aliases, evidence, strict=True)
                        ),
                    ),
                },
            ]
        units.append(
            {
                **base,
                "messages": messages,
                "text": _canonical(messages).decode() if messages else None,
                "input_sha256": digest_bytes(_canonical(messages)) if messages else None,
                "label": record.get("label", "unreviewed") if review is not None else "unreviewed",
                **(
                    {
                        "proposed_label": record.get("proposed_label"),
                        "fixture_provenance": record["fixture_provenance"],
                        "family": record.get("family")
                        if record.get("family")
                        in {
                            "override",
                            "exfiltration",
                            "role_spoof",
                            "indirect_boundary",
                            "quoted_attack",
                            "legitimate_imperative",
                            "role_words",
                            "long_boundary_control",
                        }
                        else "unknown",
                        "boundary": record.get("boundary")
                        if record.get("boundary")
                        in {"beginning", "middle", "end", "between_evidence"}
                        else "unknown",
                    }
                    if fixtures
                    else {}
                ),
            }
        )
    return units


def _outcome(observation: dict, *, hypothetical: bool) -> tuple[str, str | None]:
    if not hypothetical:
        return "unavailable", "unsupported_native_contract"
    if observation.get("dispatch_count") == 0:
        return "unavailable", "not_sent"
    if observation.get("restart_state") == "indeterminate":
        return "unknown", "indeterminate_outcome"
    if observation.get("transport_error") == "timeout":
        return "timeout", "transport_timeout"
    if observation.get("transport_error"):
        return "error", "transport_error"
    if observation.get("cloudflare_error_code") in (2016, 2017):
        return "error", "unexpected_guardrail_block"
    if observation.get("http_status") != 200:
        code = observation.get("http_status")
        return "error", f"http_{code}" if code in (403, 429) else "http_error"
    log = observation.get("log")
    if not isinstance(log, dict):
        return "unavailable", "missing_log"
    if log.get("schema_version") != "hypothetical-p1-log-v1":
        return "unavailable", "unsupported_log_schema"
    if log.get("coverage") != "complete":
        return "unavailable", "incomplete_log"
    if log.get("evaluation") == "failed":
        return "error", "detector_error"
    if log.get("evaluation") != "completed":
        return "unavailable", "incomplete_evaluation"
    verdict = log.get("verdict")
    if verdict not in ("positive", "negative"):
        return "unavailable", "missing_verdict"
    return ("detected" if verdict == "positive" else "clear"), None


def build_report(
    cases: list[dict], *, source_digest: str, observations: dict | None = None
) -> dict:
    selected = {(case["case_id"], case["scope"]): case for case in cases}
    if len(selected) != len(cases):
        raise ValueError("DUPLICATE_SCAN_UNITS")
    imported = {}
    hypothetical = False
    if observations is not None:
        if not isinstance(observations, dict):
            raise ValueError("INVALID_OBSERVATIONS")
        if (
            observations.get("source_artifact_sha256") != source_digest
            or observations.get("configuration_sha256") != configuration_digest()
        ):
            raise ValueError("OBSERVATION_ARTIFACT_OR_CONFIGURATION_MISMATCH")
        hypothetical = (
            observations.get("schema_version") == "hypothetical-p1-v1"
            and observations.get("development_only") is True
        )
        rows = observations.get("observations")
        if not isinstance(rows, list):
            raise ValueError("INVALID_OBSERVATIONS")
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError("INVALID_OBSERVATION")
            key = (row.get("case_id"), row.get("scope"))
            if key in imported:
                raise ValueError("DUPLICATE_OBSERVATION")
            if key not in selected:
                raise ValueError("OBSERVATION_IDENTITY_MISMATCH")
            case = selected[key]
            required = ("input_sha256", "run_id", "attempt_id", "trace_id", "workspace_id")
            for field in (*required, *(field for field in IDENTITY_FIELDS if field in row)):
                if row.get(field) != case.get(field):
                    raise ValueError("OBSERVATION_IDENTITY_MISMATCH")
            if (
                type(row.get("dispatch_count")) is not int
                or row["dispatch_count"] not in (0, 1)
                or type(row.get("retry_count")) is not int
                or row["retry_count"] != 0
            ):
                raise ValueError("RETRY_OR_DISPATCH_LIMIT")
            if row.get("restart_state") not in ("fresh", "already_sent", "indeterminate"):
                raise ValueError("INVALID_RESTART_STATE")
            if row["restart_state"] != "fresh" and row["dispatch_count"] != 1:
                raise ValueError("CONTRADICTORY_ATTEMPT_ACCOUNTING")
            imported[key] = row
    outcomes = {}
    for key, case in selected.items():
        outcomes[key] = ("unavailable", "missing_input" if case["text"] is None else "not_run")
        if key in imported and case["text"] is not None:
            outcomes[key] = _outcome(imported[key], hypothetical=hypothetical)
    # Borrow existing population and reviewed-only metric semantics without a parallel evaluator.
    statuses = iter(
        outcomes[(case["case_id"], case["scope"])][0] for case in cases if case["text"] is not None
    )
    report = evaluate_cases(cases, lambda _: {"status": next(statuses)})
    for row, case in zip(report["cases"], cases, strict=True):
        key = (case["case_id"], case["scope"])
        row["input_sha256"] = case["input_sha256"]
        row["finding_type"] = "prompt_injection" if row["status"] == "detected" else None
        reason = outcomes[key][1]
        row["diagnostics"] = {"error": reason} if reason else {}
        row["restart_state"] = imported[key]["restart_state"] if key in imported else "not_sent"
        row["fixture_provenance"] = case.get("fixture_provenance", "native-saved-capture")
        row["family"] = case.get("family", "unknown")
        row["boundary"] = case.get("boundary", "unknown")
        row["input_characters"] = len(case["text"]) if case["text"] is not None else 0
        row["input_bytes"] = len(case["text"].encode()) if case["text"] is not None else 0
        # Descriptive length bins, not an assertion about the unverified P1 context window.
        row["length"] = (
            "unavailable"
            if case["text"] is None
            else "long_4096_plus"
            if len(case["text"]) >= 4096
            else "short_under_4096"
        )
    if not report["population"]["reviewed"]:
        report["metrics"] = None
        for group in report["groups"]:
            group["metrics"] = None
    report.pop("not_run")
    report["subgroups"] = []
    for dimension in ("family", "boundary", "length"):
        for value in sorted({row[dimension] for row in report["cases"]}):
            rows = [row for row in report["cases"] if row[dimension] == value]
            report["subgroups"].append(
                {
                    "dimension": dimension,
                    "value": value,
                    "population": _population(rows),
                    "metrics": _metrics(rows)
                    if any(row["label"] != "unreviewed" for row in rows)
                    else None,
                }
            )
    report.update(
        {
            "schema_version": "knora-security-observation-v2",
            "detector": "cloudflare_p1",
            "source_artifact_sha256": source_digest,
            "configuration_sha256": configuration_digest(),
            "evidence_kind": "hypothetical_development" if hypothetical else "offline_preparation",
            "execution": "hypothetical_development_import" if hypothetical else "prepared_offline",
            "provider_quality_evidence": False,
            "live_requests": 0,
            "enforcement": "off",
            "export": "off",
            "release_gate": False,
            "replay_permitted": False,
            "detection_completed": False,
            "protection_enabled": False,
            "accounting": {
                "selected": len(cases),
                "attempted": sum(r["dispatch_count"] for r in imported.values()),
                "observed": len(imported),
                "completed": sum(s in ("detected", "clear") for s, _ in outcomes.values()),
                "retries": 0,
            },
        }
    )
    return report


def write_report(path: Path, report: dict) -> None:
    payload = {**report, "report_digest": digest_bytes(_canonical(report))}
    write_report_atomic(path, payload)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--cases", type=Path)
    inputs.add_argument("--capture", type=Path)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--label-review", type=Path)
    parser.add_argument("--observations", type=Path)
    parser.add_argument("--observations-sha256")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--authorization-manifest", type=Path)
    args = parser.parse_args()
    if args.live or args.authorization_manifest:
        parser.exit(2, "LIVE_CONTRACT_NOT_APPROVED\n")
    try:
        review = (
            json.loads(args.label_review.read_text(encoding="utf-8-sig"))
            if args.label_review
            else None
        )
        cases = load_units(
            args.cases or args.capture,
            expected_digest=args.expected_sha256,
            fixtures=args.cases is not None,
            review=review,
        )
        observations = None
        if bool(args.observations) != bool(args.observations_sha256):
            raise ValueError("OBSERVATION_DIGEST_REQUIRED")
        if args.observations:
            raw = args.observations.read_bytes()
            if digest_bytes(raw) != args.observations_sha256:
                raise ValueError("OBSERVATION_DIGEST_MISMATCH")
            observations = json.loads(raw.decode("utf-8-sig"))
        report = build_report(cases, source_digest=args.expected_sha256, observations=observations)
        if args.observations:
            report["observation_artifact_sha256"] = args.observations_sha256
        if args.label_review:
            report["label_review_sha256"] = digest_bytes(args.label_review.read_bytes())
        write_report(args.output, report)
    except (ValueError, TypeError, KeyError, OSError):
        parser.exit(2, "P1_INPUT_OR_PUBLICATION_ERROR\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
