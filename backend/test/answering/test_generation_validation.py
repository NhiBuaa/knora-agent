import pytest

from knora.answering.generation_validation import validate_generation
from knora.domain.errors import KnoraError
from knora.providers.generation import GenerationResult


def test_answer_marker_order_must_match_cited_evidence_ids() -> None:
    result = GenerationResult(
        decision="ANSWER",
        answer="The second rule applies. [[E2]] The first adds context. [[E1]]",
        cited_evidence_ids=("E1", "E2"),
        refusal_reason=None,
    )

    with pytest.raises(KnoraError, match="GENERATION_OUTPUT_INVALID"):
        validate_generation(result, available_evidence_ids=("E1", "E2"))


@pytest.mark.parametrize(
    ("answer", "cited_ids"),
    [
        ("Unknown. [[E9]]", ("E9",)),
        ("Duplicate. [[E1]] Again. [[E1]]", ("E1",)),
        ("Missing marker.", ("E1",)),
    ],
)
def test_answer_rejects_unknown_duplicate_or_missing_markers(answer, cited_ids) -> None:
    result = GenerationResult(
        decision="ANSWER",
        answer=answer,
        cited_evidence_ids=cited_ids,
        refusal_reason=None,
    )

    with pytest.raises(KnoraError, match="GENERATION_OUTPUT_INVALID"):
        validate_generation(result, available_evidence_ids=("E1", "E2"))


def test_malformed_marker_tokens_fail_closed() -> None:
    result = GenerationResult(
        decision="ANSWER",
        answer="fact [[E1]] trailing [[",
        cited_evidence_ids=("E1",),
        refusal_reason=None,
    )

    with pytest.raises(KnoraError, match="GENERATION_OUTPUT_INVALID"):
        validate_generation(result, available_evidence_ids=("E1",))


def test_structured_refusal_requires_empty_answer_and_citations() -> None:
    valid = GenerationResult(
        decision="REFUSAL",
        answer=None,
        cited_evidence_ids=(),
        refusal_reason="INSUFFICIENT_EVIDENCE",
    )
    invalid = GenerationResult(
        decision="REFUSAL",
        answer="provider-owned refusal",
        cited_evidence_ids=(),
        refusal_reason="INSUFFICIENT_EVIDENCE",
    )

    assert validate_generation(valid, available_evidence_ids=("E1",)).parsed_markers == ()
    with pytest.raises(KnoraError, match="GENERATION_OUTPUT_INVALID"):
        validate_generation(invalid, available_evidence_ids=("E1",))


def test_non_string_answer_fails_as_generation_contract_error() -> None:
    result = GenerationResult(
        decision="ANSWER",
        answer=123,  # type: ignore[arg-type]
        cited_evidence_ids=("E1",),
        refusal_reason=None,
    )

    with pytest.raises(KnoraError, match="GENERATION_OUTPUT_INVALID"):
        validate_generation(result, available_evidence_ids=("E1",))


