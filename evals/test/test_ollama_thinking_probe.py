import asyncio
import importlib
import json

import httpx
import pytest

from knora.domain.errors import KnoraError
from knora.providers.generation import GenerationEvidence
from knora.providers.ollama.generation import OllamaGenerationProvider


def test_thinking_probe_changes_only_bounded_request_mode_and_excludes_thinking():
    try:
        module = importlib.import_module("evals.runners.ollama_thinking_probe")
    except ModuleNotFoundError:
        pytest.fail("isolated thinking probe transport is missing")
    calls = []
    digest = "sha256:" + "b" * 64

    async def endpoint(request):
        calls.append(request)
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "qwen3:8b", "digest": digest}]})
        payload = json.loads(request.content)
        assert payload["model"] == "qwen3:8b"
        assert payload["think"] is True
        assert payload["stream"] is False
        assert payload["options"] == {"num_ctx": 8192, "num_predict": 2048, "temperature": 0}
        assert len(payload["messages"]) == 2
        assert json.loads(payload["messages"][1]["content"])["current_question"] == "How many?"
        assert int(request.headers["content-length"]) == len(request.content)
        return httpx.Response(
            200,
            json={
                "model": "qwen3:8b",
                "done_reason": "stop",
                "message": {
                    "thinking": "PRIVATE_THINKING_SENTINEL",
                    "content": json.dumps(
                        {
                            "decision": "ANSWER",
                            "answer": "Three. [[E1]]",
                            "cited_evidence_ids": ["E1"],
                            "refusal_reason": None,
                        }
                    ),
                },
            },
        )

    async def scenario():
        transport = module.ThinkingProbeTransport(inner=httpx.MockTransport(endpoint))
        async with httpx.AsyncClient(transport=transport, timeout=240, trust_env=False) as client:
            provider = OllamaGenerationProvider(
                base_url="http://127.0.0.1:11435", expected_digest=digest, client=client
            )
            result = await provider.generate(
                question="How many?", evidence=(GenerationEvidence("E1", "Three."),)
            )
        assert result.answer == "Three. [[E1]]"
        assert "PRIVATE_THINKING_SENTINEL" not in repr(result)
        assert "PRIVATE_THINKING_SENTINEL" not in json.dumps(transport.observations)
        assert len(calls) == 2
        assert len(transport.observations) == 1

    asyncio.run(scenario())


def test_probe_wall_deadline_cancels_the_request_without_retry():
    module = importlib.import_module("evals.runners.ollama_thinking_probe")
    digest = "sha256:" + "b" * 64

    async def scenario():
        cancelled = asyncio.Event()
        calls = []

        async def endpoint(request):
            calls.append(request.url.path)
            if request.url.path == "/api/tags":
                return httpx.Response(
                    200, json={"models": [{"name": "qwen3:8b", "digest": digest}]}
                )
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()

        async with httpx.AsyncClient(transport=httpx.MockTransport(endpoint)) as client:
            actual = OllamaGenerationProvider(
                base_url="http://127.0.0.1:11435", expected_digest=digest, client=client
            )
            try:
                bounded = module.BoundedThinkingProbeProvider(actual, deadline_seconds=0.01)
            except AttributeError:
                pytest.fail("probe lacks a wall deadline")
            with pytest.raises(KnoraError) as error:
                await bounded.generate(
                    question="How many?", evidence=(GenerationEvidence("E1", "Three."),)
                )
            assert error.value.code == "PROVIDER_REQUEST_FAILED"
            assert cancelled.is_set()
            assert calls == ["/api/tags", "/api/chat"]

    asyncio.run(scenario())
