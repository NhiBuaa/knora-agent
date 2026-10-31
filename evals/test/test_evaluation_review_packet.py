from pathlib import Path

import pytest
from evals.datasets.pdf_retrieval_v3_v1 import load_dataset
from evals.runners.evaluation_review_packet import (
    SYNTHETIC_CONTROLS,
    TARGET_CASES,
    FinalizerError,
    build_acceptance_review_packet,
    finalize_acceptance_results,
    format_review_packet_markdown,
    project_capture_generation_evidence,
)

CAPTURES_DIR = (
    Path(__file__).resolve().parents[1]
    / "reports"
    / "pdf_retrieval_v3_v1"
    / "baseline-b-layout-v2-continuation"
    / "captures"
)
MANIFEST_PATH = (
    Path(__file__).resolve().parents[1] / "datasets" / "pdf_retrieval_v3_v1.manifest.json"
)
DATASET_PATH = Path(__file__).resolve().parents[1] / "datasets" / "pdf_retrieval_v3_v1.jsonl"


def test_build_acceptance_review_packet_produces_deterministic_blind_packet() -> None:
    dataset = load_dataset(MANIFEST_PATH, DATASET_PATH)
    packet1 = build_acceptance_review_packet(CAPTURES_DIR, dataset, shuffle_seed=158)
    packet2 = build_acceptance_review_packet(CAPTURES_DIR, dataset, shuffle_seed=158)

    # Determinism
    assert packet1["packet_sha256"] == packet2["packet_sha256"]
    assert packet1["items_count"] == 12

    # Composition
    kinds = [it["item_kind"] for it in packet1["items"]]
    assert kinds.count("real_answer") == 6
    assert kinds.count("synthetic_control") == 4
    assert kinds.count("refusal_control") == 2

    # Verify Blind review: NO judge scores, rationales or predefined verdicts
    for it in packet1["items"]:
        assert "score" not in it
        assert "rationale" not in it
        assert "metrics" not in it
        review = it["review"]
        assert review["review_status"] == "pending_review"
        assert review["reviewer"] == ""
        assert review["correctness"]["verdict"] == "pending"
        assert review["answer_relevancy"]["verdict"] == "pending"
        assert review["faithfulness"]["verdict"] == "pending"

    # Verify Ragas appendix is not_run
    assert packet1["ragas_appendix"]["status"] == "not_run"
    assert packet1["ragas_appendix"]["drafts"] == []

    # Format markdown
    md = format_review_packet_markdown(packet1)
    assert "# Issue #158 Evaluation Tools Acceptance — Human Review Packet" in md
    assert "REV-01" in md
    assert "REV-12" in md
    assert "pdf-v3-004" in md
    assert "wrong-fact" in md


def test_build_acceptance_review_packet_preserves_all_selected_chunks_for_case_045() -> None:
    dataset = load_dataset(MANIFEST_PATH, DATASET_PATH)
    packet = build_acceptance_review_packet(CAPTURES_DIR, dataset, shuffle_seed=158)
    item_045 = next(it for it in packet["items"] if it["case_id"] == "pdf-v3-045")

    # Case 045 has 3 SELECTED candidates; citation is E3, but all 3 must be preserved
    assert len(item_045["generation_evidence"]) == 3
    aliases = [ev["alias"] for ev in item_045["generation_evidence"]]
    assert aliases == ["E1", "E2", "E3"]
    # Chunk 3 has the Apache License text
    assert "Apache License 2.0" in item_045["generation_evidence"][2]["content"]
    assert item_045["attempt"] == 1
    assert item_045["attempt_id"] == "s1-runtime-binding-20261015-01:pdf-v3-045:1"
    assert item_045["run_id"] == "s1-runtime-binding-20261015-01"


def test_project_capture_generation_evidence_negative_checks() -> None:
    # 1. Missing candidate content yields unavailable
    cap_missing_content = {
        "candidates": [
            {"chunk_id": "c1", "final_rank": 1, "final_decision": "SELECTED", "content": None}
        ],
        "public_response": {"citations": []},
    }
    evidence, verdict = project_capture_generation_evidence(cap_missing_content)
    assert evidence == []
    assert verdict == "UNAVAILABLE"

    # 2. Citation checksum mismatch yields MISMATCH and empty evidence
    cap_checksum_mismatch = {
        "candidates": [
            {
                "chunk_id": "c1",
                "final_rank": 1,
                "final_decision": "SELECTED",
                "content": "Valid content.",
            }
        ],
        "public_response": {
            "citations": [
                {
                    "evidence_id": "E1",
                    "content_checksum": "wrong-checksum",
                }
            ]
        },
    }
    evidence, verdict = project_capture_generation_evidence(cap_checksum_mismatch)
    assert evidence == []
    assert verdict == "MISMATCH"

    # 3. Citation evidence_id not in selected aliases yields MISMATCH
    cap_bad_alias = {
        "candidates": [
            {
                "chunk_id": "c1",
                "final_rank": 1,
                "final_decision": "SELECTED",
                "content": "Valid content.",
            }
        ],
        "public_response": {
            "citations": [
                {
                    "evidence_id": "E99",
                    "content_checksum": "any",
                }
            ]
        },
    }
    evidence, verdict = project_capture_generation_evidence(cap_bad_alias)
    assert evidence == []
    assert verdict == "MISMATCH"


