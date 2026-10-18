import asyncio
import importlib.util
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest


def trial():
    assert importlib.util.find_spec("evals.runners.cloudflare_p1_trial") is not None
    from evals.runners import cloudflare_p1_trial

    return cloudflare_p1_trial


def test_credential_loader_decodes_utf8_on_a_windows_cp1252_host(tmp_path, monkeypatch):
    fixture = tmp_path / "synthetic.env"
    fixture.write_text(
        "# Á kiểm tra\nKNORA_CLOUDFLARE_ACCOUNT_ID=synthetic\n", encoding="utf-8-sig"
    )
    read_text = Path.read_text

    def windows_read(path, *args, **kwargs):
        assert path == Path("C:/Developer/Projects/knora-agent/.env")
        kwargs.setdefault("encoding", "cp1252")
        return read_text(fixture, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", windows_read)
    with pytest.raises(ValueError, match="CREDENTIAL_BINDING_INVALID"):
        trial()._credentials()


def run(tmp_path, handler, **changes):
    module = trial()
    values = {
        "directory": tmp_path,
        "now": datetime(2026, 10, 17, 12, tzinfo=UTC),
        "configuration_sha256": "sha256:approved-config",
        "expected_configuration_sha256": "sha256:approved-config",
        "credentials": lambda: ("account", "TOKEN_CANARY"),
    }
    values.update(changes)

    async def execute():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await module.dispatch_first_canary(client=client, **values)

    return asyncio.run(execute())


def test_transport_sends_exact_envelope_once_and_keeps_only_safe_metadata(tmp_path):
    calls = []

    def provider(request):
        calls.append(request)
        body = json.loads(request.content)
        assert request.url.host == "api.cloudflare.com"
        assert request.method == "POST"
        assert request.headers["cf-aig-gateway-id"] == "knora-issue188-p1-trial"
        assert request.headers["cf-aig-skip-cache"] == "true"
        assert body["model"] == "@cf/openai/gpt-oss-20b"
        assert body["input"]["stream"] is False
        assert body["input"]["max_tokens"] == 256
        assert "KNORA_P1_SYNTHETIC_CANARY" in body["input"]["messages"][1]["content"]
        return httpx.Response(
            200,
            headers={"cf-aig-log-id": "native-log-1"},
            json={"success": True, "result": {"response": "RAW_BODY_CANARY"}},
        )

    result = run(tmp_path, provider)
    assert result["http_status"] == 200
    assert result["native_log_id"] == "native-log-1"
    assert result["stop"] is False
    assert result["detector_status"] == "unavailable"
    assert len(calls) == 1
    artifacts = "".join(path.read_text() for path in tmp_path.glob("*.json"))
    assert "TOKEN_CANARY" not in artifacts
    assert "RAW_BODY_CANARY" not in artifacts
    assert "messages" not in artifacts
    with pytest.raises(FileExistsError):
        run(tmp_path, provider)
    assert len(calls) == 1


@pytest.mark.parametrize("log_id", [None, "invalid/log/id"])
def test_success_without_usable_native_log_id_stops_before_second_canary(tmp_path, log_id):
    calls = []

    def provider(request):
        calls.append(request)
        headers = {} if log_id is None else {"cf-aig-log-id": log_id}
        return httpx.Response(200, headers=headers, json={"success": True})

    result = run(tmp_path, provider)
    assert result["http_status"] == 200
    assert result["success"] is True
    assert result["native_log_id"] is None
    assert result["stop"] is True
    with pytest.raises(ValueError, match="FIRST_CANARY_REQUIRED"):
        run(tmp_path, provider, case_id="p1-vi-control-1")
    assert len(calls) == 1


@pytest.mark.parametrize("status", [302, 403, 429])
def test_failure_or_redirect_is_recorded_without_retry(tmp_path, status):
    calls = []

    def provider(request):
        calls.append(request)
        return httpx.Response(status, headers={"location": "https://example.invalid"})

    result = run(tmp_path, provider)
    assert result["stop"] is True
    assert result["http_status"] == status
    assert len(calls) == 1
    assert (
        json.loads((tmp_path / "p1-vi-attack-1.reserved.json").read_text())["dispatch_count"] == 1
    )


def test_expiry_and_config_mismatch_precede_credentials_and_network(tmp_path):
    def forbidden(*args):
        raise AssertionError("must not access credentials or network")

    with pytest.raises(ValueError, match="AUTHORITY_EXPIRED"):
        run(tmp_path, forbidden, now=datetime(2026, 10, 19, tzinfo=UTC), credentials=forbidden)
    with pytest.raises(ValueError, match="CONFIGURATION_MISMATCH"):
        run(tmp_path, forbidden, configuration_sha256="sha256:other", credentials=forbidden)
    assert not list(tmp_path.iterdir())


def test_timeout_consumes_attempt_and_sanitizes_exception(tmp_path):
    def provider(request):
        raise httpx.ReadTimeout("TOKEN_CANARY", request=request)

    result = run(tmp_path, provider)
    assert result["stop"] is True
    assert result["transport_error"] == "timeout"
    assert "TOKEN_CANARY" not in json.dumps(result)
    with pytest.raises(FileExistsError):
        run(tmp_path, provider)


def test_credential_failure_is_distinct_from_connection_failure_without_secret_output(tmp_path):
    def credentials():
        raise ValueError("TOKEN_CANARY")

    def forbidden(request):
        raise AssertionError("credential failure must precede network")

    result = run(tmp_path, forbidden, credentials=credentials)
    assert result["failure_stage"] == "credential_loading"
    assert result["failure_kind"] == "ValueError"
    assert "TOKEN_CANARY" not in json.dumps(result)


def test_connection_failure_retains_only_an_allowlisted_exception_class(tmp_path):
    def provider(request):
        raise httpx.ConnectError("TOKEN_CANARY", request=request)

    result = run(tmp_path, provider)
    assert result["failure_stage"] == "http_exchange"
    assert result["failure_kind"] == "ConnectError"
    assert "TOKEN_CANARY" not in json.dumps(result)


def test_second_canary_requires_successful_first_and_stays_inside_session(tmp_path):
    calls = []

    def provider(request):
        calls.append(request)
        return httpx.Response(
            200, headers={"cf-aig-log-id": "native-log-1"}, json={"success": True}
        )

    with pytest.raises(ValueError, match="FIRST_CANARY_REQUIRED"):
        run(tmp_path, provider, case_id="p1-vi-control-1")
    assert not calls
    run(tmp_path, provider)
    with pytest.raises(ValueError, match="SESSION_EXPIRED"):
        run(
            tmp_path,
            provider,
            case_id="p1-vi-control-1",
            now=datetime(2026, 10, 17, 12, 20, tzinfo=UTC),
        )
    second = run(
        tmp_path, provider, case_id="p1-vi-control-1", now=datetime(2026, 10, 17, 12, 1, tzinfo=UTC)
    )
    assert second["case_id"] == "p1-vi-control-1"
    assert len(calls) == 2
    assert json.loads(calls[1].headers["cf-aig-metadata"])["case_id"] == "p1-vi-control-1"
    assert (tmp_path / "p1-vi-control-1.transport.json").exists()


def test_closed_session_rejects_dispatch_before_credentials(tmp_path):
    (tmp_path / "closed.json").write_text("{}")

    def forbidden(*args):
        raise AssertionError("closed session must not access credentials or network")

    with pytest.raises(ValueError, match="SESSION_CLOSED"):
        run(tmp_path, forbidden, credentials=forbidden)


def test_remaining_case_requires_two_digest_bound_native_canaries(tmp_path):
    def provider(request):
        case_id = json.loads(request.headers["cf-aig-metadata"])["case_id"]
        return httpx.Response(
            200, headers={"cf-aig-log-id": "native-" + case_id}, json={"success": True}
        )

    run(tmp_path, provider)
    with pytest.raises(ValueError, match="NATIVE_CANARIES_REQUIRED"):
        run(tmp_path, provider, case_id="p1-vi-attack-2")
    run(tmp_path, provider, case_id="p1-vi-control-1")
    for case_id in ("p1-vi-attack-1", "p1-vi-control-1"):
        transport = json.loads((tmp_path / f"{case_id}.transport.json").read_text())
        (tmp_path / f"{case_id}.native.json").write_text(
            json.dumps(
                {
                    "case_id": case_id,
                    "configuration_sha256": "sha256:approved-config",
                    "input_sha256": transport["input_sha256"],
                    "native_log_id": transport["native_log_id"],
                    "request_id_matches_response_log_id": True,
                    "case_id_and_input_digest_match": True,
                    "request_outcome": "success",
                    "status_code": 200,
                    "retry_count": 0,
                    "guardrails": {"prompt": {"P1": "FLAG"}},
                }
            )
        )
    result = run(tmp_path, provider, case_id="p1-vi-attack-2")
    assert result["case_id"] == "p1-vi-attack-2"
    assert (tmp_path / "p1-vi-attack-2.transport.json").exists()
