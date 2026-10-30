import asyncio
import json
from decimal import Decimal

import httpx
import pytest

from knora.answering.generation_validation import validate_generation
from knora.domain.errors import KnoraError
from knora.providers.generation import GenerationEvidence
from knora.providers.openai_compatible.generation import OpenAICompatibleGenerationProvider


@pytest.mark.asyncio
@pytest.mark.parametrize("version,budget", [("v1", 4096), ("v3", 8192)])
async def test_concurrent_generation_and_audit_keep_their_models_and_receipts(version, budget):
    from knora.providers.prompts.builder import BuiltPrompt
    from knora.providers.prompts.versioning import PromptDefinition

    bodies = []
    both_started = asyncio.Event()

    async def endpoint(request):
        body = json.loads(request.content)
        bodies.append(body)
        if len(bodies) == 2:
            both_started.set()
        await asyncio.wait_for(both_started.wait(), 2)
        audit = body["model"] == "@cf/openai/gpt-oss-120b"
        result = (
            {"diagnostic": True}
            if audit
            else dict(
                decision="ANSWER",
                before=[dict(text="Seven days.", support=["E1"])],
                items=[],
                after=[],
                refusal_reason=None,
            )
        )
        return httpx.Response(
            200,
            json={
                "choices": [{"finish_reason": "stop", "message": {"content": json.dumps(result)}}],
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(endpoint)) as client:
        provider = OpenAICompatibleGenerationProvider(
            base_url="https://provider.example/v1",
            api_key="secret-canary",
            model="@cf/openai/gpt-oss-20b",
            provider_identity="cloudflare-workers-ai",
            input_cost_per_million_tokens=None,
            output_cost_per_million_tokens=None,
            pricing_version=None,
            grounded_answers=True,
            direct_json_schema=True,
            max_tokens=2048,
            client=client,
        )
        prompt = BuiltPrompt(
            PromptDefinition(
                f"cloudflare-gpt-oss-source-audit-{version}",
                "Audit.",
                {"type": "object"},
                "source-audit-v1",
            ),
            [{"role": "user", "content": "Audit."}],
        )
        generated, (_, metadata) = await asyncio.gather(
            provider.generate(
                question="How long?", evidence=(GenerationEvidence("E1", "Seven days."),)
            ),
            provider.complete_answer_support(prompt),
        )
    assert generated.model == "@cf/openai/gpt-oss-20b"
    assert metadata["model"] == "@cf/openai/gpt-oss-120b"
    assert sorted((b["model"], b["max_tokens"]) for b in bodies) == [
        ("@cf/openai/gpt-oss-120b", budget),
        ("@cf/openai/gpt-oss-20b", 2048),
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("configured_model", ["@cf/openai/gpt-oss-20b", "@cf/openai/gpt-oss-120b"])
async def test_sufficiency_uses_qualified_20b_json_object_without_changing_generation(
    configured_model,
):
    from knora.providers.prompts.builder import BuiltPrompt
    from knora.providers.prompts.versioning import PromptDefinition

    bodies = []

    async def endpoint(request):
        bodies.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"finish_reason": "stop", "message": {"content": '{"diagnostic":true}'}}
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(endpoint)) as client:
        provider = OpenAICompatibleGenerationProvider(
            base_url="https://provider.example/v1",
            api_key="secret-canary",
            model=configured_model,
            provider_identity="cloudflare-workers-ai",
            input_cost_per_million_tokens=None,
            output_cost_per_million_tokens=None,
            pricing_version=None,
            max_tokens=2048,
            direct_json_schema=True,
            client=client,
        )
        _, metadata = await provider.complete_answer_support(
            BuiltPrompt(
                PromptDefinition(
                    "cloudflare-gpt-oss-source-sufficiency-v3",
                    "Inspect sources.",
                    {"type": "object"},
                    "source-sufficiency-v2",
                ),
                [
                    {"role": "system", "content": "Inspect sources."},
                    {"role": "user", "content": "Sources."},
                ],
            )
        )
        assert (
            provider._model_for_version("cloudflare-gpt-oss-cited-answer-v25") == configured_model
        )
    body = bodies[0]
    assert body["model"] == metadata["model"] == "@cf/openai/gpt-oss-20b"
    assert body["response_format"] == {"type": "json_object"}
    assert body["max_tokens"] == 2048 and body["reasoning_effort"] == "medium"
    assert "Required JSON Schema" in body["messages"][0]["content"]


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [None, "wrapped", "foreign_alias", "length"])
async def test_cloudflare_120b_json_object_keeps_strict_grounded_validation(failure):
    requests = []

    async def endpoint(request):
        body = json.loads(request.content)
        requests.append(body)
        content = json.dumps(
            {
                "decision": "ANSWER",
                "before": [
                    {"text": "7 days.", "support": ["E2" if failure == "foreign_alias" else "E1"]}
                ],
                "items": [],
                "after": [],
                "refusal_reason": None,
            }
        )
        if failure == "wrapped":
            content = "<|channel|>final " + content
        return httpx.Response(
            200,
            json={
                "model": "@cf/openai/gpt-oss-120b",
                "choices": [
                    {
                        "finish_reason": "length" if failure == "length" else "stop",
                        "message": {"content": content},
                    }
                ],
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(endpoint)) as client:
        provider = OpenAICompatibleGenerationProvider(
            base_url="https://provider.example/v1",
            api_key="secret-canary",
            model="@cf/openai/gpt-oss-120b",
            provider_identity="cloudflare-workers-ai",
            input_cost_per_million_tokens=None,
            output_cost_per_million_tokens=None,
            pricing_version=None,
            max_tokens=2048,
            direct_json_schema=True,
            grounded_answers=True,
            client=client,
        )
        if failure:
            with pytest.raises(KnoraError, match="GENERATION_OUTPUT_INVALID"):
                await provider.generate(
                    question="How long?", evidence=(GenerationEvidence("E1", "7 days."),)
                )
        else:
            result = await provider.generate(
                question="How long?", evidence=(GenerationEvidence("E1", "7 days."),)
            )
            assert result.answer_projection.statements[0].text == "7 days."
            assert result.model == "@cf/openai/gpt-oss-120b"
            assert result.prompt_version == "cloudflare-gpt-oss-cited-answer-v25:json-object-v1"
    assert len(requests) == 1
    assert requests[0]["response_format"] == {"type": "json_object"}
    assert requests[0]["max_tokens"] == 2048
    assert requests[0]["reasoning_effort"] == "medium"
    assert '"required"' in requests[0]["messages"][0]["content"]


@pytest.mark.asyncio
async def test_cloudflare_repair_uses_versioned_prompt_and_same_source_schema():
    requests = []

    async def endpoint(request):
        requests.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "content": json.dumps(
                                {
                                    "decision": "ANSWER",
                                    "before": [
                                        {
                                            "text": "Đổi trả trong 7 ngày.",
                                            "bold": None,
                                            "support": ["E1"],
                                        }
                                    ],
                                    "items": [],
                                    "after": [],
                                    "refusal_reason": None,
                                }
                            )
                        },
                    }
                ],
                "usage": {"total_tokens": 12},
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(endpoint)) as client:
        provider = OpenAICompatibleGenerationProvider(
            base_url="https://provider.example/v1",
            api_key="test",
            model="test",
            input_cost_per_million_tokens=None,
            output_cost_per_million_tokens=None,
            pricing_version=None,
            client=client,
            provider_identity="cloudflare-workers-ai",
            direct_json_schema=True,
        )
        evidence = (GenerationEvidence("E1", "Đổi trả trong 7 ngày."),)
        initial = await provider.generate(question="Bao nhiêu ngày?", evidence=evidence)
        repaired = await provider.repair_generation(question="Bao nhiêu ngày?", evidence=evidence)
    assert initial.prompt_version == "cloudflare-gpt-oss-cited-answer-v21"
    assert repaired.prompt_version.startswith("retrieval-v3-grounded-repair-v2:")
    assert requests[0]["messages"][1] == requests[1]["messages"][1]
    assert requests[0]["response_format"] == requests[1]["response_format"]
    assert requests[0]["messages"][0] != requests[1]["messages"][0]
    assert repaired.answer == "Đổi trả trong 7 ngày. [[E1]]"
    assert repaired.usage == {"total_tokens": 12}
    assert repaired.cost == {}


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["schema", "length", "permanent", "transport"])
async def test_cloudflare_initial_format_failure_never_regenerates(failure):
    requests = []

    async def endpoint(request):
        requests.append(json.loads(request.content))
        if failure == "transport":
            return httpx.Response(503)
        valid = len(requests) > 1 and failure != "permanent"
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "length" if failure == "length" and not valid else "stop",
                        "message": {
                            "content": json.dumps(
                                {
                                    "decision": "ANSWER",
                                    "before": [
                                        {"text": "Đổi trả 7 ngày.", "bold": None, "support": ["E1"]}
                                    ],
                                    "items": [],
                                    "after": [],
                                    "refusal_reason": None,
                                }
                                if valid
                                else {"decision": "ANSWER"}
                            )
                        },
                    }
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(endpoint)) as client:
        provider = OpenAICompatibleGenerationProvider(
            base_url="https://provider.example/v1",
            api_key="test",
            model="test",
            input_cost_per_million_tokens=None,
            output_cost_per_million_tokens=None,
            pricing_version=None,
            client=client,
            provider_identity="cloudflare-workers-ai",
        )
        expected = (
            "PROVIDER_REQUEST_FAILED" if failure == "transport" else "GENERATION_OUTPUT_INVALID"
        )
        with pytest.raises(KnoraError, match=expected):
            await provider.generate(
                question="Bao nhiêu ngày?", evidence=(GenerationEvidence("E1", "Đổi trả 7 ngày."),)
            )
    assert len(requests) == 1


