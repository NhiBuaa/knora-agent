from copy import deepcopy
from types import SimpleNamespace as NS

import httpx
import pytest
from evals.runners.pdf_retrieval_v3 import PdfHttpExecutor, build_report, publish_json
from evals.runners.pdf_source_binding import digest


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "fault",
    [
        None,
        "parent",
        "document",
        "workspace",
        "version",
        "index_failed",
        "index_superseded",
        "no_child",
        "not_ready",
        "not_served",
        "index_changed",
        "unavailable",
    ],
)
async def test_lexical_upload_waits_for_linked_index_and_serving_snapshot(tmp_path, fault):
    from evals.runners.milestone_3 import ObservationFailure

    source_path = tmp_path / "fixture.pdf"
    source_path.write_bytes(b"pdf")
    submitted = {
        "ingestion_job_id": "extraction",
        "document_id": "document",
        "document_version_id": "version",
    }
    terminal = {"ingestion_job_id": "extraction", "status": "succeeded"}
    ready = {
        "workspace_id": "workspace",
        "document_id": "document",
        "current_document_version_id": "version",
        "ingestion_job_id": "extraction",
        "indexing_job_id": "index",
        "indexing_status": "succeeded",
        "lexical_readiness": "ready",
        "served_document_version_id": "version",
        "answer_availability": "available",
    }
    if fault in {"parent", "document", "workspace", "version"}:
        ready[
            {
                "parent": "ingestion_job_id",
                "document": "document_id",
                "workspace": "workspace_id",
                "version": "current_document_version_id",
            }[fault]
        ] = "foreign"
    elif fault in {"index_failed", "index_superseded"}:
        ready["indexing_status"] = fault.removeprefix("index_")
    elif fault == "no_child":
        ready["indexing_job_id"] = None
    elif fault == "not_ready":
        ready["lexical_readiness"] = "not_indexed"
    elif fault == "not_served":
        ready["served_document_version_id"] = "previous"
    elif fault == "index_changed":
        ready["indexing_job_id"] = "foreign"
    elif fault == "unavailable":
        ready["answer_availability"] = "unavailable"
    calls = []

    def transport(request):
        calls.append((request.method, request.url.path))
        if request.method == "POST":
            return httpx.Response(202, json=submitted)
        if "ingestion-jobs" in request.url.path:
            return httpx.Response(200, json=terminal)
        if calls.count(("GET", request.url.path)) == 1:
            return httpx.Response(
                200,
                json={
                    **ready,
                    "indexing_job_id": "index"
                    if fault == "index_changed"
                    else ready["indexing_job_id"],
                    "indexing_status": "processing",
                    "lexical_readiness": "not_indexed",
                    "served_document_version_id": None,
                },
            )
        return httpx.Response(200, json=ready)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(transport), base_url="http://test"
    ) as client:
        executor = PdfHttpExecutor(
            client=client,
            headers={},
            reader=None,
            workspace_id="workspace",
            run_id="run",
            embedding_configuration_id=None,
            poll_interval=0,
            max_polls=3,
        )
        source = NS(id="source", path=source_path)
        if fault:
            expected = (
                "LEXICAL_UPLOAD_IDENTITY_MISMATCH"
                if fault in {"parent", "document", "workspace", "version", "index_changed"}
                else "LEXICAL_INDEX_FAILED"
                if fault in {"index_failed", "index_superseded"}
                else "LEXICAL_INDEX_TIMEOUT"
            )
            with pytest.raises(ObservationFailure, match=expected):
                await executor.upload(source)
        else:
            result = await executor.upload(source)
            assert result["ingestion_job_id"] == "extraction"
            assert result["status"] == "succeeded"
            assert result["indexing_job_id"] == "index"
            assert result["lexical_readiness"] == "ready"
            assert calls == [
                ("POST", "/v1/workspaces/workspace/documents"),
                ("GET", "/v1/workspaces/workspace/ingestion-jobs/extraction"),
                ("GET", "/v1/workspaces/workspace/documents/document"),
                ("GET", "/v1/workspaces/workspace/documents/document"),
            ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "embedding,status", [("dense-config", "succeeded"), (None, "failed"), (None, "superseded")]
)
async def test_upload_preserves_dense_and_failed_extraction_terminal_results(
    tmp_path, embedding, status
):
    source_path = tmp_path / "fixture.pdf"
    source_path.write_bytes(b"pdf")
    calls = []
    terminal = {"ingestion_job_id": "extraction", "status": status}

    def transport(request):
        calls.append(request.url.path)
        if request.method == "POST":
            return httpx.Response(
                202,
                json={
                    "ingestion_job_id": "extraction",
                    "document_id": "document",
                    "document_version_id": "version",
                },
            )
        assert request.url.path.endswith("/ingestion-jobs/extraction")
        return httpx.Response(200, json=terminal)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(transport), base_url="http://test"
    ) as client:
        executor = PdfHttpExecutor(
            client=client,
            headers={},
            reader=None,
            workspace_id="workspace",
            run_id="run",
            embedding_configuration_id=embedding,
            poll_interval=0,
        )
        assert await executor.upload(NS(id="source", path=source_path)) == terminal
    assert len(calls) == 2


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
async def test_pdf_capture_retains_bounded_prethreshold_diagnostics_and_raw_scores():
    persisted = trace()
    persisted.trace_schema_version = 2
    persisted.branch_observation_schema_version = 1
    persisted.candidate_decisions = ()
    persisted.branch_observations = (
        {
            "schema_version": 1,
            "branch": "vector",
            "status": "BELOW_THRESHOLD",
            "chunk_id": "below",
            "similarity": 0.6253242865,
            "cosine_distance": 0.3746757135,
        },
    )
    reader = NS(read_trace=lambda **_: persisted, read_pdf_chunks=lambda **_: ())
    async with httpx.AsyncClient(
        base_url="http://test",
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=refusal())),
    ) as client:
        row = await PdfHttpExecutor(
            client=client,
            headers={},
            reader=reader,
            workspace_id="workspace",
            run_id="run",
            embedding_configuration_id=persisted.embedding_configuration_id,
        ).execute(case())
    assert row["failure_code"] is None
    diagnostic = row["retrieval_diagnostics"]
    assert diagnostic["branch_observations"][0]["similarity"] == 0.6253242865
    assert diagnostic["unobserved_candidates"] == "unknown"
    assert row["candidates"] == []


