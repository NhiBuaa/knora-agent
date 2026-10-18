"""Offline #188 supplement. No credential loader, live transport or runtime hook."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from types import SimpleNamespace

from evals.runners.evaluation import write_report_atomic
from evals.scorers.security_outcomes import observe_transfer, summarize_outcomes

CASE_FIELDS = {
    "case_id",
    "language",
    "pair",
    "variant",
    "scenario",
    "model_eligible",
    "requester_authority",
    "recipient_class",
    "recipient_allowed",
    "question",
    "history",
    "generation_evidence",
    "canary",
    "asserted_facts",
    "expected_stage",
    "non_applicability",
}
LIVE_REASONS = {"not_selected", "billing_unverified", "expired", "metadata_unavailable"}
CASES_SHA256 = "0374e97b8f998f145b703dfa9818832e4a72bbe4aa1ca0c0a799ef69a686bbda"
RUBRIC_SHA256 = "096543bb9ea30860df03bd86f22cd07be631bd328aed87645035298ba5f9ae30"


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _payload_bytes(payload: dict) -> bytes:
    import httpx

    return httpx.Request("POST", "https://synthetic.invalid", json=payload).content


def load_selection(cases_raw: bytes, rubric_raw: bytes) -> tuple[list[dict], dict]:
    if _sha(cases_raw) != CASES_SHA256 or _sha(rubric_raw) != RUBRIC_SHA256:
        raise ValueError("SELECTION_DIGEST_MISMATCH")
    selection, rubric = json.loads(cases_raw), json.loads(rubric_raw)
    if (
        not isinstance(selection, dict)
        or set(selection) != {"schema", "cases"}
        or selection["schema"] != "issue188-security-cases-v1"
    ):
        raise ValueError("INVALID_SELECTION")
    if (
        not isinstance(rubric, dict)
        or rubric.get("schema") != "issue188-security-rubric-v1"
        or rubric.get("authority") != "owner_approved_master_section_12"
    ):
        raise ValueError("INVALID_RUBRIC")
    cases = selection["cases"]
    expected = {
        f"188-outcome-v1-{lang}-{pair:02}-{variant}"
        for lang in ("vi", "en")
        for pair in range(1, 9)
        for variant in ("adverse", "control")
    }
    if (
        not isinstance(cases, list)
        or len(cases) != 32
        or any(not isinstance(c, dict) or set(c) != CASE_FIELDS for c in cases)
    ):
        raise ValueError("INVALID_CASES")
    if {c["case_id"] for c in cases} != expected:
        raise ValueError("INVALID_CASE_IDENTITIES")
    rules = rubric.get("cases")
    if (
        not isinstance(rules, list)
        or len(rules) != 32
        or any(not isinstance(r, dict) for r in rules)
        or {r.get("case_id") for r in rules} != expected
    ):
        raise ValueError("RUBRIC_IDENTITY_MISMATCH")
    for case in cases:
        pair, variant, language = case["pair"], case["variant"], case["language"]
        if (
            type(pair) is not int
            or pair not in range(1, 9)
            or variant not in {"adverse", "control"}
            or language not in {"vi", "en"}
            or case["case_id"] != f"188-outcome-v1-{language}-{pair:02}-{variant}"
        ):
            raise ValueError("INVALID_CASE_BINDING")
        eligible = not ((pair == 3 and variant == "adverse") or pair == 4)
        if type(case["model_eligible"]) is not bool or case["model_eligible"] != eligible:
            raise ValueError("INVALID_ELIGIBILITY")
        if type(case["recipient_allowed"]) is not bool or case["recipient_allowed"] != (
            case["requester_authority"] == "owner_questions_ask"
        ):
            raise ValueError("INVALID_PERMISSION")
        for key in ("question", "history", "canary"):
            if not isinstance(case[key], str):
                raise ValueError("INVALID_TEXT")
        if not case["question"].strip() or len(case["question"].encode()) > 4096:
            raise ValueError("INPUT_SIZE_LIMIT")
        evidence = case["generation_evidence"]
        if (
            not isinstance(evidence, list)
            or not evidence
            or any(
                not isinstance(p, list)
                or len(p) != 2
                or p[0] != f"E{i + 1}"
                or not isinstance(p[1], str)
                or not p[1].strip()
                for i, p in enumerate(evidence)
            )
        ):
            raise ValueError("INVALID_EVIDENCE")
        if len((case["history"] + "".join(p[1] for p in evidence)).encode()) > 8192:
            raise ValueError("INPUT_SIZE_LIMIT")
    return cases, rubric


def build_payload(case: dict) -> dict | None:
    """Prepare the fixed adapter contract; a transport test checks exact agreement."""
    if case["pair"] == 3 and case["variant"] == "adverse":
        return None
    if (
        len(case["question"].encode()) > 4096
        or len((case["history"] + "".join(p[1] for p in case["generation_evidence"])).encode())
        > 8192
    ):
        raise ValueError("INPUT_SIZE_LIMIT")
    from knora.answering.interface import ConversationContext
    from knora.answering.module import AnswerQuestion
    from knora.providers.generation import GenerationEvidence
    from knora.providers.openai_compatible.generation import CLOUDFLARE_SYSTEM_PROMPT
    from knora.providers.structured_generation import STRUCTURED_RESULT_SCHEMA, user_message

    context = (
        ConversationContext("conversation-context-v2", case["history"], case["question"], (), 0)
        if case["history"]
        else None
    )
    question = AnswerQuestion._generation_question(case["question"], context)
    payload = {
        "model": "@cf/openai/gpt-oss-20b",
        "messages": [
            {"role": "system", "content": CLOUDFLARE_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": user_message(
                    question,
                    tuple(
                        GenerationEvidence(alias, content)
                        for alias, content in case["generation_evidence"]
                    ),
                ),
            },
        ],
        "response_format": {"type": "json_schema", "json_schema": STRUCTURED_RESULT_SCHEMA},
        "max_tokens": 512,
    }
    if len(_payload_bytes(payload)) > 16384:
        raise ValueError("REQUEST_SIZE_LIMIT")
    return payload


def _local_boundary(case: dict, payload: dict | None) -> str:
    from knora.access.identity import Identity
    from knora.access.workspace_authorization import WorkspaceAuthorizer
    from knora.domain.errors import KnoraError

    if case["pair"] == 3:
        authorizer = WorkspaceAuthorizer(
            SimpleNamespace(owner_for=lambda _: Identity("synthetic-issuer", "owner"))
        )
        try:
            authorizer.authorize(
                Identity("synthetic-issuer", "foreign", ("questions:ask",)),
                "synthetic-workspace",
                "questions:ask",
            )
        except KnoraError as error:
            if error.code == "WORKSPACE_ACCESS_DENIED" and payload is None:
                return "admission_unit_denied"
        raise ValueError("BOUNDARY_VIOLATION")
    serialized = json.dumps(payload, ensure_ascii=False)
    # The fake configuration is deliberately outside all provider inputs.
    config = {"service_secret": "KNORA188_CONFIG_ONLY"}
    if config["service_secret"] in serialized:
        raise ValueError("BOUNDARY_VIOLATION")
    if case["variant"] == "control" and not all(
        text in serialized for text in ("abc123", "KNORA188_EXAMPLE_ONLY")
    ):
        raise ValueError("BOUNDARY_VIOLATION")
    return "payload_isolation_only"


def run_offline(
    *, cases_raw: bytes, rubric_raw: bytes, directory: Path, run_id: str, live_reason: str
) -> dict:
    if not re.fullmatch(r"offline-[0-9]{3}", run_id) or live_reason not in LIVE_REASONS:
        raise ValueError("INVALID_RUN_METADATA")
    if directory.exists():
        raise FileExistsError(directory)
    cases, _ = load_selection(cases_raw, rubric_raw)
    rows = []
    for case in cases:
        payload = build_payload(case)
        row = {
            "case_id": case["case_id"],
            "language": case["language"],
            "variant": case["variant"],
            "model_eligible": case["model_eligible"],
            "scope": "model_output" if case["model_eligible"] else "local_unit",
            "status": "not_run" if case["model_eligible"] else "complete",
            "semantic": "unreviewed",
            "structural_validity": None,
            "input_sha256": _sha(_payload_bytes(payload)) if payload is not None else None,
            "transfer": observe_transfer(
                text=None,
                canary=case["canary"] or "UNOBSERVED",
                recipient_allowed=case["recipient_allowed"],
            ),
        }
        if not case["model_eligible"]:
            row["local_check"] = _local_boundary(case, payload)
        rows.append(row)
    report = {
        "schema": "issue188-security-outcomes-v1",
        "run_id": run_id,
        "selection_sha256": _sha(cases_raw),
        "rubric_sha256": _sha(rubric_raw),
        "code_sha256": {
            path.name: _sha(path.read_bytes())
            for path in (
                Path(__file__),
                Path(__file__).with_name("workbench_security_projection.py"),
                Path(__file__).parents[1] / "scorers/security_outcomes.py",
            )
        },
        "rows": rows,
        "counts": summarize_outcomes(rows),
        "live": {
            "status": "not_run",
            "reason": live_reason,
            "selected": 26,
            "attempted": 0,
            "completed": 0,
            "adjudicated": 0,
            "unavailable": 26,
            "usage": "unknown",
            "paid_spend_usd": "0",
        },
        "model_quality": "unverified",
        "enforcement": "off",
        "export": "off",
    }
    write_report_atomic(directory / "report.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", required=True, type=Path)
    parser.add_argument("--rubric", required=True, type=Path)
    parser.add_argument("--directory", required=True, type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--live-reason", choices=sorted(LIVE_REASONS), required=True)
    args = parser.parse_args()
    run_offline(
        cases_raw=args.cases.read_bytes(),
        rubric_raw=args.rubric.read_bytes(),
        directory=args.directory,
        run_id=args.run_id,
        live_reason=args.live_reason,
    )


if __name__ == "__main__":
    main()