@pytest.mark.asyncio
async def test_openai_compatible_generation_returns_structured_result_and_safe_metadata() -> None:
    observed: dict[str, object] = {}

    async def endpoint(request: httpx.Request) -> httpx.Response:
        observed["url"] = str(request.url)
        observed["authorization"] = request.headers["Authorization"]
        observed["payload"] = __import__("json").loads(request.content)
        return httpx.Response(
            200,
            headers={"x-request-id": "generation-request-1"},
            json={
                "id": "completion-1",
                "model": "compatible-chat-model",
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "content": (
                                '{"decision":"ANSWER","answer":"Refunds last thirty days. '
                                '[[E1]]","cited_evidence_ids":["E1"],'
                                '"refusal_reason":null}'
                            )
                        },
                    }
                ],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 5,
                    "total_tokens": 15,
                },
            },
        )

    provider = OpenAICompatibleGenerationProvider(
        base_url="https://provider.example/v1/",
        api_key="runtime-secret",
        model="compatible-chat-model",
        input_cost_per_million_tokens=Decimal("1"),
        output_cost_per_million_tokens=Decimal("2"),
        pricing_version="test-pricing-v1",
        client=httpx.AsyncClient(transport=httpx.MockTransport(endpoint)),
    )

    result = await provider.generate(
        question="What is the refund policy?",
        evidence=(GenerationEvidence(evidence_id="E1", content="Refunds last thirty days."),),
    )

    payload = observed["payload"]
    assert isinstance(payload, dict)
    assert observed["url"] == "https://provider.example/v1/chat/completions"
    assert observed["authorization"] == "Bearer runtime-secret"
    assert payload["model"] == "compatible-chat-model"
    assert payload["response_format"]["type"] == "json_schema"
    assert "E1" in payload["messages"][1]["content"]
    assert "Refunds last thirty days." in payload["messages"][1]["content"]
    assert "retained_conditions" not in json.loads(payload["messages"][1]["content"])
    assert result.decision == "ANSWER"
    assert result.answer == "Refunds last thirty days. [[E1]]"
    assert result.cited_evidence_ids == ("E1",)
    assert result.refusal_reason is None
    assert result.provider == "openai-compatible"
    assert result.model == "compatible-chat-model"
    assert result.prompt_version == "m1-cited-answer-v1"
    assert result.finish_reason == "stop"
    assert result.provider_request_id == "generation-request-1"
    assert result.usage == {
        "prompt_tokens": 10,
        "completion_tokens": 5,
        "total_tokens": 15,
    }
    assert result.cost == {
        "amount_usd": "0.00002",
        "currency": "USD",
        "pricing_version": "test-pricing-v1",
    }


