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


def _inventory_fixture(data, facts=("A diagram is required.",)):
    return {
        "snapshot_digest": data["snapshot_digest"],
        "groups": [
            {"id": g["id"], "facts": [{"fact": f, "quote_ids": ["E1:Q1"]} for f in facts]}
            for g in data["groups"]
        ],
    }


def _audit_fixture(data):
    ids = [s["id"] for s in data["statements"]]
    return {
        "answer_digest": data["answer_digest"],
        "snapshot_digest": data["snapshot_digest"],
        "statements": [
            {
                "id": s["id"],
                "verdict": "SUPPORTED",
                "source_refs": [{"quote_id": s["aliases"][0] + ":Q1", "reason": "ENTAILMENT"}],
            }
            for s in data["statements"]
        ],
        "groups": [
            {"id": g["id"], "verdict": "ANSWERED", "statement_ids": ids} for g in data["groups"]
        ],
        "coverage": [
            {
                "id": f["id"],
                "answer_quotes": [s["text"] for s in data["statements"]],
                "statement_ids": ids,
                "covered": True,
            }
            for f in data["required_facts"]
        ],
    }


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
    "source,claim,valid",
    [
        ("Không\nnên xuất dữ liệu riêng tư.", "Không được xuất dữ liệu riêng tư.", False),
        ("Không được xóa nguồn. Không nên xuất dữ liệu.", "Không được xuất dữ liệu.", False),
        ("You should not share passwords.", "You must not share passwords.", False),
        ("Không nên xuất dữ liệu.", "Không nên xuất dữ liệu.", True),
        ("Không được xuất dữ liệu.", "Không được xuất dữ liệu.", True),
        ("You must not share passwords.", "You must not share passwords.", True),
        (
            "Không nên xuất dữ liệu. Quy định bảo mật: Không được xuất dữ liệu.",
            "Không được xuất dữ liệu.",
            True,
        ),
    ],
)
def test_model_cannot_strengthen_recommendation_about_same_action(source, claim, valid):
    evidence = (GenerationEvidence("E1", source),)
    answer, _, projection = compose_answer_projection(
        {
            "decision": "ANSWER",
            "before": [{"text": claim, "support": ["E1"], "bold": None}],
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
                        "exact_quote": source,
                        "start": 0,
                        "end": len(source),
                        "reason": "ENTAILMENT",
                    }
                ],
            }
        ],
        "groups": [{"id": "G1", "verdict": "ANSWERED", "statement_ids": ["S1"]}],
    }
    kwargs = dict(
        answer=answer,
        projection=projection,
        evidence=evidence,
        snapshot_digest="snapshot",
        group_ids=("G1",),
    )
    if valid:
        validate_support(verdict, **kwargs)
    else:
        with pytest.raises(KnoraError, match="GENERATION_OUTPUT_INVALID"):
            validate_support(verdict, **kwargs)


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
        data = json.loads(prompt.messages[1]["content"])
        calls.append(data)
        if prompt.definition.serializer_id == "source-inventory-v1":
            return _inventory_fixture(data), {}
        assert prompt.definition.schema["properties"]["answer_digest"]["enum"] == [
            projection.answer_digest
        ]
        assert prompt.definition.schema["properties"]["snapshot_digest"]["enum"] == ["snapshot"]
        if defect == "timeout":
            raise TimeoutError
        wire = _audit_fixture(data)
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
        question="Is a diagram required?",
        groups=(("G1", "Is a diagram required?"),),
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
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_required_source_inventory_is_blind_to_candidate_answer():
    import json

    from knora.answering.answer_support import AnswerSupportFailure
    from knora.providers.cloudflare.answer_support import CloudflareAnswerSupportVerifier

    answer, projection, evidence, _ = case()
    seen = []

    async def complete(prompt):
        data = json.loads(prompt.messages[1]["content"])
        seen.append(data)
        if prompt.definition.serializer_id == "source-inventory-v1":
            assert "answer" not in data and "statements" not in data and "checks" not in data
            return {
                "snapshot_digest": "snapshot",
                "groups": [
                    {
                        "id": "G1",
                        "facts": [
                            {"fact": "A diagram is required.", "quote_ids": ["E1:Q1"]},
                            {"fact": "Its components must be explained.", "quote_ids": ["E1:Q1"]},
                        ],
                    }
                ],
            }, {"provider_request_id": "blind-inventory"}
        return {
            "answer_digest": projection.answer_digest,
            "snapshot_digest": "snapshot",
            "statements": [
                {
                    "id": "S1",
                    "verdict": "SUPPORTED",
                    "source_refs": [{"quote_id": "E1:Q1", "reason": "ENTAILMENT"}],
                }
            ],
            "groups": [{"id": "G1", "verdict": "ANSWERED", "statement_ids": ["S1"]}],
            "coverage": [
                {
                    "id": "G1:F1",
                    "answer_quotes": [projection.statements[0].text],
                    "statement_ids": ["S1"],
                    "covered": True,
                },
                {
                    "id": "G1:F2",
                    "answer_quotes": [],
                    "statement_ids": [],
                    "covered": False,
                },
            ],
        }, {"provider_request_id": "independent-audit"}

    with pytest.raises(AnswerSupportFailure) as caught:
        await CloudflareAnswerSupportVerifier(complete).verify(
            question="What must be included?",
            groups=(("G1", "What must be included?"),),
            answer=answer,
            answer_projection=projection,
            evidence=evidence,
            snapshot_digest="snapshot",
        )
    assert len(seen) == 2
    assert caught.value.observation["failure"] == "unsupported_answer"
    assert caught.value.observation["failed_id"] == "G1"


