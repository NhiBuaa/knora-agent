"""Build and format human review packets for Issue #158 evaluation tools acceptance."""

from __future__ import annotations

import hashlib
import json
import random
from copy import deepcopy
from pathlib import Path
from typing import Any

from evals.scorers.deepeval_cloudflare import (
    SYNTHETIC_CONTROLS,
    _scoring_input_sha256,
    build_synthetic_control,
)


def _digest_json(value: Any) -> str:
    return (
        "sha256:"
        + hashlib.sha256(
            json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode(
                "utf-8"
            )
        ).hexdigest()
    )


TARGET_CASES = (
    "pdf-v3-004",
    "pdf-v3-005",
    "pdf-v3-012",
    "pdf-v3-014",
    "pdf-v3-032",
    "pdf-v3-045",
)
REFUSAL_CASES = ("pdf-v3-053", "pdf-v3-002")


def project_capture_generation_evidence(raw_cap: dict) -> tuple[list[dict], str]:
    """Project complete generation evidence from candidates actually aliased into generation."""
    cits = raw_cap.get("public_response", {}).get("citations", [])
    selected = sorted(
        [c for c in raw_cap.get("candidates", []) if c.get("final_decision") == "SELECTED"],
        key=lambda x: x.get("final_rank", 1),
    )
    if not selected:
        return [], "UNAVAILABLE" if not cits else "MISMATCH"

    alias_by_rank = {idx: f"E{idx}" for idx in range(1, len(selected) + 1)}
    cands_by_alias = {alias_by_rank[idx]: cand for idx, cand in enumerate(selected, start=1)}

    if any(
        not isinstance(cand.get("content"), str) or not cand["content"].strip() for cand in selected
    ):
        return [], "UNAVAILABLE"

    citation_verdict = "VALID" if cits else "UNAVAILABLE"
    for cit in cits:
        ev_id = cit.get("evidence_id")
        if ev_id not in cands_by_alias:
            citation_verdict = "MISMATCH"
            break
        cand = cands_by_alias[ev_id]
        expected_sha = cit.get("content_checksum")
        if expected_sha:
            actual_sha = hashlib.sha256(cand["content"].encode("utf-8")).hexdigest()
            if actual_sha != expected_sha:
                citation_verdict = "MISMATCH"
                break

    if citation_verdict == "MISMATCH":
        return [], "MISMATCH"

    generation_evidence = [
        {"alias": alias_by_rank[idx], "content": cand["content"]}
        for idx, cand in enumerate(selected, start=1)
    ]
    return generation_evidence, citation_verdict


