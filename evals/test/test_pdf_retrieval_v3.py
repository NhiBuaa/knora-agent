from copy import deepcopy
from types import SimpleNamespace as NS

import httpx
import pytest
from evals.runners.pdf_retrieval_v3 import PdfHttpExecutor, build_report, publish_json
from evals.runners.pdf_source_binding import digest


def case(id="q1", parent=None):
    return NS(
        id=id,
        question="Policy?",
        parent_case_id=parent,
        expected_behavior="ANSWER",
        evidence_groups=(("limit",),),
    )


def trace():
    return NS(
        trace_id="trace-1",
        workspace_id="workspace",
        decision="REFUSAL",
        answer=None,
        refusal_reason="INSUFFICIENT_EVIDENCE",
        parsed_markers=(),
        candidates=(),
        alias_mapping={},
        retrieval_configuration_id="retrieval-evidence-containment-v1",
        embedding_configuration_id="embedding-cloudflare-qwen3-06b-1024-v1",
        provider_metadata={"generation": {}},
        retrieval_latency_ms=1.0,
    )


def refusal():
    return {
        "trace_id": "trace-1",
        "workspace_id": "workspace",
        "decision": "REFUSAL",
        "answer": None,
        "refusal_reason": "INSUFFICIENT_EVIDENCE",
        "citations": [],
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("drift", ["none", "answer", "workspace", "trace", "profile"])
async def test_exact_public_trace_binding(drift):
    persisted = trace()
    if drift == "answer":
        persisted.answer = "hidden answer"
    if drift == "workspace":
        persisted.workspace_id = "other"
    if drift == "trace":
        persisted.trace_id = "other-trace"
    if drift == "profile":
        persisted.embedding_configuration_id = "other-profile"
    reader = NS(read_trace=lambda **_: persisted, read_pdf_chunks=lambda **_: ())
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=refusal())),
        base_url="http://test",
    ) as client:
        executor = PdfHttpExecutor(
            client=client,
            headers={},
            reader=reader,
            workspace_id="workspace",
            run_id="run",
            embedding_configuration_id=trace().embedding_configuration_id,
        )
        row = await executor.execute(case())
    assert row["trace_id"] == "trace-1"
    assert row["attempt_id"] == "run:q1:1"
    assert row["failure_code"] == (None if drift == "none" else "OBSERVATION_MISMATCH")
    if drift == "none":
        assert row["response_sha256"] == digest(refusal())


@pytest.mark.asyncio
async def test_follow_up_polls_only_the_admitted_turn_and_checks_question():
    seen = []

    def transport(request):
        seen.append(request.url.path)
        if request.method == "POST":
            return httpx.Response(
                202,
                json={
                    "id": "turn-2",
                    "conversation_id": "conversation-1",
                    "question": "Policy?",
                    "status": "queued",
                },
            )
        return httpx.Response(
            200,
            json={
                "id": "turn-2",
                "conversation_id": "conversation-1",
                "question": "wrong question",
                "status": "refused",
                "result": refusal(),
            },
        )

    reader = NS(read_trace=lambda **_: trace(), read_pdf_chunks=lambda **_: ())
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(transport), base_url="http://test"
    ) as client:
        executor = PdfHttpExecutor(
            client=client,
            headers={},
            reader=reader,
            workspace_id="workspace",
            run_id="run",
            embedding_configuration_id=trace().embedding_configuration_id,
            poll_interval=0,
        )
        row = await executor.execute(case("q2", "q1"), conversation_id="conversation-1")
    assert row["failure_code"] == "TURN_MISMATCH"
    assert seen == [
        "/v1/workspaces/workspace/conversations/conversation-1/turns",
        "/v1/workspaces/workspace/conversations/conversation-1/turns/turn-2",
    ]


