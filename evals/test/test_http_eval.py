import json
from types import SimpleNamespace

import httpx
import pytest
from evals.runners.evaluation import EvaluationCase
from evals.runners.run_http_eval import HttpEvaluationExecutor


@pytest.mark.asyncio
async def test_http_executor_uses_question_endpoint_and_resolves_trace_ownership() -> None:
    requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "decision": "ANSWER",
                "answer": "Refunds are available for 30 days. [[E1]]",
                "citations": [
                    {
                        "evidence_id": "E1",
                        "source_key": "support/refund-policy",
                        "excerpt": "Refunds are available for 30 days.",
                        "start_line": 1,
                        "end_line": 1,
                    }
                ],
                "refusal_reason": None,
                "trace_id": "trace-1",
            },
        )

    trace = SimpleNamespace(
        candidates=(
            SimpleNamespace(
                chunk_id="chunk-1",
                source_key="support/refund-policy",
                chunk_ordinal=0,
                workspace_id="evaluation-m1",
                final_decision="SELECTED",
            ),
        ),
        alias_mapping={"E1": "chunk-1"},
        provider_metadata={
            "retrieval": {"latency_ms": 4.5},
            "embedding": {"provider": "deterministic-local", "usage": {}, "cost": {}},
            "generation": {
                "provider": "deterministic-local",
                "model": "deterministic-cited-answer-v1",
                "prompt_version": "deterministic-m1-v1",
                "usage": {},
                "cost": {},
            },
        },
        retrieval_latency_ms=4.5,
        retrieval_configuration_id="retrieval-m1-v1",
        embedding_configuration_id="embedding-local-m1-v2",
    )
    reader = SimpleNamespace(read_trace=lambda **kwargs: trace)
    client = httpx.AsyncClient(transport=httpx.MockTransport(handle))
    executor = HttpEvaluationExecutor(
        endpoint="http://knora.test/v1/questions",
        api_key="runtime-secret",
        trace_reader=reader,
        client=client,
    )
    case = EvaluationCase(
        "refund",
        "answerable",
        "evaluation-m1",
        "How long?",
        "ANSWER",
        ("support/refund-policy",),
        ("support/refund-policy#0",),
        ("30 days",),
        "30 days",
    )

    observation = await executor.execute(case)
    await client.aclose()

    assert requests[0].headers["X-API-Key"] == "runtime-secret"
    assert json.loads(requests[0].content) == {
        "workspace_id": "evaluation-m1",
        "question": "How long?",
    }
    assert observation.retrieved_chunks == ("support/refund-policy#0",)
    assert observation.candidate_workspaces == ("evaluation-m1",)
    assert observation.cited_chunks == ("support/refund-policy#0",)
    assert observation.retrieval_configuration_id == "retrieval-m1-v1"
    assert observation.embedding_provider == "deterministic-local"
    assert observation.generation_prompt_version == "deterministic-m1-v1"


@pytest.mark.asyncio
async def test_http_executor_rejects_citation_to_excluded_trace_candidate() -> None:
    def handle(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "decision": "ANSWER",
                "answer": "Refunds are available. [[E1]]",
                "citations": [
                    {
                        "evidence_id": "E1",
                        "source_key": "support/refund-policy",
                        "excerpt": "Refunds are available.",
                        "start_line": 1,
                        "end_line": 1,
                    }
                ],
                "refusal_reason": None,
                "trace_id": "trace-1",
            },
        )

    trace = SimpleNamespace(
        candidates=(
            SimpleNamespace(
                chunk_id="chunk-excluded",
                source_key="support/refund-policy",
                chunk_ordinal=0,
                workspace_id="evaluation-m1",
                final_decision="BUDGET_EXCEEDED",
            ),
        ),
        alias_mapping={"E1": "chunk-excluded"},
        provider_metadata={},
        retrieval_latency_ms=4.5,
        retrieval_configuration_id="retrieval-m1-v1",
        embedding_configuration_id="embedding-local-m1-v2",
    )
    client = httpx.AsyncClient(transport=httpx.MockTransport(handle))
    observation = await HttpEvaluationExecutor(
        endpoint="http://knora.test/v1/questions",
        api_key="runtime-secret",
        trace_reader=SimpleNamespace(read_trace=lambda **_kwargs: trace),
        client=client,
    ).execute(
        EvaluationCase(
            "refund",
            "answerable",
            "evaluation-m1",
            "How long?",
            "ANSWER",
            ("support/refund-policy",),
            ("support/refund-policy#0",),
            ("30 days",),
            "30 days",
        )
    )
    await client.aclose()

    assert observation.decision == "ERROR"
    assert observation.provider_error == "ObservationFailure"


@pytest.mark.asyncio
async def test_http_executor_rejects_malformed_public_citation_projection() -> None:
    def handle(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "decision": "ANSWER",
                "answer": "Refunds are available. [[E1]]",
                "citations": [{"evidence_id": "E1", "source_key": "support/refund-policy"}],
                "refusal_reason": None,
                "trace_id": "trace-1",
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handle))
    observation = await HttpEvaluationExecutor(
        endpoint="http://knora.test/v1/questions",
        api_key="runtime-secret",
        trace_reader=SimpleNamespace(
            read_trace=lambda **_kwargs: pytest.fail("trace must not be read")
        ),
        client=client,
    ).execute(
        EvaluationCase(
            "refund",
            "answerable",
            "evaluation-m1",
            "How long?",
            "ANSWER",
            ("support/refund-policy",),
            ("support/refund-policy#0",),
            ("30 days",),
            "30 days",
        )
    )
    await client.aclose()

    assert observation.decision == "ERROR"
    assert observation.provider_error == "ObservationFailure"
