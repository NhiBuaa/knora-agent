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
