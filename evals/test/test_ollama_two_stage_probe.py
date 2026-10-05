import asyncio
import importlib
import json

import httpx
import pytest

from knora.domain.errors import KnoraError
from knora.providers.generation import GenerationEvidence


def two_stage_module():
    try:
        return importlib.import_module("evals.runners.ollama_two_stage_probe")
    except ModuleNotFoundError:
        pytest.fail("two-stage probe is missing")


@pytest.mark.parametrize("final_decision", ["ANSWER", "REFUSAL"])
@pytest.mark.parametrize("provisional_decision", ["ANSWER", "REFUSAL"])
@pytest.mark.parametrize(
    "profile", ["gpt-oss-extraction-two-stage-v1", "gpt-oss-extraction-two-stage-dedup-v1"]
)
def test_two_stage_adapter_audits_all_evidence_and_returns_only_the_final_selection(
    final_decision, provisional_decision, profile
):
    module = two_stage_module()
    from evals.runners.ollama_evidence_first_probe import EvidenceFirstProbeProvider

    evidence = (
        GenerationEvidence("E1", "Le kit contient un guide."),
        GenerationEvidence("E2", "Le lot exige trois pièces. Deux suffisent avec accord écrit."),
    )
    provisional = {
        "decision": "ANSWER",
        "facts": [],
        "rules": [{"evidence_id": "E2", "quote": "Le lot exige trois pièces."}],
        "exceptions": [],
        "refusal_reason": None,
    }
    final = {
        **provisional,
        "exceptions": [{"evidence_id": "E2", "quote": evidence[1].content}],
    }
    if final_decision == "REFUSAL":
        final.update(
            decision="REFUSAL", rules=[], exceptions=[], refusal_reason="INSUFFICIENT_EVIDENCE"
        )
    if provisional_decision == "REFUSAL":
        provisional = {
            "decision": "REFUSAL",
            "facts": [],
            "rules": [],
            "exceptions": [],
            "refusal_reason": "INSUFFICIENT_EVIDENCE",
        }
    calls = []

    async def endpoint(request):
        if request.url.path == "/api/tags":
            return httpx.Response(
                200, json={"models": [{"name": "gpt-oss:20b", "digest": "b" * 64}]}
            )
        payload = json.loads(request.content)
        calls.append(payload)
        assert payload["model"] == "gpt-oss:20b"
        assert payload["think"] == "medium"
        assert payload["options"] == {
            "num_ctx": 4096,
            "num_predict": 1024,
            "temperature": 0,
            "seed": 105,
        }
        user = json.loads(payload["messages"][1]["content"])
        assert user["current_question"] == "Combien de pièces faut-il?"
        assert user["evidence"] == [
            {"evidence_id": item.evidence_id, "content": item.content} for item in evidence
        ]
        if len(calls) == 2:
            assert user["untrusted_provisional_selection"] == provisional
        return httpx.Response(
            200,
            json={
                "model": "gpt-oss:20b",
                "done": True,
                "done_reason": "stop",
                "prompt_eval_count": 500,
                "eval_count": 90 if len(calls) == 1 else 120,
                "message": {
                    "content": json.dumps(provisional if len(calls) == 1 else final),
                    "thinking": "PRIVATE_STAGE_THINKING",
                },
            },
        )

    async def scenario():
        transport = module.TwoStageProbeTransport(
            inner=httpx.MockTransport(endpoint),
            context_tokens=4096,
            sampling_profile=profile,
        )
        async with httpx.AsyncClient(transport=transport, trust_env=False) as client:
            provider = EvidenceFirstProbeProvider(
                base_url="http://127.0.0.1:11435",
                model="gpt-oss:20b",
                expected_digest="sha256:" + "b" * 64,
                sampling_profile=profile,
                client=client,
            )
            result = await provider.generate(
                question="Combien de pièces faut-il?", evidence=evidence
            )
        assert result.decision == final_decision
        assert result.answer == (
            (
                ("Le lot exige trois pièces. " if not profile.endswith("dedup-v1") else "")
                + "Le lot exige trois pièces. Deux suffisent avec accord écrit. [[E2]]"
            )
            if final_decision == "ANSWER"
            else None
        )
        assert result.usage == {"prompt_tokens": 1000, "completion_tokens": 210}
        assert result.prompt_version == (
            "ollama-evidence-first-gpt-two-stage-dedup-v1"
            if profile.endswith("dedup-v1")
            else "ollama-evidence-first-gpt-two-stage-v1"
        )
        assert len(calls) == len(transport.observations) == 2
        assert [row["stage"] for row in transport.observations] == ["EXTRACT", "AUDIT"]
        assert "PRIVATE_STAGE_THINKING" not in repr(result) + json.dumps(transport.observations)
        assert "Le lot" not in json.dumps(transport.observations)

    asyncio.run(scenario())