def test_historical_trace_without_fields_stays_unavailable():
    from evals.runners.pdf_retrieval_v3 import project_retrieval_diagnostics

    assert project_retrieval_diagnostics(trace()) == {
        "schema_version": 1,
        "status": "unavailable",
        "reason": "TRACE_FIELDS_UNAVAILABLE",
    }


def test_bm25_report_retains_native_depth_beyond_primary_candidates():
    from evals.runners.pdf_retrieval_v3 import project_retrieval_diagnostics

    persisted = trace()
    persisted.candidates = ()
    persisted.alias_mapping = {}
    persisted.candidate_decisions = ()
    persisted.trace_schema_version = 3
    persisted.branch_observation_schema_version = 2
    persisted.branch_observations = tuple(
        {
            "schema_version": 2,
            "branch": "bm25",
            "score_kind": "bm25",
            "status": "REVOKED" if rank <= 8 else "RANK_LIMIT",
            "chunk_id": str(rank),
            "branch_rank": rank,
            "raw_score": float(20 - rank),
            "index_generation_id": "generation",
            "lexical_policy_id": "profile",
        }
        for rank in range(1, 11)
    )
    persisted.provider_metadata["retrieval"] = {
        "mode": "bm25-only",
        "score_policy": {"candidate_limit": 8, "query_limit": 200},
    }
    diagnostic = project_retrieval_diagnostics(persisted)
    assert diagnostic["native_top200"] == list(persisted.branch_observations)
    row = {
        "case_id": "q1",
        "failure_code": None,
        "response_sha256": "r",
        "selected_chunk_ids": [],
        "decision": "REFUSAL",
        "retrieval_diagnostics": diagnostic,
    }
    dataset = NS(cases=(case(),), dataset_sha256="a", corpus_sha256="b")
    supplement = build_report(dataset, [row], {"limit": ("9",)}, {})["cases"][0][
        "retrieval_diagnostics"
    ]
    assert supplement["coverage"] == {
        "retrieved_top8": [False],
        "retrieved_top200": [True],
        "generation_selected": [False],
    }
    assert supplement["coverage_scope"] == "native_top200_observations"
    assert supplement["ordered_candidate_ids"] == []


@pytest.mark.parametrize("ranks", [[2], [1, 1], list(range(1, 202))])
def test_bm25_diagnostics_reject_incomplete_or_oversized_native_rank_window(ranks):
    from evals.runners.milestone_3 import ObservationFailure
    from evals.runners.pdf_retrieval_v3 import project_retrieval_diagnostics

    persisted = trace()
    persisted.candidates, persisted.candidate_decisions = (), ()
    persisted.trace_schema_version, persisted.branch_observation_schema_version = 3, 2
    persisted.provider_metadata["retrieval"] = {"mode": "bm25-only"}
    persisted.branch_observations = tuple(
        {"branch": "bm25", "status": "REVOKED", "branch_rank": rank, "chunk_id": str(index)}
        for index, rank in enumerate(ranks)
    )
    with pytest.raises(ObservationFailure, match="NATIVE_DIAGNOSTICS_MISMATCH"):
        project_retrieval_diagnostics(persisted)


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


