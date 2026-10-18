"""Approved finite P3 synthetic trial; default execution remains offline."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path

import httpx
from evals.runners.cloudflare_p1_shadow import load_units
from evals.runners.evaluation import write_report_atomic

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "evals/test/fixtures/cloudflare_p1_shadow/cases.json"
SOURCE_SHA = "sha256:2cac53d286a9ca1496614c9a5f24af548efd35380b92bb6063299f106d10a186"
DIRECTORY = ROOT / "evals/reports/cloudflare_p1_shadow/p3-trial-002"
EXPIRES = datetime(2026, 10, 18, 11, 10, tzinfo=UTC)
GATEWAY = "knora-issue188-p1-trial"
CASE = "p1-vi-attack-1"
CANARIES = (CASE, "p1-vi-control-1")


def _credentials():
    selected = {}
    for line in (
        Path("C:/Developer/Projects/knora-agent/.env").read_text(encoding="utf-8-sig").splitlines()
    ):
        key, separator, value = line.partition("=")
        if separator and key.strip() in {
            "KNORA_CLOUDFLARE_ACCOUNT_ID",
            "KNORA_CLOUDFLARE_API_TOKEN",
        }:
            key = key.strip()
            if key in selected:
                raise ValueError("DUPLICATE_CREDENTIAL_SETTING")
            selected[key] = value.strip().strip("\"'")
    account = selected.get("KNORA_CLOUDFLARE_ACCOUNT_ID", "")
    token = selected.get("KNORA_CLOUDFLARE_API_TOKEN", "")
    if (
        hashlib.sha256(account.encode()).hexdigest()
        != "785e7d1ca8bb4774c9edb984427b812b149a755d67d0d92ee12ff79a23c080da"
        or not token
        or any(character.isspace() for character in token)
    ):
        raise ValueError("CREDENTIAL_BINDING_INVALID")
    return account, token


async def dispatch_first_canary(
    *,
    directory,
    now,
    configuration_sha256,
    expected_configuration_sha256,
    credentials,
    client,
    case_id=CASE,
):
    if now >= EXPIRES or now < datetime(2026, 10, 17, 11, 12, tzinfo=UTC):
        raise ValueError("AUTHORITY_EXPIRED")
    if configuration_sha256 != expected_configuration_sha256:
        raise ValueError("CONFIGURATION_MISMATCH")
    if (directory / "closed.json").exists():
        raise ValueError("SESSION_CLOSED")
    units = load_units(FIXTURE, expected_digest=SOURCE_SHA, fixtures=True)
    if case_id not in {unit["case_id"] for unit in units}:
        raise ValueError("CANARY_INPUT_MISMATCH")
    remaining_seconds = 1200
    if case_id != CASE:
        first_path = directory / f"{CASE}.transport.json"
        if not first_path.exists():
            raise ValueError("FIRST_CANARY_REQUIRED")
        first = json.loads(first_path.read_text(encoding="utf-8"))
        if first["stop"] or first["http_status"] != 200 or first["success"] is not True:
            raise ValueError("FIRST_CANARY_REQUIRED")
        elapsed = (now - datetime.fromisoformat(first["utc"])).total_seconds()
        if not 0 <= elapsed < 1200:
            raise ValueError("SESSION_EXPIRED")
        remaining_seconds -= elapsed
    if case_id not in CANARIES:
        for canary in CANARIES:
            native_path = directory / f"{canary}.native.json"
            transport_path = directory / f"{canary}.transport.json"
            if not native_path.exists() or not transport_path.exists():
                raise ValueError("NATIVE_CANARIES_REQUIRED")
            native = json.loads(native_path.read_text(encoding="utf-8"))
            transport = json.loads(transport_path.read_text(encoding="utf-8"))
            if (
                transport["stop"]
                or not transport["native_log_id"]
                or native.get("case_id") != canary
                or native.get("configuration_sha256") != configuration_sha256
                or native.get("input_sha256") != transport["input_sha256"]
                or native.get("native_log_id") != transport["native_log_id"]
                or native.get("request_id_matches_response_log_id") is not True
                or native.get("case_id_and_input_digest_match") is not True
                or native.get("request_outcome") != "success"
                or native.get("status_code") != 200
                or native.get("retry_count") != 0
                or native.get("guardrails") != {"prompt": {"P1": "FLAG"}}
            ):
                raise ValueError("NATIVE_CANARIES_REQUIRED")
    case = next(unit for unit in units if unit["case_id"] == case_id)
    if not case["messages"]:
        raise ValueError("CANARY_INPUT_MISMATCH")
    reserved = directory / f"{case_id}.reserved.json"
    # Reserve durably before credential loading/send: interruption can never permit replay.
    reservation = {
        "case_id": case_id,
        "utc": now.isoformat(),
        "dispatch_count": 1,
        "input_sha256": case["input_sha256"],
        "configuration_sha256": configuration_sha256,
        "source_artifact_sha256": SOURCE_SHA,
        "restart_state": "indeterminate",
    }
    write_report_atomic(reserved, reservation)
    result = {
        **reservation,
        "http_status": None,
        "success": None,
        "error_codes": [],
        "native_log_id": None,
        "detector_status": "unavailable",
        "stop": True,
        "transport_error": None,
        "failure_stage": None,
        "failure_kind": None,
    }
    stage = "credential_loading"
    try:
        account, token = credentials()
        stage = "http_exchange"
        async with asyncio.timeout(min(59, remaining_seconds)):
            async with client.stream(
                "POST",
                f"https://api.cloudflare.com/client/v4/accounts/{account}/ai/run",
                headers={
                    "Authorization": f"Bearer {token}",
                    "cf-aig-gateway-id": GATEWAY,
                    "cf-aig-skip-cache": "true",
                    "cf-aig-collect-log": "true",
                    "cf-aig-metadata": json.dumps(
                        {"case_id": case_id, "input_sha256": case["input_sha256"]}
                    ),
                },
                json={
                    "model": "@cf/openai/gpt-oss-20b",
                    "input": {"messages": case["messages"], "stream": False, "max_tokens": 256},
                },
                follow_redirects=False,
            ) as response:
                result["http_status"] = response.status_code
                log_id = response.headers.get("cf-aig-log-id", "")
                if re.fullmatch(r"[A-Za-z0-9_-]{1,128}", log_id):
                    result["native_log_id"] = log_id
                raw = bytearray()
                async for chunk in response.aiter_bytes():
                    raw.extend(chunk)
                    if len(raw) > 262144:
                        raise ValueError("OVERSIZED_RESPONSE")
                if response.status_code == 200:
                    payload = json.loads(raw)
                    if not isinstance(payload, dict):
                        raise ValueError("INVALID_RESPONSE")
                    result["success"] = (
                        payload.get("success") if type(payload.get("success")) is bool else None
                    )
                    result["error_codes"] = [
                        error["code"]
                        for error in (payload.get("errors") or [])
                        if isinstance(error, dict) and type(error.get("code")) is int
                    ]
                    result["stop"] = (
                        result["success"] is not True
                        or result["native_log_id"] is None
                        or bool(result["error_codes"])
                        or response.headers.get("cf-aig-cache-status", "").upper() == "HIT"
                    )
    except (TimeoutError, httpx.TimeoutException):
        result["transport_error"] = "timeout"
        result["failure_stage"] = stage
        result["failure_kind"] = "timeout"
    except (ValueError, TypeError, KeyError, OSError, httpx.HTTPError) as error:
        result["transport_error"] = "transport_or_response_error"
        result["failure_stage"] = stage
        name = type(error).__name__
        result["failure_kind"] = (
            name
            if name
            in {
                "ValueError",
                "TypeError",
                "KeyError",
                "FileNotFoundError",
                "PermissionError",
                "UnicodeDecodeError",
                "ConnectError",
                "ReadError",
                "WriteError",
                "RemoteProtocolError",
                "LocalProtocolError",
            }
            else "other"
        )
    write_report_atomic(directory / f"{case_id}.transport.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute-approved-p3", action="store_true")
    parser.add_argument("--case", choices=CANARIES, default=CASE)
    parser.add_argument("--remaining", action="store_true")
    args = parser.parse_args()
    if not args.execute_approved_p3:
        print("OFFLINE: no credential read or network")
        return 0
    try:
        snapshot = (DIRECTORY / "configuration.json").read_bytes()
        expected = (DIRECTORY / "configuration.sha256").read_text().strip()

        async def execute():
            async with httpx.AsyncClient(
                timeout=55, trust_env=False, follow_redirects=False
            ) as client:
                case_ids = (
                    [
                        unit["case_id"]
                        for unit in load_units(FIXTURE, expected_digest=SOURCE_SHA, fixtures=True)
                        if unit["case_id"] not in CANARIES
                    ]
                    if args.remaining
                    else [args.case]
                )
                results = []
                for case_id in case_ids:
                    result = await dispatch_first_canary(
                        directory=DIRECTORY,
                        now=datetime.now(UTC),
                        configuration_sha256="sha256:" + hashlib.sha256(snapshot).hexdigest(),
                        expected_configuration_sha256=expected,
                        credentials=_credentials,
                        client=client,
                        case_id=case_id,
                    )
                    results.append(result)
                    if result["stop"]:
                        break
                return results

        results = asyncio.run(execute())
        print(json.dumps(results))
        return 2 if any(result["stop"] for result in results) else 0
    except (ValueError, TypeError, OSError):
        print("P3_ADMISSION_OR_PUBLICATION_ERROR")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
