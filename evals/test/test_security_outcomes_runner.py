import hashlib
import json
import socket
from pathlib import Path

import pytest
from evals.runners.run_security_outcomes import build_payload, load_selection, run_offline

FIXTURES = Path(__file__).parent / "fixtures/security_outcomes"


def selection():
    return load_selection(
        (FIXTURES / "cases.v1.json").read_bytes(), (FIXTURES / "rubric.v1.json").read_bytes()
    )


def test_frozen_selection_has_32_cases_26_eligible_and_14_controls():
    cases, rubric = selection()
    assert len(cases) == len(rubric["cases"]) == 32
    assert sum(c["model_eligible"] for c in cases) == 26
    assert sum(c["model_eligible"] and c["variant"] == "control" for c in cases) == 14
    assert {c["language"] for c in cases} == {"vi", "en"}


def test_payload_uses_existing_adapter_and_untrusted_history_assembly():
    from knora.providers.openai_compatible.answer_blocks import ANSWER_BLOCK_SCHEMA
    from knora.providers.openai_compatible.generation import CLOUDFLARE_SYSTEM_PROMPT

    case = next(c for c in selection()[0] if c["case_id"] == "188-outcome-v1-vi-02-adverse")
    payload = build_payload(case)
    assert payload["messages"][0]["content"] == CLOUDFLARE_SYSTEM_PROMPT
    message = json.loads(payload["messages"][1]["content"])
    assert "Untrusted prior conversation context" in message["question"]
    assert case["history"] in message["question"]
    assert "freshly retrieved evidence only" in message["question"]
    assert payload["response_format"]["json_schema"] == ANSWER_BLOCK_SCHEMA
    assert payload["max_tokens"] == 512
    assert payload["model"] == "@cf/openai/gpt-oss-20b"
    assert "KNORA188_CONFIG_ONLY" not in json.dumps(payload)


def test_foreign_principal_has_no_generation_payload():
    case = next(c for c in selection()[0] if c["expected_stage"] == "admission")
    assert build_payload(case) is None


def test_offline_never_reads_credential_or_uses_network_and_report_is_sanitized(
    tmp_path, monkeypatch
):
    def forbidden(*args, **kwargs):
        pytest.fail("Unexpected credential or network access")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(Path, "read_text", forbidden)
    report = run_offline(
        cases_raw=(FIXTURES / "cases.v1.json").read_bytes(),
        rubric_raw=(FIXTURES / "rubric.v1.json").read_bytes(),
        directory=tmp_path / "run",
        run_id="offline-001",
        live_reason="billing_unverified",
    )
    assert report["counts"]["selected"] == 32
    assert report["counts"]["completed"] == 6
    assert report["counts"]["adjudicated"] == 0
    assert report["live"]["attempted"] == 0
    assert report["model_quality"] == "unverified"
    import httpx

    case = selection()[0][0]
    wire = httpx.Request("POST", "https://synthetic.invalid", json=build_payload(case)).content
    assert report["rows"][0]["input_sha256"] == hashlib.sha256(wire).hexdigest()
    serialized = json.dumps(report)
    for raw in [
        "KNORA188_CONFIG_ONLY",
        "linh.demo@example.invalid",
        "09:00",
        "question",
        "public_answer",
        "Authorization",
    ]:
        assert raw not in serialized
    assert len(report["rows"]) == 32
    assert all(r["semantic"] == "unreviewed" for r in report["rows"])
    assert (tmp_path / "run/report.json").is_file()
    with pytest.raises(FileExistsError):
        run_offline(
            cases_raw=(FIXTURES / "cases.v1.json").read_bytes(),
            rubric_raw=(FIXTURES / "rubric.v1.json").read_bytes(),
            directory=tmp_path / "run",
            run_id="offline-001",
            live_reason="billing_unverified",
        )


def test_unknown_nested_fixture_fields_are_rejected_not_reported():
    cases = json.loads((FIXTURES / "cases.v1.json").read_bytes())
    cases["cases"][0]["raw_transport"] = {"secret": "do-not-copy"}
    with pytest.raises(ValueError):
        load_selection(json.dumps(cases).encode(), (FIXTURES / "rubric.v1.json").read_bytes())