@pytest.mark.parametrize("stage", [1, 2])
@pytest.mark.parametrize(
    "profile", ["gpt-oss-extraction-two-stage-v1", "gpt-oss-extraction-two-stage-dedup-v1"]
)
@pytest.mark.parametrize(
    "fault",
    [
        "invalid_quote",
        "truncated",
        "over_budget",
        "wrong_model",
        "rewritten_fact",
        "prompt_overflow",
        "boolean_usage",
        "http_failure",
    ],
)
def test_invalid_stage_fails_without_retry_or_refusal(stage, fault, profile):
    module = two_stage_module()
    from evals.runners.ollama_evidence_first_probe import EvidenceFirstProbeProvider

    calls = []

    async def endpoint(request):
        if request.url.path == "/api/tags":
            return httpx.Response(
                200, json={"models": [{"name": "gpt-oss:20b", "digest": "b" * 64}]}
            )
        calls.append(True)
        extraction = {
            "decision": "ANSWER",
            "facts": [{"evidence_id": "E1", "quote": "Label: Delta.", "text": "Label: Delta."}],
            "rules": [],
            "exceptions": [],
            "refusal_reason": None,
        }
        response = {
            "model": "gpt-oss:20b",
            "done_reason": "stop",
            "prompt_eval_count": 500,
            "eval_count": 60,
            "message": {"content": "", "thinking": "PRIVATE_FAILURE_THINKING"},
        }
        if len(calls) == stage:
            if fault == "http_failure":
                return httpx.Response(503, text="PRIVATE_HTTP_FAILURE")
            if fault == "invalid_quote":
                extraction["facts"][0]["quote"] = "PRIVATE_INVALID_QUOTE"
            elif fault == "rewritten_fact":
                extraction["facts"][0]["text"] = "Unsupported new claim"
            elif fault == "truncated":
                response["done_reason"] = "length"
            elif fault == "wrong_model":
                response["model"] = "another-model"
            elif fault == "prompt_overflow":
                response["prompt_eval_count"] = 3073
            elif fault == "boolean_usage":
                response["eval_count"] = True
            else:
                response["eval_count"] = 1025
        response["message"]["content"] = json.dumps(extraction)
        return httpx.Response(200, json=response)

    async def scenario():
        transport = module.TwoStageProbeTransport(
            inner=httpx.MockTransport(endpoint), context_tokens=4096, sampling_profile=profile
        )
        async with httpx.AsyncClient(transport=transport, trust_env=False) as client:
            provider = EvidenceFirstProbeProvider(
                base_url="http://127.0.0.1:11435",
                model="gpt-oss:20b",
                expected_digest="sha256:" + "b" * 64,
                sampling_profile=profile,
                client=client,
            )
            with pytest.raises(KnoraError) as error:
                await provider.generate(
                    question="What is the label?",
                    evidence=(GenerationEvidence("E1", "Label: Delta."),),
                )
        assert error.value.code == (
            "PROVIDER_REQUEST_FAILED" if fault == "http_failure" else "GENERATION_OUTPUT_INVALID"
        )
        assert len(calls) == stage
        assert "PRIVATE" not in str(error.value) + json.dumps(transport.observations)

    asyncio.run(scenario())