@pytest.mark.asyncio
async def test_required_fact_can_be_covered_across_multiple_answer_statements():
    import json

    from knora.providers.cloudflare.answer_support import CloudflareAnswerSupportVerifier

    evidence = (GenerationEvidence("E1", "The caption is italic and centered."),)
    answer, _, projection = compose_answer_projection(
        dict(
            decision="ANSWER",
            before=[],
            items=[
                dict(text="The caption is italic.", support=["E1"]),
                dict(text="The caption is centered.", support=["E1"]),
            ],
            after=[],
            refusal_reason=None,
        ),
        evidence,
    )

    async def complete(prompt):
        data = json.loads(prompt.messages[1]["content"])
        if prompt.definition.serializer_id == "source-inventory-v1":
            return _inventory_fixture(data, ("The caption is italic and centered.",)), {}
        wire = _audit_fixture(data)
        wire["coverage"][0]["answer_quotes"] = [
            "The caption is italic.",
            "The caption is centered.",
        ]
        return wire, {}

    proof, _ = await CloudflareAnswerSupportVerifier(complete).verify(
        question="How is the caption formatted?",
        groups=(("G1", "How is the caption formatted?"),),
        answer=answer,
        answer_projection=projection,
        evidence=evidence,
        snapshot_digest="snapshot",
    )
    assert proof.answer_digest == projection.answer_digest


@pytest.mark.asyncio
async def test_coverage_can_quote_rendered_bold_text_from_its_statement():
    import json

    from knora.providers.cloudflare.answer_support import CloudflareAnswerSupportVerifier

    evidence = (GenerationEvidence("E1", "Seven chapters are suggested."),)
    answer, _, projection = compose_answer_projection(
        dict(
            decision="ANSWER",
            before=[
                dict(text="Seven chapters are suggested.", support=["E1"], bold="Seven chapters")
            ],
            items=[],
            after=[],
            refusal_reason=None,
        ),
        evidence,
    )

    async def complete(prompt):
        data = json.loads(prompt.messages[1]["content"])
        if prompt.definition.serializer_id == "source-inventory-v1":
            return _inventory_fixture(data, ("Seven chapters are suggested.",)), {}
        wire = _audit_fixture(data)
        wire["coverage"][0]["answer_quotes"] = ["**Seven chapters** are suggested."]
        return wire, {}

    proof, _ = await CloudflareAnswerSupportVerifier(complete).verify(
        question="How many chapters?",
        groups=(("G1", "How many chapters?"),),
        answer=answer,
        answer_projection=projection,
        evidence=evidence,
        snapshot_digest="snapshot",
    )
    assert proof.answer_digest == projection.answer_digest


