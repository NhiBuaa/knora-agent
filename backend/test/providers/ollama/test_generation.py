import json
from dataclasses import asdict

import httpx
import pytest

from knora.domain.errors import KnoraError
from knora.providers.generation import GenerationEvidence
from knora.providers.ollama.generation import OllamaGenerationProvider

DIGEST = "sha256:" + "b" * 64


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("content", "decision", "answer", "aliases", "reason"),
    [
        (
            '{"decision":"ANSWER","answer":"Gợi ý 7 chương. [[E1]]",'
            '"cited_evidence_ids":["E1"],"refusal_reason":null}',
            "ANSWER",
            "Gợi ý 7 chương. [[E1]]",
            ("E1",),
            None,
        ),
        (
            '{"decision":"REFUSAL","answer":null,'
            '"cited_evidence_ids":[],"refusal_reason":"INSUFFICIENT_EVIDENCE"}',
            "REFUSAL",
            None,
            (),
            "INSUFFICIENT_EVIDENCE",
        ),
    ],
)
async def test_ollama_chat_returns_structured_result(
    content: str, decision: str, answer: str | None, aliases: tuple[str, ...], reason: str | None
) -> None:
    requests: list[dict] = []

    async def endpoint(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "qwen3:8b", "digest": DIGEST}]})
        assert str(request.url) == "http://ollama.test:11434/api/chat"
        assert "authorization" not in request.headers
        requests.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "model": "qwen3:8b",
                "message": {"role": "assistant", "content": content, "thinking": "private"},
                "done": True,
                "done_reason": "stop",
                "prompt_eval_count": 42,
                "eval_count": 17,
            },
        )

    provider = OllamaGenerationProvider(
        base_url="http://ollama.test:11434",
        model="qwen3:8b",
        expected_digest=DIGEST,
        client=httpx.AsyncClient(transport=httpx.MockTransport(endpoint)),
    )
    result = await provider.generate(
        question="Báo cáo có mấy chương?",
        evidence=(GenerationEvidence("E1", "Gợi ý gồm 7 chương."),),
    )

    assert requests[0]["model"] == "qwen3:8b"
    assert requests[0]["stream"] is False
    assert requests[0]["think"] is False
    assert requests[0]["format"]["type"] == "object"
    assert requests[0]["options"]["num_predict"] > 0
    assert "E1" in requests[0]["messages"][1]["content"]
    assert result.decision == decision
    assert result.answer == answer
    assert result.cited_evidence_ids == aliases
    assert result.refusal_reason == reason
    assert result.provider == "ollama"
    assert result.model == "qwen3:8b"
    assert result.prompt_version == "ollama-qwen3-cited-answer-v5"
    assert result.usage == {"prompt_tokens": 42, "completion_tokens": 17}
    assert result.cost == {}
    assert "private" not in json.dumps(asdict(result))


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["malformed", "missing", "timeout", "http"])
async def test_ollama_chat_fails_safely(failure: str) -> None:
    async def endpoint(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "qwen3:8b", "digest": DIGEST}]})
        if failure == "timeout":
            raise httpx.ReadTimeout("secret-canary", request=request)
        if failure == "http":
            return httpx.Response(503, text="secret-canary")
        content = "not-json" if failure == "malformed" else '{"decision":"ANSWER"}'
        return httpx.Response(200, json={"model": "qwen3:8b", "message": {"content": content}})

    provider = OllamaGenerationProvider(
        base_url="http://ollama.test:11434",
        model="qwen3:8b",
        expected_digest=DIGEST,
        client=httpx.AsyncClient(transport=httpx.MockTransport(endpoint)),
    )
    with pytest.raises(KnoraError) as captured:
        await provider.generate(question="Báo cáo?", evidence=(GenerationEvidence("E1", "A"),))
    assert captured.value.code == (
        "PROVIDER_REQUEST_FAILED" if failure in {"timeout", "http"} else "GENERATION_OUTPUT_INVALID"
    )
    assert "secret-canary" not in str(captured.value)


