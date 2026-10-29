from dataclasses import replace

import pytest

from knora.answering.answer_support import validate_projection, validate_support
from knora.domain.errors import KnoraError
from knora.providers.generation import GenerationEvidence
from knora.providers.openai_compatible.answer_blocks import compose_answer_projection


def case():
    evidence = (
        GenerationEvidence("E1", "A diagram is required. Explain its components and interactions."),
    )
    answer, _, projection = compose_answer_projection(
        {
            "decision": "ANSWER",
            "before": [{"text": "Phải có sơ đồ kiến trúc.", "support": ["E1"], "bold": None}],
            "items": [],
            "after": [],
            "refusal_reason": None,
        },
        evidence,
    )
    verdict = {
        "answer_digest": projection.answer_digest,
        "snapshot_digest": "snapshot",
        "statements": [
            {
                "id": "S1",
                "verdict": "SUPPORTED",
                "source_refs": [
                    {
                        "alias": "E1",
                        "exact_quote": "A diagram is required.",
                        "start": 0,
                        "end": 22,
                        "reason": "ENTAILMENT",
                    }
                ],
            }
        ],
        "groups": [{"id": "G1", "verdict": "ANSWERED", "statement_ids": ["S1"]}],
    }
    return answer, projection, evidence, verdict


def test_translated_paraphrase_is_valid_with_exact_source_proof():
    answer, projection, evidence, verdict = case()
    proof = validate_support(
        verdict,
        answer=answer,
        projection=projection,
        evidence=evidence,
        snapshot_digest="snapshot",
        group_ids=("G1",),
    )
    assert proof.answer_digest == projection.answer_digest


@pytest.mark.parametrize(
    "defect",
    [
        "unknown",
        "contradicted",
        "offset",
        "quote",
        "alias",
        "digest",
        "snapshot",
        "missing_statement",
        "duplicate_statement",
        "missing_group",
        "extra",
        "group_unknown",
        "unknown_statement",
        "empty_refs",
    ],
)
def test_invalid_proof_fails_closed(defect):
    answer, projection, evidence, verdict = case()
    statement = verdict["statements"][0]
    ref = statement["source_refs"][0]
    if defect in {"unknown", "contradicted"}:
        statement["verdict"] = defect.upper()
    elif defect == "offset":
        ref["start"] = 1
    elif defect == "quote":
        ref["exact_quote"] = "not in source"
    elif defect == "alias":
        ref["alias"] = "E2"
    elif defect == "digest":
        verdict["answer_digest"] = "other"
    elif defect == "snapshot":
        verdict["snapshot_digest"] = "other"
    elif defect == "missing_statement":
        verdict["statements"] = []
    elif defect == "duplicate_statement":
        verdict["statements"].append(statement)
    elif defect == "missing_group":
        verdict["groups"] = []
    elif defect == "extra":
        verdict["extra"] = True
    elif defect == "group_unknown":
        verdict["groups"][0]["verdict"] = "UNKNOWN"
    elif defect == "unknown_statement":
        verdict["groups"][0]["statement_ids"] = ["S2"]
    elif defect == "empty_refs":
        statement["source_refs"] = []
    with pytest.raises(KnoraError, match="GENERATION_OUTPUT_INVALID"):
        validate_support(
            verdict,
            answer=answer,
            projection=projection,
            evidence=evidence,
            snapshot_digest="snapshot",
            group_ids=("G1",),
        )


def test_projection_cannot_leave_factual_text_unchecked():
    answer, projection, evidence, _ = case()
    with pytest.raises(KnoraError):
        validate_projection(answer + " invented claim", projection, evidence)
    bad = replace(projection, statements=(replace(projection.statements[0], end=3),))
    with pytest.raises(KnoraError):
        validate_projection(answer, bad, evidence)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "defect", [None, "foreign_quote", "missing", "unknown", "timeout", "extra"]
)
async def test_cloudflare_wire_references_resolve_to_exact_unicode_source(defect):
    import json

    from knora.providers.cloudflare.answer_support import CloudflareAnswerSupportVerifier

    answer, projection, evidence, _ = case()
    calls = []

    async def complete(prompt):
        calls.append(prompt)
        if defect == "timeout":
            raise TimeoutError
        data = json.loads(prompt.messages[1]["content"])
        quote = next(q for q in data["evidence"] if "A diagram is required." in q["exact_quote"])
        wire = {
            "answer_digest": projection.answer_digest,
            "snapshot_digest": "snapshot",
            "statements": [
                {
                    "id": "S1",
                    "verdict": "SUPPORTED",
                    "source_refs": [{"quote_id": quote["quote_id"], "reason": "ENTAILMENT"}],
                }
            ],
            "groups": [{"id": "G1", "verdict": "ANSWERED", "statement_ids": ["S1"]}],
        }
        if defect == "foreign_quote":
            wire["statements"][0]["source_refs"][0]["quote_id"] = "E99:Q1"
        if defect == "missing":
            wire["groups"] = []
        if defect == "unknown":
            wire["statements"][0]["verdict"] = "UNKNOWN"
        if defect == "extra":
            wire["rewrite"] = "invented answer"
        return wire, {"provider": "cloudflare-workers-ai"}

    verifier = CloudflareAnswerSupportVerifier(complete)
    kwargs = dict(
        question="Sơ đồ có bắt buộc không?",
        groups=(("G1", "Sơ đồ có bắt buộc không?"),),
        answer=answer,
        answer_projection=projection,
        evidence=evidence,
        snapshot_digest="snapshot",
    )
    if defect:
        with pytest.raises(
            KnoraError,
            match="PROVIDER_REQUEST_FAILED" if defect == "timeout" else "GENERATION_OUTPUT_INVALID",
        ):
            await verifier.verify(**kwargs)
    else:
        proof, _ = await verifier.verify(**kwargs)
        assert (
            "exact_quote" in proof.verdict_json and "A diagram is required." in proof.verdict_json
        )
    assert len(calls) == 1


