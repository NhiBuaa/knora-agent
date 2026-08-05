import json
from decimal import Decimal

import httpx
import pytest
from evals.runners.evaluation import (
    EvaluationCase,
    EvaluationDataset,
    EvaluationObservation,
    EvaluationProvenance,
    SemanticEvaluation,
    build_report,
)
from evals.scorers.openai_compatible import (
    OpenAICompatibleSemanticScorer,
    SemanticScorerConfiguration,
    SemanticScorerError,
)


def _case() -> EvaluationCase:
    return EvaluationCase(
        id="refund-window",
        category="answerable",
        workspace_id="evaluation-m1-r2",
        question="How long are refunds accepted?",
        expected_behavior="ANSWER",
        expected_source_documents=("support/refund-policy",),
        acceptable_relevant_chunks=("support/refund-policy#0",),
        required_facts=("30 days",),
        reference_answer="Refund requests are accepted within 30 days.",
    )


def _observation() -> EvaluationObservation:
    return EvaluationObservation(
        case_id="refund-window",
        retrieved_chunks=("support/refund-policy#0",),
        retrieval_latency_ms=4.0,
        decision="ANSWER",
        answer="Refunds are accepted within 30 days. [[E1]]",
        refusal_reason=None,
        cited_chunks=("support/refund-policy#0",),
        citation_evidence_ids=("E1",),
        answer_marker_ids=("E1",),
        candidate_workspaces=("evaluation-m1-r2",),
        trace_id="trace-1",
        generation_provider="openai-compatible",
        generation_model="answer-model",
        evidence=(
            (
                "E1",
                "support/refund-policy#0",
                "Refund requests are accepted within 30 days of purchase.",
            ),
        ),
    )


@pytest.mark.asyncio
async def test_semantic_scorer_sends_aliases_and_returns_four_scores() -> None:
    observed: dict[str, object] = {}

    async def endpoint(request: httpx.Request) -> httpx.Response:
        observed["authorization"] = request.headers["Authorization"]
        observed["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            headers={"x-request-id": "judge-request-1"},
            json={
                "id": "judge-completion-1",
                "model": "judge-model",
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    metric: {"score": 0.75, "rationale": f"{metric} rationale"}
                                    for metric in (
                                        "citation_entailment",
                                        "faithfulness",
                                        "answer_relevance",
                                        "refusal_correctness",
                                    )
                                }
                            )
                        }
                    }
                ],
                "usage": {"prompt_tokens": 100, "completion_tokens": 40, "total_tokens": 140},
            },
        )

    scorer = OpenAICompatibleSemanticScorer(
        SemanticScorerConfiguration(
            base_url="https://judge.example/v1",
            api_key="runtime-judge-key",
            model="judge-model",
            version="semantic-scorer-v1",
            measurement_method="llm-judge-v1",
            input_cost_per_million_tokens=Decimal("1"),
            output_cost_per_million_tokens=Decimal("2"),
            pricing_version="judge-pricing-v1",
        ),
        client=httpx.AsyncClient(transport=httpx.MockTransport(endpoint)),
    )

    result = await scorer.score(case=_case(), observation=_observation())
    await scorer.aclose()

    assert observed["authorization"] == "Bearer runtime-judge-key"
    payload = observed["payload"]
    assert isinstance(payload, dict)
    assert payload["model"] == "judge-model"
    assert payload["temperature"] == 0
    assert payload["response_format"]["type"] == "json_schema"
    user_content = payload["messages"][1]["content"]
    assert "E1" in user_content
    assert "support/refund-policy#0" in user_content
    assert "Refund requests are accepted within 30 days" in user_content
    assert result.provider_request_id == "judge-request-1"
    assert result.provider == "openai-compatible"
    assert result.model == "judge-model"
    assert result.scorer_version == "semantic-scorer-v1"
    assert result.measurement_method == "llm-judge-v1"
    assert result.prompt_version == "m1-semantic-judge-v1"
    assert result.pricing_version == "judge-pricing-v1"
    assert result.scores == {
        "citation_entailment": 0.75,
        "faithfulness": 0.75,
        "answer_relevance": 0.75,
        "refusal_correctness": 0.75,
    }
    assert result.token_usage == {
        "prompt_tokens": 100,
        "completion_tokens": 40,
        "total_tokens": 140,
    }
    assert result.cost_usd == "0.00018"