def test_supplement_keeps_top8_top200_and_generation_coverage_separate():
    diagnostic = {
        "schema_version": 1,
        "status": "observed",
        "ordered_candidate_ids": [str(i) for i in range(10)],
        "generation_evidence_chunk_ids": ["0"],
        "branch_observations": [{"raw_score": 3.25}],
        "candidate_decisions": [{"decision_reason": "CHUNK_COUNT_LIMIT"}],
    }
    row = {
        "case_id": "q1",
        "failure_code": None,
        "response_sha256": "r",
        "selected_chunk_ids": ["0"],
        "decision": "ANSWER",
        "retrieval_diagnostics": diagnostic,
    }
    dataset = NS(cases=(case(),), dataset_sha256="a", corpus_sha256="b")
    report = build_report(dataset, [row], {"limit": ("9",)}, {})
    supplement = report["cases"][0]["retrieval_diagnostics"]
    assert supplement["coverage"] == {
        "retrieved_top8": [False],
        "retrieved_top200": [True],
        "generation_selected": [False],
    }
    assert supplement["branch_observations"] == [{"raw_score": 3.25}]
    assert supplement["candidate_decisions"][0]["decision_reason"] == "CHUNK_COUNT_LIMIT"
    assert report["metrics"] == {"all_evidence_groups_covered": 0.0}
    missing = build_report(dataset, [row], {"limit": ()}, {})
    assert missing["cases"][0]["retrieval_diagnostics"]["coverage"] is None
    assert missing["denominators"]["extraction_or_mapping_missing"] == 1


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


def test_bm25_comparison_keeps_baseline_depth_selected_failures_and_full_denominator():
    from evals.runners.pdf_retrieval_v3 import build_bm25_comparison

    control = NS(id="control", evidence_groups=())
    unmapped = NS(id="missing", evidence_groups=(("missing-anchor",),))
    dataset = NS(
        cases=(case(), unmapped, case("failed"), case("not-run"), control),
        dataset_sha256="gold",
        corpus_sha256="corpus",
    )
    bm25 = [
        {
            "case_id": "q1",
            "failure_code": None,
            "candidates": [{"chunk_id": "1"}],
            "selected_chunk_ids": ["1"],
            "retrieval_diagnostics": {
                "native_top200": [
                    {"branch": "bm25", "chunk_id": str(i), "branch_rank": i} for i in range(1, 11)
                ]
            },
        },
        {"case_id": "failed", "failure_code": "LEXICAL_RETRIEVAL_UNAVAILABLE"},
        {
            "case_id": "control",
            "failure_code": None,
            "candidates": [],
            "selected_chunk_ids": [],
            "retrieval_diagnostics": {"native_top200": []},
        },
    ]
    baseline = [
        {
            "case_id": "q1",
            "failure_code": None,
            "candidates": [{"chunk_id": "9"}],
            "selected_chunk_ids": [],
        },
        {"case_id": "missing", "failure_code": None, "candidates": [], "selected_chunk_ids": []},
    ]
    before = deepcopy((bm25, baseline))
    report = build_bm25_comparison(dataset, bm25, baseline, {"limit": ("9",)})
    assert report["denominator"] == 5
    assert [row["case_id"] for row in report["cases"]] == [c.id for c in dataset.cases]
    observed = report["cases"][0]
    assert observed["bm25"]["top8_group_coverage"] == [False]
    assert observed["bm25"]["top200_group_coverage"] == [True]
    assert observed["bm25"]["selected_group_coverage"] == [False]
    assert observed["baseline_b"]["candidate_group_coverage"] == [True]
    assert observed["baseline_b"]["selected_group_coverage"] == [False]
    assert observed["bm25"]["native_top200_ids"] == [str(i) for i in range(1, 11)]
    assert report["cases"][1]["mapping_status"] == "extraction_or_mapping_missing"
    assert report["cases"][1]["baseline_b"]["candidate_group_coverage"] is None
    assert report["cases"][2]["bm25"] == {
        "status": "observation_failed",
        "failure_code": "LEXICAL_RETRIEVAL_UNAVAILABLE",
    }
    assert report["cases"][3]["bm25"] == {"status": "not_run"}
    assert report["cases"][4]["mapping_status"] == "no_answer_control"
    assert report["cases"][4]["bm25"]["top8_group_coverage"] is None
    assert report["semantic_quality"] == "not_assessed"
    assert (bm25, baseline) == before