@pytest.mark.asyncio
async def test_generation_prompt_requires_citation_ids_to_follow_first_marker_order() -> None:
    observed: dict[str, object] = {}

    async def endpoint(request: httpx.Request) -> httpx.Response:
        observed["payload"] = __import__("json").loads(request.content)
        return httpx.Response(
            200,
            json={
                "model": "compatible-chat-model",
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "content": (
                                '{"decision":"ANSWER","answer":"Refunds. [[E1]]",'
                                '"cited_evidence_ids":["E1"],"refusal_reason":null}'
                            )
                        },
                    }
                ],
            },
        )

    provider = OpenAICompatibleGenerationProvider(
        base_url="https://provider.example/v1",
        api_key="runtime-secret",
        model="compatible-chat-model",
        input_cost_per_million_tokens=Decimal("0"),
        output_cost_per_million_tokens=Decimal("0"),
        pricing_version="test-pricing-v1",
        client=httpx.AsyncClient(transport=httpx.MockTransport(endpoint)),
    )

    await provider.generate(
        question="What is the refund policy?",
        evidence=(GenerationEvidence(evidence_id="E1", content="Refunds."),),
    )

    payload = observed["payload"]
    assert isinstance(payload, dict)
    system_prompt = payload["messages"][0]["content"]
    assert "cited_evidence_ids" in system_prompt
    assert "same order that their markers first appear" in system_prompt
    assert "use each inline marker at most once" in system_prompt
    assert "Fact A [[E1]]; fact B [[E1]]" in system_prompt
    assert "For ANSWER, refusal_reason MUST be null." not in system_prompt


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["malformed", "http", "timeout"])
async def test_openai_compatible_generation_normalizes_failures_without_retry(
    failure: str,
) -> None:
    calls = 0

    async def endpoint(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if failure == "timeout":
            raise httpx.ReadTimeout("secret-canary-timeout", request=request)
        if failure == "http":
            return httpx.Response(500, text="secret-canary-body")
        return httpx.Response(
            200,
            json={
                "model": "compatible-chat-model",
                "choices": [{"finish_reason": "stop", "message": {"content": "not-json"}}],
            },
        )

    provider = OpenAICompatibleGenerationProvider(
        base_url="https://provider.example/v1",
        api_key="secret-canary-key",
        model="compatible-chat-model",
        input_cost_per_million_tokens=Decimal("1"),
        output_cost_per_million_tokens=Decimal("2"),
        pricing_version="test-pricing-v1",
        client=httpx.AsyncClient(transport=httpx.MockTransport(endpoint)),
    )

    with pytest.raises(KnoraError) as captured:
        await provider.generate(
            question="What is the refund policy?",
            evidence=(GenerationEvidence(evidence_id="E1", content="Refunds last thirty days."),),
        )

    expected = "GENERATION_OUTPUT_INVALID" if failure == "malformed" else "PROVIDER_REQUEST_FAILED"
    assert captured.value.code == expected
    assert str(captured.value) == expected
    assert "secret-canary" not in str(captured.value)
    assert calls == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["paragraph", "list", "refusal"])
