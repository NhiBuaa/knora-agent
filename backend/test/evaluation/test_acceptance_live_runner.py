"""Tests for acceptance live runner CLI and entrypoint (Task T3)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from knora.evaluation.live_admission import _SLOTS_V2, reviewed_build_pins

NOW = datetime(2026, 10, 24, 0, 0, tzinfo=UTC)


def make_test_manifest_v3(tmp_path: Path) -> dict:
    build = reviewed_build_pins()
    items = []
    for case_id in ("004", "005", "012", "014", "032", "045"):
        items.append(
            {
                "item_id": case_id,
                "slot": "judge_real",
                "cap": 12,
                "input_digest": "a" * 64,
                "native_identity": {
                    "case_id": case_id,
                    "run_id": f"run-{case_id}",
                    "attempt_id": f"att-{case_id}",
                    "attempt": 1,
                    "trace_id": f"tr-{case_id}",
                    "workspace_id": "w1",
                },
            }
        )
    for variant in ("wrong-fact", "off-topic", "unsupported", "missing-exception"):
        items.append(
            {
                "item_id": f"control-{variant}",
                "slot": "judge_synthetic",
                "cap": 12,
                "input_digest": "b" * 64,
                "native_identity": {
                    "case_id": f"control-{variant}",
                    "run_id": f"run-{variant}",
                    "attempt_id": f"att-{variant}",
                    "attempt": 1,
                    "trace_id": f"tr-{variant}",
                    "workspace_id": "w1",
                },
            }
        )
    for refusal_id in ("053", "002"):
        items.append(
            {
                "item_id": f"refusal-{refusal_id}",
                "slot": "refusal_deterministic",
                "cap": 0,
                "input_digest": "c" * 64,
                "native_identity": {
                    "case_id": refusal_id,
                    "run_id": f"run-{refusal_id}",
                    "attempt_id": f"att-{refusal_id}",
                    "attempt": 1,
                    "trace_id": f"tr-{refusal_id}",
                    "workspace_id": "w1",
                },
            }
        )

    journal_path = tmp_path / "test_journal.sqlite"
    return {
        "manifest_version": 3,
        "package_id": "acceptance-runner-test-v3",
        "journal_path": str(journal_path.resolve()),
        "code_sha": build["code_sha"],
        "reviewed_build": build,
        "gold_v1": {
            "dataset_id": "pdf-set-v3",
            "dataset_digest": "6" * 64,
            "version": 1,
            "cases": {"ANSWER": "pdf-v3-004", "REFUSAL": "pdf-v3-053"},
            "sources": {
                "version-1": {"document_id": "document-1", "raw_sha256": "a" * 64},
                "version-2": {"document_id": "document-2", "raw_sha256": "b" * 64},
            },
        },
        "decision_reference": "issue158/evaluation-tools-acceptance",
        "approved_by": "owner",
        "account_id": "a" * 32,
        "ownership": {"workspace_id": "w1", "resource_id": "owned-test-runner"},
        "live_approved_at": NOW.isoformat(),
        "package_deadline": (NOW + timedelta(days=7)).isoformat(),
        "max_attempts": 121,
        "startup_cap": 0,
        "window_cap": 8,
        "slots": dict(_SLOTS_V2),
        "skipped_slots": ["corpus_prepare", "qa_gold_v1_answer"],
        "items": items,
    }


def test_cli_missing_required_arguments(tmp_path: Path):
    from scripts.run_acceptance_live import main

    # Calling with no arguments or missing required arguments must exit with nonzero code
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code != 0

    with pytest.raises(SystemExit) as exc:
        main(["--manifest", str(tmp_path / "m.json")])
    assert exc.value.code != 0


def test_preflight_mode_checks_pins_without_journal_creation(tmp_path: Path):
    from scripts.run_acceptance_live import main

    manifest = make_test_manifest_v3(tmp_path)
    manifest_file = tmp_path / "manifest.json"
    manifest_file.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    journal_path = Path(manifest["journal_path"])
    output_dir = tmp_path / "output"

    code = main(
        [
            "--manifest",
            str(manifest_file),
            "--journal",
            str(journal_path),
            "--output",
            str(output_dir),
            "--mode",
            "preflight",
        ]
    )
    assert code == 0
    # Preflight must NOT create the journal file
    assert not journal_path.exists()
    assert (output_dir / "preflight-summary.json").exists()


def test_execute_mode_stops_for_human_review_when_labels_missing(tmp_path: Path):
    from scripts.run_acceptance_live import main

    manifest = make_test_manifest_v3(tmp_path)
    manifest_file = tmp_path / "manifest.json"
    manifest_file.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    journal_path = Path(manifest["journal_path"])
    output_dir = tmp_path / "output"

    def mock_ragas_exchange(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "model": "@cf/openai/gpt-oss-20b",
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "content": json.dumps(
                                {
                                    "drafts": [
                                        {
                                            "language": "vi",
                                            "question": "Câu hỏi nháp?",
                                            "reference_answer": "Câu trả lời nháp.",
                                            "hops": [
                                                {
                                                    "chunk_ref": "academic-phonlp:p1:0-264",
                                                    "quote": "PHONLP",
                                                    "necessary_claim": "Claim 1",
                                                },
                                                {
                                                    "chunk_ref": "hierarchy-03:p2:0-273",
                                                    "quote": "Hierarchy",
                                                    "necessary_claim": "Claim 2",
                                                },
                                            ],
                                        }
                                    ]
                                }
                            )
                        },
                    }
                ],
                "usage": {"completion_tokens": 50},
            },
        )

    code = main(
        [
            "--manifest",
            str(manifest_file),
            "--journal",
            str(journal_path),
            "--output",
            str(output_dir),
            "--mode",
            "execute",
            "--mock-ragas",
        ],
        mock_handler=mock_ragas_exchange,
    )

    # Exit 0 indicating successful generation of review packet and waiting for human review
    assert code == 0
    assert journal_path.exists()
    # Review packet must be exported for human review
    review_packet_path = output_dir / "issue-158-human-review-packet.json"
    assert review_packet_path.exists()
    packet = json.loads(review_packet_path.read_text(encoding="utf-8"))
    assert len(packet["items"]) == 12
    # Status summary indicates blocked on human labels before judge execution
    summary_path = output_dir / "acceptance-run-summary.json"
    assert summary_path.exists()
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["status"] == "WAITING_FOR_HUMAN_REVIEW"


def test_execute_mode_with_approved_human_labels_proceeds_to_completion(tmp_path: Path):
    from scripts.run_acceptance_live import main

    manifest = make_test_manifest_v3(tmp_path)
    manifest_file = tmp_path / "manifest.json"
    manifest_file.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    journal_path = Path(manifest["journal_path"])
    output_dir = tmp_path / "output"

    # Create approved human labels file for all 12 items
    human_labels = {
        "reviewer": "owner",
        "reviewed_at": NOW.isoformat(),
        "packet_digest": "d" * 64,
        "labels": {
            "004": {
                "correctness": 1.0,
                "answer_relevancy": 1.0,
                "faithfulness": 1.0,
                "notes": "OK",
            },
            "005": {
                "correctness": 1.0,
                "answer_relevancy": 1.0,
                "faithfulness": 1.0,
                "notes": "OK",
            },
            "012": {
                "correctness": 1.0,
                "answer_relevancy": 1.0,
                "faithfulness": 1.0,
                "notes": "OK",
            },
            "014": {
                "correctness": 1.0,
                "answer_relevancy": 1.0,
                "faithfulness": 1.0,
                "notes": "OK",
            },
            "032": {
                "correctness": 1.0,
                "answer_relevancy": 1.0,
                "faithfulness": 1.0,
                "notes": "OK",
            },
            "045": {
                "correctness": 1.0,
                "answer_relevancy": 1.0,
                "faithfulness": 1.0,
                "notes": "OK",
            },
            "control-wrong-fact": {
                "correctness": 0.0,
                "answer_relevancy": 1.0,
                "faithfulness": 0.0,
                "notes": "Rejected",
            },
            "control-off-topic": {
                "correctness": 0.0,
                "answer_relevancy": 0.0,
                "faithfulness": 1.0,
                "notes": "Rejected",
            },
            "control-unsupported": {
                "correctness": 0.0,
                "answer_relevancy": 1.0,
                "faithfulness": 0.0,
                "notes": "Rejected",
            },
            "control-missing-exception": {
                "correctness": 0.0,
                "answer_relevancy": 0.5,
                "faithfulness": 0.0,
                "notes": "Rejected",
            },
            "refusal-053": {"decision": "REFUSAL", "notes": "Consistent"},
            "refusal-002": {"decision": "REFUSAL", "notes": "False refusal noted"},
        },
    }
    labels_path = tmp_path / "approved-human-labels.json"
    labels_path.write_text(json.dumps(human_labels, indent=2), encoding="utf-8")

    code = main(
        [
            "--manifest",
            str(manifest_file),
            "--journal",
            str(journal_path),
            "--output",
            str(output_dir),
            "--mode",
            "execute",
            "--human-labels",
            str(labels_path),
            "--mock-ragas",
            "--mock-judge",
        ]
    )

    assert code == 0
    assert journal_path.exists()
    assert (output_dir / "issue-158-human-review-packet.json").exists()
    summary = json.loads((output_dir / "acceptance-run-summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "SCORED_READY_FOR_OWNER_REVIEW"
    assert summary["pending_owner_gate"] == "GATE_3_FINAL_ACCEPTANCE"