def test_citation_alignment_and_factual_substance_probes() -> None:
    """F14: Verify citation-level segment alignment, number fidelity, and substantive facts."""
    import hashlib
    import re

    from knora.answering.query_planning import Subquestion, extract_protected_spans
    from knora.answering.stores import RetrievalCandidate

    def _make_cand(cid: str, text: str, heading: tuple[str, ...]) -> RetrievalCandidate:
        return RetrievalCandidate(
            document_id="d",
            document_version_id="v",
            source_key="policy",
            source_name="policy.pdf",
            chunk_set_id="s",
            embedding_set_id=None,
            embedding_configuration_id=None,
            chunk_id=cid,
            chunk_ordinal=0,
            heading_path=heading,
            start_line=1,
            end_line=10,
            content=text,
            content_checksum=hashlib.sha256(text.encode()).hexdigest(),
            token_count=len(text.split()),
            cosine_distance=None,
            similarity=None,
            fusion_score=0.5,
        )

    c2 = _make_cand("c2", "Chương 2 thời hạn đổi trả 7 ngày.", ("Chương 2",))
    c5 = _make_cand("c5", "Chương 5 miễn phí vận chuyển.", ("Chương 5",))
    groups = [
        Subquestion(
            id="s2",
            text="Chương 2 thời hạn đổi trả",
            protected_spans=extract_protected_spans("Chương 2"),
        ),
        Subquestion(
            id="s5",
            text="Chương 5 phí vận chuyển",
            protected_spans=extract_protected_spans("Chương 5"),
        ),
    ]
    alias_map = {"E1": c2, "E2": c5}

    def _check(ans_text: str):
        g = GenerationResult(
            decision="ANSWER",
            answer=ans_text,
            cited_evidence_ids=tuple(re.findall(r"\[\[(E\d+)\]\]", ans_text)),
            refusal_reason=None,
        )
        return validate_generation(
            g,
            available_evidence_ids=("E1", "E2"),
            required_subquestions=groups,
            alias_to_candidate=alias_map,
        )

    # 1. Padded heading-only answer must fail closed
    with pytest.raises(KnoraError, match="GENERATION_OUTPUT_INVALID"):
        _check("Chương 2 và Chương 5, đây chỉ là phần giới thiệu tổng quan chung. [[E1]] [[E2]]")

    # 2. Concise factually supported answer must pass
    val = _check("Chương 2: 7 ngày [[E1]]. Chương 5: miễn phí [[E2]].")
    assert val.parsed_markers == ("E1", "E2")

    # 3. Wrong number (70 vs 7) must fail closed
    with pytest.raises(KnoraError, match="GENERATION_OUTPUT_INVALID"):
        _check("Chương 2: thời hạn đổi trả 70 ngày [[E1]]. Chương 5: miễn phí vận chuyển [[E2]].")

    # 4. Swapped citations (E2 for C2, E1 for C5) must fail closed
    with pytest.raises(KnoraError, match="GENERATION_OUTPUT_INVALID"):
        _check("Chương 2: 7 ngày [[E2]]. Chương 5: miễn phí [[E1]].")

    # 5. Factless answer with one shared word must fail closed
    with pytest.raises(KnoraError, match="GENERATION_OUTPUT_INVALID"):
        _check("Chương 2: thời gian [[E1]]. Chương 5: phí khác [[E2]].")


def _make_cand(
    chunk_id: str,
    content: str,
    heading_path: tuple[str, ...] = (),
):
    from knora.answering.stores import RetrievalCandidate

    return RetrievalCandidate(
        document_id="doc-1",
        document_version_id="ver-1",
        source_key="policy",
        source_name="policy.pdf",
        chunk_set_id="cset-1",
        embedding_set_id=None,
        embedding_configuration_id=None,
        chunk_id=chunk_id,
        chunk_ordinal=0,
        heading_path=heading_path,
        start_line=1,
        end_line=10,
        content=content,
        content_checksum=f"chk-{chunk_id}",
        token_count=len(content.split()),
        cosine_distance=0.1,
        similarity=0.9,
    )


