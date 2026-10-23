import hashlib
import json
import sys
from datetime import UTC, datetime

import httpx
import pytest
from evals.runners.langfuse_bridge import BridgeError, export_report, main, preview_report


def _report():
    return {
        "observations": [
            {
                "case_id": "case-1",
                "trace_id": "trace-1",
                "status": "observed",
                "decision": "ANSWER",
                "retrieval_latency_ms": 12.5,
                "end_to_end_latency_ms": 42.25,
                "retrieval_configuration_id": "private config name",
                "generation_evidence": [{"content": "RAW_EVIDENCE_SENTINEL"}],
                "public_answer": "RAW_ANSWER_SENTINEL",
                "question": "RAW_QUESTION_SENTINEL",
                "provider_error": {"nested": "RAW_ERROR_SENTINEL"},
                "credentials": {"token": "RAW_CREDENTIAL_SENTINEL"},
                "source_bindings": [{"source_key": "RAW_SOURCE_SENTINEL"}],
            }
        ],
        "provenance": {"workspace_id": "RAW_WORKSPACE_SENTINEL"},
    }


def _raw_report():
    return json.dumps(_report(), sort_keys=True).encode()


def test_preview_is_deterministic_opaque_and_only_allowlisted() -> None:
    raw = _raw_report()
    imported_at = datetime(2026, 10, 14, tzinfo=UTC)
    first = preview_report(raw, project_key=b"project-secret-1234567890", imported_at=imported_at)
    assert first == preview_report(
        raw, project_key=b"project-secret-1234567890", imported_at=imported_at
    )
    assert first != preview_report(
        raw, project_key=b"different-project-secret", imported_at=imported_at
    )
    body = json.dumps(first, sort_keys=True)
    for sentinel in (
        "RAW_EVIDENCE_SENTINEL",
        "RAW_ANSWER_SENTINEL",
        "RAW_QUESTION_SENTINEL",
        "RAW_ERROR_SENTINEL",
        "RAW_CREDENTIAL_SENTINEL",
        "RAW_SOURCE_SENTINEL",
        "RAW_WORKSPACE_SENTINEL",
        "case-1",
        "trace-1",
        "private config name",
    ):
        assert sentinel not in body
    span = first["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
    attrs = {item["key"]: item["value"] for item in span["attributes"]}
    assert attrs["langfuse.trace.metadata.retrieval_latency_ms"] == {"doubleValue": 12.5}
    assert attrs["langfuse.trace.metadata.end_to_end_latency_ms"] == {"doubleValue": 42.25}
    assert len(span["traceId"]) == 32
    assert len(span["spanId"]) == 16
    assert span["startTimeUnixNano"] == span["endTimeUnixNano"] == "1791936000000000000"
    assert first["source_report_sha256"] == "sha256:" + hashlib.sha256(raw).hexdigest()
    assert (
        first["payload_sha256"]
        == hashlib.sha256(
            json.dumps(first["resourceSpans"], sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
    )


def _approved_preview():
    imported_at = datetime(2026, 10, 14, tzinfo=UTC)
    payload = preview_report(
        _raw_report(), project_key=b"project-secret-1234567890", imported_at=imported_at
    )
    return imported_at, payload["payload_sha256"]


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -1, True, "3.0"])
def test_bad_duration_fails_closed(bad) -> None:
    report = _report()
    report["observations"][0]["retrieval_latency_ms"] = bad
    with pytest.raises(BridgeError, match="DIAGNOSTIC_INVALID"):
        preview_report(json.dumps(report).encode(), project_key=b"project-secret-1234567890")


def test_known_observation_failure_status_is_preserved_and_arbitrary_text_is_not() -> None:
    report = _report()
    report["observations"][0]["status"] = "observation_failure"
    preview = preview_report(json.dumps(report).encode(), project_key=b"project-secret-1234567890")
    span = preview["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
    attrs = {item["key"]: item["value"] for item in span["attributes"]}
    assert attrs["langfuse.trace.metadata.observation_status"] == {
        "stringValue": "observation_failure"
    }
    report["observations"][0]["status"] = "RAW_ERROR_SENTINEL"
    preview = preview_report(json.dumps(report).encode(), project_key=b"project-secret-1234567890")
    assert "RAW_ERROR_SENTINEL" not in json.dumps(preview)


def test_export_rebuilds_allowlist_through_real_sdk_mock_transport() -> None:
    requests = []
    imported_at, digest = _approved_preview()

    def endpoint(request):
        requests.append(request)
        return httpx.Response(200, json={})

    with httpx.Client(transport=httpx.MockTransport(endpoint)) as transport:
        exported = export_report(
            _raw_report(),
            project_key=b"project-secret-1234567890",
            public_key="pk-test",
            secret_key="sk-test",
            httpx_client=transport,
            imported_at=imported_at,
            reviewed_payload_sha256=digest,
        )
    assert exported["status"] == "exported"
    assert len(requests) == 1
    assert requests[0].url == "https://jp.cloud.langfuse.com/api/public/otel/v1/traces"
    assert requests[0].headers["x-langfuse-ingestion-version"] == "4"
    sent = json.loads(requests[0].content)
    assert sent["resourceSpans"] == exported["payload"]["resourceSpans"]
    assert "RAW_" not in requests[0].content.decode()


def test_export_rejects_partial_success_without_echoing_error() -> None:
    imported_at, digest = _approved_preview()
    with (
        httpx.Client(
            transport=httpx.MockTransport(
                lambda _request: httpx.Response(
                    200, json={"partialSuccess": {"rejectedSpans": 1, "errorMessage": "secret"}}
                )
            )
        ) as transport,
        pytest.raises(BridgeError, match="EXPORT_REJECTED"),
    ):
        export_report(
            _raw_report(),
            project_key=b"project-secret-1234567890",
            public_key="pk-test",
            secret_key="sk-test",
            httpx_client=transport,
            imported_at=imported_at,
            reviewed_payload_sha256=digest,
        )


def test_export_requires_review_of_exact_payload_before_sdk_or_http() -> None:
    with (
        httpx.Client(
            transport=httpx.MockTransport(lambda _request: pytest.fail("unexpected HTTP"))
        ) as transport,
        pytest.raises(BridgeError, match="EXPORT_NOT_APPROVED"),
    ):
        export_report(
            _raw_report(),
            project_key=b"project-secret-1234567890",
            public_key="pk-test",
            secret_key="sk-test",
            httpx_client=transport,
        )


def test_preview_does_not_read_ambient_keys(monkeypatch) -> None:
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "ambient-secret")
    preview = preview_report(_raw_report(), project_key=b"project-secret-1234567890")
    assert "ambient-secret" not in json.dumps(preview)


def test_preview_cli_publishes_immutable_local_report(tmp_path, monkeypatch) -> None:
    source = tmp_path / "m3.json"
    key = tmp_path / "key"
    output = tmp_path / "preview.json"
    source.write_bytes(_raw_report())
    key.write_bytes(b"project-secret-1234567890")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "langfuse_bridge",
            "--report",
            str(source),
            "--project-key-file",
            str(key),
            "--output",
            str(output),
        ],
    )
    assert main() == 0
    first = output.read_bytes()
    assert (
        json.loads(first)["source_report_sha256"]
        == "sha256:" + hashlib.sha256(_raw_report()).hexdigest()
    )
    assert main() == 2
    assert output.read_bytes() == first