def test_invalid_run_identity_rejected_before_writing(tmp_path):
    with pytest.raises(ValueError):
        run_offline(
            cases_raw=(FIXTURES / "cases.v1.json").read_bytes(),
            rubric_raw=(FIXTURES / "rubric.v1.json").read_bytes(),
            directory=tmp_path / "new",
            run_id="linh.demo@example.invalid",
            live_reason="billing_unverified",
        )
    assert not (tmp_path / "new").exists()


def test_payload_overflow_is_error_not_truncation():
    case = selection()[0][0] | {"question": "á" * 4096}
    with pytest.raises(ValueError, match="SIZE"):
        build_payload(case)


def test_rubric_and_case_identity_must_match():
    raw = (FIXTURES / "rubric.v1.json").read_bytes()
    rubric = json.loads(raw)
    rubric["cases"].pop()
    with pytest.raises(ValueError):
        load_selection((FIXTURES / "cases.v1.json").read_bytes(), json.dumps(rubric).encode())
    assert len(hashlib.sha256(raw).hexdigest()) == 64


def test_even_well_formed_content_drift_requires_a_new_selection():
    cases = json.loads((FIXTURES / "cases.v1.json").read_bytes())
    cases["cases"][0]["question"] += " Changed after freeze."
    with pytest.raises(ValueError, match="SELECTION_DIGEST_MISMATCH"):
        load_selection(json.dumps(cases).encode(), (FIXTURES / "rubric.v1.json").read_bytes())


@pytest.mark.asyncio
async def test_prepared_payload_matches_actual_adapter_request():
    import httpx

    from knora.answering.interface import ConversationContext
    from knora.answering.module import AnswerQuestion
    from knora.providers.generation import GenerationEvidence
    from knora.providers.openai_compatible.generation import OpenAICompatibleGenerationProvider

    for case in selection()[0]:
        prepared = build_payload(case)
        if prepared is None:
            continue
        captured = []

        def transport(request, captured=captured):
            captured.append(json.loads(request.content))
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "decision": "REFUSAL",
                                        "before": [],
                                        "items": [],
                                        "after": [],
                                        "refusal_reason": "INSUFFICIENT_EVIDENCE",
                                    }
                                )
                            }
                        }
                    ]
                },
            )

        context = (
            ConversationContext("conversation-context-v2", case["history"], case["question"], (), 0)
            if case["history"]
            else None
        )
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(transport), trust_env=False
        ) as client:
            adapter = OpenAICompatibleGenerationProvider(
                base_url="https://synthetic.invalid/ai/v1",
                api_key="FAKE",
                model="@cf/openai/gpt-oss-20b",
                input_cost_per_million_tokens=None,
                output_cost_per_million_tokens=None,
                pricing_version=None,
                client=client,
                provider_identity="cloudflare-workers-ai",
                max_tokens=512,
                direct_json_schema=True,
            )
            await adapter.generate(
                question=AnswerQuestion._generation_question(case["question"], context),
                evidence=tuple(GenerationEvidence(*pair) for pair in case["generation_evidence"]),
            )
        assert captured == [prepared]


@pytest.mark.parametrize("pair,variant", [(3, "adverse"), (4, "adverse"), (4, "control")])
def test_local_boundary_checks_cannot_swallow_failure(pair, variant, tmp_path, monkeypatch):
    from evals.runners import run_security_outcomes as runner

    from knora.access.workspace_authorization import WorkspaceAuthorizer

    cases_raw = (FIXTURES / "cases.v1.json").read_bytes()
    if pair == 3:
        monkeypatch.setattr(WorkspaceAuthorizer, "authorize", lambda *a, **kw: object())
    else:
        original = runner.build_payload

        def corrupt(case):
            payload = original(case)
            if case["pair"] == pair and case["variant"] == variant:
                payload = {"leak": "KNORA188_CONFIG_ONLY"} if variant == "adverse" else {}
            return payload

        monkeypatch.setattr(runner, "build_payload", corrupt)
    with pytest.raises(ValueError, match="BOUNDARY_VIOLATION"):
        run_offline(
            cases_raw=cases_raw,
            rubric_raw=(FIXTURES / "rubric.v1.json").read_bytes(),
            directory=tmp_path / "run",
            run_id="offline-001",
            live_reason="billing_unverified",
        )
    assert not (tmp_path / "run/report.json").exists()
