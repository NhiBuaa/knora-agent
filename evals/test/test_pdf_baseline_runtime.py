from datetime import UTC, datetime, timedelta

import httpx
import pytest
from evals.runners.pdf_baseline_runtime import FreeOnlyGuard

NOW = datetime(2026, 10, 14, 12, tzinfo=UTC)
ACCOUNT = "a" * 32


def preflight(**changes):
    value = {
        "account_id": ACCOUNT,
        "plan": "Workers Free",
        "checked_at": NOW.isoformat(),
        "neurons_used": 100,
        "daily_limit": 10000,
        "models_free_eligible": True,
        "evidence": "https://dash.cloudflare.com/account/workers-ai/usage",
        "no_paid_gateway": True,
    }
    return value | changes


def request():
    return httpx.Request(
        "POST",
        f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT}/ai/run/@cf/qwen/qwen3-embedding-0.6b",
        json={"documents": ["one", "two"]},
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"plan": "Workers Paid"},
        {"neurons_used": 10000},
        {"models_free_eligible": False},
        {"no_paid_gateway": False},
        {"checked_at": (NOW - timedelta(days=1)).isoformat()},
    ],
)
def test_non_free_or_stale_preflight_stops_before_dispatch(tmp_path, changes):
    with pytest.raises(ValueError, match="Free"):
        FreeOnlyGuard(
            tmp_path / "counts.json",
            run_identity={"run": "one"},
            preflight=preflight(**changes),
            clock=lambda: NOW,
        )
    assert not (tmp_path / "counts.json").exists()


def test_attempt_counter_survives_timeout_and_resume(tmp_path):
    path = tmp_path / "counts.json"
    guard = FreeOnlyGuard(
        path, run_identity={"run": "one"}, preflight=preflight(), clock=lambda: NOW
    )
    guard.before_request(request())
    resumed = FreeOnlyGuard(
        path, run_identity={"run": "one"}, preflight=preflight(), clock=lambda: NOW
    )
    assert resumed.state["embedding_inputs"] == 2
    resumed.state["embedding_inputs"] = 2500
    resumed.save()
    with pytest.raises(RuntimeError, match="REQUEST_LIMIT"):
        resumed.before_request(request())
    assert resumed.state["embedding_inputs"] == 2500


def test_quota_error_blocks_all_requests_until_daily_reset(tmp_path):
    path = tmp_path / "counts.json"
    guard = FreeOnlyGuard(
        path, run_identity={"run": "one"}, preflight=preflight(), clock=lambda: NOW
    )
    guard.before_request(request())
    guard.after_response(httpx.Response(429, request=request()))
    with pytest.raises(RuntimeError, match="QUOTA_PAUSED"):
        guard.before_request(request())
    later = NOW + timedelta(days=1)
    resumed = FreeOnlyGuard(
        path,
        run_identity={"run": "one"},
        preflight=preflight(checked_at=later.isoformat(), neurons_used=0),
        clock=lambda: later,
    )
    resumed.before_request(request())
    assert resumed.state["embedding_inputs"] == 4


def test_same_file_cannot_reset_baseline_or_admit_unknown_ai_endpoint(tmp_path):
    path = tmp_path / "counts.json"
    guard = FreeOnlyGuard(
        path, run_identity={"run": "one"}, preflight=preflight(), clock=lambda: NOW
    )
    with pytest.raises(ValueError, match="identity"):
        FreeOnlyGuard(path, run_identity={"run": "two"}, preflight=preflight(), clock=lambda: NOW)
    with pytest.raises(RuntimeError, match="ENDPOINT"):
        guard.before_request(httpx.Request("POST", "https://example.com", json={}))


def test_midnight_expiry_persists_pause_before_any_request_and_can_resume(tmp_path):
    moment = [NOW]
    path = tmp_path / "counts.json"
    guard = FreeOnlyGuard(
        path, run_identity={"run": "one"}, preflight=preflight(), clock=lambda: moment[0]
    )
    moment[0] = NOW + timedelta(days=1)
    with pytest.raises(RuntimeError, match="FREE_PREFLIGHT_EXPIRED"):
        guard.before_request(request())
    assert guard.state["stop_reason"] == "FREE_PREFLIGHT_EXPIRED"
    assert guard.state["embedding_inputs"] == 0
    resumed = FreeOnlyGuard(
        path,
        run_identity={"run": "one"},
        preflight=preflight(checked_at=moment[0].isoformat()),
        clock=lambda: moment[0],
    )
    assert resumed.state["stop_reason"] is None
    resumed.before_request(request())
    assert resumed.state["embedding_inputs"] == 2


def test_actual_http_hook_counts_generation_and_rejects_paid_endpoint_before_transport(tmp_path):
    guard = FreeOnlyGuard(
        tmp_path / "counts.json",
        run_identity={"run": "one"},
        preflight=preflight(),
        clock=lambda: NOW,
    )
    seen = []
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda req: seen.append(req.url.path) or httpx.Response(200, json={})
        ),
        event_hooks={"request": [guard.before_request]},
    ) as client:
        client.post(
            f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT}/ai/v1/chat/completions",
            json={"model": "@cf/openai/gpt-oss-20b", "max_tokens": 1024},
        )
        with pytest.raises(RuntimeError, match="ENDPOINT"):
            client.post("https://gateway.ai.cloudflare.com/paid", json={})
        guard.state["generation_attempts"] = 70
        guard.save()
        with pytest.raises(RuntimeError, match="REQUEST_LIMIT"):
            client.post(
                f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT}/ai/v1/chat/completions",
                json={"model": "@cf/openai/gpt-oss-20b", "max_tokens": 1024},
            )
    assert len(seen) == 1
