"""Offline M3 metadata preview and an explicitly invoked, narrow Langfuse export seam."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import math
from datetime import UTC, datetime
from pathlib import Path

import httpx
from evals.runners.evaluation import write_report_atomic


class BridgeError(ValueError):
    pass


def _opaque(key: bytes, kind: str, value: str) -> str:
    return hmac.new(key, f"knora-langfuse-v1\0{kind}\0{value}".encode(), hashlib.sha256).hexdigest()


def _attribute(name: str, value: str | float) -> dict:
    kind = "doubleValue" if type(value) is float else "stringValue"
    return {"key": f"langfuse.trace.metadata.{name}", "value": {kind: value}}


def preview_report(
    raw_report: bytes, *, project_key: bytes, imported_at: datetime | None = None
) -> dict:
    """Project only fixed safe fields; source report and arbitrary strings stay local."""
    if not isinstance(project_key, bytes) or len(project_key) < 16:
        raise BridgeError("PROJECT_KEY_INVALID")
    try:
        source = json.loads(raw_report)
        observations = source["observations"]
        if not isinstance(observations, list) or not observations:
            raise ValueError
        run_source = "sha256:" + hashlib.sha256(raw_report).hexdigest()
        moment = imported_at or datetime.now(UTC)
        if moment.tzinfo is None:
            raise ValueError
        when = str(int(moment.timestamp() * 1_000_000_000))
        spans = []
        seen = set()
        for item in observations:
            case = item["case_id"]
            trace = item.get("trace_id")
            if (
                not isinstance(case, str)
                or not case
                or (trace is not None and not isinstance(trace, str))
            ):
                raise ValueError
            if case in seen:
                raise ValueError
            seen.add(case)
            join = f"{run_source}\0{case}\0attempt-1"
            attrs = [
                _attribute("run_id", _opaque(project_key, "run", run_source)),
                _attribute("case_id", _opaque(project_key, "case", case)),
                _attribute("attempt_id", _opaque(project_key, "attempt", join)),
            ]
            if trace:
                attrs.append(_attribute("knora_trace_id", _opaque(project_key, "trace", trace)))
            config = item.get("retrieval_configuration_id")
            if isinstance(config, str) and config:
                attrs.append(
                    _attribute("retrieval_configuration_id", _opaque(project_key, "config", config))
                )
            for name in ("retrieval_latency_ms", "end_to_end_latency_ms"):
                value = item.get(name)
                if value is not None:
                    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                        raise BridgeError("DIAGNOSTIC_INVALID")
                    attrs.append(_attribute(name, float(value)))
            status = item.get("status")
            attrs.append(
                _attribute(
                    "observation_status", status if status in ("observed", "failure") else "unknown"
                )
            )
            spans.append(
                {
                    "traceId": _opaque(project_key, "otel-trace", join)[:32],
                    "spanId": _opaque(project_key, "otel-span", join)[:16],
                    "name": "knora-evaluation-import",
                    "startTimeUnixNano": when,
                    "endTimeUnixNano": when,
                    "attributes": attrs,
                }
            )
    except BridgeError:
        raise
    except (KeyError, TypeError, ValueError, OverflowError) as error:
        raise BridgeError("REPORT_INVALID") from error
    resource_spans = [{"scopeSpans": [{"spans": spans}]}]
    return {
        "source_report_sha256": run_source,
        "payload_sha256": hashlib.sha256(
            json.dumps(resource_spans, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
        "resourceSpans": resource_spans,
    }


def export_report(
    raw_report: bytes,
    *,
    project_key: bytes,
    public_key: str,
    secret_key: str,
    httpx_client: httpx.Client,
    imported_at: datetime | None = None,
    reviewed_payload_sha256: str | None = None,
) -> dict:
    """Explicit caller only; rebuild projection rather than accepting preview JSON."""
    if reviewed_payload_sha256 is None or imported_at is None:
        raise BridgeError("EXPORT_NOT_APPROVED")
    if not public_key or not secret_key:
        raise BridgeError("EXPORT_CREDENTIALS_INVALID")
    payload = preview_report(raw_report, project_key=project_key, imported_at=imported_at)
    if not hmac.compare_digest(payload["payload_sha256"], reviewed_payload_sha256):
        raise BridgeError("EXPORT_NOT_APPROVED")
    from langfuse.api.client import LangfuseAPI
    from langfuse.api.opentelemetry.types.otel_resource_span import OtelResourceSpan

    resource_spans = [
        OtelResourceSpan.model_validate(
            {
                "scope_spans": [
                    {
                        "spans": [
                            {
                                "trace_id": span["traceId"],
                                "span_id": span["spanId"],
                                "name": span["name"],
                                "start_time_unix_nano": span["startTimeUnixNano"],
                                "end_time_unix_nano": span["endTimeUnixNano"],
                                "attributes": [
                                    {
                                        "key": attr["key"],
                                        "value": {
                                            "double_value"
                                            if "doubleValue" in attr["value"]
                                            else "string_value": next(iter(attr["value"].values()))
                                        },
                                    }
                                    for attr in span["attributes"]
                                ],
                            }
                            for span in payload["resourceSpans"][0]["scopeSpans"][0]["spans"]
                        ]
                    }
                ]
            }
        )
    ]
    client = LangfuseAPI(
        base_url="https://jp.cloud.langfuse.com",
        username=public_key,
        password=secret_key,
        headers={"x-langfuse-ingestion-version": "4"},
        follow_redirects=False,
        httpx_client=httpx_client,
    )
    try:
        result = client.opentelemetry.export_traces(
            resource_spans=resource_spans,
            request_options={"max_retries": 0, "timeout_in_seconds": 30},
        )
    except Exception as error:
        raise BridgeError("EXPORT_FAILED") from error
    if result.model_extra and result.model_extra.get("partialSuccess"):
        raise BridgeError("EXPORT_REJECTED")
    return {"status": "exported", "payload": payload}


def main() -> int:
    parser = argparse.ArgumentParser(description="Preview safe M3 metadata for Langfuse locally")
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--project-key-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        payload = preview_report(
            args.report.read_bytes(), project_key=args.project_key_file.read_bytes()
        )
        write_report_atomic(args.output, payload)
    except (BridgeError, OSError) as error:
        print(str(error) if isinstance(error, BridgeError) else "PREVIEW_IO_FAILED")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
