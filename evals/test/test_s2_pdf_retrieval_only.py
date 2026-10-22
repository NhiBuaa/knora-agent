"""Frozen B queries drive one native window per case, never generation."""

from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from backend.test.answering.test_bm25_contract import LexicalStore, candidate
from evals.runners import pdf_retrieval_v3 as runner

from knora.answering.stores import RetrievalConfiguration
from knora.domain.errors import KnoraError


def inputs():
    dataset = SimpleNamespace(
        corpus_sha256="corpus",
        dataset_sha256="gold",
        cases=(
            SimpleNamespace(id="first", question="Original?", parent_case_id=None),
            SimpleNamespace(id="follow", question="And that?", parent_case_id="first"),
            SimpleNamespace(id="third", question="Failure?", parent_case_id=None),
        ),
    )
    baseline = [
        {"case_id": "first", "failure_code": None, "response_sha256": "first-response"},
        {
            "case_id": "follow",
            "failure_code": None,
            "response_sha256": "follow-response",
            "provider_metadata": {
                "conversation_context": {
                    "policy_id": "conversation-context-v2",
                    "selected_turn_ids": ["old-parent"],
                    "retrieval_query": (
                        "Previous user question: Original?\nCurrent question: And that?"
                    ),
                }
            },
        },
        {"case_id": "third", "failure_code": None, "response_sha256": "third-response"},
    ]
    return dataset, baseline


def test_frozen_context_one_dispatch_selector_and_retained_failure_no_retry(tmp_path):
    dataset, baseline = inputs()
    config = RetrievalConfiguration.bm25_top8_v1()
    result = LexicalStore((candidate(),)).result
    store = Mock()
    store.retrieve_candidates.side_effect = [
        result,
        result,
        KnoraError("LEXICAL_RETRIEVAL_UNAVAILABLE"),
    ]
    rows = runner.collect_bm25_cases(
        dataset,
        store,
        baseline,
        tmp_path,
        run_id="run",
        workspace_id="workspace",
        configuration=config,
        derivation_sha256="derivation",
    )
    assert len(rows) == 3
    assert store.retrieve_candidates.call_count == 3
    assert [call.kwargs["query_text"] for call in store.retrieve_candidates.call_args_list] == [
        "Original?",
        baseline[1]["provider_metadata"]["conversation_context"]["retrieval_query"],
        "Failure?",
    ]
    assert rows[0]["selected_chunk_ids"] == [candidate().chunk_id]
    assert rows[0]["generation_status"] == "not_run"
    assert "public_response" not in rows[0] and "decision" not in rows[0]
    assert rows[1]["query_source"] == "frozen_baseline_b_conversation_context"
    assert rows[2]["failure_code"] == "LEXICAL_RETRIEVAL_UNAVAILABLE"
    assert len(list(tmp_path.glob("dispatch-*.json"))) == 3
    assert len(list(tmp_path.glob("case-*.json"))) == 3
    replay = runner.collect_bm25_cases(
        dataset,
        store,
        baseline,
        tmp_path,
        run_id="run",
        workspace_id="workspace",
        configuration=config,
        derivation_sha256="derivation",
    )
    assert replay == rows
    assert store.retrieve_candidates.call_count == 3


@pytest.mark.parametrize(
    "fault", ["missing_context", "query_drift", "missing_case", "duplicate", "config"]
)
def test_invalid_frozen_inputs_fail_before_any_dispatch(tmp_path, fault):
    dataset, baseline = inputs()
    config = RetrievalConfiguration.bm25_top8_v1()
    if fault == "missing_context":
        baseline[1].pop("provider_metadata")
    elif fault == "query_drift":
        baseline[1]["provider_metadata"]["conversation_context"]["retrieval_query"] = "foreign?"
    elif fault == "missing_case":
        baseline.pop()
    elif fault == "duplicate":
        baseline.append(baseline[0])
    else:
        config = replace(config, candidate_k=200)
    store = Mock()
    with pytest.raises(ValueError):
        runner.collect_bm25_cases(
            dataset,
            store,
            baseline,
            tmp_path,
            run_id="run",
            workspace_id="workspace",
            configuration=config,
            derivation_sha256="derivation",
        )
    store.retrieve_candidates.assert_not_called()
    assert not list(tmp_path.iterdir())


def test_unresolved_dispatch_never_issues_a_second_query(tmp_path):
    dataset, baseline = inputs()
    (tmp_path / "dispatch-first-attempt-1.json").write_text("{}", encoding="utf-8")
    store = Mock()
    with pytest.raises(ValueError, match="unresolved dispatch"):
        runner.collect_bm25_cases(
            dataset,
            store,
            baseline,
            tmp_path,
            run_id="run",
            workspace_id="workspace",
            configuration=RetrievalConfiguration.bm25_top8_v1(),
            derivation_sha256="derivation",
        )
    store.retrieve_candidates.assert_not_called()


def test_later_unresolved_dispatch_blocks_entire_resume_before_queries(tmp_path):
    dataset, baseline = inputs()
    (tmp_path / "dispatch-third-attempt-1.json").write_text("{}", encoding="utf-8")
    store = Mock()
    with pytest.raises(ValueError, match="unresolved dispatch"):
        runner.collect_bm25_cases(
            dataset,
            store,
            baseline,
            tmp_path,
            run_id="run",
            workspace_id="workspace",
            configuration=RetrievalConfiguration.bm25_top8_v1(),
            derivation_sha256="derivation",
        )
    store.retrieve_candidates.assert_not_called()


def test_resume_rejects_changed_frozen_context_before_queries(tmp_path):
    dataset, baseline = inputs()
    store = Mock()
    store.retrieve_candidates.side_effect = KnoraError("LEXICAL_RETRIEVAL_UNAVAILABLE")
    runner.collect_bm25_cases(
        dataset,
        store,
        baseline,
        tmp_path,
        run_id="run",
        workspace_id="workspace",
        configuration=RetrievalConfiguration.bm25_top8_v1(),
        derivation_sha256="derivation",
    )
    store.reset_mock()
    baseline[1]["provider_metadata"]["conversation_context"]["selected_turn_ids"] = ["other"]
    with pytest.raises(ValueError, match="identity mismatch"):
        runner.collect_bm25_cases(
            dataset,
            store,
            baseline,
            tmp_path,
            run_id="run",
            workspace_id="workspace",
            configuration=RetrievalConfiguration.bm25_top8_v1(),
            derivation_sha256="derivation",
        )
    store.retrieve_candidates.assert_not_called()
