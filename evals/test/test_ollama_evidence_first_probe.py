import asyncio
import importlib
import json

import httpx
import pytest

from knora.answering.generation_validation import validate_generation
from knora.domain.errors import KnoraError
from knora.providers.generation import GenerationEvidence


def probe_module():
    try:
        return importlib.import_module("evals.runners.ollama_evidence_first_probe")
    except ModuleNotFoundError:
        pytest.fail("evidence-first probe is missing")


def supported_payload():
    return {
        "decision": "ANSWER",
        "facts": [],
        "rules": [{"evidence_id": "E2", "quote": "Không ghi số điện thoại trên phiếu."}],
        "exceptions": [
            {"evidence_id": "E2", "quote": "Riêng bản nội bộ được ghi khi quản lý chấp thuận."}
        ],
        "refusal_reason": None,
    }


EVIDENCE = (
    GenerationEvidence("E1", "Tên biểu mẫu: Delta."),
    GenerationEvidence(
        "E2",
        "Không ghi số điện thoại trên phiếu. Riêng bản nội bộ được ghi khi quản lý chấp thuận.",
    ),
)


def test_rendering_preserves_source_prohibition_and_exception_with_one_marker():
    result = probe_module().render_result(supported_payload(), EVIDENCE)
    assert result.answer == (
        "Không ghi số điện thoại trên phiếu. "
        "Riêng bản nội bộ được ghi khi quản lý chấp thuận. [[E2]]"
    )
    assert result.cited_evidence_ids == ("E2",)
    validate_generation(result, available_evidence_ids=("E1", "E2"))


@pytest.mark.parametrize("fault", ["unknown_alias", "wrong_source", "invented_quote"])
def test_source_validation_rejects_quote_faults_instead_of_repairing(fault):
    payload = supported_payload()
    if fault == "unknown_alias":
        payload["rules"][0]["evidence_id"] = "E9"
    elif fault == "wrong_source":
        payload["rules"][0]["evidence_id"] = "E1"
    else:
        payload["rules"][0]["quote"] = "Không bắt buộc ghi số điện thoại."
    with pytest.raises(KnoraError) as error:
        probe_module().render_result(payload, EVIDENCE)
    assert error.value.code == "GENERATION_OUTPUT_INVALID"


def test_refusal_cannot_contain_any_extracted_fact():
    payload = supported_payload()
    payload.update(decision="REFUSAL", refusal_reason="INSUFFICIENT_EVIDENCE")
    with pytest.raises(KnoraError):
        probe_module().render_result(payload, EVIDENCE)
    payload.update(rules=[], exceptions=[])
    result = probe_module().render_result(payload, EVIDENCE)
    assert result.answer is None
    assert result.cited_evidence_ids == ()
    validate_generation(result, available_evidence_ids=("E1", "E2"))


def test_rendering_orders_markers_by_claims_and_preserves_facts_with_qualifications():
    payload = supported_payload()
    payload["facts"] = [
        {"evidence_id": "E1", "quote": "Tên biểu mẫu: Delta.", "text": "Biểu mẫu tên Delta."}
    ]
    result = probe_module().render_result(payload, EVIDENCE)
    assert result.answer == (
        "Biểu mẫu tên Delta. [[E1]]\n\n"
        "Không ghi số điện thoại trên phiếu. "
        "Riêng bản nội bộ được ghi khi quản lý chấp thuận. [[E2]]"
    )
    assert result.cited_evidence_ids == ("E1", "E2")


@pytest.mark.parametrize(
    "fault", ["extra_field", "missing_field", "bad_list", "empty_answer", "marker_in_fact"]
)
def test_malformed_extraction_is_a_failure_not_a_refusal(fault):
    payload = supported_payload()
    if fault == "extra_field":
        payload["answer"] = "Invented"
    elif fault == "missing_field":
        del payload["exceptions"]
    elif fault == "bad_list":
        payload["facts"] = None
    elif fault == "empty_answer":
        payload.update(rules=[], exceptions=[])
    else:
        payload["facts"] = [
            {"evidence_id": "E1", "quote": "Tên biểu mẫu: Delta.", "text": "Delta [[E9]]"}
        ]
    with pytest.raises(KnoraError) as error:
        probe_module().render_result(payload, EVIDENCE)
    assert error.value.code == "GENERATION_OUTPUT_INVALID"


def test_real_adapter_roundtrip_uses_one_chat_call_and_captures_no_thinking():
    module = probe_module()
    digest = "sha256:" + "b" * 64
    calls = []

    async def endpoint(request):
        calls.append(request.url.path)
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "qwen3:8b", "digest": digest}]})
        body = json.loads(request.content)
        assert body["format"]["properties"]["rules"]["type"] == "array"
        assert body["think"] is False
        assert body["options"]["num_predict"] <= 2048
        assert int(request.headers["content-length"]) == len(request.content)
        return httpx.Response(
            200,
            json={
                "model": "qwen3:8b",
                "done_reason": "stop",
                "eval_count": 120,
                "message": {
                    "thinking": "PRIVATE_REASONING_SENTINEL",
                    "content": json.dumps(supported_payload()),
                },
            },
        )

    async def scenario():
        transport = module.EvidenceFirstProbeTransport(inner=httpx.MockTransport(endpoint))
        async with httpx.AsyncClient(transport=transport, trust_env=False) as client:
            provider = module.EvidenceFirstProbeProvider(
                base_url="http://127.0.0.1:11435", expected_digest=digest, client=client
            )
            result = await provider.generate(question="Có bắt buộc ghi không?", evidence=EVIDENCE)
        assert result.answer == (
            "Không ghi số điện thoại trên phiếu. "
            "Riêng bản nội bộ được ghi khi quản lý chấp thuận. [[E2]]"
        )
        assert result.prompt_version == "ollama-evidence-first-probe-v1"
        assert result.usage == {"completion_tokens": 120}
        assert "PRIVATE_REASONING_SENTINEL" not in repr(result)
        serialized = json.dumps(transport.observations)
        assert "PRIVATE_REASONING_SENTINEL" not in serialized
        assert "Không ghi" not in serialized
        assert calls == ["/api/tags", "/api/chat"]

    asyncio.run(scenario())
