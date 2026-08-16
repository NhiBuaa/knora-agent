from __future__ import annotations

import os
from dataclasses import dataclass

import httpx
import pytest
from evals.datasets.milestone_3 import (
    AnswerExpectations,
    EvidenceExpectations,
    Milestone3Case,
    RetrievalRelevance,
)
from evals.runners.m3_readiness_main import (
    ResponseFaultInjectingPost,
    TraceFaultInjectingReader,
    build_diagnostic_case,
    current_source_pythonpath,
    select_diagnostic_case,
)


def test_response_fault_injector_emits_malformed_refusal_payload() -> None:
    request = httpx.Request("POST", "http://knora.test/v1/questions")

    def post(_url: str, **_kwargs: object) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "decision": "ANSWER",
                "answer": "fact [[E1]]",
                "citations": [{"evidence_id": "E1"}],
                "refusal_reason": None,
                "trace_id": "trace-1",
                "workspace_id": "workspace",
            },
            request=request,
        )

    response = ResponseFaultInjectingPost(post, mode="malformed-refusal")(
        "http://knora.test/v1/questions"
    )

    assert response.json() == {
        "decision": "REFUSAL",
        "answer": "malformed",
        "citations": [],
        "refusal_reason": "INSUFFICIENT_EVIDENCE",
        "trace_id": "trace-1",
        "workspace_id": "workspace",
    }


def test_response_fault_injector_rejects_unknown_mode() -> None:
    with pytest.raises(ValueError, match="unsupported response fault mode"):
        ResponseFaultInjectingPost(lambda *_args, **_kwargs: None, mode="unknown")


def _case(*, case_id: str = "answer-1", behavior: str = "ANSWER") -> Milestone3Case:
    return Milestone3Case(
        case_id,
        "lexical_exact_match" if behavior == "ANSWER" else "insufficient_evidence_refusal",
        "workspace",
        "question",
        behavior,
        RetrievalRelevance(
            behavior == "ANSWER", ("support/a#0",) if behavior == "ANSWER" else ()
        ),
        AnswerExpectations(
            ("fact",) if behavior == "ANSWER" else (),
            "fact" if behavior == "ANSWER" else None,
        ),
        EvidenceExpectations(
            ("support/a",) if behavior == "ANSWER" else (),
            ("support/a#0",) if behavior == "ANSWER" else (),
        ),
        None if behavior == "ANSWER" else "INSUFFICIENT_EVIDENCE",
    )


def test_select_diagnostic_case_can_select_refusal_case() -> None:
    selected = select_diagnostic_case(
        (_case(), _case(case_id="refusal-1", behavior="REFUSAL")),
        workspace_id="workspace",
        case_id="refusal-1",
        question=None,
        behavior="ANSWER",
    )

    assert selected.id == "refusal-1"
    assert selected.expected_behavior == "REFUSAL"


def test_select_diagnostic_case_uses_requested_behavior_by_default() -> None:
    selected = select_diagnostic_case(
        (_case(), _case(case_id="refusal-1", behavior="REFUSAL")),
        workspace_id="workspace",
        case_id=None,
        question=None,
        behavior="REFUSAL",
    )

    assert selected.id == "refusal-1"
    assert selected.expected_behavior == "REFUSAL"


def test_build_diagnostic_case_preserves_custom_answer_contract() -> None:
    case = build_diagnostic_case(
        workspace_id="workspace",
        case_id="custom-answer",
        question="refunds accepted 30 days",
        behavior="ANSWER",
    )

    assert case.id == "custom-answer"
    assert case.question == "refunds accepted 30 days"
    assert case.expected_behavior == "ANSWER"
    assert case.workspace_id == "workspace"


def test_build_diagnostic_case_preserves_custom_refusal_contract() -> None:
    case = build_diagnostic_case(
        workspace_id="workspace",
        case_id="custom-refusal",
        question="the and or",
        behavior="REFUSAL",
    )

    assert case.expected_behavior == "REFUSAL"
    assert case.refusal_expectation == "INSUFFICIENT_EVIDENCE"


def test_production_source_pythonpath_pins_worktree_before_inherited_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PYTHONPATH", "inherited-source")

    paths = current_source_pythonpath().split(os.pathsep)

    assert paths[0].endswith("backend\\src") or paths[0].endswith("backend/src")
    assert paths[1] == "inherited-source"


@pytest.mark.parametrize(
    "mode",
    ["missing", "response-trace-id-mismatch", "workspace-mismatch", "unauthorized"],
)
def test_trace_fault_injector_exercises_fail_closed_production_seams(mode: str) -> None:
    @dataclass(frozen=True)
    class Trace:
        trace_id: str
        workspace_id: str

    @dataclass
    class Reader:
        trace: Trace

        def read_trace(self, *, workspace_id: str, **_kwargs):
            if workspace_id != "workspace":
                raise LookupError("unauthorized")
            return self.trace

    reader = TraceFaultInjectingReader(
        Reader(Trace("trace-1", "workspace")), mode=mode
    )

    if mode in {"missing", "unauthorized"}:
        with pytest.raises(LookupError):
            reader.read_trace(trace_id="trace-1", workspace_id="workspace")
        return

    result = reader.read_trace(trace_id="trace-1", workspace_id="workspace")
    if mode == "response-trace-id-mismatch":
        assert result.trace_id != "trace-1"
        assert result.workspace_id == "workspace"
    else:
        assert result.trace_id == "trace-1"
        assert result.workspace_id != "workspace"