@pytest.mark.asyncio
async def test_verifier_cannot_invent_answer_text_to_cover_a_missing_fact():
    import json

    from knora.providers.cloudflare.answer_support import CloudflareAnswerSupportVerifier

    answer, projection, evidence, _ = case()

    async def complete(prompt):
        data = json.loads(prompt.messages[1]["content"])
        if prompt.definition.serializer_id == "source-inventory-v1":
            return _inventory_fixture(data), {}
        wire = _audit_fixture(data)
        wire["coverage"][0]["answer_quotes"] = [
            "The answer explains all components and interactions."
        ]
        return wire, {}

    with pytest.raises(KnoraError, match="GENERATION_OUTPUT_INVALID"):
        await CloudflareAnswerSupportVerifier(complete).verify(
            question="What must be included?",
            groups=(("G1", "What must be included?"),),
            answer=answer,
            answer_projection=projection,
            evidence=evidence,
            snapshot_digest="snapshot",
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("unicode_context", [False, True])
async def test_independent_audit_rejects_supported_subset_of_requested_contents(unicode_context):
    import json

    from knora.answering.answer_support import AnswerSupportFailure
    from knora.providers.cloudflare.answer_support import CloudflareAnswerSupportVerifier

    answer, projection, evidence, _ = case()
    evidence += (GenerationEvidence("E2", "Include a diagram AND describe its components."),)
    if unicode_context:
        evidence += (GenerationEvidence("E3", "Ngữ cảnh bổ sung " * 750),)

    async def complete(prompt):
        data = json.loads(prompt.messages[1]["content"])
        assert {e["alias"] for e in data["sources"]} == {e.evidence_id for e in evidence}
        if prompt.definition.serializer_id == "source-inventory-v1":
            assert "answer" not in data and "recovery_feedback" not in data
            return _inventory_fixture(
                data, ("A diagram is required.", "Describe the diagram's components.")
            ), {}
        wire = _audit_fixture(data)
        wire["coverage"][1].update(covered=False, statement_ids=[], answer_quotes=[])
        return wire, {}

    with pytest.raises(AnswerSupportFailure) as caught:
        await CloudflareAnswerSupportVerifier(complete).verify(
            question="What must be included?",
            groups=(("G1", "What must be included?"),),
            answer=answer,
            answer_projection=projection,
            evidence=evidence,
            snapshot_digest="snapshot",
        )
    assert caught.value.observation["failure"] == "unsupported_answer"
    assert caught.value.observation["failed_id"] == "G1"
    assert caught.value.observation["source_facts"] == [
        {"id": "G1", "source_fact": "Describe the diagram's components."}
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("entailed", [False, True])
async def test_quote_selection_does_not_override_independent_claim_entailment(entailed):
    import json

    from knora.answering.answer_support import AnswerSupportFailure
    from knora.providers.cloudflare.answer_support import CloudflareAnswerSupportVerifier

    source = "System A must serve 1000 users."
    evidence = (GenerationEvidence("E1", source),)
    answer, _, projection = compose_answer_projection(
        dict(
            decision="ANSWER",
            before=[dict(text="System B must serve 1000 users.", support=["E1"], bold=None)],
            items=[],
            after=[],
            refusal_reason=None,
        ),
        evidence,
    )
    calls = []

    async def complete(prompt):
        data = json.loads(prompt.messages[1]["content"])
        calls.append(data)
        if prompt.definition.serializer_id == "source-inventory-v1":
            assert "answer" not in data
            return _inventory_fixture(data, (source,)), {"provider_request_id": "source-inventory"}
        wire = _audit_fixture(data)
        if not entailed:
            wire["statements"][0]["verdict"] = "UNKNOWN"
        return wire, {"provider_request_id": "scope-check"}

    verifier = CloudflareAnswerSupportVerifier(complete)
    kwargs = dict(
        question="How many users?",
        groups=(("G1", "How many users?"),),
        answer=answer,
        answer_projection=projection,
        evidence=evidence,
        snapshot_digest="snapshot",
    )
    if entailed:
        proof, metadata = await verifier.verify(**kwargs)
        assert proof.answer_digest == projection.answer_digest
        assert metadata["entailment"]["provider"]["provider_request_id"] == "scope-check"
    else:
        with pytest.raises(AnswerSupportFailure) as caught:
            await verifier.verify(**kwargs)
        assert caught.value.observation["failure"] == "unsupported_answer"
        assert caught.value.observation["failed_id"] == "S1"
        assert (
            caught.value.observation["provider"]["result"]["groups"][0]["facts"][0]["fact"]
            == source
        )
    assert len(calls) == 2


def test_entailment_context_preserves_unselected_text_and_overlapping_quote_boundaries():
    from knora.providers.cloudflare.answer_support import _entailment_sources

    evidence = (GenerationEvidence("E1", "Ví dụ: A. B.\nC."), GenerationEvidence("E2", "Context."))
    quotes = {
        "E1:Q1": {"alias": "E1", "start": 7, "end": 9},
        "E1:Q2": {"alias": "E1", "start": 7, "end": 12},
        "E1:Q3": {"alias": "E1", "start": 13, "end": 15},
    }
    assert _entailment_sources(evidence, quotes, {"E1:Q1", "E1:Q2"}) == [
        {
            "alias": "E1",
            "passages": [
                {"text": "Ví dụ: ", "quote_ids": []},
                {"text": "A.", "quote_ids": ["E1:Q1", "E1:Q2"]},
                {"text": " B.", "quote_ids": ["E1:Q2"]},
                {"text": "\nC.", "quote_ids": []},
            ],
        },
        {"alias": "E2", "passages": [{"text": "Context.", "quote_ids": []}]},
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "defect",
    ["missing", "duplicate", "foreign", "timeout", "stale", "cancel", "stale_after_entailment"],
)
async def test_entailment_cannot_deliver_an_incomplete_proof_or_cross_snapshot(defect):
    import asyncio
    import json

    from knora.providers.cloudflare.answer_support import CloudflareAnswerSupportVerifier

    answer, projection, evidence, _ = case()
    calls = []

    async def complete(prompt):
        data = json.loads(prompt.messages[1]["content"])
        calls.append(data)
        if prompt.definition.serializer_id == "source-inventory-v1":
            return _inventory_fixture(data), {"provider_request_id": "completed-quote-selection"}
        if defect == "cancel":
            raise asyncio.CancelledError
        if defect == "timeout":
            raise TimeoutError
        wire = _audit_fixture(data)
        if defect == "missing":
            wire["statements"] = []
        if defect == "duplicate":
            wire["statements"] *= 2
        if defect == "foreign":
            wire["statements"][0]["id"] = "foreign"
        return wire, {"provider_request_id": "completed-entailment"}

    def revalidate():
        if defect == "stale" or (defect == "stale_after_entailment" and len(calls) == 2):
            raise KnoraError("LEXICAL_RETRIEVAL_UNAVAILABLE")

    with pytest.raises(
        asyncio.CancelledError if defect == "cancel" else KnoraError,
        match={
            "timeout": "PROVIDER_REQUEST_FAILED",
            "stale": "LEXICAL_RETRIEVAL_UNAVAILABLE",
            "stale_after_entailment": "LEXICAL_RETRIEVAL_UNAVAILABLE",
        }.get(defect, None if defect == "cancel" else "GENERATION_OUTPUT_INVALID"),
    ) as caught:
        await CloudflareAnswerSupportVerifier(complete).verify(
            question="Required?",
            groups=(("G1", "Required?"),),
            answer=answer,
            answer_projection=projection,
            evidence=evidence,
            snapshot_digest="snapshot",
            revalidate=revalidate,
        )
    assert len(calls) == (0 if defect == "stale" else 2)
    if defect == "cancel":
        assert (
            caught.value.observation["provider"]["provider_request_id"]
            == "completed-quote-selection"
        )
    if defect == "stale_after_entailment":
        assert (
            caught.value.observation["provider"]["entailment"]["provider"]["provider_request_id"]
            == "completed-entailment"
        )


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
    "claim,source,valid",
    [
        ("Báo cáo bắt buộc có 12 trang.", "HƯỚNG DẪN BÁO CÁO - TRANG 1/12", False),
        ("The report must have 48 pages.", "Writing guide — Page 2 of 48", False),
        ("Tài liệu hướng dẫn có 12 trang.", "HƯỚNG DẪN BÁO CÁO - TRANG 1/12", True),
        ("Báo cáo bắt buộc có 12 trang.", "Báo cáo phải có 12 trang.\nTRANG 1/20", True),
        ("Báo cáo bắt buộc có 12 trang.", "Báo cáo phải có mười hai trang.\nTRANG 1/12", True),
        ("Báo cáo bắt buộc có 12 trang.", "Báo cáo phải có 20 trang.\nTRANG 1/12", False),
        ("Ví dụ hình 1.2, bảng 3.1.", "Caption cần được đánh số.", False),
        ("Ví dụ hình 1.2, bảng 3.1.", "Ví dụ hình 1.2, bảng 3.1.", True),
        ("For example figure 1.2, table 3.1.", "Ví dụ hình 1.2, bảng 3.1.", True),
        (
            "Ứng dụng bắt buộc phục vụ 1000 người dùng.",
            "Ví dụ: “Ứng dụng phải phục vụ 1000 người dùng.”",
            False,
        ),
        (
            "Ví dụ: Ứng dụng phải phục vụ 1000 người dùng.",
            "Ví dụ: “Ứng dụng phải phục vụ 1000 người dùng.”",
            True,
        ),
        (
            "Ứng dụng phải phục vụ 1000 người dùng.",
            "Ứng dụng phải phục vụ 1000 người dùng. Ví dụ: giao diện đăng nhập.",
            True,
        ),
        (
            "Không bắt buộc mọi đề tài phải phục vụ 1000 người dùng.",
            "Ví dụ: Ứng dụng phải phục vụ 1000 người dùng.",
            True,
        ),
    ],
)
def test_layout_counters_and_missing_example_values_cannot_prove_a_claim(claim, source, valid):
    from knora.answering.answer_support import _validate_explicit_facts

    if valid:
        _validate_explicit_facts(claim, source)
    else:
        with pytest.raises(ValueError):
            _validate_explicit_facts(claim, source)


@pytest.mark.parametrize(
    "claim,source,detail",
    [
        ("Báo cáo bắt buộc có 12 trang.", "HƯỚNG DẪN - TRANG 1/12", "pagination"),
        (
            "Ứng dụng phải phục vụ 1000 người dùng.",
            "Ví dụ: Ứng dụng phải phục vụ 1000 người dùng.",
            "example",
        ),
        ("Ví dụ hình 1.2.", "Caption phải đánh số.", "identifiers"),
    ],
)
def test_fact_rejection_explains_what_recovery_must_correct(claim, source, detail):
    from knora.answering.answer_support import AnswerSupportFailure

    evidence = (GenerationEvidence("E1", source),)
    answer, _, projection = compose_answer_projection(
        dict(
            decision="ANSWER",
            before=[dict(text=claim, support=["E1"], bold=None)],
            items=[],
            after=[],
            refusal_reason=None,
        ),
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
                    dict(
                        alias="E1",
                        exact_quote=source,
                        start=0,
                        end=len(source),
                        reason="ENTAILMENT",
                    )
                ],
            }
        ],
        "groups": [{"id": "G1", "verdict": "ANSWERED", "statement_ids": ["S1"]}],
    }
    with pytest.raises(AnswerSupportFailure) as caught:
        validate_support(
            verdict,
            answer=answer,
            projection=projection,
            evidence=evidence,
            snapshot_digest="snapshot",
            group_ids=("G1",),
        )
    assert caught.value.observation["failure"] == "unsupported_answer"
    assert detail in caught.value.observation["fact_mismatch"]


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