async def test_cloudflare_chat_uses_direct_schema_and_preserves_identity(case: str) -> None:
    observed = {}
    calls = 0
    decision = "REFUSAL" if case == "refusal" else "ANSWER"
    blocks = [
        {
            "kind": "paragraph",
            "text": "Refunds.",
            "support": ["E1"],
            "bold": None,
        }
    ]
    expected = "Refunds. [[E1]]"
    if case == "list":
        blocks = [
            {
                "kind": "paragraph",
                "text": "There are 2 parts.",
                "bold": "2 parts",
                "support": ["E1"],
            },
            {
                "kind": "list",
                "items": [{"text": title, "support": ["E1"]} for title in ("Alpha", "Beta")],
            },
        ]
        expected = "There are **2 parts**.\n\n- Alpha\n- Beta\n\n[[E1]]"

    async def endpoint(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        observed["request"] = request
        content = json.dumps(
            {
                "decision": decision,
                "before": [{k: v for k, v in blocks[0].items() if k != "kind"}]
                if decision == "ANSWER"
                else [],
                "items": blocks[1]["items"] if case == "list" else [],
                "after": [],
                "refusal_reason": None if decision == "ANSWER" else "INSUFFICIENT_EVIDENCE",
            }
        )
        return httpx.Response(
            200,
            json={
                "model": "@cf/openai/gpt-oss-20b",
                "choices": [{"finish_reason": "stop", "message": {"content": content}}],
            },
        )

    provider = OpenAICompatibleGenerationProvider(
        base_url="https://api.cloudflare.com/client/v4/accounts/0123456789abcdef0123456789abcdef/ai/v1",
        api_key="secret-canary",
        model="@cf/openai/gpt-oss-20b",
        input_cost_per_million_tokens=None,
        output_cost_per_million_tokens=None,
        pricing_version=None,
        provider_identity="cloudflare-workers-ai",
        max_tokens=1024,
        direct_json_schema=True,
        client=httpx.AsyncClient(transport=httpx.MockTransport(endpoint)),
    )

    result = await provider.generate(
        question="Báo cáo có bao nhiêu chương?" if case == "list" else "What is the refund policy?",
        evidence=(GenerationEvidence("E1", "Refunds. Alpha; Beta."),),
    )
    request = observed["request"]
    assert calls == 1
    payload = __import__("json").loads(request.content)
    assert request.url.path.endswith("/ai/v1/chat/completions")
    assert payload["model"] == "@cf/openai/gpt-oss-20b"
    assert payload["max_tokens"] == 1024
    assert payload["response_format"]["type"] == "json_schema"
    assert payload["response_format"]["json_schema"]["properties"]["decision"]["enum"] == [
        "ANSWER",
        "REFUSAL",
    ]
    assert result.answer == (expected if decision == "ANSWER" else None)
    assert result.cited_evidence_ids == (("E1",) if decision == "ANSWER" else ())
    assert __import__("json").loads(payload["messages"][1]["content"])["question"] == (
        "Báo cáo có bao nhiêu chương?" if case == "list" else "What is the refund policy?"
    )
    assert result.provider == "cloudflare-workers-ai"
    assert result.model == "@cf/openai/gpt-oss-20b"
    assert result.prompt_version == "cloudflare-gpt-oss-cited-answer-v21"
    assert result.decision == decision
    assert result.usage == {}
    assert result.cost == {}
    assert validate_generation(result, available_evidence_ids=("E1",)).parsed_markers == (
        ("E1",) if decision == "ANSWER" else ()
    )


@pytest.mark.asyncio
async def test_missing_usage_never_produces_zero_dollar_cost() -> None:
    provider = OpenAICompatibleGenerationProvider(
        base_url="https://provider.example/v1",
        api_key="secret-canary",
        model="compatible-chat-model",
        input_cost_per_million_tokens=Decimal("1"),
        output_cost_per_million_tokens=Decimal("2"),
        pricing_version="test-pricing-v1",
        client=httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(
                    200,
                    json={
                        "choices": [
                            {
                                "message": {
                                    "content": '{"decision":"REFUSAL","answer":null,'
                                    '"cited_evidence_ids":[],"refusal_reason":"INSUFFICIENT_EVIDENCE"}'
                                }
                            }
                        ]
                    },
                )
            )
        ),
    )
    result = await provider.generate(question="Unknown?", evidence=())
    assert result.cost == {}


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [401, 403, 429, 500, 503])
async def test_cloudflare_chat_safely_normalizes_http_errors(status: int) -> None:
    calls = 0

    async def endpoint(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(status, text="secret-canary-body")

    provider = OpenAICompatibleGenerationProvider(
        base_url="https://api.cloudflare.com/client/v4/accounts/0123456789abcdef0123456789abcdef/ai/v1",
        api_key="secret-canary",
        model="@cf/openai/gpt-oss-20b",
        input_cost_per_million_tokens=None,
        output_cost_per_million_tokens=None,
        pricing_version=None,
        provider_identity="cloudflare-workers-ai",
        client=httpx.AsyncClient(transport=httpx.MockTransport(endpoint)),
    )
    with pytest.raises(KnoraError, match="PROVIDER_REQUEST_FAILED") as captured:
        await provider.generate(question="Unknown?", evidence=())
    assert "secret-canary" not in str(captured.value)
    assert calls == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["length-null", "length-valid", "malformed", "timeout"])