@pytest.mark.parametrize(
    "fault", ["duplicate_case", "foreign_case", "refill", "selected_outside_top8"]
)
def test_bm25_comparison_rejects_bad_case_identity_or_refilled_evidence(fault):
    from evals.runners.pdf_retrieval_v3 import build_bm25_comparison

    dataset = NS(cases=(case(),), dataset_sha256="gold", corpus_sha256="corpus")
    row = {
        "case_id": "q1",
        "failure_code": None,
        "candidates": [{"chunk_id": "9"}],
        "selected_chunk_ids": [],
        "retrieval_diagnostics": {
            "native_top200": [
                {"branch": "bm25", "chunk_id": str(i), "branch_rank": i} for i in range(1, 11)
            ]
        },
    }
    rows = [row]
    if fault == "duplicate_case":
        rows.append(deepcopy(row))
    elif fault == "foreign_case":
        row["case_id"] = "foreign"
    elif fault == "selected_outside_top8":
        row["candidates"] = [{"chunk_id": "1"}]
        row["selected_chunk_ids"] = ["9"]
    with pytest.raises(ValueError):
        build_bm25_comparison(dataset, rows, [], {"limit": ("9",)})


@pytest.mark.parametrize("fault", ["reordered", "gap", "duplicate_rank", "oversized"])
def test_saved_bm25_comparison_uses_validated_native_ranks_not_json_position(fault):
    from evals.runners.pdf_retrieval_v3 import build_bm25_comparison

    dataset = NS(cases=(case(),), dataset_sha256="gold", corpus_sha256="corpus")
    native = [
        {"branch": "bm25", "chunk_id": str(rank), "branch_rank": rank} for rank in range(1, 11)
    ]
    row = {
        "case_id": "q1",
        "failure_code": None,
        "candidates": [],
        "selected_chunk_ids": [],
        "retrieval_diagnostics": {"native_top200": native},
    }
    if fault == "reordered":
        native.insert(0, native.pop(8))
        before = deepcopy(row)
        report = build_bm25_comparison(dataset, [row], [], {"limit": ("9",)})
        assert report["cases"][0]["bm25"]["top8_group_coverage"] == [False]
        assert report["cases"][0]["bm25"]["native_top200_ids"] == [str(i) for i in range(1, 11)]
        assert row == before
    else:
        if fault == "gap":
            native.pop(1)
        elif fault == "duplicate_rank":
            native[1]["branch_rank"] = 1
        else:
            native.extend(
                {"branch": "bm25", "chunk_id": str(rank), "branch_rank": rank}
                for rank in range(11, 202)
            )
        with pytest.raises(ValueError, match="NATIVE_DIAGNOSTICS_MISMATCH"):
            build_bm25_comparison(dataset, [row], [], {"limit": ("9",)})


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


def test_build_report_with_ranking_dataset_computes_macro_ndcg_and_ranking_metrics():
    from evals.runners.pdf_retrieval_v3 import build_report
    from evals.runners.retrieval_ranking import RankingJudgment

    j_a = RankingJudgment(query_id="q1", chunk_id="chunk-1", content_checksum="chk1", grade=1)
    j_b = RankingJudgment(query_id="q1", chunk_id="chunk-2", content_checksum="chk2", grade=0)

    rk_case = NS(
        id="q1",
        judgments=(j_a, j_b),
        judgments_by_chunk_id={"chunk-1": j_a, "chunk-2": j_b},
    )
    ranking_dataset = NS(
        candidate_universe_ids=frozenset({"chunk-1", "chunk-2"}),
        cases_by_id={"q1": rk_case},
    )

    dataset = NS(cases=(case(id="q1"),), dataset_sha256="a", corpus_sha256="b")
    row = {
        "case_id": "q1",
        "failure_code": None,
        "response_sha256": "r",
        "selected_chunk_ids": ["chunk-1"],
        "candidates": [
            {"chunk_id": "chunk-1", "score": 1.0},
            {"chunk_id": "chunk-2", "score": 0.5},
        ],
        "decision": "ANSWER",
    }

    report = build_report(
        dataset,
        [row],
        {"limit": ("chunk-1",)},
        {},
        ranking_dataset=ranking_dataset,
    )

    assert report["metrics"]["all_evidence_groups_covered"] == 1.0
    assert report["metrics"]["macro_ndcg_at_10"] == 1.0
    assert report["metrics"]["macro_mrr"] == 1.0
    assert report["metrics"]["macro_hit_at_10"] == 1.0
    assert report["metrics"]["macro_recall_at_10"] == 1.0
    assert report["metrics"]["ranking_denominators"] == {
        "total": 1,
        "evaluable": 1,
        "not_applicable": 0,
        "missing_or_failed": 0,
    }
    case_res = report["cases"][0]
    assert case_res["ranking"]["ndcg"] == 1.0
    assert case_res["ranking"]["hit_at_10"] == 1.0
