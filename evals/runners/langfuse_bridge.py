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
            attempt = item.get("attempt")
            attempt_key = item.get("attempt_id") or (
                f"attempt-{attempt}" if attempt is not None else "attempt-1"
            )
            join = f"{run_source}\0{case}\0{attempt_key}"
            attrs = [
                _attribute("run_id", _opaque(project_key, "run", run_source)),
                _attribute("case_id", _opaque(project_key, "case", case)),
                _attribute("attempt_id", _opaque(project_key, "attempt", join)),
            ]
            if attempt is not None:
                attrs.append(_attribute("attempt_number", float(attempt)))
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
                    "observation_status",
                    status
                    if status in ("observed", "failure", "observation_failure")
                    else "unknown",
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
        "trace_ids": [span["traceId"] for span in spans],
        "span_ids": [span["spanId"] for span in spans],
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


class ReceiptManager:
    """Atomic, no-clobber receipts on the local filesystem."""

    @staticmethod
    def reserve(
        receipt_path: Path,
        *,
        approval_id: str,
        project_key_fingerprint: str,
        payload_sha256: str,
        trace_ids: list[str],
        observation_ids: list[str],
        imported_at: str,
    ) -> dict:
        receipt_path = Path(receipt_path)
        if receipt_path.exists():
            raise BridgeError("RECEIPT_ALREADY_EXISTS")
        data = {
            "status": "RESERVED",
            "approval_id": approval_id,
            "project_key_fingerprint": project_key_fingerprint,
            "payload_sha256": payload_sha256,
            "trace_ids": trace_ids,
            "observation_ids": observation_ids,
            "imported_at": imported_at,
            "reserved_at": datetime.now(UTC).isoformat(),
        }
        try:
            with receipt_path.open("xb") as f:
                f.write(json.dumps(data, indent=2, sort_keys=True).encode("utf-8"))
        except FileExistsError:
            raise BridgeError("RECEIPT_ALREADY_EXISTS") from None
        return data

    @staticmethod
    def read(receipt_path: Path) -> dict:
        receipt_path = Path(receipt_path)
        if not receipt_path.is_file():
            raise BridgeError("RECEIPT_NOT_FOUND")
        return json.loads(receipt_path.read_text(encoding="utf-8"))

    @staticmethod
    def update(receipt_path: Path, **updates) -> dict:
        data = ReceiptManager.read(receipt_path)
        data.update(updates)
        data["updated_at"] = datetime.now(UTC).isoformat()
        temp_path = receipt_path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        temp_path.replace(receipt_path)
        return data


def readback_trace(client: httpx.Client, trace_id: str) -> dict | None:
    """Read a specific trace by ID to verify attributes and ingestion."""
    url = f"/api/public/traces/{trace_id}"
    response = client.get(url, timeout=30.0)
    if response.status_code == 404:
        return None
    if response.status_code != 200:
        raise BridgeError(f"READBACK_FAILED_{response.status_code}")
    return response.json()


def readback_observations(
    client: httpx.Client, trace_id: str, *, max_pages: int = 10, limit: int = 50
) -> list[dict]:
    """Read observations associated with a trace across all pages."""
    all_obs = []
    page = 1
    while page <= max_pages:
        url = f"/api/public/observations?traceId={trace_id}&page={page}&limit={limit}"
        response = client.get(url, timeout=30.0)
        if response.status_code == 404:
            return all_obs
        if response.status_code != 200:
            raise BridgeError(f"READBACK_FAILED_{response.status_code}")
        data = response.json()
        if isinstance(data, list):
            all_obs.extend(data)
            break
        elif isinstance(data, dict):
            items = data.get("data", [])
            all_obs.extend(items)
            meta = data.get("meta", {})
            if "totalPages" in meta:
                if page >= meta["totalPages"] or not items:
                    break
            elif not items or len(items) < limit:
                break
            page += 1
        else:
            break
    return all_obs


def readback_scores(
    client: httpx.Client, trace_id: str, *, max_pages: int = 10, limit: int = 50
) -> list[dict]:
    """Read scores associated with a trace across all pages; pilot requires 0 scores."""
    all_scores = []
    page = 1
    while page <= max_pages:
        url = f"/api/public/scores?traceId={trace_id}&page={page}&limit={limit}"
        response = client.get(url, timeout=30.0)
        if response.status_code == 404:
            return all_scores
        if response.status_code != 200:
            raise BridgeError(f"READBACK_FAILED_{response.status_code}")
        data = response.json()
        if isinstance(data, list):
            all_scores.extend(data)
            break
        elif isinstance(data, dict):
            items = data.get("data", [])
            all_scores.extend(items)
            meta = data.get("meta", {})
            if "totalPages" in meta:
                if page >= meta["totalPages"] or not items:
                    break
            elif not items or len(items) < limit:
                break
            page += 1
        else:
            break
    return all_scores