@pytest.mark.parametrize("max_tokens", [1024, 2048, 4096])
async def test_cloudflare_chat_rejects_invalid_completion_without_retry(
    failure: str, max_tokens: int
) -> None:
    calls = 0
    valid = json.dumps(
        {
            "decision": "ANSWER",
            "before": [{"text": "Answer.", "support": ["E1"], "bold": None}],
            "items": [],
            "after": [],
            "refusal_reason": None,
        }
    )

    async def endpoint(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        assert json.loads(request.content)["max_tokens"] == max_tokens
        if failure == "timeout":
            raise httpx.ReadTimeout("secret-canary-timeout", request=request)
        content = None if failure == "length-null" else valid if failure == "length-valid" else "{"
        return httpx.Response(
            200,
            json={
                "model": "@cf/openai/gpt-oss-20b",
                "choices": [
                    {
                        "finish_reason": "length" if failure.startswith("length") else "stop",
                        "message": {"content": content},
                    }
                ],
            },
        )

    provider = OpenAICompatibleGenerationProvider(
        base_url="https://provider.example/ai/v1",
        api_key="secret-canary",
        model="@cf/openai/gpt-oss-20b",
        input_cost_per_million_tokens=None,
        output_cost_per_million_tokens=None,
        pricing_version=None,
        provider_identity="cloudflare-workers-ai",
        max_tokens=max_tokens,
        direct_json_schema=True,
        client=httpx.AsyncClient(transport=httpx.MockTransport(endpoint)),
    )

    expected = "PROVIDER_REQUEST_FAILED" if failure == "timeout" else "GENERATION_OUTPUT_INVALID"
    with pytest.raises(KnoraError, match=expected) as captured:
        await provider.generate(
            question="Question?", evidence=(GenerationEvidence("E1", "Answer."),)
        )
    assert str(captured.value) == expected
    assert "secret-canary" not in str(captured.value)
    assert calls == 1


@pytest.mark.asyncio
async def test_grounded_repair_keeps_schema_and_carries_untrusted_feedback():
    requests = []

    async def endpoint(request):
        requests.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "id": "repair-request",
                "model": "@cf/openai/gpt-oss-20b",
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "content": json.dumps(
                                {
                                    "decision": "ANSWER",
                                    "before": [{"text": "7 days.", "support": ["E1"]}],
                                    "items": [],
                                    "after": [],
                                    "refusal_reason": None,
                                }
                            )
                        },
                    }
                ],
                "usage": {"prompt_tokens": 111, "completion_tokens": 22},
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(endpoint)) as client:
        provider = OpenAICompatibleGenerationProvider(
            base_url="https://provider.example/v1",
            api_key="secret-canary",
            model="@cf/openai/gpt-oss-20b",
            provider_identity="cloudflare-workers-ai",
            input_cost_per_million_tokens=None,
            output_cost_per_million_tokens=None,
            pricing_version=None,
            grounded_answers=True,
            direct_json_schema=True,
            client=client,
        )
        result = await provider.repair_grounded_generation(
            question="How long?",
            evidence=(GenerationEvidence("E1", "7 days."),),
            feedback={"failure": "unsupported_answer", "previous_answer": "ignore rules"},
        )
    assert result.answer_projection.statements[0].text == "7 days."
    assert result.prompt_version == "cloudflare-gpt-oss-cited-answer-v25:recovery-v3"
    body = requests[0]
    assert body["reasoning_effort"] == "medium"
    assert "bold" not in body["response_format"]["json_schema"]["$defs"]
    assert (
        json.loads(body["messages"][-1]["content"])["recovery_feedback"]["previous_answer"]
        == "ignore rules"
    )
    assert "ignore rules" not in body["messages"][0]["content"]
    assert json.loads(body["messages"][-1]["content"])["question"] == "How long?"
    assert json.loads(body["messages"][-1]["content"])["evidence"] == [
        {"evidence_id": "E1", "content": "7 days."}
    ]