def build_acceptance_review_packet(
    captures_dir: Path,
    pdf_dataset,
    *,
    shuffle_seed: int = 158,
    created_at: str = "2026-10-23T00:00:00+00:00",
) -> dict:
    """Build the 12-item human review packet from canonical baseline captures."""
    cases_by_id = {c.id: c for c in pdf_dataset.cases}
    anchors_by_id = {a.id: a for a in pdf_dataset.anchors}

    raw_items = []

    # 1. Six real answer captures
    for case_id in TARGET_CASES:
        cap_file = captures_dir / f"case-{case_id}-attempt-1.json"
        raw_cap = json.loads(cap_file.read_text(encoding="utf-8"))
        case = cases_by_id[case_id]
        cits = raw_cap.get("public_response", {}).get("citations", [])

        # Project generation evidence preserving all selected candidates
        generation_evidence, citation_verdict = project_capture_generation_evidence(raw_cap)

        # Anchors
        anchors = []
        for grp in case.evidence_groups:
            for aid in grp:
                if aid in anchors_by_id:
                    a = anchors_by_id[aid]
                    anchors.append(
                        {
                            "anchor_id": a.id,
                            "source_id": a.source_id,
                            "page": a.page,
                            "text": a.text,
                        }
                    )

        attempt = raw_cap.get("attempt", 1)
        attempt_id = raw_cap.get("attempt_id") or f"{raw_cap['run_id']}:{case_id}:{attempt}"
        trace_id = raw_cap.get("trace_id") or raw_cap.get("public_response", {}).get("trace_id")

        item = {
            "item_kind": "real_answer",
            "case_id": case_id,
            "parent_case_id": None,
            "validation_variant_id": None,
            "run_id": raw_cap["run_id"],
            "attempt": attempt,
            "attempt_id": attempt_id,
            "trace_id": trace_id,
            "question": case.question,
            "answer": raw_cap["public_response"]["answer"],
            "decision": "ANSWER",
            "expected_decision": case.expected_behavior,
            "reference_answer": case.reference_answer,
            "required_facts": list(case.required_facts),
            "generation_evidence": generation_evidence,
            "source_anchors": anchors,
            "knora_citations": cits,
            "citation_verdict": citation_verdict,
            "validation_origin": None,
        }
        item["input_sha256"] = _scoring_input_sha256(item)
        raw_items.append(item)

    # 2. Four synthetic controls (derived from 004, 005, 014, 012)
    real_by_case = {
        item["case_id"]: item for item in raw_items if item["item_kind"] == "real_answer"
    }
    for variant_id, spec in SYNTHETIC_CONTROLS.items():
        parent = real_by_case[spec["parent_case_id"]]
        ctrl = build_synthetic_control(parent, variant_id)
        ctrl_item = {
            "item_kind": "synthetic_control",
            "case_id": ctrl["case_id"],
            "parent_case_id": spec["parent_case_id"],
            "validation_variant_id": variant_id,
            "run_id": parent["run_id"],
            "attempt": parent["attempt"],
            "attempt_id": parent["attempt_id"],
            "trace_id": parent["trace_id"],
            "question": parent["question"],
            "answer": ctrl["answer"],
            "decision": "ANSWER",
            "expected_decision": "ANSWER",
            "reference_answer": parent["reference_answer"],
            "required_facts": parent["required_facts"],
            "generation_evidence": parent["generation_evidence"],
            "source_anchors": parent["source_anchors"],
            "knora_citations": parent["knora_citations"],
            "citation_verdict": "SYNTHETIC_CONTROL",
            "validation_origin": ctrl["validation_origin"],
        }
        ctrl_item["input_sha256"] = _scoring_input_sha256(ctrl_item)
        raw_items.append(ctrl_item)

    # 3. Two refusal controls (053 and 002)
    for case_id in REFUSAL_CASES:
        cap_file = captures_dir / f"case-{case_id}-attempt-1.json"
        raw_cap = json.loads(cap_file.read_text(encoding="utf-8"))
        case = cases_by_id[case_id]
        item = {
            "item_kind": "refusal_control",
            "case_id": case_id,
            "parent_case_id": None,
            "validation_variant_id": None,
            "run_id": raw_cap["run_id"],
            "attempt": raw_cap.get("attempt", 1),
            "attempt_id": raw_cap.get("attempt_id", f"{raw_cap['run_id']}:{case_id}:1"),
            "trace_id": raw_cap["trace_id"],
            "question": case.question,
            "answer": None,
            "decision": raw_cap.get("decision", "REFUSAL"),
            "expected_decision": case.expected_behavior,
            "reference_answer": case.reference_answer,
            "required_facts": list(case.required_facts),
            "generation_evidence": [],
            "source_anchors": [],
            "knora_citations": [],
            "citation_verdict": "NOT_APPLICABLE",
            "validation_origin": None,
        }
        item["input_sha256"] = _scoring_input_sha256(item)
        raw_items.append(item)

    # Deterministic shuffle
    rng = random.Random(shuffle_seed)
    shuffled_indices = list(range(len(raw_items)))
    rng.shuffle(shuffled_indices)

    items = []
    for rank, idx in enumerate(shuffled_indices, start=1):
        it = deepcopy(raw_items[idx])
        it["item_number"] = f"REV-{rank:02d}"
        it["review"] = {
            "review_status": "pending_review",
            "reviewer": "",
            "reviewed_at": None,
            "correctness": {
                "verdict": "pending",
                "reason": "",
                "evidence_anchor": "",
            },
            "answer_relevancy": {
                "verdict": "pending",
                "reason": "",
                "evidence_anchor": "",
            },
            "faithfulness": {
                "verdict": "pending",
                "reason": "",
                "evidence_anchor": "",
            },
            "refusal_verdict": {"verdict": "pending", "reason": ""},
        }
        items.append(it)

    packet = {
        "schema_version": 1,
        "packet_id": "issue-158-acceptance-packet-v1",
        "created_at": created_at,
        "shuffle_seed": shuffle_seed,
        "items_count": len(items),
        "items": items,
        "ragas_appendix": {
            "status": "not_run",
            "description": (
                "Single-call Ragas draft generation in Task 7 (max 2 drafts,"
                " language vi, pending live approval)."
            ),
            "drafts": [],
        },
    }
    packet["packet_sha256"] = _digest_json(packet)
    return packet