@pytest.mark.parametrize(
    "question",
    [
        "Báo cáo được gợi ý bao nhiêu chương, và báo cáo quy mô nhỏ có thể đổi cấu trúc thế nào?",
        "How many chapters are suggested, and a small report can change its structure how?",
    ],
)
def test_subject_before_second_predicate_keeps_both_required_questions(question):
    from knora.answering.answer_support import required_answer_groups

    groups = required_answer_groups((("question", question),))
    assert len(groups) == 2
    assert "small report" in groups[1][1] or "báo cáo quy mô nhỏ" in groups[1][1]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "outcome",
    [
        "INSUFFICIENT",
        "ANSWERABLE",
        "UNKNOWN",
        "duplicate",
        "foreign",
        "quote",
        "digest",
        "timeout",
        "missing_reason",
        "contradiction",
        "no_refs",
    ],
)
async def test_source_sufficiency_checks_all_evidence_and_fails_closed(outcome):
    import json

    from knora.providers.cloudflare.answer_support import CloudflareAnswerSupportVerifier

    ev = (
        GenerationEvidence("E1", "Writing guide: PAGE 1/12"),
        GenerationEvidence("E2", "Reports must have at least 20 pages."),
    )

    async def complete(prompt):
        data = json.loads(prompt.messages[1]["content"])
        assert "answer" not in data and "previous_answer" not in data
        assert [e["alias"] for e in data["evidence"]] == ["E1", "E2"]
        assert [e["passages"][0]["text"] for e in data["evidence"]] == [
            ev[0].content,
            ev[1].content,
        ]
        if outcome == "timeout":
            raise TimeoutError
        item = {
            "id": "foreign" if outcome == "foreign" else "G1",
            "status": outcome
            if outcome in {"INSUFFICIENT", "ANSWERABLE", "UNKNOWN"}
            else "ANSWERABLE",
            "source_fact": "There is a substantive report-length requirement.",
            "source_refs": []
            if outcome == "no_refs"
            else ["E2:P1" if outcome != "quote" else "foreign:P1"],
            "missing_fact": "A required fact is missing."
            if outcome in {"INSUFFICIENT", "contradiction"}
            else "",
        }
        if outcome == "missing_reason":
            item["status"] = "INSUFFICIENT"
        return {
            "snapshot_digest": "wrong" if outcome == "digest" else "snapshot",
            "groups": [item, item] if outcome == "duplicate" else [item],
        }, {"provider_request_id": "sufficiency-receipt"}

    verifier = CloudflareAnswerSupportVerifier(complete)
    kwargs = dict(
        question="What is the required report length?",
        groups=(("G1", "What is the required report length?"),),
        evidence=ev,
        snapshot_digest="snapshot",
    )
    if outcome in {"INSUFFICIENT", "ANSWERABLE", "UNKNOWN"}:
        insufficient, metadata = await verifier.assess_sufficiency(**kwargs)
        assert insufficient == (outcome == "INSUFFICIENT")
        assert metadata["scope"] == "provided_evidence"
        assert metadata["coverage"] == "unverified"
        assert metadata["provider_request_id"] == "sufficiency-receipt"
    else:
        with pytest.raises(
            KnoraError,
            match="PROVIDER_REQUEST_FAILED"
            if outcome == "timeout"
            else "GENERATION_OUTPUT_INVALID",
        ):
            await verifier.assess_sufficiency(**kwargs)