@pytest.mark.asyncio
async def test_semantic_scorer_sanitizes_invalid_responses() -> None:
    async def endpoint(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "not-json"}}],
            },
        )

    scorer = OpenAICompatibleSemanticScorer(
        SemanticScorerConfiguration(
            base_url="https://judge.example/v1",
            api_key="secret-judge-key",
            model="judge-model",
            version="semantic-scorer-v1",
            measurement_method="llm-judge-v1",
        ),
        client=httpx.AsyncClient(transport=httpx.MockTransport(endpoint)),
    )

    with pytest.raises(SemanticScorerError) as captured:
        await scorer.score(case=_case(), observation=_observation())
    await scorer.aclose()

    assert captured.value.code == "SCORER_RESPONSE_INVALID"
    assert str(captured.value) == "SCORER_RESPONSE_INVALID"
    assert "secret-judge" not in str(captured.value)


def test_model_backed_report_keeps_semantic_and_system_metrics_separate() -> None:
    case = _case()
    observation = _observation()
    evaluation = SemanticEvaluation(
        case_id=case.id,
        scores={metric: 0.8 for metric in (
            "citation_entailment",
            "faithfulness",
            "answer_relevance",
            "refusal_correctness",
        )},
        rationales={"faithfulness": "grounded"},
        provider="openai-compatible",
        model="judge-model",
        scorer_version="semantic-scorer-v1",
        measurement_method="llm-judge-v1",
        prompt_version="m1-semantic-judge-v1",
        pricing_version="judge-pricing-v1",
        provider_request_id="judge-request-1",
        token_usage={"prompt_tokens": 100, "completion_tokens": 40},
        cost_usd="0.00018",
        latency_ms=30.0,
    )
    report = build_report(
        EvaluationDataset((case,)),
        (observation,),
        provenance=EvaluationProvenance(
            "dataset-v1",
            "sha256:dataset",
            "corpus-v1",
            "sha256:corpus",
            "chunking-v1",
            "embedding-v1",
            "retrieval-v1",
            "openai-compatible:answer-model:m1-cited-answer-v1",
            "semantic-scorer-v1",
            "llm-judge-v1",
        ),
        mode="model-backed",
        semantic_evaluations=(evaluation,),
        scorer_method="llm-judge-v1",
    )

    assert report["semantic"]["status"] == "completed"
    assert report["semantic"]["scorer"] == {
        "provider": "openai-compatible",
        "model": "judge-model",
        "version": "semantic-scorer-v1",
        "measurement_method": "llm-judge-v1",
        "prompt_versions": ["m1-semantic-judge-v1"],
        "pricing_versions": ["judge-pricing-v1"],
    }
    assert report["semantic"]["metrics"]["citation_entailment"] == {
        "denominator": 1,
        "mean": 0.8,
        "cases": [{"id": "refund-window", "score": 0.8}],
    }
    assert "threshold" not in report["semantic"]
    assert report["system"]["semantic_scorer"] == {
        "latency_ms": {"mean": 30.0, "min": 30.0, "max": 30.0},
        "token_usage": {"completion_tokens": 40, "prompt_tokens": 100},
        "usage_status": "observed",
        "cost_usd": "0.00018",
        "cost_status": "observed",
        "provider_errors": 0,
    }


def test_semantic_scorer_configuration_requires_runtime_values(monkeypatch) -> None:
    monkeypatch.delenv("KNORA_SEMANTIC_SCORER_BASE_URL", raising=False)
    monkeypatch.delenv("KNORA_SEMANTIC_SCORER_API_KEY", raising=False)
    monkeypatch.delenv("KNORA_SEMANTIC_SCORER_MODEL", raising=False)

    with pytest.raises(SemanticScorerError, match="missing semantic scorer configuration"):
        SemanticScorerConfiguration.from_environment(
            version="semantic-scorer-v1",
            measurement_method="llm-judge-v1",
        )
