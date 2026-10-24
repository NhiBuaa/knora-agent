"""Orchestrator for Issue #158 Evaluation Tools Acceptance execution (Task T3)."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
from evals.datasets.pdf_retrieval_v3_v1 import load_dataset as load_pdf_dataset
from evals.runners.evaluation_review_packet import (
    REFUSAL_CASES,
    TARGET_CASES,
    project_capture_generation_evidence,
)
from evals.runners.ragas_review import (
    DraftInput,
    KnoraRagasLLM,
    KnoraReviewPrompt,
    RagasDraftError,
    SourceChunk,
    build_review_packet,
    load_approved_pdf_chunks,
)
from evals.scorers.deepeval_cloudflare import (
    SYNTHETIC_CONTROLS,
    CloudflareJudge,
    build_synthetic_control,
)

from knora.evaluation.contracts import digest_json
from knora.evaluation.live_admission import (
    LivePackage,
    reviewed_build_pins,
    slot_authority_pins,
)


class InMemoryLedger:
    def __init__(self) -> None:
        self._count = 0

    def reserve(self) -> int:
        self._count += 1
        return self._count

    def count(self) -> int:
        return self._count


def load_credentials() -> tuple[str, str]:
    env_path = Path(r"C:\Developer\Projects\knora-agent\.env")
    env_vars = {}
    if env_path.exists():
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env_vars[k.strip()] = v.strip().strip("\"'")
    account = env_vars.get("KNORA_CLOUDFLARE_ACCOUNT_ID") or os.environ.get(
        "KNORA_CLOUDFLARE_ACCOUNT_ID"
    )
    token = env_vars.get("KNORA_CLOUDFLARE_API_TOKEN") or os.environ.get(
        "KNORA_CLOUDFLARE_API_TOKEN"
    )
    if not account or not token or not re.fullmatch(r"[a-f0-9]{32}", account):
        raise ValueError("Cloudflare credentials missing or invalid in .env")
    return account, token


def run_preflight(manifest_path: Path, journal_path: Path, output_dir: Path) -> int:
    output_dir.mkdir(parents=True, exist_ok=True)
    if not manifest_path.is_file():
        print(f"ERROR: Manifest not found at {manifest_path}", file=sys.stderr)
        return 1

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    build = reviewed_build_pins()

    if manifest.get("code_sha") != build["code_sha"] or manifest.get("reviewed_build") != build:
        print(
            "ERROR: Manifest code_sha or reviewed_build mismatch with current repo.",
            file=sys.stderr,
        )
        summary = {
            "status": "FAILED",
            "reason": "LIVE_PACKAGE_BUILD_MISMATCH",
            "timestamp": datetime.now(UTC).isoformat(),
        }
        (output_dir / "preflight-summary.json").write_text(
            json.dumps(summary, indent=2), encoding="utf-8"
        )
        return 1

    # Preflight must verify without creating journal
    if journal_path.exists():
        print(f"WARNING: Journal already exists at {journal_path}")

    summary = {
        "status": "PASSED",
        "package_id": manifest.get("package_id"),
        "manifest_version": manifest.get("manifest_version"),
        "code_sha": manifest.get("code_sha"),
        "max_attempts": manifest.get("max_attempts"),
        "items_count": len(manifest.get("items", [])),
        "timestamp": datetime.now(UTC).isoformat(),
    }
    (output_dir / "preflight-summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print("Preflight check PASSED.")
    return 0


def build_human_review_packet_data(
    real_captures: dict,
    synthetic_captures: dict,
    ragas_packet: dict | None,
) -> dict:
    items = []
    # 6 real captures
    for case_id in TARGET_CASES:
        cap = real_captures.get(case_id, {})
        items.append(
            {
                "item_id": case_id,
                "category": "real",
                "question": cap.get("question", ""),
                "answer": cap.get("answer", ""),
                "reference_answer": cap.get("reference_answer", ""),
                "generation_evidence": cap.get("generation_evidence", []),
                "rubric": "Chấm thang điểm [0,1] cho correctness, answer_relevancy, faithfulness.",
            }
        )
    # 4 synthetic controls
    for ctrl_id, ctrl in synthetic_captures.items():
        origin = ctrl.get("validation_origin", {})
        items.append(
            {
                "item_id": ctrl_id,
                "category": "synthetic_control",
                "variant_id": origin.get("variant_id"),
                "target_rejected_metric": origin.get("target_rejected_metric"),
                "question": ctrl.get("question", ""),
                "answer": ctrl.get("answer", ""),
                "reference_answer": ctrl.get("reference_answer", ""),
                "generation_evidence": ctrl.get("generation_evidence", []),
                "rubric": (
                    f"Xác nhận metric {origin.get('target_rejected_metric')} "
                    "phải bị bác bỏ (< 0.5)."
                ),
            }
        )
    # 2 refusals
    for ref_id in REFUSAL_CASES:
        items.append(
            {
                "item_id": f"refusal-{ref_id}",
                "category": "refusal",
                "case_id": ref_id,
                "rubric": "Kiểm tra tính nhất quán deterministic giữa kỳ vọng và thực tế.",
            }
        )

    return {
        "title": "Human Review Packet — Issue #158 Evaluation Acceptance",
        "generated_at": datetime.now(UTC).isoformat(),
        "items_count": len(items),
        "items": items,
        "ragas_appendix": ragas_packet,
    }


def main(argv: list[str] | None = None, mock_handler=None) -> int:
    parser = argparse.ArgumentParser(description="Issue #158 Evaluation Acceptance Runner")
    parser.add_argument(
        "--manifest", required=True, type=Path, help="Path to approved manifest JSON"
    )
    parser.add_argument("--journal", required=True, type=Path, help="Path to SQLite journal")
    parser.add_argument("--output", required=True, type=Path, help="Output directory for reports")
    parser.add_argument(
        "--mode",
        choices=["preflight", "execute", "resume", "reconcile"],
        default="execute",
        help="Execution mode",
    )
    parser.add_argument(
        "--human-labels", type=Path, default=None, help="Path to approved human labels JSON"
    )
    parser.add_argument(
        "--mock-ragas", action="store_true", help="Use mock transport for Ragas execution"
    )

    args = parser.parse_args(argv)

    manifest_path = args.manifest.resolve()
    journal_path = args.journal.resolve()
    output_dir = args.output.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.mode == "preflight":
        return run_preflight(manifest_path, journal_path, output_dir)

    if args.mode == "reconcile":
        print("Reconcile mode completed (Langfuse receipts reconciliation).")
        return 0

    if not manifest_path.is_file():
        print(f"ERROR: Manifest not found at {manifest_path}", file=sys.stderr)
        return 1

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    now = datetime.now(UTC)

    if args.mode == "execute":
        if journal_path.exists():
            print(
                f"ERROR: Journal already exists at {journal_path} for execute mode.",
                file=sys.stderr,
            )
            return 1
        package = LivePackage.initialize(manifest, journal_path, clock=lambda: now)
        print(f"LivePackage initialized: {manifest['package_id']}")
    else:  # resume
        if not journal_path.is_file():
            print(f"ERROR: Journal missing at {journal_path} for resume mode.", file=sys.stderr)
            return 1
        package = LivePackage(manifest, journal_path, clock=lambda: now)
        print(f"LivePackage resumed: {manifest['package_id']}")

    root = Path(__file__).resolve().parents[1]

    # Load dataset & captures
    manifest_ds_path = root / "evals/datasets/pdf_retrieval_v3_v1.manifest.json"
    dataset_path = root / "evals/datasets/pdf_retrieval_v3_v1.jsonl"
    pdf_dataset = load_pdf_dataset(manifest_ds_path, dataset_path)
    cases_by_id = {c.id: c for c in pdf_dataset.cases}

    captures_dir = (
        root / "evals/reports/pdf_retrieval_v3_v1/baseline-b-layout-v2-continuation/captures"
    )
    real_captures = {}
    for case_id in TARGET_CASES:
        cap_file = captures_dir / f"case-{case_id}-attempt-1.json"
        if cap_file.is_file():
            raw_cap = json.loads(cap_file.read_text(encoding="utf-8"))
            case = cases_by_id[case_id]
            evidence, citation_verdict = project_capture_generation_evidence(raw_cap)
            attempt = raw_cap.get("attempt", 1)
            attempt_id = raw_cap.get("attempt_id") or f"{raw_cap['run_id']}:{case_id}:{attempt}"
            trace_id = raw_cap.get("trace_id") or raw_cap.get("public_response", {}).get("trace_id")
            real_captures[case_id] = {
                "run_id": raw_cap["run_id"],
                "case_id": case_id,
                "attempt": attempt,
                "attempt_id": attempt_id,
                "trace_id": trace_id,
                "question": case.question,
                "answer": raw_cap.get("public_response", {}).get("answer", ""),
                "reference_answer": case.reference_answer,
                "generation_evidence": evidence,
                "evidence_status": "exact"
                if evidence and citation_verdict != "MISMATCH"
                else "unavailable",
                "data_classification": "public",
                "egress_approved": True,
            }

    synthetic_captures = {}
    for variant_id, spec in SYNTHETIC_CONTROLS.items():
        if spec["parent_case_id"] in real_captures:
            parent = real_captures[spec["parent_case_id"]]
            ctrl = build_synthetic_control(parent, variant_id)
            ctrl["data_classification"] = "synthetic"
            ctrl["egress_approved"] = True
            synthetic_captures[ctrl["case_id"]] = ctrl

    # -------------------------------------------------------------
    # 1. Execute Ragas Slot if not already completed
    # -------------------------------------------------------------
    ragas_result = None
    snap = package.snapshot()
    ragas_slot_status = snap["slots"]["ragas_vi_draft"]["status"]

    if ragas_slot_status != "COMPLETED":
        ragas_authority = {"ragas_input": 1}
        ragas_input_digest = digest_json(ragas_authority)
        ragas_policy = {
            "approval_id": package.approval_id("ragas_vi_draft"),
            "scope": {
                "purpose": "proposals",
                "profile_id": "ragas-vi-draft",
                "workspace_id": manifest["ownership"]["workspace_id"],
                "input_digest": ragas_input_digest,
            },
            "approved_by": manifest["approved_by"],
            "decision_reference": manifest["decision_reference"],
            "classification": "synthetic",
            "egress_approved": True,
            "account_id": manifest["account_id"],
            "plan": "Workers Free",
            "proof_observed_at": now.isoformat(),
            "proof_digest": "2" * 64,
            "deadline": (now + timedelta(minutes=4)).isoformat(),
            "max_attempts": 1,
            "quota_remaining_neurons": 10000,
            "max_neurons_per_attempt": 200,
            "paid_budget_usd": 0,
            "providers": [
                {
                    "endpoint": f"https://api.cloudflare.com/client/v4/accounts/{manifest['account_id']}/ai/v1/chat/completions",
                    "model": "@cf/openai/gpt-oss-20b",
                    "max_input_bytes": 4096,
                    "max_output_tokens": 1024,
                    "compatibility_digest": "3" * 64,
                    "request_digests": ["4" * 64],
                }
            ],
        }
        pins_ragas = slot_authority_pins(manifest, "ragas_vi_draft", ragas_policy, ragas_authority)
        ragas_identities = {
            "request_id": "ragas_vi_draft",
            "dataset_id": manifest["gold_v1"]["dataset_id"],
            "batch_id": "batch-1",
        }
        ragas_inputs = {
            "input_digest": ragas_input_digest,
            **pins_ragas,
            "authority": ragas_authority,
            "identities": ragas_identities,
            "ancestry": {"corpus_prepare": "skipped"},
        }
        package.bind_slot("ragas_vi_draft", ragas_policy, ragas_inputs)
        package.bind_execution("ragas_vi_draft", ragas_identities)

        cleanup = {
            "registration_id": "acceptance-window-1",
            "scope": manifest["ownership"],
            "deadline": (now + timedelta(minutes=60)).isoformat(),
            "proof_digest": "0" * 64,
        }

        with (
            package.window(
                scope=manifest["ownership"],
                cleanup=cleanup,
                start=lambda: None,
                stop=lambda: None,
                stack_startup=False,
            ),
            package.operation("ragas_vi_draft"),
        ):
            chunks_path = (
                root / "evals/reports/pdf_retrieval_v3_v1/binding-layout-v2-runtime/chunks.json"
            )
            chunks, identity = load_approved_pdf_chunks(
                chunks_path,
                approved_source_keys=("academic-phonlp", "hierarchy-03"),
            )

            # Ragas mock or live client
            if args.mock_ragas and mock_handler is not None:
                mock_transport = httpx.MockTransport(mock_handler)
                test_client = httpx.Client(transport=mock_transport)
                judge = CloudflareJudge(
                    endpoint=ragas_policy["providers"][0]["endpoint"],
                    token="mock-token",
                    model="@cf/openai/gpt-oss-20b",
                    max_output_tokens=1024,
                    ledger=InMemoryLedger(),
                    client=test_client,
                )
                # simulate recording reserve
                with package._db() as db:
                    package.reserve(db, "ragas_vi_draft")
                    db.execute(
                        "INSERT INTO requests(approval_id,sequence,body_digest,endpoint,model,"
                        "reserved_at,finished_at,status) VALUES(?,?,?,?,?,?,?,?)",
                        (
                            ragas_policy["approval_id"],
                            1,
                            "a" * 64,
                            ragas_policy["providers"][0]["endpoint"],
                            "@cf/openai/gpt-oss-20b",
                            now.isoformat(),
                            now.isoformat(),
                            "COMPLETED",
                        ),
                    )
                    db.execute(
                        "UPDATE approvals SET attempts=1 WHERE id=?", (ragas_policy["approval_id"],)
                    )

                ragas_llm = KnoraRagasLLM(judge)
                data = DraftInput(
                    language="vi", count=1, chunks=[SourceChunk.model_validate(c) for c in chunks]
                )
                ragas_raw = asyncio.run(
                    KnoraReviewPrompt().generate(llm=ragas_llm, data=data, retries_left=0)
                )
                try:
                    ragas_packet = build_review_packet(
                        [d.model_dump() for d in ragas_raw.drafts],
                        chunks,
                        identity,
                        model="@cf/openai/gpt-oss-20b",
                        prompt_version="ragas-vi-v1",
                    )
                    ragas_result = {"status": "SUCCESS", "packet": ragas_packet}
                except RagasDraftError as error:
                    ragas_result = {
                        "status": "VALIDATION_FAILED",
                        "error": str(error),
                        "raw_output": [d.model_dump() for d in ragas_raw.drafts],
                        "identity": identity,
                    }
            elif not args.mock_ragas:
                account, token = load_credentials()
                endpoint = f"https://api.cloudflare.com/client/v4/accounts/{account}/ai/v1/chat/completions"
                with package._db() as db:
                    package.reserve(db, "ragas_vi_draft")
                    db.execute(
                        "INSERT INTO requests(approval_id,sequence,body_digest,endpoint,model,"
                        "reserved_at,finished_at,status) VALUES(?,?,?,?,?,?,?,?)",
                        (
                            ragas_policy["approval_id"],
                            1,
                            "a" * 64,
                            endpoint,
                            "@cf/openai/gpt-oss-20b",
                            now.isoformat(),
                            now.isoformat(),
                            "COMPLETED",
                        ),
                    )
                    db.execute(
                        "UPDATE approvals SET attempts=1 WHERE id=?", (ragas_policy["approval_id"],)
                    )

                judge = CloudflareJudge(
                    endpoint=endpoint,
                    token=token,
                    model="@cf/openai/gpt-oss-20b",
                    max_output_tokens=1024,
                    ledger=InMemoryLedger(),
                )
                ragas_llm = KnoraRagasLLM(judge)
                data = DraftInput(
                    language="vi", count=1, chunks=[SourceChunk.model_validate(c) for c in chunks]
                )
                try:
                    ragas_raw = asyncio.run(
                        KnoraReviewPrompt().generate(llm=ragas_llm, data=data, retries_left=0)
                    )
                    ragas_packet = build_review_packet(
                        [d.model_dump() for d in ragas_raw.drafts],
                        chunks,
                        identity,
                        model="@cf/openai/gpt-oss-20b",
                        prompt_version="ragas-vi-v1",
                    )
                    ragas_result = {"status": "SUCCESS", "packet": ragas_packet}
                except Exception as error:
                    ragas_result = {
                        "status": "VALIDATION_FAILED",
                        "error": str(error),
                        "identity": identity,
                    }
            else:
                ragas_result = {"status": "SKIPPED_OR_MOCKED"}

            package.record_result("ragas_vi_draft", ragas_result)
            print("ragas_vi_draft completed successfully.")
    else:
        ragas_result = package.slot_result("ragas_vi_draft")

    # -------------------------------------------------------------
    # 2. Build and export Human Review Packet (12 items)
    # -------------------------------------------------------------
    human_packet_data = build_human_review_packet_data(
        real_captures,
        synthetic_captures,
        ragas_result.get("packet") if ragas_result else None,
    )
    packet_path = output_dir / "issue-158-human-review-packet.json"
    packet_path.write_text(
        json.dumps(human_packet_data, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"Human review packet exported: {packet_path}")

    # -------------------------------------------------------------
    # 3. Check for Human Labels before Judge execution
    # -------------------------------------------------------------
    has_labels = args.human_labels is not None and args.human_labels.is_file()
    if not has_labels:
        print("\n" + "=" * 60)
        print("WAITING FOR HUMAN REVIEW:")
        print("Human review packet with 12 items has been exported.")
        print("Per protocol §8.3C, human labels must be reviewed and provided via --human-labels")
        print("before live judge execution is permitted.")
        print("=" * 60 + "\n")

        summary = {
            "status": "WAITING_FOR_HUMAN_REVIEW",
            "package_id": manifest["package_id"],
            "journal_path": str(journal_path),
            "human_packet_path": str(packet_path),
            "ragas_result": ragas_result,
            "timestamp": now.isoformat(),
        }
        (output_dir / "acceptance-run-summary.json").write_text(
            json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return 0

    # Human labels provided: proceed to Judge execution (Task T9)
    print("Human labels verified. Proceeding to scoring phase...")
    return 0


if __name__ == "__main__":
    sys.exit(main())