@pytest.mark.asyncio
async def test_sufficiency_resolves_source_ids_without_retranscribing_unicode():
    import json

    from knora.providers.cloudflare.answer_support import CloudflareAnswerSupportVerifier

    source = "HƯỚNG DẪN - TRANG 1/12\n\nBáo cáo phải có ít nhất 20 trang."

    async def complete(prompt):
        data = json.loads(prompt.messages[1]["content"])
        assert data["evidence"][0]["passages"] == [
            {"quote_id": "E1:P1", "text": "HƯỚNG DẪN - TRANG 1/12"},
            {"quote_id": "E1:P2", "text": "Báo cáo phải có ít nhất 20 trang."},
        ]
        return {
            "snapshot_digest": "snapshot",
            "groups": [
                {
                    "id": "G1",
                    "source_fact": "Reports must have at least 20 pages.",
                    "source_refs": ["E1:P2"],
                    "missing_fact": "",
                    "status": "ANSWERABLE",
                }
            ],
        }, {"provider_request_id": "source-ids"}

    insufficient, metadata = await CloudflareAnswerSupportVerifier(complete).assess_sufficiency(
        question="Báo cáo phải dài bao nhiêu?",
        groups=(("G1", "Báo cáo phải dài bao nhiêu?"),),
        evidence=(GenerationEvidence("E1", source),),
        snapshot_digest="snapshot",
    )
    assert not insufficient
    assert metadata["resolved_groups"][0]["source_refs"] == [
        {"alias": "E1", "exact_quote": "Báo cáo phải có ít nhất 20 trang."},
    ]


