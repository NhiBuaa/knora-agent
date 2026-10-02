import asyncio
import hashlib
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


def test_gpt_oss_probe_uses_low_reasoning_and_preserves_extraction_contract():
    module = probe_module()
    digest = "sha256:" + "b" * 64

    async def endpoint(request):
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "gpt-oss:20b", "digest": digest}]})
        payload = json.loads(request.content)
        assert payload["think"] == "low"
        assert payload["options"] == {
            "num_ctx": 4096,
            "num_predict": 2048,
            "temperature": 0,
            "seed": 105,
        }
        assert payload["format"] == module.EXTRACTION_SCHEMA
        assert payload["messages"][0]["content"] == module.SYSTEM_PROMPT
        return httpx.Response(
            200,
            json={
                "model": "gpt-oss:20b",
                "done": True,
                "done_reason": "stop",
                "message": {
                    "content": json.dumps(supported_payload()),
                    "thinking": "PRIVATE_GPT_REASONING_CANARY",
                },
            },
        )

    async def scenario():
        transport = module.EvidenceFirstProbeTransport(
            inner=httpx.MockTransport(endpoint),
            sampling_profile="gpt-oss-low-v1",
            seed=105,
            context_tokens=4096,
        )
        async with httpx.AsyncClient(transport=transport, trust_env=False) as client:
            provider = module.EvidenceFirstProbeProvider(
                base_url="http://127.0.0.1:11435",
                model="gpt-oss:20b",
                expected_digest=digest,
                client=client,
            )
            result = await provider.generate(question="Có bắt buộc ghi không?", evidence=EVIDENCE)
        assert result.cited_evidence_ids == ("E2",)
        assert "chấp thuận" in result.answer
        assert transport.observations[0]["think"] == "low"
        assert "PRIVATE_GPT_REASONING_CANARY" not in repr(result) + json.dumps(
            transport.observations
        )

    asyncio.run(scenario())


@pytest.mark.parametrize("profile", ["gpt-oss-extraction-v2", "gpt-oss-extraction-v3"])
def test_gpt_extraction_sends_schema_and_examples_without_changing_output_contract(profile):
    module = probe_module()
    requests = []
    digest = "sha256:" + "b" * 64

    async def endpoint(request):
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "gpt-oss:20b", "digest": digest}]})
        payload = json.loads(request.content)
        requests.append(payload)
        prompt = payload["messages"][0]["content"]
        assert json.dumps(module.EXTRACTION_SCHEMA, sort_keys=True) in prompt
        assert '"decision":"REFUSAL"' in prompt
        assert '"decision":"ANSWER"' in prompt
        assert payload["format"] == module.EXTRACTION_SCHEMA
        assert payload["think"] == "low"
        if profile.endswith("v3"):
            assert "A prohibition is not optionality" in prompt
            assert "different property or unit" in prompt
            assert "every condition and required approval" in prompt
            assert '"quote":"EXACT_RULE_QUOTE"' in prompt
        return httpx.Response(
            200,
            json={
                "model": "gpt-oss:20b",
                "done_reason": "stop",
                "message": {
                    "content": json.dumps(supported_payload()),
                    "thinking": "PRIVATE_CANARY",
                },
            },
        )

    async def scenario():
        transport = module.EvidenceFirstProbeTransport(
            inner=httpx.MockTransport(endpoint), sampling_profile=profile
        )
        async with httpx.AsyncClient(transport=transport, trust_env=False) as client:
            provider = module.EvidenceFirstProbeProvider(
                base_url="http://127.0.0.1:11435",
                model="gpt-oss:20b",
                expected_digest=digest,
                client=client,
                sampling_profile=profile,
            )
            result = await provider.generate(question="Có được ghi không?", evidence=EVIDENCE)
        assert result.answer == (
            "Không ghi số điện thoại trên phiếu. "
            "Riêng bản nội bộ được ghi khi quản lý chấp thuận. [[E2]]"
        )
        assert (
            result.prompt_version
            == f"ollama-evidence-first-gpt-extraction-{profile.rsplit('-', 1)[-1]}"
        )
        assert len(requests) == 1
        assert (
            transport.observations[0]["system_prompt_sha256"]
            == hashlib.sha256(requests[0]["messages"][0]["content"].encode()).hexdigest()
        )
        assert "PRIVATE_CANARY" not in repr(result) + json.dumps(transport.observations)

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("fault", "stage"),
    [("missing_decision", "EXTRACTION_FIELDS"), ("bad_quote", "SOURCE_QUOTE")],
)
def test_invalid_extraction_reports_safe_failure_stage_without_source_text(fault, stage):
    payload = supported_payload()
    if fault == "missing_decision":
        del payload["decision"]
    else:
        payload["rules"][0]["quote"] = "PRIVATE_INVALID_QUOTE_CANARY"
    with pytest.raises(KnoraError) as error:
        probe_module().render_result(payload, EVIDENCE)
    assert error.value.code == "GENERATION_OUTPUT_INVALID"
    assert getattr(error.value, "invalid_output_stage", None) == stage
    assert "PRIVATE_INVALID_QUOTE_CANARY" not in str(error.value)


