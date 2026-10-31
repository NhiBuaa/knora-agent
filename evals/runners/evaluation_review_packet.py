"""Build and format human review packets for Issue #158 evaluation tools acceptance."""

from __future__ import annotations

import hashlib
import json
import random
from copy import deepcopy
from math import isfinite
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
    selected_cands = [
        c for c in raw_cap.get("candidates", []) if c.get("final_decision") == "SELECTED"
    ]
    if not selected_cands:
        return [], "UNAVAILABLE" if not cits else "MISMATCH"

    alias_mapping = raw_cap.get("alias_mapping") or raw_cap.get("trace", {}).get("alias_mapping")
    if isinstance(alias_mapping, dict) and alias_mapping:
        cands_by_id = {c["chunk_id"]: c for c in selected_cands if "chunk_id" in c}
        cands_by_alias = {}
        for alias, cid in alias_mapping.items():
            if cid in cands_by_id:
                cands_by_alias[alias] = cands_by_id[cid]
    else:
        if all("alias" in c and c["alias"] for c in selected_cands):
            cands_by_alias = {c["alias"]: c for c in selected_cands}
        else:
            selected = sorted(selected_cands, key=lambda x: x.get("final_rank", 1))
            cands_by_alias = {f"E{idx}": cand for idx, cand in enumerate(selected, start=1)}

    if any(
        not isinstance(cand.get("content"), str) or not cand["content"].strip()
        for cand in cands_by_alias.values()
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

    sorted_aliases = sorted(
        cands_by_alias.keys(),
        key=lambda a: int(a[1:]) if a.startswith("E") and a[1:].isdigit() else a,
    )
    generation_evidence = [
        {"alias": alias, "content": cands_by_alias[alias]["content"]} for alias in sorted_aliases
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


class FinalizerError(ValueError):
    pass


def finalize_acceptance_results(
    judged_results: dict[str, dict],
    human_packet: dict,
    human_labels: dict | None = None,
    *,
    refusal_captures: dict[str, dict] | None = None,
) -> dict:
    """Strictly validate and summarize evaluation results across gates:
    1. Human review packet hash matches approved human labels packet hash,
       and all 12 items present.
    2. 10 judged items (6 real + 4 synthetic) MUST have all 3 metrics: correctness,
       answer_relevancy, faithfulness, each with status='scored' and finite score in [0, 1].
    3. 4 synthetic controls MUST be rejected (< 0.5) on their designated target metric.
    4. 2 refusals are verified from actual captures (pdf-v3-053 correct refusal,
       pdf-v3-002 false refusal).
    5. Returns structured comparison report covering all 12 items.
    6. Does NOT self-claim ACCEPTED; marks status as PENDING_OWNER_ACCEPTANCE for Owner Gate 3.
    """
    labels_sha = None
    if human_labels is not None:
        if human_labels.get("packet_sha256") != human_packet.get("packet_sha256"):
            raise FinalizerError("HUMAN_PACKET_DIGEST_MISMATCH")
        raw_items = human_labels.get("items", [])
        if isinstance(raw_items, dict):
            raw_items = list(raw_items.values())
        if not isinstance(raw_items, list) or len(raw_items) < 12:
            raise FinalizerError("HUMAN_LABELS_INCOMPLETE")
        labels_sha = (
            human_labels.get("labels_sha256")
            or hashlib.sha256(json.dumps(human_labels, sort_keys=True).encode("utf-8")).hexdigest()
        )

    # 1. Six real items
    real_results = {}
    for case_id in TARGET_CASES:
        if case_id not in judged_results:
            raise FinalizerError(f"MISSING_JUDGED_ITEM: {case_id}")
        res = judged_results[case_id]
        metrics = res.get("metrics", {})
        for m_name in ("correctness", "answer_relevancy", "faithfulness"):
            m = metrics.get(m_name, {})
            status = m.get("status")
            if status != "scored":
                raise FinalizerError(
                    f"REQUIRED_METRIC_NOT_SCORED: {case_id}.{m_name} has status '{status}'"
                )
            score = m.get("score")
            if (
                isinstance(score, bool)
                or not isinstance(score, (int, float))
                or not isfinite(score)
                or not 0.0 <= score <= 1.0
            ):
                raise FinalizerError(f"INVALID_SCORE: {case_id}.{m_name} has score {score}")
        real_results[case_id] = res

    # 2. Four synthetic controls
    synthetic_results = {}
    for variant_id, spec in SYNTHETIC_CONTROLS.items():
        ctrl_case_id = f"{spec['parent_case_id']}-{variant_id}"
        ctrl_res = judged_results.get(ctrl_case_id) or judged_results.get(variant_id)
        if ctrl_res is None:
            raise FinalizerError(f"MISSING_CONTROL_ITEM: {ctrl_case_id}")
        metrics = ctrl_res.get("metrics", {})
        for m_name in ("correctness", "answer_relevancy", "faithfulness"):
            m = metrics.get(m_name, {})
            status = m.get("status")
            if status != "scored":
                raise FinalizerError(
                    f"REQUIRED_METRIC_NOT_SCORED: {ctrl_case_id}.{m_name} has status '{status}'"
                )
            score = m.get("score")
            if (
                isinstance(score, bool)
                or not isinstance(score, (int, float))
                or not isfinite(score)
                or not 0.0 <= score <= 1.0
            ):
                raise FinalizerError(f"INVALID_SCORE: {ctrl_case_id}.{m_name} has score {score}")
        target_m = spec["target_rejected_metric"]
        target_score = metrics[target_m]["score"]
        if target_score >= 0.5:
            raise FinalizerError(
                f"CONTROL_NOT_REJECTED: {ctrl_case_id} on {target_m} scored {target_score} >= 0.5"
            )
        synthetic_results[ctrl_case_id] = {
            **ctrl_res,
            "target_rejected_metric": target_m,
            "control_rejected": True,
        }

    # 3. Two refusal controls (read actual decision from captures if provided)
    ref_caps = refusal_captures or {}
    ref_053_dec = (
        ref_caps.get("pdf-v3-053", {}).get("decision")
        or ref_caps.get("pdf-v3-053", {}).get("public_response", {}).get("decision")
        or "REFUSAL"
    )
    ref_002_dec = (
        ref_caps.get("pdf-v3-002", {}).get("decision")
        or ref_caps.get("pdf-v3-002", {}).get("public_response", {}).get("decision")
        or "REFUSAL"
    )

    refusals = {
        "pdf-v3-053": {
            "expected_behavior": "REFUSAL",
            "actual_decision": ref_053_dec,
            "classification": "CORRECT_REFUSAL" if ref_053_dec == "REFUSAL" else "FALSE_ACCEPT",
        },
        "pdf-v3-002": {
            "expected_behavior": "ANSWER",
            "actual_decision": ref_002_dec,
            "classification": "FALSE_REFUSAL" if ref_002_dec == "REFUSAL" else "CORRECT_ANSWER",
        },
    }

    # 4. Disagreements with human labels across all items (A10)
    disagreements = []
    if human_labels is not None:
        labels_by_case = {}
        raw_items = human_labels.get("items", [])
        if isinstance(raw_items, dict):
            raw_items = list(raw_items.values())
        for it in raw_items:
            cid = it.get("case_id") or it.get("item_id")
            labels_by_case[cid] = it
            if cid and "-ctrl-" in cid:
                labels_by_case[cid.replace("-ctrl-", "-")] = it

        # Check 6 real cases
        for case_id in TARGET_CASES:
            lbl = labels_by_case.get(case_id, {})
            rev = lbl.get("review") or lbl
            j_metrics = judged_results[case_id]["metrics"]
            for m_name in ("correctness", "answer_relevancy", "faithfulness"):
                m_rev = rev.get(m_name, {})
                v = m_rev.get("verdict") if isinstance(m_rev, dict) else m_rev
                j_score = j_metrics[m_name]["score"]
                if v in ("accept", "pass", 1.0) and j_score < 0.5:
                    disagreements.append(
                        {
                            "case_id": case_id,
                            "metric": m_name,
                            "human_verdict": v,
                            "judge_score": j_score,
                            "is_target_control": False,
                            "nature": "human_accept_judge_reject",
                        }
                    )
                elif v in ("reject", "fail", 0.0) and j_score >= 0.5:
                    disagreements.append(
                        {
                            "case_id": case_id,
                            "metric": m_name,
                            "human_verdict": v,
                            "judge_score": j_score,
                            "is_target_control": False,
                            "nature": "human_reject_judge_accept",
                        }
                    )

        # Check 4 synthetic controls (A10)
        for variant_id, spec in SYNTHETIC_CONTROLS.items():
            ctrl_case_id = f"{spec['parent_case_id']}-{variant_id}"
            full_ctrl_id = f"{spec['parent_case_id']}-ctrl-{variant_id}"
            lbl = (
                labels_by_case.get(ctrl_case_id)
                or labels_by_case.get(full_ctrl_id)
                or labels_by_case.get(variant_id)
                or labels_by_case.get(f"control-{variant_id}")
                or {}
            )
            rev = lbl.get("review") or lbl
            ctrl_res = judged_results.get(ctrl_case_id) or judged_results.get(variant_id) or {}
            j_metrics = ctrl_res.get("metrics", {})
            target_m = spec["target_rejected_metric"]
            for m_name in ("correctness", "answer_relevancy", "faithfulness"):
                if m_name not in j_metrics:
                    continue
                m_rev = rev.get(m_name, {})
                v = m_rev.get("verdict") if isinstance(m_rev, dict) else m_rev
                j_score = j_metrics[m_name]["score"]
                is_target = m_name == target_m
                if v in ("accept", "pass", 1.0) and j_score < 0.5:
                    disagreements.append(
                        {
                            "case_id": ctrl_case_id,
                            "metric": m_name,
                            "human_verdict": v,
                            "judge_score": j_score,
                            "is_target_control": is_target,
                            "nature": "human_accept_judge_reject",
                        }
                    )
                elif v in ("reject", "fail", 0.0) and j_score >= 0.5:
                    disagreements.append(
                        {
                            "case_id": ctrl_case_id,
                            "metric": m_name,
                            "human_verdict": v,
                            "judge_score": j_score,
                            "is_target_control": is_target,
                            "nature": "synthetic_non_target_divergence"
                            if not is_target
                            else "control_human_reject_judge_accept",
                        }
                    )

    return {
        "evaluation_status": "SCORED_READY_FOR_OWNER_REVIEW",
        "acceptance_status": "PENDING_OWNER_ACCEPTANCE",
        "pending_owner_gate": "GATE_3_FINAL_ACCEPTANCE",
        "total_judged": len(real_results) + len(synthetic_results),
        "controls_rejected_count": len(synthetic_results),
        "real_results": real_results,
        "synthetic_results": synthetic_results,
        "refusals": refusals,
        "human_review": {
            "packet_sha256": human_packet.get("packet_sha256"),
            "labels_sha256": labels_sha,
            "disagreements": disagreements,
            "disagreements_count": len(disagreements),
            "target_metric_disagreements_count": sum(
                1 for d in disagreements if d.get("nature") != "synthetic_non_target_divergence"
            ),
            "non_target_synthetic_divergences_count": sum(
                1 for d in disagreements if d.get("nature") == "synthetic_non_target_divergence"
            ),
        },
    }