def test_each_list_item_retains_own_support_despite_coalesced_markers():
    evidence = (GenerationEvidence("E1", "Fact one."), GenerationEvidence("E2", "Fact two."))
    answer, cited, projection = compose_answer_projection(
        {
            "decision": "ANSWER",
            "before": [],
            "items": [
                {"text": "Fact one.", "support": ["E1"]},
                {"text": "Fact two.", "support": ["E2"]},
            ],
            "after": [],
            "refusal_reason": None,
        },
        evidence,
    )
    assert cited == ("E1", "E2")
    assert [s.aliases for s in projection.statements] == [("E1",), ("E2",)]
    validate_projection(answer, projection, evidence)


@pytest.mark.parametrize(
    "claim,source,valid",
    [
        ("70 ngày", "7 ngày", False),
        ("1 tuần", "7 ngày", True),
        ("7 ngày", "1 tuần", True),
        ("7 tháng", "1 tháng", False),
        ("12/03/2024", "03/12/2024", False),
        ("2024-12-03", "03/12/2024", True),
        ("Mã C2", "Mã C20", False),
        ("Mã C20", "Mã C20", True),
    ],
)
def test_provable_fact_mismatch_cannot_be_overridden_by_model(claim, source, valid):
    from knora.answering.answer_support import _validate_explicit_facts

    if valid:
        _validate_explicit_facts(claim, source)
    else:
        with pytest.raises(ValueError):
            _validate_explicit_facts(claim, source)


@pytest.mark.parametrize(
    "question,parts",
    [
        ("Sơ đồ có bắt buộc không, và cần trình bày những gì kèm sơ đồ?", 2),
        ("Is the diagram required and what must accompany it?", 2),
        ("What are frontend and backend?", 1),
        ("So sánh chương 2 và chương 3", 1),
    ],
)
def test_verification_retains_each_coordinated_question(question, parts):
    from knora.answering.answer_support import required_answer_groups

    groups = required_answer_groups((("sub_1", question),))
    assert len(groups) == parts


def test_grounded_renderer_owns_formatting_and_preserves_singleton_fact():
    from knora.providers.openai_compatible.answer_blocks import compose_grounded_answer

    evidence = (GenerationEvidence("E1", "Không chụp IDE. Copy và định dạng mã nguồn."),)
    payload = {
        "decision": "ANSWER",
        "before": [{"text": "Không chụp màn hình IDE.", "support": ["E1"]}],
        "items": [{"text": "Copy mã nguồn\nvà định dạng văn bản.", "support": ["E1"]}],
        "after": [],
        "refusal_reason": None,
    }
    answer, cited, projection = compose_grounded_answer(payload, evidence)
    assert answer == "Không chụp màn hình IDE.\n\nCopy mã nguồn và định dạng văn bản. [[E1]]"
    assert cited == ("E1",)
    assert [s.text for s in projection.statements] == [
        "Không chụp màn hình IDE.",
        "Copy mã nguồn và định dạng văn bản.",
    ]
    validate_projection(answer, projection, evidence)


def test_grounded_schema_has_no_model_selected_emphasis():
    from knora.providers.prompts.builder import build_prompt

    prompt = build_prompt("cloudflare-grounded-answer", question="Bao nhiêu chương?", evidence=())
    assert prompt.definition.version == "cloudflare-gpt-oss-cited-answer-v23"
    assert "bold" not in str(prompt.definition.schema)
    assert "null" not in str(prompt.definition.schema["$defs"]["_Statement"])