def test_report_keeps_missing_extraction_out_of_retrieval_denominator():
    dataset = NS(cases=(case(), case("q2"), case("q3")), dataset_sha256="a", corpus_sha256="b")
    base = {
        "case_id": "q1",
        "failure_code": None,
        "response_sha256": "r",
        "selected_chunk_ids": ["one"],
        "decision": "ANSWER",
    }
    missing = deepcopy(base)
    missing["case_id"] = "q2"
    report = build_report(dataset, [base, missing], {"limit": ()}, {})
    assert report["denominators"] == {
        "total": 3,
        "attempted": 2,
        "observed": 2,
        "retrieval_evaluable": 0,
        "extraction_or_mapping_missing": 2,
        "not_run": 1,
        "observation_failed": 0,
        "provider_failed": 0,
    }
    assert report["metrics"]["all_evidence_groups_covered"] is None
    assert report["cases"][2]["status"] == "not_run"
    assert report["tools"] == "not_run"


def test_response_review_cannot_be_reused_for_another_answer():
    dataset = NS(cases=(case(),), dataset_sha256="a", corpus_sha256="b")
    row = {
        "case_id": "q1",
        "failure_code": None,
        "response_sha256": "new",
        "selected_chunk_ids": ["one"],
        "decision": "ANSWER",
    }
    with pytest.raises(ValueError, match="response review"):
        build_report(
            dataset,
            [row],
            {"limit": ("one",)},
            {"q1": {"response_sha256": "old", "reviewer": "NhiBuaa", "correctness": True}},
        )


def test_publication_cannot_clobber_previous_run(tmp_path):
    path = tmp_path / "report.json"
    publish_json(path, {"run_id": "first"})
    with pytest.raises(FileExistsError):
        publish_json(path, {"run_id": "second"})
    assert "first" in path.read_text()


@pytest.mark.asyncio
async def test_provider_failure_is_not_a_malformed_trace_observation():
    reader = NS(read_trace=lambda **_: pytest.fail("no trace exists for failed provider"))
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(502, json={"error": {"code": "PROVIDER_REQUEST_FAILED"}})
        ),
        base_url="http://test",
    ) as client:
        executor = PdfHttpExecutor(
            client=client,
            headers={},
            reader=reader,
            workspace_id="workspace",
            run_id="run",
            embedding_configuration_id=trace().embedding_configuration_id,
        )
        row = await executor.execute(case())
    assert row["failure_code"] == "PROVIDER_FAILED"
    assert row["provider_error"] == "PROVIDER_REQUEST_FAILED"
    assert row["http_status"] == 502


@pytest.mark.asyncio
async def test_follow_up_rejects_trace_that_omits_parent_context():
    def transport(request):
        return httpx.Response(
            200,
            json={
                "id": "turn-2",
                "conversation_id": "conversation-1",
                "question": "Policy?",
                "status": "refused",
                "result": refusal(),
            },
        )

    reader = NS(read_trace=lambda **_: trace(), read_pdf_chunks=lambda **_: ())
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(transport), base_url="http://test"
    ) as client:
        executor = PdfHttpExecutor(
            client=client,
            headers={},
            reader=reader,
            workspace_id="workspace",
            run_id="run",
            embedding_configuration_id=trace().embedding_configuration_id,
            poll_interval=0,
        )
        row = await executor.execute(
            case("q2", "q1"), conversation_id="conversation-1", parent_turn_id="turn-1"
        )
    assert row["failure_code"] == "FOLLOW_UP_CONTEXT_MISSING"


