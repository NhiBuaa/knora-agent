import json
from dataclasses import replace

import pytest

from knora.evaluation.contracts import (
    Case,
    DatasetIdentity,
    EvidenceAnchor,
    EvidenceGroup,
    FreezeApproval,
    GoldDataset,
    LegacyDatasetReference,
    NoAnswerScope,
    PdfSource,
    RuntimeBinding,
    canonical_json,
    digest_json,
    freeze_dataset,
    select_cases,
)

SHA = "a" * 64


def dataset() -> GoldDataset:
    source = PdfSource("doc-1", "version-1", SHA)
    second = PdfSource("doc-2", "version-2", "b" * 64)
    return GoldDataset(
        DatasetIdentity("set-1", 1, "workspace-1", "pdf-gold-v1", "pdf-metrics-v1"),
        (source, second),
        (
            Case(
                "base",
                "What is A?",
                "ANSWER",
                "A is stated.",
                ("A",),
                "en",
                "single-source",
                (EvidenceGroup((EvidenceAnchor("version-1", 1, "A is stated."),)),),
            ),
            Case(
                "follow-up",
                "What links A and B?",
                "ANSWER",
                "A links B.",
                ("A links B",),
                "en",
                "multi-hop",
                (
                    EvidenceGroup(
                        (
                            EvidenceAnchor("version-1", 1, "A is stated."),
                            EvidenceAnchor("version-1", 2, "Alternate A."),
                        )
                    ),
                    EvidenceGroup((EvidenceAnchor("version-2", 3, "B is stated."),)),
                ),
                context_dependencies=("base",),
            ),
            Case(
                "no-answer",
                "What is C?",
                "REFUSAL",
                None,
                (),
                "en",
                "no-answer",
                (),
                no_answer_scope=NoAnswerScope(
                    ("version-1", "version-2"), "Reviewed both source PDFs for C"
                ),
            ),
        ),
    )


def approval(gold: GoldDataset) -> FreezeApproval:
    return FreezeApproval("issuer-1", "owner-1", gold.digest)


def test_freeze_and_roundtrip_do_not_require_runtime_binding():
    gold = dataset()
    frozen = freeze_dataset(gold, approval(gold))

    assert frozen.reference.digest == gold.digest
    assert frozen.to_json() == canonical_json(json.loads(frozen.to_json()))
    assert type(frozen).from_json(frozen.to_json()) == frozen
    assert RuntimeBinding(frozen.reference, "MISSING")


def test_freeze_rejects_stale_digest_and_serialization_rechecks_gold():
    gold = dataset()
    with pytest.raises(ValueError, match="digest"):
        freeze_dataset(gold, FreezeApproval("issuer-1", "owner-1", "0" * 64))

    frozen = freeze_dataset(gold, approval(gold))
    encoded = json.loads(frozen.to_json())
    encoded["gold"]["cases"][0]["question"] = "Tampered"
    with pytest.raises(ValueError, match="digest"):
        type(frozen).from_json(canonical_json(encoded))


def test_canonical_json_has_independently_known_utf8_digest():
    value = {"b": [2, 1], "a": "đ"}
    assert canonical_json(value) == '{"a":"đ","b":[2,1]}'
    assert digest_json(value) == "0469d4274e3006500e602e8106530a169bf9b1c16c6e6b6c0f7a07d7e93f49d5"


def test_selection_preserves_gold_and_explicit_context_population():
    frozen = freeze_dataset(dataset(), approval(dataset()))
    selection = select_cases(frozen, ("follow-up", "no-answer"))

    assert selection.reference == frozen.reference
    assert selection.selected_case_ids == ("follow-up", "no-answer")
    assert selection.context_only_case_ids == ("base",)
    assert selection.context_only_case_ids != selection.selected_case_ids
    assert frozen.gold.cases == dataset().cases
    assert type(selection).from_json(selection.to_json(), frozen) == selection


def test_refusal_requires_verified_scope_and_answer_needs_all_groups():
    gold = dataset()
    assert len(gold.cases[1].evidence_groups) == 2
    assert len(gold.cases[1].evidence_groups[0].alternatives) == 2
    assert gold.cases[2].no_answer_scope.checked_document_version_ids == (
        "version-1",
        "version-2",
    )
    with pytest.raises(ValueError, match="scope"):
        replace(gold.cases[2], no_answer_scope=None)
    with pytest.raises(ValueError, match="evidence"):
        replace(gold.cases[1], evidence_groups=())


@pytest.mark.parametrize(
    "arguments",
    (
        ("version-1", 0, "quote"),
        ("version-1", 1, "quote", None, None, 2, 5),
        ("version-1", 1, "quote", "extract-1", SHA, 5, 5),
    ),
)
def test_invalid_anchor_or_offset_is_rejected(arguments):
    with pytest.raises(ValueError):
        EvidenceAnchor(*arguments)


def test_valid_offset_anchor_pins_extraction_snapshot():
    anchor = EvidenceAnchor("version-1", 1, "quote", "extract-1", SHA, 0, 5)
    assert anchor.end_offset == 5


def test_duplicate_unknown_and_cyclic_case_references_fail():
    gold = dataset()
    with pytest.raises(ValueError, match="duplicate"):
        replace(gold, cases=gold.cases + (gold.cases[0],))
    with pytest.raises(ValueError, match="unknown"):
        replace(gold, cases=(replace(gold.cases[0], context_dependencies=("absent",)),))
    with pytest.raises(ValueError, match="cyclic"):
        replace(
            gold,
            cases=(
                replace(gold.cases[0], context_dependencies=("follow-up",)),
                gold.cases[1],
            ),
        )
    with pytest.raises(ValueError, match="unknown"):
        select_cases(freeze_dataset(gold, approval(gold)), ("absent",))
    with pytest.raises(ValueError, match="duplicate"):
        select_cases(freeze_dataset(gold, approval(gold)), ("base", "base"))


def test_source_references_and_legacy_digest_stay_format_specific():
    gold = dataset()
    with pytest.raises(ValueError, match="unknown"):
        replace(
            gold,
            cases=(
                replace(
                    gold.cases[0],
                    evidence_groups=(EvidenceGroup((EvidenceAnchor("missing", 1, "x"),)),),
                ),
            ),
        )
    legacy = LegacyDatasetReference(
        "m3-dataset-v1", "m3-set", 1, "workspace-1", "native-checksum", "m3-metrics-v1"
    )
    assert legacy.native_digest == "native-checksum"


def test_json_parser_rejects_scalar_instead_of_array():
    encoded = dataset().to_dict()
    encoded["cases"][0]["required_facts"] = "A"
    with pytest.raises(ValueError, match="required_facts"):
        GoldDataset.from_dict(encoded)


def test_selection_includes_transitive_context_in_dependency_order():
    gold = dataset()
    chained = replace(gold.cases[2], context_dependencies=("follow-up",))
    gold = replace(gold, cases=gold.cases[:2] + (chained,))
    frozen = freeze_dataset(gold, approval(gold))

    assert select_cases(frozen, ("no-answer",)).context_only_case_ids == (
        "base",
        "follow-up",
    )