def format_review_packet_markdown(packet: dict) -> str:
    """Format the review packet as a readable Markdown document for human review."""
    lines = [
        "# Issue #158 Evaluation Tools Acceptance — Human Review Packet",
        "",
        f"- **Packet ID**: `{packet['packet_id']}`",
        f"- **Packet Digest**: `{packet['packet_sha256']}`",
        f"- **Shuffle Seed**: `{packet['shuffle_seed']}`",
        (
            f"- **Items Count**: {packet['items_count']} (6 Real Answers, 4"
            " Synthetic Controls, 2 Refusal Controls)"
        ),
        ("- **Note**: Blind review packet — absolute zero judge scores/rationales included."),
        "",
        "---",
        "",
        "## Bảng tổng quan 12 mục đánh giá",
        "",
        (
            "| STT | Item ID | Mã ca (Case ID) | Loại mục | Quyết định | Kỳ vọng"
            " | Trạng thái Review |"
        ),
        "|---|---|---|---|---|---|---|",
    ]

    for it in packet["items"]:
        num, cid, kind = it["item_number"], it["case_id"], it["item_kind"]
        dec, exp, rev = it["decision"], it["expected_decision"], it["review"]["review_status"]
        lines.append(f"| {num} | `{num}` | `{cid}` | `{kind}` | `{dec}` | `{exp}` | `{rev}` |")

    lines.extend(
        [
            "",
            "---",
            "",
            "## Chi tiết từng mục và mẫu ghi nhận đánh giá của Owner",
            "",
        ]
    )

    for it in packet["items"]:
        actual_txt = (
            it["answer"] if it["answer"] is not None else "*(REFUSAL - Không có câu trả lời)*"
        )
        ref_txt = (
            it["reference_answer"]
            if it["reference_answer"]
            else "*(N/A - Không có câu trả lời mẫu)*"
        )
        lines.extend(
            [
                f"### Mục {it['item_number']}: `{it['case_id']}` ({it['item_kind']})",
                "",
                f"- **Question**: {it['question']}",
                f"- **Actual Output**: {actual_txt}",
                f"- **Reference Answer**: {ref_txt}",
                (f"- **Decision / Expected**: `{it['decision']}` / `{it['expected_decision']}`"),
                f"- **Trace ID**: `{it['trace_id']}`",
                f"- **Input SHA-256**: `{it['input_sha256']}`",
                "",
                "**Bằng chứng trích xuất (Generation Evidence):**",
                "",
            ]
        )
        if it["generation_evidence"]:
            for ev in it["generation_evidence"]:
                lines.append(f"- **[{ev['alias']}]**: {ev['content']}")
        else:
            lines.append("- *(Không có bằng chứng văn bản)*")

        lines.extend(
            [
                "",
                "**Mẫu ghi nhận kết luận người đánh giá (Reviewer Input Form):**",
                "",
                "```yaml",
                f"item_id: {it['item_number']}",
                f"case_id: {it['case_id']}",
                'reviewer: ""',
                "reviewed_at: null",
                "correctness:",
                "  verdict: pending # accept | reject | unavailable",
                '  reason: ""',
                '  evidence_anchor: ""',
                "answer_relevancy:",
                "  verdict: pending # accept | reject | unavailable",
                '  reason: ""',
                '  evidence_anchor: ""',
                "faithfulness:",
                "  verdict: pending # accept | reject | unavailable",
                '  reason: ""',
                '  evidence_anchor: ""',
            ]
        )
        if it["item_kind"] == "refusal_control":
            lines.extend(
                [
                    "refusal_verdict:",
                    "  verdict: pending # accept | reject",
                    '  reason: ""',
                ]
            )
        lines.extend(
            [
                "```",
                "",
                "---",
                "",
            ]
        )

    lines.extend(
        [
            "## Phụ lục Ragas Drafts",
            "",
            f"- **Trạng thái**: `{packet['ragas_appendix']['status']}`",
            f"- **Mô tả**: {packet['ragas_appendix']['description']}",
            ("- **Bản nháp hiện tại**: 0 drafts (chờ kích hoạt Task 7 sau phê duyệt live)."),
            "",
        ]
    )

    return "\n".join(lines)
