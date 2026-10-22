"""Score a persisted M3 report with optional explicitly reviewed Cloudflare preflight."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

from evals.datasets.milestone_3 import (
    load_milestone_3_dataset,
    load_milestone_3_dataset_manifest,
)
from evals.scorers.deepeval_cloudflare import (
    AttemptLedger,
    CloudflareJudge,
    JudgeError,
    derive_captures,
    publish_supplement,
    score_capture,
    validate_free_preflight,
)


def run_capture(
    source: dict,
    cases: list | tuple,
    *,
    run_id: str,
    output: Path,
    case_ids: tuple[str, ...] = (),
    preflight: dict | None = None,
    token: str | None = None,
    ledger_path: Path | None = None,
) -> dict:
    if output.exists():
        raise FileExistsError(output)
    captures = derive_captures(source, cases, run_id=run_id)
    if case_ids:
        if len(case_ids) != len(set(case_ids)) or set(case_ids) - {
            item["case_id"] for item in captures
        }:
            raise JudgeError("CASE_SELECTION_INVALID")
        captures = [item for item in captures if item["case_id"] in set(case_ids)]
    if preflight is not None and not 1 <= len(captures) <= 2:
        raise JudgeError("LIVE_CASE_LIMIT_EXCEEDED")
    digest = (
        "sha256:"
        + hashlib.sha256(
            json.dumps(captures, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()
    )
    if preflight is None:
        judge = type("OfflineModel", (), {"get_model_name": lambda self: "not_run"})()
        results = [score_capture(item, judge, measure=False) for item in captures]
    else:
        account = validate_free_preflight(preflight, run_id=run_id, capture_sha256=digest)
        if not token or ledger_path is None:
            raise JudgeError("JUDGE_CONFIGURATION_INVALID")
        if any(not isinstance(item["trace_id"], str) or not item["trace_id"] for item in captures):
            raise JudgeError("CAPTURE_TRACE_MISMATCH")
        started = datetime.fromisoformat(preflight["trial_started_at_utc"])
        deadline = started + timedelta(minutes=60)
        ledger = AttemptLedger(ledger_path, run_id=run_id, deadline=deadline, cap=24)
        judge = CloudflareJudge(
            endpoint=f"https://api.cloudflare.com/client/v4/accounts/{account}/ai/v1/chat/completions",
            token=token,
            model="@cf/openai/gpt-oss-20b",
            max_output_tokens=preflight["max_output_tokens"],
            ledger=ledger,
        )
        try:
            results = [
                score_capture(
                    {
                        **item,
                        "data_classification": preflight["approved_data_classification"],
                        "egress_approved": True,
                    },
                    judge,
                )
                for item in captures
            ]
        finally:
            judge.client.close()
    return publish_supplement(output, source, captures, results)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--dataset-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument("--preflight", type=Path)
    args = parser.parse_args()
    try:
        raw_report = args.report.read_bytes()
        source = json.loads(raw_report)
        run_id = "sha256:" + hashlib.sha256(raw_report).hexdigest()
        identity = load_milestone_3_dataset_manifest(args.dataset_manifest, args.dataset)
        if source.get("provenance", {}).get("dataset_digest") != identity.checksum:
            raise JudgeError("DATASET_PROVENANCE_MISMATCH")
        dataset = load_milestone_3_dataset(args.dataset)
        preflight = (
            json.loads(args.preflight.read_text(encoding="utf-8")) if args.preflight else None
        )
        run_capture(
            source,
            dataset.cases,
            run_id=run_id,
            output=args.output,
            case_ids=tuple(args.case_id),
            preflight=preflight,
            token=os.environ.get("KNORA_CF_EVALUATION_TOKEN") if preflight else None,
            ledger_path=Path(__file__).resolve().parents[1]
            / "reports"
            / ".deepeval-ledgers"
            / f"{run_id.removeprefix('sha256:')}.sqlite3",
        )
    except (JudgeError, FileExistsError, OSError, ValueError, TypeError, KeyError) as error:
        print(type(error).__name__ if not isinstance(error, JudgeError) else str(error))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