@pytest.mark.parametrize(
    ("model", "profile"),
    [("gpt-oss:20b", "qwen-nonthinking-v1"), ("qwen3:8b", "gpt-oss-low-v1")],
)
def test_probe_rejects_model_profile_mismatch_before_http(model, profile):
    module = probe_module()
    calls = []

    async def endpoint(request):
        calls.append(request.url.path)
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": model, "digest": "b" * 64}]})
        return httpx.Response(200, json={"message": {"content": json.dumps(supported_payload())}})

    async def scenario():
        transport = module.EvidenceFirstProbeTransport(
            inner=httpx.MockTransport(endpoint),
            sampling_profile=profile,
        )
        async with httpx.AsyncClient(transport=transport, trust_env=False) as client:
            provider = module.EvidenceFirstProbeProvider(
                base_url="http://127.0.0.1:11435",
                model=model,
                expected_digest="sha256:" + "b" * 64,
                client=client,
            )
            with pytest.raises(KnoraError, match="GENERATION_OUTPUT_INVALID"):
                await provider.generate(question="Có bắt buộc ghi không?", evidence=EVIDENCE)
        assert "/api/chat" not in calls

    asyncio.run(scenario())


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


@pytest.mark.parametrize(("model", "context_tokens"), [("qwen3:8b", 8192), ("qwen3:14b", 4096)])
def test_real_adapter_roundtrip_uses_one_chat_call_and_captures_no_thinking(model, context_tokens):
    module = probe_module()
    digest = "sha256:" + "b" * 64
    calls = []

    async def endpoint(request):
        calls.append(request.url.path)
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": model, "digest": digest}]})
        body = json.loads(request.content)
        assert body["format"]["properties"]["rules"]["type"] == "array"
        assert body["think"] is False
        assert body["options"]["num_predict"] <= 2048
        assert body["options"]["num_ctx"] == context_tokens
        assert body["model"] == model
        assert int(request.headers["content-length"]) == len(request.content)
        return httpx.Response(
            200,
            json={
                "model": model,
                "done_reason": "stop",
                "eval_count": 120,
                "message": {
                    "thinking": "PRIVATE_REASONING_SENTINEL",
                    "content": json.dumps(supported_payload()),
                },
            },
        )

    async def scenario():
        transport = module.EvidenceFirstProbeTransport(
            inner=httpx.MockTransport(endpoint), context_tokens=context_tokens
        )
        async with httpx.AsyncClient(transport=transport, trust_env=False) as client:
            provider = module.EvidenceFirstProbeProvider(
                base_url="http://127.0.0.1:11435",
                model=model,
                expected_digest=digest,
                client=client,
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


@pytest.mark.parametrize(
    ("profile", "thinking", "temperature", "top_p"),
    [
        ("qwen-nonthinking-v1", False, 0.7, 0.8),
        ("qwen-thinking-v1", True, 0.6, 0.95),
    ],
)
def test_sampling_profile_reaches_actual_request_without_changing_extraction(
    profile, thinking, temperature, top_p
):
    module = probe_module()
    digest = "sha256:" + "b" * 64

    async def endpoint(request):
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "qwen3:8b", "digest": digest}]})
        payload = json.loads(request.content)
        assert payload["think"] is thinking
        options = payload["options"]
        assert options == {
            "num_ctx": 8192,
            "num_predict": 2048,
            "temperature": temperature,
            "top_p": top_p,
            "top_k": 20,
            "min_p": 0,
            "seed": 105,
        }
        return httpx.Response(
            200,
            json={"model": "qwen3:8b", "message": {"content": json.dumps(supported_payload())}},
        )

    async def scenario():
        try:
            transport = module.EvidenceFirstProbeTransport(
                inner=httpx.MockTransport(endpoint),
                sampling_profile=profile,
                seed=105,
            )
        except TypeError:
            pytest.fail("probe cannot apply the declared sampling profile")
        async with httpx.AsyncClient(transport=transport, trust_env=False) as client:
            provider = module.EvidenceFirstProbeProvider(
                base_url="http://127.0.0.1:11435", expected_digest=digest, client=client
            )
            result = await provider.generate(question="Có bắt buộc ghi không?", evidence=EVIDENCE)
        assert result.cited_evidence_ids == ("E2",)
        assert "chấp thuận" in result.answer
        assert transport.observations[0]["options"]["seed"] == 105
        assert transport.observations[0]["think"] is thinking
        assert transport.request_policy_id.endswith(f":{profile}:seed105")

    asyncio.run(scenario())
