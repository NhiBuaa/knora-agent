import asyncio
import hashlib
import json
import os
from argparse import Namespace

import httpx
import pytest
from evals.runners.ollama_grounding import CASES, collect, evaluate_case

from knora.providers.generation import GenerationResult
from knora.providers.ollama.generation import OllamaGenerationProvider


class Provider:
    def __init__(self, result):
        self.result = result

    async def generate(self, *, question, evidence):
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


@pytest.mark.parametrize(
    ("result", "expected"),
    [
        (
            GenerationResult("ANSWER", "Nhiệt độ là 18 độ C. [[E2]]", ("E2",), None),
            (True, True, True, True),
        ),
        (
            GenerationResult("ANSWER", "Nhiệt độ là 18 độ C. [[E1]]", ("E1",), None),
            (True, True, True, False),
        ),
        (
            GenerationResult("ANSWER", "Nhiệt độ là 31 độ C. [[E2]]", ("E2",), None),
            (True, True, False, True),
        ),
        (
            GenerationResult("REFUSAL", None, (), "INSUFFICIENT_EVIDENCE"),
            (True, False, False, False),
        ),
        (
            GenerationResult("ANSWER", "PRIVATE [[E9]]", ("E9",), None),
            (False, False, False, False),
        ),
    ],
)
def test_checks_decision_facts_and_alias_independently(result, expected):
    row = asyncio.run(evaluate_case(CASES[3], Provider(result)))
    assert (
        tuple(
            row[key]
            for key in (
                "structural_valid",
                "decision_correct",
                "literal_patterns_match",
                "aliases_correct",
            )
        )
        == expected
    )
    assert row["literal_checks_passed"] is all(expected)
    assert "Nhiệt độ" not in json.dumps(row)
    assert "PRIVATE" not in json.dumps(row)


def test_provider_failure_is_sanitized_and_never_counted_as_refusal():
    row = asyncio.run(evaluate_case(CASES[0], Provider(RuntimeError("PRIVATE SECRET"))))
    assert row["error"] == "PROVIDER_ERROR"
    assert row["literal_checks_passed"] is False
    assert row["decision_correct"] is False
    assert "PRIVATE" not in json.dumps(row)


def test_development_report_counts_all_observations_and_exports_no_inputs():
    report = asyncio.run(
        collect(Provider(GenerationResult("REFUSAL", None, (), "INSUFFICIENT_EVIDENCE")))
    )
    assert report["literal_passed_count"] == 4
    assert report["observation_count"] == 11
    assert report["held_out"] is False
    assert report["conversation_gate"] == "NOT_EVALUATED"
    assert report["semantic_review"] == "NOT_EVALUATED"
    serialized = json.dumps(report, ensure_ascii=False)
    for case in CASES:
        assert case.question not in serialized
        for item in case.evidence:
            assert item.content not in serialized


def test_deadline_expiry_stops_measurement_without_fabricating_unrun_cases():
    from knora.domain.errors import KnoraError

    class ExpiringProvider:
        deadline_expired = False

        async def generate(self, **kwargs):
            self.deadline_expired = True
            raise KnoraError("PROVIDER_REQUEST_FAILED")

    report = asyncio.run(collect(ExpiringProvider(), stop_on_deadline=True))
    assert report["observation_count"] == 1
    assert report["case_count"] == 11
    assert report["stopped_after_deadline"] is True
    assert report["unmeasured_case_count"] == 10
    assert report["cases"][0]["error"] == "PROVIDER_ERROR"


