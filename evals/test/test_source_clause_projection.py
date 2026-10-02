import importlib

import pytest
from evals.runners.ollama_evidence_first_probe import render_result

from knora.domain.errors import KnoraError
from knora.providers.generation import GenerationEvidence


def projection(payload, evidence):
    try:
        module = importlib.import_module("evals.runners.source_clause_projection")
    except ModuleNotFoundError:
        pytest.fail("validated source clause projection is missing")
    return module.render_source_clauses(payload, evidence)


def selection(*, facts=(), rules=(), exceptions=(), decision="ANSWER"):
    return {
        "decision": decision,
        "facts": list(facts),
        "rules": list(rules),
        "exceptions": list(exceptions),
        "refusal_reason": "INSUFFICIENT_EVIDENCE" if decision == "REFUSAL" else None,
    }


def test_duplicate_quotes_are_rendered_once_without_changing_the_legacy_renderer():
    evidence = (GenerationEvidence("E1", "Gardez le couvercle fermé."),)
    quote = {"evidence_id": "E1", "quote": evidence[0].content}
    payload = selection(facts=[{**quote, "text": quote["quote"]}], rules=[quote])
    assert render_result(payload, evidence).answer.count(evidence[0].content) == 2
    result = projection(payload, evidence)
    assert result.answer == "Gardez le couvercle fermé. [[E1]]"
    assert result.cited_evidence_ids == ("E1",)


def test_overlapping_selections_retain_the_complete_qualified_alternative():
    source = "Quatre pièces sont nécessaires. Deux suffisent après accord écrit du chef."
    evidence = (GenerationEvidence("E1", source),)
    payload = selection(
        rules=[{"evidence_id": "E1", "quote": "Quatre pièces sont nécessaires."}],
        exceptions=[{"evidence_id": "E1", "quote": source}],
    )
    assert projection(payload, evidence).answer == source + " [[E1]]"


def test_partial_overlap_copies_the_exact_union_including_decimal_punctuation():
    source = "Dose 2.5 ml: fermer la valve, puis vérifier l'accord du Dr. Lin."
    evidence = (GenerationEvidence("E1", source),)
    payload = selection(
        rules=[{"evidence_id": "E1", "quote": "Dose 2.5 ml: fermer la valve,"}],
        exceptions=[
            {"evidence_id": "E1", "quote": "fermer la valve, puis vérifier l'accord du Dr. Lin."}
        ],
    )
    assert projection(payload, evidence).answer == source + " [[E1]]"


def test_disjoint_selections_do_not_add_the_unselected_source_content():
    evidence = (GenerationEvidence("E1", "Fermez. SECRET_NON_SELECTED. Attendez l'accord."),)
    payload = selection(
        rules=[
            {"evidence_id": "E1", "quote": "Fermez."},
            {"evidence_id": "E1", "quote": "Attendez l'accord."},
        ]
    )
    assert projection(payload, evidence).answer == "Fermez. Attendez l'accord. [[E1]]"


def test_adjacent_selected_spans_keep_the_original_source_spacing():
    evidence = (GenerationEvidence("E1", "Gardez le couvercle fermé."),)
    payload = selection(
        rules=[{"evidence_id": "E1", "quote": "Gardez le couvercle"}],
        exceptions=[{"evidence_id": "E1", "quote": " fermé."}],
    )
    assert projection(payload, evidence).answer == "Gardez le couvercle fermé. [[E1]]"


def test_overlap_chain_keeps_source_order_even_when_selections_arrive_in_reverse_order():
    evidence = (GenerationEvidence("E1", "ABCDE"),)
    payload = selection(
        rules=[{"evidence_id": "E1", "quote": "CDE"}],
        exceptions=[
            {"evidence_id": "E1", "quote": "BC"},
            {"evidence_id": "E1", "quote": "AB"},
        ],
    )
    assert projection(payload, evidence).answer == "ABCDE [[E1]]"


def test_an_ambiguous_occurrence_is_not_merged_into_a_different_source_context():
    source = "Valve fermée. Exemple: Valve fermée. Seulement avec autorisation."
    evidence = (GenerationEvidence("E1", source),)
    payload = selection(
        rules=[
            {"evidence_id": "E1", "quote": "Valve fermée."},
            {"evidence_id": "E1", "quote": "Valve fermée."},
            {"evidence_id": "E1", "quote": "Exemple: Valve fermée. Seulement avec autorisation."},
        ]
    )
    assert projection(payload, evidence).answer == source + " [[E1]]"


def test_equal_text_under_distinct_aliases_keeps_both_citations_in_selected_order():
    evidence = (GenerationEvidence("E1", "Restez ici."), GenerationEvidence("E2", "Restez ici."))
    payload = selection(
        rules=[
            {"evidence_id": "E2", "quote": "Restez ici."},
            {"evidence_id": "E1", "quote": "Restez ici."},
        ]
    )
    result = projection(payload, evidence)
    assert result.answer == "Restez ici. [[E2]]\n\nRestez ici. [[E1]]"
    assert result.cited_evidence_ids == ("E2", "E1")


def test_refusal_is_not_converted_into_an_answer():
    result = projection(selection(decision="REFUSAL"), (GenerationEvidence("E1", "Le guide."),))
    assert result.decision == "REFUSAL"
    assert result.answer is None and result.cited_evidence_ids == ()
    assert result.refusal_reason == "INSUFFICIENT_EVIDENCE"


@pytest.mark.parametrize(
    "fault", ["invented_quote", "invented_fact", "unknown_alias", "missing_field"]
)
def test_projection_rejects_invalid_input_before_removing_repetition(fault):
    payload = selection(
        facts=[{"evidence_id": "E1", "quote": "Note: Alpha.", "text": "Note: Alpha."}]
    )
    if fault == "invented_quote":
        payload["facts"][0]["quote"] = "PRIVATE_INVENTED_QUOTE"
    elif fault == "invented_fact":
        payload["facts"][0]["text"] = "PRIVATE_NEW_FACT"
    elif fault == "unknown_alias":
        payload["facts"][0]["evidence_id"] = "E99"
    else:
        del payload["decision"]
    with pytest.raises(KnoraError) as error:
        projection(payload, (GenerationEvidence("E1", "Note: Alpha."),))
    assert error.value.code == "GENERATION_OUTPUT_INVALID"
    assert "PRIVATE" not in str(error.value)