def _make_mock_judged_results():
    results = {}
    for case_id in TARGET_CASES:
        results[case_id] = {
            "case_id": case_id,
            "metrics": {
                "correctness": {"status": "scored", "score": 0.95, "rationale": "Accurate."},
                "answer_relevancy": {"status": "scored", "score": 0.90, "rationale": "Relevant."},
                "faithfulness": {"status": "scored", "score": 0.98, "rationale": "Faithful."},
            },
        }
    for variant_id, spec in SYNTHETIC_CONTROLS.items():
        ctrl_case_id = f"{spec['parent_case_id']}-{variant_id}"
        target_m = spec["target_rejected_metric"]
        metrics = {
            "correctness": {"status": "scored", "score": 0.90, "rationale": "ok"},
            "answer_relevancy": {"status": "scored", "score": 0.90, "rationale": "ok"},
            "faithfulness": {"status": "scored", "score": 0.90, "rationale": "ok"},
        }
        metrics[target_m] = {"status": "scored", "score": 0.15, "rationale": "Rejected as planned."}
        results[ctrl_case_id] = {
            "case_id": ctrl_case_id,
            "metrics": metrics,
        }
    return results


def test_finalize_acceptance_results_success():
    judged = _make_mock_judged_results()
    packet = {"packet_sha256": "digest-123", "items": []}
    res = finalize_acceptance_results(judged, packet)
    assert res["acceptance_status"] == "PENDING_OWNER_ACCEPTANCE"
    assert res["evaluation_status"] == "SCORED_READY_FOR_OWNER_REVIEW"
    assert res["pending_owner_gate"] == "GATE_3_FINAL_ACCEPTANCE"
    assert res["total_judged"] == 10
    assert res["controls_rejected_count"] == 4
    assert res["refusals"]["pdf-v3-053"]["classification"] == "CORRECT_REFUSAL"
    assert res["refusals"]["pdf-v3-002"]["classification"] == "FALSE_REFUSAL"


def test_finalize_acceptance_results_rejects_missing_or_unscored_metric():
    judged = _make_mock_judged_results()
    packet = {"packet_sha256": "digest-123", "items": []}

    # Error metric
    judged["pdf-v3-004"]["metrics"]["faithfulness"] = {
        "status": "error",
        "score": None,
        "error": "Timeout",
    }
    with pytest.raises(
        FinalizerError,
        match="REQUIRED_METRIC_NOT_SCORED: pdf-v3-004.faithfulness has status 'error'",
    ):
        finalize_acceptance_results(judged, packet)

    # not_applicable metric
    judged["pdf-v3-004"]["metrics"]["faithfulness"] = {
        "status": "not_applicable",
        "score": None,
    }
    with pytest.raises(
        FinalizerError,
        match="REQUIRED_METRIC_NOT_SCORED: pdf-v3-004.faithfulness has status 'not_applicable'",
    ):
        finalize_acceptance_results(judged, packet)


def test_finalize_acceptance_results_rejects_unrejected_control():
    judged = _make_mock_judged_results()
    packet = {"packet_sha256": "digest-123", "items": []}

    # Control scored >= 0.5 on its target rejected metric
    ctrl_id = "pdf-v3-004-wrong-fact"
    judged[ctrl_id]["metrics"]["correctness"]["score"] = 0.75
    with pytest.raises(FinalizerError, match="CONTROL_NOT_REJECTED"):
        finalize_acceptance_results(judged, packet)


def test_finalize_acceptance_results_validates_human_packet_digest_and_tracks_disagreements():
    judged = _make_mock_judged_results()
    packet = {"packet_sha256": "digest-correct", "items": []}

    # Mismatched digest
    bad_labels = {"packet_sha256": "digest-wrong", "items": []}
    with pytest.raises(FinalizerError, match="HUMAN_PACKET_DIGEST_MISMATCH"):
        finalize_acceptance_results(judged, packet, bad_labels)

    # Valid labels with disagreement (all 12 items provided)
    good_items = [
        {
            "case_id": "pdf-v3-004",
            "review": {
                "correctness": {"verdict": "reject"},  # Judge has 0.95 -> disagreement!
                "answer_relevancy": {"verdict": "accept"},
                "faithfulness": {"verdict": "accept"},
            },
        }
    ]
    for i in range(1, 12):
        good_items.append({"case_id": f"dummy-{i}", "review": "accept"})

    good_labels = {
        "packet_sha256": "digest-correct",
        "items": good_items,
    }
    res = finalize_acceptance_results(judged, packet, good_labels)
    assert res["acceptance_status"] == "PENDING_OWNER_ACCEPTANCE"
    assert res["evaluation_status"] == "SCORED_READY_FOR_OWNER_REVIEW"
    disagreements = res["human_review"]["disagreements"]
    assert len(disagreements) == 1
    assert disagreements[0]["case_id"] == "pdf-v3-004"
    assert disagreements[0]["nature"] == "human_reject_judge_accept"
