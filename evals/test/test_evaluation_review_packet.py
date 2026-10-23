from pathlib import Path

from evals.datasets.pdf_retrieval_v3_v1 import load_dataset
from evals.runners.evaluation_review_packet import (
    build_acceptance_review_packet,
    format_review_packet_markdown,
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