def delete_traces(
    client: httpx.Client, trace_ids: list[str], *, receipt_path: Path | None = None
) -> dict:
    """Exact owned trace IDs deletion only; no wildcard deletion."""
    if not trace_ids or not isinstance(trace_ids, list):
        raise BridgeError("DELETE_IDS_INVALID")
    if len(trace_ids) > 3:
        raise BridgeError("DELETE_CAP_EXCEEDED")
    for tid in trace_ids:
        if not isinstance(tid, str) or not tid:
            raise BridgeError("DELETE_IDS_INVALID")

    url = "/api/public/traces"
    response = client.request("DELETE", url, json={"traceIds": trace_ids}, timeout=30.0)
    if response.status_code not in (200, 202, 204):
        raise BridgeError(f"DELETE_FAILED_{response.status_code}")

    res_data = {
        "status": "delete_accepted",
        "deleted_trace_ids": trace_ids,
        "http_status": response.status_code,
        "timestamp": datetime.now(UTC).isoformat(),
    }
    if receipt_path is not None:
        ReceiptManager.update(receipt_path, deletion=res_data)
    return res_data


def verify_deleted(
    client: httpx.Client,
    trace_ids: list[str],
    *,
    max_polls: int = 5,
    poll_fn: callable = None,
    receipt_path: Path | None = None,
) -> bool:
    """Verify that traces, observations, and scores are completely gone from the API."""
    for tid in trace_ids:
        deleted = False
        for _ in range(max_polls):
            if poll_fn:
                poll_fn()
            trace = readback_trace(client, tid)
            obs = readback_observations(client, tid)
            scores = readback_scores(client, tid)
            if trace is None and not obs and not scores:
                deleted = True
                break
        if not deleted:
            raise BridgeError(f"DELETION_NOT_VERIFIED_{tid}")
    if receipt_path is not None:
        ReceiptManager.update(
            receipt_path, deletion_verified=True, verified_at=datetime.now(UTC).isoformat()
        )
    return True


def reconcile_receipt(receipt_path: Path, client: httpx.Client) -> dict:
    """Reconcile a pending or interrupted receipt by checking and deleting remaining traces."""
    data = ReceiptManager.read(receipt_path)
    status = data.get("status")
    trace_ids = data.get("trace_ids", [])
    if status == "RESERVED":
        existing = [tid for tid in trace_ids if readback_trace(client, tid) is not None]
        if existing:
            delete_traces(client, existing, receipt_path=receipt_path)
            verify_deleted(client, existing, receipt_path=receipt_path)
            return ReceiptManager.update(receipt_path, status="RECONCILED_DELETED")
        return ReceiptManager.update(receipt_path, status="ABORTED_NO_WRITES")

    if status in ("POSTED", "DELETE_PENDING"):
        existing = [tid for tid in trace_ids if readback_trace(client, tid) is not None]
        if existing:
            delete_traces(client, existing, receipt_path=receipt_path)
            verify_deleted(client, existing, receipt_path=receipt_path)
        else:
            verify_deleted(client, trace_ids, receipt_path=receipt_path)
        return ReceiptManager.update(receipt_path, status="RECONCILED_DELETED")

    return data


