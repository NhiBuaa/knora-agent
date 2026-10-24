from pathlib import Path

from evals.datasets.pdf_retrieval_v3_v1 import load_dataset
from evals.runners.evaluation_review_packet import (
    build_acceptance_review_packet,
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