@pytest.mark.asyncio
async def test_failed_parent_prevents_child_dispatch(tmp_path):
    from evals.runners.pdf_retrieval_v3 import collect_cases

    parent = {
        "run_id": "run",
        "case_id": "q1",
        "workspace_id": "workspace",
        "dataset_sha256": "a",
        "corpus_sha256": "b",
        "derivation_sha256": "d",
        "attempt": 1,
        "failure_code": "PROVIDER_FAILED",
        "conversation_id": "conversation-1",
    }
    publish_json(tmp_path / "case-q1-attempt-1.json", parent)
    dataset = NS(
        cases=(case(), case("q2", "q1"), case("q3")), dataset_sha256="a", corpus_sha256="b"
    )
    calls = []

    async def execute(current, **kwargs):
        calls.append(current.id)
        return {
            "run_id": "run",
            "case_id": current.id,
            "workspace_id": "workspace",
            "attempt": 1,
            "failure_code": None,
        }

    executor = NS(
        run_id="run",
        workspace_id="workspace",
        assert_not_paused=lambda: None,
        execute=execute,
        is_paused=lambda: False,
    )
    rows = await collect_cases(dataset, executor, tmp_path, derivation_sha256="d")
    assert rows[1]["failure_code"] == "FOLLOW_UP_CONTEXT_MISSING"
    assert calls == ["q3"]
    assert not (tmp_path / "dispatch-q2-attempt-1.json").exists()


@pytest.mark.asyncio
async def test_failed_conversation_provider_is_classified_before_trace_read():
    result = {
        "id": "turn-1",
        "conversation_id": "conversation-1",
        "question": "Policy?",
        "status": "failed",
        "error_code": "PROVIDER_REQUEST_FAILED",
    }
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=result)),
        base_url="http://test",
    ) as client:
        executor = PdfHttpExecutor(
            client=client,
            headers={},
            reader=None,
            workspace_id="workspace",
            run_id="run",
            embedding_configuration_id=trace().embedding_configuration_id,
            poll_interval=0,
        )
        row = await executor.execute(case(), conversation_id="conversation-1")
    assert row["failure_code"] == "PROVIDER_FAILED"
    assert row["provider_error"] == "PROVIDER_REQUEST_FAILED"


@pytest.mark.parametrize(
    "changed", ["run_id", "workspace_id", "dataset_sha256", "corpus_sha256", "derivation_sha256"]
)
def test_saved_report_artifact_rejects_mixed_run_or_source(changed):
    from evals.runners.pdf_retrieval_v3 import validate_artifact_identity

    row = {
        "run_id": "run",
        "workspace_id": "workspace",
        "dataset_sha256": "a",
        "corpus_sha256": "b",
        "derivation_sha256": "d",
    }
    row[changed] = "other"
    with pytest.raises(ValueError, match="identity"):
        validate_artifact_identity(
            row,
            NS(dataset_sha256="a", corpus_sha256="b"),
            "run",
            "workspace",
            derivation_sha256="d",
        )


def test_report_counter_file_must_belong_to_the_same_baseline_run():
    from evals.runners.pdf_retrieval_v3 import validate_counter_identity

    dataset = NS(dataset_sha256="a", corpus_sha256="b")
    counters = {
        "run_identity": {
            "run_id": "other",
            "corpus_sha256": "b",
            "dataset_sha256": "a",
            "baseline": "pypdf-layout-v2/qwen3-06b/gpt-oss20b/containment0.65",
        }
    }
    with pytest.raises(ValueError, match="identity"):
        validate_counter_identity(counters, dataset, "run")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "changed", ["run_id", "workspace_id", "dataset_sha256", "derivation_sha256"]
)
async def test_quota_resume_rejects_drift_before_any_new_dispatch(tmp_path, changed):
    from evals.runners.pdf_retrieval_v3 import collect_cases

    row = {
        "run_id": "run",
        "case_id": "q1",
        "workspace_id": "workspace",
        "dataset_sha256": "a",
        "corpus_sha256": "b",
        "derivation_sha256": "d",
        "attempt": 1,
        "failure_code": "QUOTA_PAUSED",
    }
    row[changed] = "changed"
    publish_json(tmp_path / "case-q1-attempt-1.json", row)
    dataset = NS(cases=(case(),), dataset_sha256="a", corpus_sha256="b")
    executor = NS(run_id="run", workspace_id="workspace")
    with pytest.raises(ValueError, match="identity"):
        await collect_cases(dataset, executor, tmp_path, derivation_sha256="d", resume_quota=True)