def run_langfuse_pilot(
    raw_canary_report: bytes,
    raw_real_report: bytes,
    *,
    project_key: bytes,
    public_key: str,
    secret_key: str,
    httpx_client: httpx.Client,
    receipt_dir: Path,
    approval_id: str,
    imported_at: datetime | None = None,
    canary_payload_sha256: str | None = None,
    real_payload_sha256: str | None = None,
    poll_fn: callable = None,
) -> dict:
    """Execute the bounded 2-POST / 2-DELETE / readback pilot flow."""
    moment = imported_at or datetime.now(UTC)
    receipt_dir = Path(receipt_dir)
    receipt_dir.mkdir(parents=True, exist_ok=True)

    # R7: Both payload digests required BEFORE first network write
    if not canary_payload_sha256 or not real_payload_sha256:
        raise BridgeError("PAYLOAD_DIGESTS_REQUIRED")

    # Offline preview and verification of BOTH payloads before any network mutation
    canary_preview = preview_report(raw_canary_report, project_key=project_key, imported_at=moment)
    if len(canary_preview["trace_ids"]) != 1:
        raise BridgeError("CANARY_PAYLOAD_INVALID")
    canary_sha = canary_preview["payload_sha256"]
    if not hmac.compare_digest(canary_sha, canary_payload_sha256):
        raise BridgeError("CANARY_SHA_MISMATCH")

    real_preview = preview_report(raw_real_report, project_key=project_key, imported_at=moment)
    if not (1 <= len(real_preview["trace_ids"]) <= 2):
        raise BridgeError("REAL_PAYLOAD_INVALID")
    real_sha = real_preview["payload_sha256"]
    if not hmac.compare_digest(real_sha, real_payload_sha256):
        raise BridgeError("REAL_SHA_MISMATCH")

    key_fingerprint = hashlib.sha256(project_key).hexdigest()[:16]
    canary_receipt_path = receipt_dir / "canary_receipt.json"
    real_receipt_path = receipt_dir / "real_receipt.json"

    # Reserve canary
    ReceiptManager.reserve(
        canary_receipt_path,
        approval_id=approval_id + ":canary",
        project_key_fingerprint=key_fingerprint,
        payload_sha256=canary_sha,
        trace_ids=canary_preview["trace_ids"],
        observation_ids=canary_preview["span_ids"],
        imported_at=moment.isoformat(),
    )

    canary_tid = canary_preview["trace_ids"][0]
    canary_posted = False

    # Canary Lifecycle with cleanup on error (R8)
    try:
        export_report(
            raw_canary_report,
            project_key=project_key,
            public_key=public_key,
            secret_key=secret_key,
            httpx_client=httpx_client,
            imported_at=moment,
            reviewed_payload_sha256=canary_sha,
        )
        canary_posted = True
        ReceiptManager.update(canary_receipt_path, status="POSTED")

        # Readback Verification
        trace_data = readback_trace(httpx_client, canary_tid)
        if trace_data is None:
            raise BridgeError("CANARY_READBACK_EMPTY")
        scores = readback_scores(httpx_client, canary_tid)
        if scores:
            raise BridgeError("UNEXPECTED_SCORES_FOUND")

        # Delete & verify
        delete_traces(httpx_client, [canary_tid], receipt_path=canary_receipt_path)
        verify_deleted(
            httpx_client, [canary_tid], poll_fn=poll_fn, receipt_path=canary_receipt_path
        )
    except Exception:
        if canary_posted:
            try:
                delete_traces(httpx_client, [canary_tid], receipt_path=canary_receipt_path)
                verify_deleted(
                    httpx_client, [canary_tid], poll_fn=poll_fn, receipt_path=canary_receipt_path
                )
            except Exception:
                pass
        raise

    # Reserve real
    ReceiptManager.reserve(
        real_receipt_path,
        approval_id=approval_id + ":real",
        project_key_fingerprint=key_fingerprint,
        payload_sha256=real_sha,
        trace_ids=real_preview["trace_ids"],
        observation_ids=real_preview["span_ids"],
        imported_at=moment.isoformat(),
    )

    real_posted = False
    try:
        export_report(
            raw_real_report,
            project_key=project_key,
            public_key=public_key,
            secret_key=secret_key,
            httpx_client=httpx_client,
            imported_at=moment,
            reviewed_payload_sha256=real_sha,
        )
        real_posted = True
        ReceiptManager.update(real_receipt_path, status="POSTED")

        # Readback Verification
        for tid in real_preview["trace_ids"]:
            if readback_trace(httpx_client, tid) is None:
                raise BridgeError(f"REAL_READBACK_EMPTY_{tid}")
            if readback_scores(httpx_client, tid):
                raise BridgeError("UNEXPECTED_SCORES_FOUND")

        # Delete & verify
        delete_traces(httpx_client, real_preview["trace_ids"], receipt_path=real_receipt_path)
        verify_deleted(
            httpx_client, real_preview["trace_ids"], poll_fn=poll_fn, receipt_path=real_receipt_path
        )
    except Exception:
        if real_posted:
            try:
                delete_traces(
                    httpx_client, real_preview["trace_ids"], receipt_path=real_receipt_path
                )
                verify_deleted(
                    httpx_client,
                    real_preview["trace_ids"],
                    poll_fn=poll_fn,
                    receipt_path=real_receipt_path,
                )
            except Exception:
                pass
        raise

    return {
        "status": "COMPLETED",
        "canary_trace_id": canary_tid,
        "real_trace_ids": real_preview["trace_ids"],
        "receipts": {
            "canary": str(canary_receipt_path),
            "real": str(real_receipt_path),
        },
    }


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