@pytest.mark.asyncio
@pytest.mark.parametrize("current", ["sha256:" + "c" * 64, None, "not-a-digest"])
async def test_ollama_generation_rejects_model_drift_before_chat(current: str | None) -> None:
    chats = 0

    async def endpoint(request: httpx.Request) -> httpx.Response:
        nonlocal chats
        if request.url.path == "/api/tags":
            models = [{"name": "qwen3:8b", "digest": current}] if current else []
            return httpx.Response(200, json={"models": models})
        chats += 1
        return httpx.Response(200, json={"model": "qwen3:8b", "message": {"content": "{}"}})

    provider = OllamaGenerationProvider(
        base_url="http://ollama.test:11434",
        model="qwen3:8b",
        expected_digest=DIGEST,
        client=httpx.AsyncClient(transport=httpx.MockTransport(endpoint)),
    )
    with pytest.raises(KnoraError, match="GENERATION_MODEL_MISMATCH"):
        await provider.generate(question="Báo cáo?", evidence=(GenerationEvidence("E1", "A"),))
    assert chats == 0


@pytest.mark.asyncio
async def test_chat_keeps_current_question_separate_and_preserves_evidence_aliases() -> None:
    paths: list[str] = []
    bodies: list[dict] = []

    async def endpoint(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "qwen3:8b", "digest": DIGEST}]})
        bodies.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "model": "qwen3:8b",
                "message": {
                    "content": json.dumps(
                        {
                            "decision": "ANSWER",
                            "answer": "18 độ C. [[E2]]",
                            "cited_evidence_ids": ["E2"],
                            "refusal_reason": None,
                        }
                    )
                },
                "done": True,
                "done_reason": "stop",
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(endpoint)) as client:
        provider = OllamaGenerationProvider(
            base_url="http://ollama.test:11434", expected_digest=DIGEST, client=client
        )
        result = await provider.generate(
            question="Nhiệt độ bao nhiêu?",
            evidence=(
                GenerationEvidence("E1", "Kiểm tra nhiệt kế mỗi ca."),
                GenerationEvidence("E2", "Duy trì nhiệt độ 18 độ C."),
            ),
        )

    assert paths == ["/api/tags", "/api/chat"]
    assert [message["role"] for message in bodies[0]["messages"]] == ["system", "user"]
    assert json.loads(bodies[0]["messages"][1]["content"]) == {
        "evidence": [
            {"evidence_id": "E1", "content": "Kiểm tra nhiệt kế mỗi ca."},
            {"evidence_id": "E2", "content": "Duy trì nhiệt độ 18 độ C."},
        ],
        "current_question": "Nhiệt độ bao nhiêu?",
    }
    assert bodies[0]["options"] == {"num_ctx": 8192, "num_predict": 1024, "temperature": 0}
    assert result.cited_evidence_ids == ("E2",)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "content",
    [
        "not-json",
        '{"decision":"ANSWER","answer":"Unsupported alias [[E9]]",'
        '"cited_evidence_ids":["E9"],"refusal_reason":null}',
    ],
)
async def test_invalid_generation_is_never_repaired_or_converted_to_refusal(content: str) -> None:
    from knora.answering.generation_validation import validate_generation

    paths: list[str] = []

    async def endpoint(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "qwen3:8b", "digest": DIGEST}]})
        return httpx.Response(200, json={"message": {"content": content}, "done": True})

    async with httpx.AsyncClient(transport=httpx.MockTransport(endpoint)) as client:
        provider = OllamaGenerationProvider(
            base_url="http://ollama.test:11434", expected_digest=DIGEST, client=client
        )
        with pytest.raises(KnoraError, match="GENERATION_OUTPUT_INVALID"):
            result = await provider.generate(
                question="Question?", evidence=(GenerationEvidence("E1", "Evidence."),)
            )
            validate_generation(result, available_evidence_ids=("E1",))
    assert paths == ["/api/tags", "/api/chat"]
