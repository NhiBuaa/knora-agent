from copy import deepcopy
from hashlib import sha256
from types import SimpleNamespace as NS

import pytest
from evals.runners.pdf_source_binding import (
    group_coverage,
    propose_bindings,
    validate_binding_review,
)


def fixture():
    dataset = NS(
        corpus_sha256="a" * 64,
        dataset_sha256="b" * 64,
        sources=(NS(id="policy", sha256="c" * 64),),
        anchors=(NS(id="limit", source_id="policy", page=1, text="Limit 30 days"),),
    )
    text = "Limit 30 days."
    chunk = NS(
        workspace_id="workspace",
        chunk_id="chunk-1",
        source_key="policy",
        document_version_id="version-1",
        chunk_set_id="set-1",
        raw_sha256="c" * 64,
        parser_configuration_id="parser",
        normalizer_configuration_id="normalizer",
        chunking_configuration_id="chunker",
        page_start=1,
        page_end=1,
        start_offset=0,
        end_offset=len(text),
        content=text,
        content_checksum=sha256(text.encode()).hexdigest(),
    )
    return dataset, chunk


def review(proposals):
    return {
        "status": "approved",
        "reviewer": "NhiBuaa",
        "decision_url": "https://github.com/NhiBuaa/knora-agent/issues/153#review",
        "proposal_sha256": proposals["proposal_sha256"],
        "choices": {"limit": [0]},
    }


def test_exact_match_never_becomes_a_reviewed_binding_automatically():
    dataset, chunk = fixture()
    proposals = propose_bindings(dataset, (chunk,))
    assert proposals["anchors"]["limit"]["status"] == "proposed"
    with pytest.raises(ValueError, match="review"):
        validate_binding_review(proposals, {"status": "pending"})
    assert validate_binding_review(proposals, review(proposals)) == {"limit": ("chunk-1",)}


def test_repeated_text_is_ambiguous_even_inside_one_chunk():
    dataset, chunk = fixture()
    chunk.content = "Limit 30 days. Limit 30 days."
    chunk.end_offset = len(chunk.content)
    chunk.content_checksum = sha256(chunk.content.encode()).hexdigest()
    proposals = propose_bindings(dataset, (chunk,))
    assert proposals["anchors"]["limit"]["status"] == "ambiguous"
    assert len(proposals["anchors"]["limit"]["matches"]) == 2
    ambiguous_review = review(proposals)
    ambiguous_review["choices"]["limit"] = [0, 1]
    with pytest.raises(ValueError, match="ambiguous"):
        validate_binding_review(proposals, ambiguous_review)


def test_overlap_is_one_source_occurrence_with_two_chunk_alternatives():
    dataset, chunk = fixture()
    overlap = deepcopy(chunk)
    overlap.chunk_id = "chunk-2"
    proposals = propose_bindings(dataset, (chunk, overlap))
    assert proposals["anchors"]["limit"]["status"] == "proposed"
    assert validate_binding_review(proposals, review(proposals)) == {
        "limit": ("chunk-1", "chunk-2")
    }


def test_missing_extraction_is_not_an_empty_positive_gold():
    dataset, _ = fixture()
    proposals = propose_bindings(dataset, ())
    assert proposals["anchors"]["limit"]["status"] == "missing"
    missing_review = review(proposals)
    missing_review["choices"]["limit"] = []
    assert validate_binding_review(proposals, missing_review) == {"limit": ()}
    assert group_coverage((("limit",),), {"limit": ()}, ("unrelated",)) == (False,)


@pytest.mark.parametrize("mutation", ["source", "checksum", "page", "offset"])
def test_derivation_drift_is_rejected(mutation):
    dataset, chunk = fixture()
    if mutation == "source":
        chunk.raw_sha256 = "d" * 64
    elif mutation == "checksum":
        chunk.content_checksum = "e" * 64
    elif mutation == "page":
        chunk.page_end = 2
    else:
        chunk.end_offset += 1
    with pytest.raises(ValueError, match="derivation"):
        propose_bindings(dataset, (chunk,))


def test_review_cannot_survive_changed_persisted_derivation():
    dataset, chunk = fixture()
    old = propose_bindings(dataset, (chunk,))
    old_review = review(old)
    chunk.chunk_set_id = "new-set"
    changed = propose_bindings(dataset, (chunk,))
    with pytest.raises(ValueError, match="digest"):
        validate_binding_review(changed, old_review)


def test_and_groups_use_or_alternatives_without_partial_pass():
    bindings = {"a": ("one",), "b": ("two",), "c": ("three",)}
    assert group_coverage((("a", "b"), ("c",)), bindings, ("two",)) == (True, False)
    assert group_coverage((("a", "b"), ("c",)), bindings, ("two", "three")) == (True, True)