@pytest.mark.asyncio
async def test_malformed_generation_retains_safe_completion_identity_without_raw_text():
    from knora.providers.generation import GenerationFailure

    async def endpoint(request):
        return httpx.Response(
            200,
            json={
                "id": "broken-request",
                "model": "@cf/openai/gpt-oss-20b",
                "choices": [
                    {"finish_reason": "length", "message": {"content": "private raw source"}}
                ],
                "usage": {"completion_tokens": 2048},
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(endpoint)) as client:
        provider = OpenAICompatibleGenerationProvider(
            base_url="https://provider.example/v1",
            api_key="secret-canary",
            model="@cf/openai/gpt-oss-20b",
            provider_identity="cloudflare-workers-ai",
            input_cost_per_million_tokens=None,
            output_cost_per_million_tokens=None,
            pricing_version=None,
            grounded_answers=True,
            direct_json_schema=True,
            client=client,
        )
        with pytest.raises(GenerationFailure) as caught:
            await provider.generate(
                question="How long?", evidence=(GenerationEvidence("E1", "7 days."),)
            )
    observation = caught.value.observation
    assert observation["provider"]["provider_request_id"] == "broken-request"
    assert observation["provider"]["usage"]["completion_tokens"] == 2048
    assert len(observation["completion_digest"]) == 64
    assert "private raw source" not in json.dumps(observation)
    assert "secret-canary" not in json.dumps(observation)