def test_live_runner_records_actual_request_bound_and_cpu_runtime(monkeypatch, tmp_path):
    from evals.runners.ollama_grounding import run_live

    digest = "sha256:" + "a" * 64
    request_prompts = []

    def endpoint(request):
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "qwen3:8b", "digest": digest}]})
        if request.url.path == "/api/ps":
            return httpx.Response(
                200,
                json={
                    "models": [
                        {
                            "name": "qwen3:8b",
                            "context_length": 8192,
                            "size": 6000000000,
                            "size_vram": 0,
                        }
                    ]
                },
            )
        request_prompts.append(json.loads(request.content)["messages"][0]["content"])
        return httpx.Response(
            200,
            json={
                "message": {
                    "content": json.dumps(
                        {
                            "decision": "REFUSAL",
                            "answer": None,
                            "cited_evidence_ids": [],
                            "refusal_reason": "INSUFFICIENT_EVIDENCE",
                        }
                    )
                },
                "done": True,
            },
        )

    original_client = httpx.AsyncClient

    def client(**kwargs):
        return original_client(transport=httpx.MockTransport(endpoint), **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", client)
    report = asyncio.run(
        run_live(
            Namespace(
                base_url="http://ollama.test",
                model="qwen3:8b",
                digest=digest,
                repetitions=1,
                private_output=tmp_path / "responses.private.json",
            )
        )
    )
    assert report["request_options"] == {"num_ctx": 8192, "num_predict": 1024, "temperature": 0}
    assert report["generation_request_count"] == 11
    assert (
        report["system_prompt_sha256"]
        == hashlib.sha256(request_prompts[0].encode("utf-8")).hexdigest()
    )
    assert report["inference_runtime"] == {
        "context_tokens": 8192,
        "model_size_bytes": 6000000000,
        "size_vram_bytes": 0,
    }
    private_content = (tmp_path / "responses.private.json").read_bytes()
    assert report["private_responses_sha256"] == hashlib.sha256(private_content).hexdigest()
    private_rows = json.loads(private_content)["responses"]
    assert len(private_rows) == 11
    assert private_rows[0]["case_id"] == "absent_fee"
    assert private_rows[0]["repetition"] == 1
    assert private_rows[0]["result"] == {
        "decision": "REFUSAL",
        "answer": None,
        "cited_evidence_ids": [],
        "refusal_reason": "INSUFFICIENT_EVIDENCE",
    }


def test_literal_tokens_never_claim_semantic_correctness():
    result = GenerationResult(
        "ANSWER", "Được dùng dung môi; không cần tránh chất này. [[E1]]", ("E1",), None
    )
    row = asyncio.run(evaluate_case(CASES[2], Provider(result)))
    assert row["literal_patterns_match"] is True
    assert row["semantic_review"] == "NOT_EVALUATED"
    assert "facts_correct" not in row


def test_literal_prohibition_check_rejects_known_not_required_answer():
    result = GenerationResult(
        "ANSWER",
        "Không. Phiếu Atlas không bắt buộc ghi số điện thoại cá nhân. [[E1]]",
        ("E1",),
        None,
    )
    row = asyncio.run(evaluate_case(CASES[6], Provider(result)))
    assert row["literal_patterns_match"] is False
    assert row["semantic_review"] == "NOT_EVALUATED"


def test_private_capture_preserves_exact_answer_while_public_row_exports_only_hash():
    captures = []
    answer = "Nhiệt độ là 18 độ C. [[E2]]"
    result = GenerationResult("ANSWER", answer, ("E2",), None)
    row = asyncio.run(evaluate_case(CASES[3], Provider(result), captured_responses=captures))
    expected_hash = hashlib.sha256(answer.encode("utf-8")).hexdigest()
    assert row["answer_sha256"] == expected_hash
    assert captures == [
        {
            "case_id": "support_after_distractor",
            "answer_sha256": expected_hash,
            "result": {
                "decision": "ANSWER",
                "answer": answer,
                "cited_evidence_ids": ["E2"],
                "refusal_reason": None,
            },
        }
    ]
    assert answer not in json.dumps(row, ensure_ascii=False)


@pytest.mark.skipif(
    os.environ.get("KNORA_RUN_LIVE_OLLAMA_GROUNDING") != "1",
    reason="requires the explicitly enabled pinned real Ollama model",
)
def test_real_ollama_synthetic_grounding():
    async def run():
        provider = OllamaGenerationProvider(
            base_url=os.environ.get("KNORA_OLLAMA_BASE_URL", "http://127.0.0.1:11435"),
            expected_digest=os.environ["KNORA_EXPECTED_GENERATION_MODEL_DIGEST"],
        )
        try:
            return await collect(provider)
        finally:
            await provider.aclose()

    report = asyncio.run(run())
    check_keys = ("case_id", "decision_correct", "literal_patterns_match", "aliases_correct")
    failures = [
        {key: row[key] for key in check_keys}
        for row in report["cases"]
        if not row["literal_checks_passed"]
    ]
    assert not failures, failures