def test_r6_f14_statement_support_rejection_and_acceptance() -> None:
    from knora.answering.generation_validation import validate_generation
    from knora.domain.errors import KnoraError
    from knora.providers.generation import GenerationResult

    # Source candidate: "Thời hạn đổi trả là 7 ngày."
    cand = _make_cand("c1", "Thời hạn đổi trả là 7 ngày.")
    alias_map = {"E1": cand}
    available = ("E1",)

    # Negative 1: Unrelated claim ("Sao Hỏa có sự sống [[E1]].") -> MUST REJECT
    res_mars = GenerationResult(
        decision="ANSWER",
        answer="Sao Hỏa có sự sống [[E1]].",
        cited_evidence_ids=("E1",),
        refusal_reason=None,
    )
    with pytest.raises(KnoraError, match="GENERATION_OUTPUT_INVALID"):
        validate_generation(
            res_mars, available_evidence_ids=available, alias_to_candidate=alias_map
        )

    # Negative 2: Uncited claim before citation -> MUST REJECT
    res_uncited = GenerationResult(
        decision="ANSWER",
        answer="Mọi khách hàng được hoàn tiền vô điều kiện. Thời hạn đổi trả là 7 ngày [[E1]].",
        cited_evidence_ids=("E1",),
        refusal_reason=None,
    )
    with pytest.raises(KnoraError, match="GENERATION_OUTPUT_INVALID"):
        validate_generation(
            res_uncited, available_evidence_ids=available, alias_to_candidate=alias_map
        )

    # Negative 3: Swapped claim ("Phí vận chuyển là 7 ngày [[E1]].") -> MUST REJECT
    res_swapped = GenerationResult(
        decision="ANSWER",
        answer="Phí vận chuyển là 7 ngày [[E1]].",
        cited_evidence_ids=("E1",),
        refusal_reason=None,
    )
    with pytest.raises(KnoraError, match="GENERATION_OUTPUT_INVALID"):
        validate_generation(
            res_swapped, available_evidence_ids=available, alias_to_candidate=alias_map
        )

    # Negative 4: Ungrounded claim ("Đổi trả miễn phí trong 7 ngày [[E1]].") -> MUST REJECT
    res_free = GenerationResult(
        decision="ANSWER",
        answer="Đổi trả miễn phí trong 7 ngày [[E1]].",
        cited_evidence_ids=("E1",),
        refusal_reason=None,
    )
    with pytest.raises(KnoraError, match="GENERATION_OUTPUT_INVALID"):
        validate_generation(
            res_free, available_evidence_ids=available, alias_to_candidate=alias_map
        )

    # Negative 5: Compound statement with alien clause
    # ("Đổi trả 7 ngày; Sao Hỏa có sự sống [[E1]].") -> MUST REJECT
    res_compound = GenerationResult(
        decision="ANSWER",
        answer="Đổi trả 7 ngày; Sao Hỏa có sự sống [[E1]].",
        cited_evidence_ids=("E1",),
        refusal_reason=None,
    )
    with pytest.raises(KnoraError, match="GENERATION_OUTPUT_INVALID"):
        validate_generation(
            res_compound, available_evidence_ids=available, alias_to_candidate=alias_map
        )

    # Positive 1: Exact supported claim -> MUST PASS
    res_exact = GenerationResult(
        decision="ANSWER",
        answer="Thời hạn đổi trả là 7 ngày [[E1]].",
        cited_evidence_ids=("E1",),
        refusal_reason=None,
    )
    val_exact = validate_generation(
        res_exact, available_evidence_ids=available, alias_to_candidate=alias_map
    )
    assert val_exact.parsed_markers == ("E1",)

    # Positive 2: Whitelisted 1 tuần <-> 7 ngày -> MUST PASS
    res_week = GenerationResult(
        decision="ANSWER",
        answer="Thời hạn đổi trả là 1 tuần [[E1]].",
        cited_evidence_ids=("E1",),
        refusal_reason=None,
    )
    val_week = validate_generation(
        res_week, available_evidence_ids=available, alias_to_candidate=alias_map
    )
    assert val_week.parsed_markers == ("E1",)

    # Positive 3: Concise supported answer -> MUST PASS
    res_concise = GenerationResult(
        decision="ANSWER",
        answer="7 ngày [[E1]].",
        cited_evidence_ids=("E1",),
        refusal_reason=None,
    )
    val_concise = validate_generation(
        res_concise, available_evidence_ids=available, alias_to_candidate=alias_map
    )
    assert val_concise.parsed_markers == ("E1",)

    # Positive 4: Citation after period ("7 ngày. [[E1]]") -> MUST PASS
    res_period = GenerationResult(
        decision="ANSWER",
        answer="7 ngày. [[E1]]",
        cited_evidence_ids=("E1",),
        refusal_reason=None,
    )
    val_period = validate_generation(
        res_period, available_evidence_ids=available, alias_to_candidate=alias_map
    )
    assert val_period.parsed_markers == ("E1",)