def test_preview_preserves_native_attempt_and_attempt_id() -> None:
    report = _report()
    report["observations"][0]["attempt"] = 2
    report["observations"][0]["attempt_id"] = "saved-run:case-1:2"
    preview = preview_report(json.dumps(report).encode(), project_key=b"project-secret-1234567890")
    span = preview["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
    attrs = {item["key"]: item["value"] for item in span["attributes"]}
    assert attrs["langfuse.trace.metadata.attempt_number"] == {"doubleValue": 2.0}
    assert "trace_ids" in preview
    assert len(preview["trace_ids"]) == 1


def test_receipt_manager_enforces_exclusive_creation_and_no_clobber(tmp_path) -> None:
    from evals.runners.langfuse_bridge import ReceiptManager

    receipt_file = tmp_path / "test_receipt.json"
    data = ReceiptManager.reserve(
        receipt_file,
        approval_id="app-1",
        project_key_fingerprint="fp12345",
        payload_sha256="a" * 64,
        trace_ids=["t1"],
        observation_ids=["o1"],
        imported_at="2026-10-23T00:00:00Z",
    )
    assert data["status"] == "RESERVED"

    # Exclusive creation prevents second reservation
    with pytest.raises(BridgeError, match="RECEIPT_ALREADY_EXISTS"):
        ReceiptManager.reserve(
            receipt_file,
            approval_id="app-2",
            project_key_fingerprint="fp12345",
            payload_sha256="b" * 64,
            trace_ids=["t2"],
            observation_ids=["o2"],
            imported_at="2026-10-23T00:00:00Z",
        )

    # Update succeeds atomically
    updated = ReceiptManager.update(receipt_file, status="POSTED", http_status=200)
    assert updated["status"] == "POSTED"
    assert updated["http_status"] == 200
    assert ReceiptManager.read(receipt_file)["status"] == "POSTED"


def test_delete_traces_exact_ids_and_bounded_cap() -> None:
    from evals.runners.langfuse_bridge import delete_traces

    # Over cap (>3) rejected before network
    with pytest.raises(BridgeError, match="DELETE_CAP_EXCEEDED"):
        delete_traces(None, ["t1", "t2", "t3", "t4"])

    # Invalid IDs rejected
    with pytest.raises(BridgeError, match="DELETE_IDS_INVALID"):
        delete_traces(None, [])

    # Successful delete call
    requests = []

    def endpoint(request):
        requests.append(request)
        return httpx.Response(200, json={"status": "ok"})

    with httpx.Client(
        base_url="https://jp.cloud.langfuse.com", transport=httpx.MockTransport(endpoint)
    ) as client:
        res = delete_traces(client, ["trace-1", "trace-2"])
        assert res["status"] == "delete_accepted"
        assert len(requests) == 1
        assert requests[0].method == "DELETE"
        assert requests[0].url == "https://jp.cloud.langfuse.com/api/public/traces"
        sent_body = json.loads(requests[0].content)
        assert sent_body == {"traceIds": ["trace-1", "trace-2"]}


def test_verify_deleted_polls_until_gone_or_fails() -> None:
    from evals.runners.langfuse_bridge import verify_deleted

    # Case 1: Trace disappears on second poll
    call_count = {"trace": 0}

    def mock_server(request):
        if request.url.path == "/api/public/traces/t1":
            call_count["trace"] += 1
            if call_count["trace"] == 1:
                return httpx.Response(200, json={"id": "t1"})
            return httpx.Response(404, json={"message": "not found"})
        if request.url.path == "/api/public/observations":
            return httpx.Response(200, json=[])
        return httpx.Response(404)

    with httpx.Client(
        base_url="https://jp.cloud.langfuse.com", transport=httpx.MockTransport(mock_server)
    ) as client:
        assert verify_deleted(client, ["t1"], max_polls=3) is True

    # Case 2: Trace persists past max_polls -> raises
    with (
        httpx.Client(
            base_url="https://jp.cloud.langfuse.com",
            transport=httpx.MockTransport(
                lambda r: httpx.Response(
                    200, json={"id": "persist"} if "/traces/" in str(r.url) else []
                )
            ),
        ) as client,
        pytest.raises(BridgeError, match="DELETION_NOT_VERIFIED_persist"),
    ):
        verify_deleted(client, ["persist"], max_polls=2)


def test_pilot_cycle_enforces_canary_then_real_and_full_lifecycle(tmp_path) -> None:
    from evals.runners.langfuse_bridge import run_langfuse_pilot

    canary_report = _report()
    real_report = {
        "observations": [
            {**_report()["observations"][0], "case_id": "real-1", "trace_id": "r-trace-1"},
            {**_report()["observations"][0], "case_id": "real-2", "trace_id": "r-trace-2"},
        ]
    }
    raw_canary = json.dumps(canary_report).encode()
    raw_real = json.dumps(real_report).encode()

    deleted_traces = set()
    requests_log = []

    def mock_langfuse_api(request):
        requests_log.append((request.method, str(request.url)))
        path = request.url.path
        if request.method == "POST" and "otel/v1/traces" in path:
            return httpx.Response(200, json={})
        if request.method == "DELETE" and path == "/api/public/traces":
            body = json.loads(request.content)
            for tid in body.get("traceIds", []):
                deleted_traces.add(tid)
            return httpx.Response(200, json={"status": "ok"})
        if request.method == "GET" and path.startswith("/api/public/traces/"):
            tid = path.split("/")[-1]
            if tid in deleted_traces:
                return httpx.Response(404, json={"message": "deleted"})
            return httpx.Response(200, json={"id": tid})
        if request.method == "GET" and path == "/api/public/observations":
            tid = request.url.params.get("traceId")
            if tid in deleted_traces:
                return httpx.Response(200, json=[])
            return httpx.Response(200, json=[{"id": f"obs-{tid}"}])
        if request.method == "GET" and path == "/api/public/scores":
            return httpx.Response(200, json=[])
        return httpx.Response(404)

    with httpx.Client(
        base_url="https://jp.cloud.langfuse.com",
        transport=httpx.MockTransport(mock_langfuse_api),
    ) as client:
        result = run_langfuse_pilot(
            raw_canary,
            raw_real,
            project_key=b"project-secret-1234567890",
            public_key="pk-test",
            secret_key="sk-test",
            httpx_client=client,
            receipt_dir=tmp_path / "receipts",
            approval_id="pilot-test-app",
        )
        assert result["status"] == "COMPLETED"
        assert len(result["real_trace_ids"]) == 2

    # Verify requests count
    posts = [r for r in requests_log if r[0] == "POST"]
    deletes = [r for r in requests_log if r[0] == "DELETE"]
    assert len(posts) == 2  # exactly 2 POSTs
    assert len(deletes) == 2  # exactly 2 DELETEs
