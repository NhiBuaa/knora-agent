"""Replay saved case001 through the existing executor; no network, DB or promotion.

Run from the repository root with its Python environment. JSON is printed only;
redirect it to a new evidence file when recording a revalidation.
"""

import asyncio
import hashlib
import json
import subprocess
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace as NS

import httpx
from evals.datasets.pdf_retrieval_v3_v1 import load_dataset, validate_approval
from evals.runners.pdf_retrieval_v3 import PdfHttpExecutor
from evals.runners.pdf_source_binding import (
    chunk_record,
    digest,
    propose_bindings,
    validate_binding_review,
)

ROOT = Path.cwd()
PACKET = ROOT / "evals/reports/pdf_retrieval_v3_v1/baseline-b-layout-v2"
BINDING = PACKET.parent / "binding-layout-v2-runtime"


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


async def main():
    inputs = [PACKET / entry["path"] for entry in read(PACKET / "archive-manifest.json")["files"]]
    inputs += [PACKET / "report.json", BINDING / "binding-review.json"]
    before = {path.relative_to(ROOT).as_posix(): sha(path) for path in inputs}
    for entry in read(PACKET / "archive-manifest.json")["files"]:
        assert sha(PACKET / entry["path"]) == entry["sha256"]
    manifest = ROOT / "evals/datasets/pdf_retrieval_v3_v1.manifest.json"
    gold = manifest.with_name("pdf_retrieval_v3_v1.jsonl")
    dataset = load_dataset(manifest, gold)
    validate_approval(dataset, read(manifest.with_name("pdf_retrieval_v3_v1.approval.json")))
    frozen = [manifest, gold, *(source.path for source in dataset.sources)]
    for path in frozen:
        blob = subprocess.check_output(
            ["git", "show", f"2ce2fe6:{path.relative_to(ROOT).as_posix()}"], cwd=ROOT
        )
        assert path.read_bytes() == blob
    saved = read(PACKET / "captures/case-pdf-v3-001-attempt-1.json")
    raw_trace = read(PACKET / "operational-evidence/trace-pdf-v3-001.json")
    post = read(PACKET / "operational-evidence/persistence-after-stop.json")
    chunks = read(BINDING / "chunks.json")["chunks"]
    assert len(chunks) == len(post["chunks"]) == 47
    actual = {chunk["chunk_id"]: chunk for chunk in post["chunks"]}
    for chunk in chunks:
        assert all(
            actual[chunk["chunk_id"]][k] == v
            for k, v in chunk.items()
            if k in actual[chunk["chunk_id"]]
        )
    snapshot = [NS(**(chunk | actual[chunk["chunk_id"]])) for chunk in chunks]
    proposal = read(BINDING / "proposals.json")
    assert propose_bindings(dataset, snapshot) == proposal
    bindings = validate_binding_review(proposal, read(BINDING / "binding-review.json"))
    assert sum(bool(v) for v in bindings.values()) == 61
    assert sum(not v for v in bindings.values()) == 25
    assert saved["corpus_sha256"] == dataset.corpus_sha256
    assert saved["dataset_sha256"] == dataset.dataset_sha256
    assert saved["derivation_sha256"] == proposal["derivation_sha256"]
    assert saved["trace_id"] == raw_trace["id"]
    assert saved["workspace_id"] == raw_trace["workspace_id"]
    assert saved["turn_id"] == raw_trace["conversation_turn_id"]
    assert saved["response_sha256"] == digest(saved["public_response"])
    assert saved["failure_code"] == "CASE_FAILED_NO_RETRY"
    assert raw_trace["generation_status"] == "completed"
    assert raw_trace["validation_outcome"] == "valid"
    candidates = tuple(
        NS(
            **(
                chunk_record(next(c for c in snapshot if c.chunk_id == d["chunk_id"]))
                | actual[d["chunk_id"]]
                | d
            )
        )
        for d in raw_trace["candidate_decisions"]
    )
    trace = NS(
        **(
            raw_trace
            | {
                "trace_id": raw_trace["id"],
                "candidates": candidates,
                "retrieval_latency_ms": raw_trace["provider_metadata"]["retrieval"]["latency_ms"],
            }
        )
    )
    current_case = next(c for c in dataset.cases if c.id == saved["case_id"])
    assert current_case.question == raw_trace["question"]
    reader = NS(read_trace=lambda **_: trace, read_pdf_chunks=lambda **_: snapshot)

    async def replay(payload):
        # Synthetic HTTP envelope only; the saved public response is copied unchanged.
        turn = {
            "id": saved["turn_id"],
            "conversation_id": saved["conversation_id"],
            "question": current_case.question,
            "status": "answered",
            "result": payload,
        }
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda _: httpx.Response(200, json=turn)),
            base_url="http://offline.invalid",
        ) as client:
            return await PdfHttpExecutor(
                client=client,
                headers={},
                reader=reader,
                workspace_id=saved["workspace_id"],
                run_id=saved["run_id"],
                embedding_configuration_id=raw_trace["embedding_configuration_id"],
                poll_interval=0,
            ).execute(current_case, conversation_id=saved["conversation_id"])

    result = await replay(saved["public_response"])
    assert result["failure_code"] is None, result["failure_code"]
    for key in (
        "response_sha256",
        "run_id",
        "case_id",
        "attempt_id",
        "workspace_id",
        "conversation_id",
        "turn_id",
        "trace_id",
    ):
        assert result[key] == saved[key]
    rejected = {}
    for key in (
        "excerpt",
        "source_key",
        "start_line",
        "document_version_id",
        "content_checksum",
        "page_start",
        "page_end",
        "start_offset",
        "end_offset",
    ):
        tampered = deepcopy(saved["public_response"])
        value = tampered["citations"][0][key]
        tampered["citations"][0][key] = value + 1 if type(value) is int else value + " tampered"
        failed = await replay(tampered)
        assert failed["failure_code"], key
        rejected[key] = failed["failure_code"]
    counters = read(PACKET / "captures/counters.json")
    assert counters["stop_reason"] == "CASE_FAILED_NO_RETRY"
    assert counters["query_embedding_attempts"] == counters["baseline_b_generation_attempts"] == 1
    assert read(PACKET / "report.json")["denominators"]["not_run"] == 59
    assert before == {path.relative_to(ROOT).as_posix(): sha(path) for path in inputs}
    print(
        json.dumps(
            {
                "mode": "offline_saved_capture_revalidation_only",
                "validation": "accepted",
                "collection_promotion": "not_authorized",
                "semantic_review": "pending",
                "saved_identity": {
                    k: saved[k]
                    for k in (
                        "run_id",
                        "case_id",
                        "attempt_id",
                        "workspace_id",
                        "conversation_id",
                        "turn_id",
                        "trace_id",
                        "response_sha256",
                        "corpus_sha256",
                        "dataset_sha256",
                        "derivation_sha256",
                    )
                },
                "proposal_sha256": proposal["proposal_sha256"],
                "binding_review_sha256": digest(read(BINDING / "binding-review.json")),
                "code_text_lf_sha256": {
                    path.relative_to(ROOT).as_posix(): hashlib.sha256(
                        path.read_text(encoding="utf-8").encode()
                    ).hexdigest()
                    for path in (
                        ROOT / "evals/runners/milestone_3.py",
                        ROOT / "backend/src/knora/answering/excerpt.py",
                        Path(__file__),
                    )
                },
                "frozen_files_unchanged": len(frozen),
                "binding_mapped": 61,
                "binding_missing": 25,
                "snapshot_chunks_verified": 47,
                "negative_checks": rejected,
                "unchanged_input_sha256": before,
                "original_failure_code": saved["failure_code"],
                "original_observation_failure_code": saved["observation_failure_code"],
                "original_denominators": read(PACKET / "report.json")["denominators"],
                "model_calls": 0,
                "database_calls": 0,
                "external_http_calls": 0,
                "synthetic_transport": (
                    "httpx.MockTransport; turn envelope reconstructed from saved IDs"
                ),
                "live_persistence_rechecked": False,
                "paid_budget_usd": 0,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