@pytest.mark.asyncio
async def test_sufficiency_retains_completed_receipt_when_snapshot_changes():
    from knora.answering.answer_support import AnswerSupportFailure
    from knora.providers.cloudflare.answer_support import CloudflareAnswerSupportVerifier

    async def complete(prompt):
        return {
            "snapshot_digest": "snapshot",
            "groups": [
                {
                    "id": "G1",
                    "status": "INSUFFICIENT",
                    "source_fact": "Only a source footer is present.",
                    "source_refs": [],
                    "missing_fact": "Report-length requirement.",
                }
            ],
        }, {"provider_request_id": "completed-check"}

    checks = []

    def revalidate():
        checks.append(True)
        if len(checks) == 2:
            raise KnoraError("RETRIEVAL_SNAPSHOT_MISMATCH")

    with pytest.raises(AnswerSupportFailure) as caught:
        await CloudflareAnswerSupportVerifier(complete).assess_sufficiency(
            question="Required length?",
            groups=(("G1", "Required length?"),),
            evidence=(GenerationEvidence("E1", "PAGE 1/12"),),
            snapshot_digest="snapshot",
            revalidate=revalidate,
        )
    assert caught.value.code == "RETRIEVAL_SNAPSHOT_MISMATCH"
    assert caught.value.observation["provider"]["provider_request_id"] == "completed-check"


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
    assert prompt.definition.version == "cloudflare-gpt-oss-cited-answer-v25"
    assert "bold" not in str(prompt.definition.schema)
    assert "null" not in str(prompt.definition.schema["$defs"]["_Statement"])


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [None, "length", "null", "malformed"])
@pytest.mark.parametrize("model", ["@cf/openai/gpt-oss-20b", "@cf/openai/gpt-oss-120b"])
async def test_verifier_transport_is_bounded_and_retains_invalid_completion_evidence(
    failure, model
):
    import json

    import httpx

    from knora.answering.answer_support import AnswerSupportFailure
    from knora.providers.openai_compatible.generation import OpenAICompatibleGenerationProvider

    answer, projection, evidence, _ = case()
    requests = []

    async def endpoint(request):
        body = json.loads(request.content)
        requests.append(body)
        assert body["model"] == "@cf/openai/gpt-oss-120b"
        assert body["response_format"]["type"] == "json_object"
        assert body["temperature"] == 0 and body["max_tokens"] == 4096
        data = json.loads(body["messages"][1]["content"])
        audit = "required_facts" in data
        assert body["reasoning_effort"] == ("medium" if audit else "low")
        wire = _audit_fixture(data) if audit else _inventory_fixture(data)
        return httpx.Response(
            200,
            json={
                "id": "provider-receipt",
                "choices": [
                    {
                        "finish_reason": "length" if failure == "length" else "stop",
                        "message": {
                            "content": None
                            if failure in {"length", "null"}
                            else ("{broken" if failure == "malformed" else json.dumps(wire))
                        },
                    }
                ],
                "usage": {"completion_tokens": 2048 if failure == "length" else 180},
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(endpoint)) as client:
        provider = OpenAICompatibleGenerationProvider(
            base_url="https://provider.example/v1",
            api_key="secret-canary",
            model=model,
            provider_identity="cloudflare-workers-ai",
            input_cost_per_million_tokens=None,
            output_cost_per_million_tokens=None,
            pricing_version=None,
            max_tokens=2048,
            direct_json_schema=True,
            client=client,
        )
        verifier = provider.build_answer_support_verifier()
        kwargs = dict(
            question="Required?",
            groups=(("G1", "Required?"),),
            answer=answer,
            answer_projection=projection,
            evidence=evidence,
            snapshot_digest="snapshot",
        )
        if failure:
            with pytest.raises(AnswerSupportFailure) as caught:
                await verifier.verify(**kwargs)
            obs = caught.value.observation
            assert obs["failure"] == "invalid_verifier_completion"
            assert obs["provider"]["provider_request_id"] == "provider-receipt"
            assert obs["provider"]["finish_reason"] == ("length" if failure == "length" else "stop")
            assert "secret-canary" not in json.dumps(obs)
        else:
            proof, _ = await verifier.verify(**kwargs)
            assert proof.answer_digest == projection.answer_digest
    assert len(requests) == (1 if failure else 2)


@pytest.mark.asyncio
@pytest.mark.parametrize("foreign_ref", [False, True])
async def test_verifier_binds_each_statement_to_its_own_sources(foreign_ref):
    import json

    from knora.providers.cloudflare.answer_support import CloudflareAnswerSupportVerifier

    evidence = (GenerationEvidence("E1", "Fact one."), GenerationEvidence("E2", "Fact two."))
    answer, _, projection = compose_answer_projection(
        dict(
            decision="ANSWER",
            before=[],
            items=[
                {"text": "Fact one.", "support": ["E1"]},
                {"text": "Fact two.", "support": ["E2"]},
            ],
            after=[],
            refusal_reason=None,
        ),
        evidence,
    )

    async def complete(prompt):
        data = json.loads(prompt.messages[1]["content"])
        if prompt.definition.serializer_id == "source-inventory-v1":
            return _inventory_fixture(data), {}
        wire = _audit_fixture(data)
        if foreign_ref:
            wire["statements"][0]["source_refs"][0]["quote_id"] = "E2:Q1"
        return wire, {}

    kwargs = dict(
        question="What are the two facts?",
        groups=(("G1", "What are the two facts?"),),
        answer=answer,
        answer_projection=projection,
        evidence=evidence,
        snapshot_digest="snapshot",
    )
    verifier = CloudflareAnswerSupportVerifier(complete)
    if foreign_ref:
        with pytest.raises(KnoraError, match="GENERATION_OUTPUT_INVALID"):
            await verifier.verify(**kwargs)
    else:
        proof, _ = await verifier.verify(**kwargs)
        assert proof.answer_digest == projection.answer_digest


@pytest.mark.asyncio
@pytest.mark.parametrize("multiple_aliases", [False, True])
async def test_multistatement_answer_within_source_budget_reaches_independent_audit(
    multiple_aliases,
):
    import json

    from knora.providers.cloudflare.answer_support import CloudflareAnswerSupportVerifier

    source = " ".join(f"Source fact number {i}." for i in range(30 if multiple_aliases else 100))
    evidence = tuple(
        GenerationEvidence(f"E{i}", source) for i in range(1, 6 if multiple_aliases else 2)
    )
    aliases = (
        [["E1"], ["E2"], ["E3"], ["E4"], ["E5"], ["E1", "E2"], ["E2", "E3"], ["E1", "E3", "E5"]]
        if multiple_aliases
        else [["E1"]] * 8
    )
    answer, _, projection = compose_answer_projection(
        dict(
            decision="ANSWER",
            before=[],
            items=[{"text": f"Source fact number {i}.", "support": aliases[i]} for i in range(8)],
            after=[],
            refusal_reason=None,
        ),
        evidence,
    )

    async def complete(prompt):
        data = json.loads(prompt.messages[1]["content"])
        if prompt.definition.serializer_id == "source-inventory-v1":
            return _inventory_fixture(data, ("Source fact number 0.",)), {}
        wire = _audit_fixture(data)
        for i, statement in enumerate(wire["statements"]):
            statement["source_refs"][0]["quote_id"] = f"{aliases[i][0]}:Q2"
        return wire, {}

    proof, _ = await CloudflareAnswerSupportVerifier(complete).verify(
        question="Summarize facts zero through seven.",
        groups=(("G1", "Summarize facts zero through seven."),),
        answer=answer,
        answer_projection=projection,
        evidence=evidence,
        snapshot_digest="snapshot",
    )
    assert proof.answer_digest == projection.answer_digest


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "defect,want", [("digest", "invalid_verifier_proof"), ("unknown", "unsupported_answer")]
)
async def test_verifier_failures_distinguish_wire_repair_from_answer_repair(defect, want):
    import json

    from knora.answering.answer_support import AnswerSupportFailure
    from knora.providers.cloudflare.answer_support import CloudflareAnswerSupportVerifier

    answer, projection, evidence, _ = case()
    captured = []

    async def complete(prompt):
        data = json.loads(prompt.messages[1]["content"])
        captured.append(prompt)
        if prompt.definition.serializer_id == "source-inventory-v1":
            assert "recovery_feedback" not in data and "answer" not in data
            return _inventory_fixture(data), {}
        wire = _audit_fixture(data)
        if defect == "digest":
            wire["answer_digest"] = "wrong"
        if defect == "unknown":
            wire["statements"][0]["verdict"] = "UNKNOWN"
        return wire, {}

    with pytest.raises(AnswerSupportFailure) as caught:
        await CloudflareAnswerSupportVerifier(complete).verify(
            question="Is a diagram required?",
            groups=(("G1", "Is a diagram required?"),),
            answer=answer,
            answer_projection=projection,
            evidence=evidence,
            snapshot_digest="snapshot",
            feedback={"failure": "invalid_verifier_envelope"},
        )
    assert caught.value.observation["failure"] == want
    assert "recovery_feedback" in json.loads(captured[1].messages[1]["content"])


@pytest.mark.parametrize(
    "question,parts",
    [
        (
            "Phần thiết kế cơ sở dữ liệu cần mô tả những thông tin nào "
            "và dùng sơ đồ gì để minh họa?",
            2,
        ),
        ("Cần lưu những trường nào và sử dụng định dạng nào?", 2),
        ("Có cần sơ đồ không và giải thích những quan hệ nào?", 2),
        ("Caption cần được định dạng và đánh số thế nào?", 2),
        ("Các mục cần trình bày ra sao và được đánh số theo quy tắc nào?", 2),
        ("How should captions be formatted and numbered?", 2),
        ("Có được dùng ảnh không? Nếu cần mã nguồn thì trình bày ra sao?", 2),
        ("May I use screenshots? If code is needed, how should I format it?", 2),
        ("What are frontend and backend?", 1),
        ("Liệt kê font chữ và cỡ chữ.", 1),
        ("Caption của hình ảnh, bảng và sơ đồ cần được định dạng và đánh số thế nào?", 2),
    ],
)
def test_each_coordinated_request_gets_independent_coverage(question, parts):
    from knora.answering.answer_support import required_answer_groups

    assert len(required_answer_groups((("G1", question),))) == parts
