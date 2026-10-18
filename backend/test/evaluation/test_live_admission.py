"""Live authority and provider attempts are tested without external HTTP."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import UTC, datetime, timedelta

import httpx
import pytest

NOW = datetime(2026, 10, 18, 4, 0, tzinfo=UTC)
ENDPOINT = "https://api.cloudflare.com/client/v4/accounts/" + "a" * 32 + "/ai/v1/chat/completions"
MODEL = "@cf/openai/gpt-oss-20b"


def scope():
    return {
        "purpose": "qa",
        "profile_id": "live-test",
        "workspace_id": "w1",
        "input_digest": "a" * 64,
    }


def approval():
    from knora.evaluation.contracts import digest_json

    return {
        "approval_id": "owner-decision-1",
        "scope": scope(),
        "approved_by": "owner",
        "decision_reference": "issue192/test-only",
        "classification": "synthetic",
        "egress_approved": True,
        "account_id": "a" * 32,
        "plan": "Workers Free",
        "proof_observed_at": NOW.isoformat(),
        "proof_digest": "b" * 64,
        "deadline": (NOW + timedelta(minutes=4)).isoformat(),
        "max_attempts": 2,
        "quota_remaining_neurons": 100,
        "max_neurons_per_attempt": 2,
        "paid_budget_usd": 0,
        "providers": [
            {
                "endpoint": ENDPOINT,
                "model": MODEL,
                "max_input_bytes": 4096,
                "max_output_tokens": 32,
                "compatibility_digest": "c" * 64,
                "request_digests": [digest_json(body())],
            }
        ],
    }


def gate(tmp_path, policy=None, clock=None):
    from knora.evaluation.live_admission import LiveAdmission

    return LiveAdmission(
        policy or approval(), tmp_path / "attempts.sqlite", clock=clock or (lambda: NOW)
    )


def body(**updates):
    return {
        "model": MODEL,
        "max_tokens": 32,
        "messages": [{"role": "user", "content": "synthetic"}],
        **updates,
    }


def success(request):
    return httpx.Response(
        200,
        json={
            "model": MODEL,
            "choices": [{"finish_reason": "stop", "message": {"content": "OK"}}],
            "usage": {"completion_tokens": 2},
        },
    )


def client(admission, handler=success):
    return httpx.Client(
        transport=admission.transport(mock=httpx.MockTransport(handler)), follow_redirects=True
    )


def test_default_transport_denies_without_dispatch_context(tmp_path):
    admission = gate(tmp_path)
    with client(admission) as http, pytest.raises(ValueError, match="LIVE_DISPATCH_REQUIRED"):
        http.post(ENDPOINT, json=body())
    assert admission.snapshot() == {"attempts": 0, "pending": None, "stopped": False}


@pytest.mark.parametrize(
    "field,value",
    [
        ("purpose", "scoring"),
        ("profile_id", "other"),
        ("workspace_id", "other"),
        ("input_digest", "f" * 64),
    ],
)
def test_scope_mismatch_denies_before_reservation(tmp_path, field, value):
    admission = gate(tmp_path)
    with pytest.raises(ValueError, match="LIVE_SCOPE_MISMATCH"):
        admission.verify({**scope(), field: value})
    assert admission.snapshot()["attempts"] == 0


@pytest.mark.parametrize(
    "field,value",
    [
        ("plan", "Workers Paid"),
        ("egress_approved", False),
        ("classification", "private"),
        ("paid_budget_usd", 1),
        ("max_attempts", True),
        ("quota_remaining_neurons", 3),
        ("proof_digest", ""),
        ("approved_by", ""),
    ],
)
def test_unproven_or_paid_policy_is_rejected(tmp_path, field, value):
    with pytest.raises(ValueError, match="LIVE_APPROVAL_INVALID"):
        gate(tmp_path, {**approval(), field: value})


def test_expired_or_future_proof_fails_closed(tmp_path):
    clock = [NOW]
    admission = gate(tmp_path, clock=lambda: clock[0])
    clock[0] = NOW + timedelta(minutes=5)
    with pytest.raises(ValueError, match="LIVE_APPROVAL_EXPIRED"):
        admission.verify(scope())
    clock[0] = NOW - timedelta(seconds=1)
    with pytest.raises(ValueError, match="LIVE_APPROVAL_EXPIRED"):
        admission.verify(scope())


def test_actual_http_attempts_persist_and_cap_survives_restart(tmp_path):
    admission = gate(tmp_path)
    with admission.dispatch(scope()), client(admission) as http:
        assert http.post(ENDPOINT, json=body()).status_code == 200
        assert http.post(ENDPOINT, json=body()).status_code == 200
    resumed = gate(tmp_path)
    assert resumed.snapshot() == {"attempts": 2, "pending": None, "stopped": False}
    with pytest.raises(ValueError, match="LIVE_ATTEMPT_CAP"):
        resumed.verify(scope())


def test_immutable_approval_cannot_reset_existing_budget(tmp_path):
    gate(tmp_path)
    changed = approval()
    changed["max_attempts"] = 3
    with pytest.raises(ValueError, match="LIVE_APPROVAL_CONFLICT"):
        gate(tmp_path, changed)


def test_approval_copies_host_input_and_has_stable_provenance(tmp_path):
    policy = approval()
    admission = gate(tmp_path, policy)
    before = admission.verify(scope())
    policy["scope"]["workspace_id"] = "other"
    assert admission.verify(scope()) == before
    assert before["approval_id"] == "owner-decision-1"
    assert len(before["approval_digest"]) == 64
    assert before == gate(tmp_path).verify(scope())


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(302, headers={"Location": "https://example.test/"}),
        httpx.Response(500),
        httpx.Response(
            200, json={"choices": [{"finish_reason": "length", "message": {"content": "partial"}}]}
        ),
    ],
)
def test_error_redirect_and_truncation_latch_stop_without_replay(tmp_path, response):
    admission = gate(tmp_path)
    sent = []

    def handler(request):
        sent.append(str(request.url))
        return response

    with pytest.raises(ValueError), admission.dispatch(scope()), client(admission, handler) as http:
        http.post(ENDPOINT, json=body())
    assert sent == [ENDPOINT]
    assert gate(tmp_path).snapshot()["attempts"] == 1
    assert gate(tmp_path).snapshot()["stopped"]
    with pytest.raises(ValueError, match="LIVE_STOPPED"):
        gate(tmp_path).verify(scope())


def test_timeout_is_consumed_and_stop_survives_restart(tmp_path):
    admission = gate(tmp_path)

    def timeout(request):
        raise httpx.ReadTimeout("synthetic", request=request)

    with (
        pytest.raises(httpx.ReadTimeout),
        admission.dispatch(scope()),
        client(admission, timeout) as http,
    ):
        http.post(ENDPOINT, json=body())
    assert gate(tmp_path).snapshot() == {"attempts": 1, "pending": 1, "stopped": True}


@pytest.mark.parametrize(
    "url,payload",
    [
        (ENDPOINT + "?override=1", body()),
        (ENDPOINT, body(model="other")),
        (ENDPOINT, body(max_tokens=33)),
        (ENDPOINT, body(max_tokens=True)),
    ],
)
def test_unapproved_provider_or_tokens_do_not_dispatch(tmp_path, url, payload):
    admission = gate(tmp_path)
    with pytest.raises(ValueError), admission.dispatch(scope()), client(admission) as http:
        http.post(url, json=payload)
    assert admission.snapshot()["attempts"] == 0


def test_pending_request_blocks_restart_and_parallel_reservation(tmp_path):
    admission = gate(tmp_path)
    from threading import Event

    entered, release = Event(), Event()

    def handler(request):
        entered.set()
        assert release.wait(5)
        return success(request)

    def send():
        with admission.dispatch(scope()), client(admission, handler) as http:
            return http.post(ENDPOINT, json=body()).status_code

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(send)
        assert entered.wait(5)
        try:
            with pytest.raises(ValueError, match="LIVE_REQUEST_PENDING"):
                gate(tmp_path).verify(scope())
            assert gate(tmp_path).snapshot()["attempts"] == 1
        finally:
            release.set()
        assert future.result() == 200


@pytest.mark.asyncio
async def test_async_transport_counts_each_request_and_clamps_timeout(tmp_path):
    admission = gate(tmp_path)
    observed = []

    async def handler(request):
        observed.append(deepcopy(request.extensions["timeout"]))
        return success(request)

    with admission.dispatch(scope()):
        async with httpx.AsyncClient(
            transport=admission.async_transport(mock=httpx.MockTransport(handler))
        ) as http:
            await http.post(ENDPOINT, json=body(), timeout=1000)
    assert observed and all(0 < value <= 240 for value in observed[0].values())
    assert admission.snapshot()["attempts"] == 1


def test_corpus_or_prompt_drift_is_denied_before_egress(tmp_path):
    admission = gate(tmp_path)
    sent = []
    with (
        pytest.raises(ValueError, match="LIVE_REQUEST_UNAPPROVED"),
        admission.dispatch(scope()),
        client(admission, lambda r: sent.append(r)) as http,
    ):
        http.post(
            ENDPOINT,
            json=body(messages=[{"role": "user", "content": "unapproved new corpus text"}]),
        )
    assert sent == [] and admission.snapshot()["attempts"] == 0


@pytest.mark.asyncio
async def test_slow_continuous_stream_is_cancelled_and_closed(tmp_path):
    import asyncio

    closed = []
    policy = approval()
    start = datetime.now(UTC)
    policy.update(
        proof_observed_at=start.isoformat(), deadline=(start + timedelta(seconds=0.2)).isoformat()
    )
    admission = gate(tmp_path, policy, clock=lambda: datetime.now(UTC))

    class Stream(httpx.AsyncByteStream):
        async def __aiter__(self):
            while True:
                yield b" "
                await asyncio.sleep(0.01)

        async def aclose(self):
            closed.append(True)

    async def handler(request):
        return httpx.Response(200, stream=Stream())

    with pytest.raises((httpx.ReadTimeout, ValueError)), admission.dispatch(scope()):
        async with httpx.AsyncClient(
            transport=admission.async_transport(mock=httpx.MockTransport(handler))
        ) as http:
            await http.post(ENDPOINT, json=body())
    assert closed == [True]
    assert admission.snapshot() == {"attempts": 1, "pending": 1, "stopped": True}


def test_sync_helper_is_killed_and_reaped_at_deadline_without_network(tmp_path, monkeypatch):
    import sys
    import time

    import knora.evaluation.live_admission as module

    policy = approval()
    start = datetime.now(UTC)
    policy.update(
        proof_observed_at=start.isoformat(), deadline=(start + timedelta(seconds=0.4)).isoformat()
    )
    admission = gate(tmp_path, policy, clock=lambda: datetime.now(UTC))
    # Exercise the real process lifecycle with a sleeping, network-free child.
    monkeypatch.setattr(
        module, "_helper_command", lambda: (sys.executable, "-c", "import time; time.sleep(60)")
    )
    reaped = []
    original = module.asyncio.create_subprocess_exec

    async def spawn(*args, **kwargs):
        process = await original(*args, **kwargs)
        reaped.append(process)
        return process

    monkeypatch.setattr(module.asyncio, "create_subprocess_exec", spawn)
    started = time.monotonic()
    with (
        pytest.raises((httpx.ReadTimeout, ValueError)),
        admission.dispatch(scope()),
        httpx.Client(transport=admission.transport()) as http,
    ):
        http.post(ENDPOINT, json=body())
    assert time.monotonic() - started < 2
    assert reaped and reaped[0].returncode is not None
    assert admission.snapshot() == {"attempts": 1, "pending": 1, "stopped": True}


@pytest.mark.asyncio
async def test_stop_cancels_active_request_and_restart_cannot_replay(tmp_path):
    import asyncio

    admission = gate(tmp_path)
    entered, cancelled = asyncio.Event(), asyncio.Event()

    async def handler(request):
        entered.set()
        try:
            await asyncio.sleep(60)
        finally:
            cancelled.set()

    async def send():
        with admission.dispatch(scope()):
            async with httpx.AsyncClient(
                transport=admission.async_transport(mock=httpx.MockTransport(handler))
            ) as http:
                await http.post(ENDPOINT, json=body())

    task = asyncio.create_task(send())
    await entered.wait()
    gate(tmp_path).stop()
    with pytest.raises(ValueError, match="LIVE_STOPPED"):
        await asyncio.wait_for(task, 2)
    assert cancelled.is_set()
    assert gate(tmp_path).snapshot() == {"attempts": 1, "pending": 1, "stopped": True}


@pytest.mark.asyncio
async def test_failure_reaps_transport_before_stop_journal_write(tmp_path, monkeypatch):
    import asyncio

    admission = gate(tmp_path)
    entered, cancelled = asyncio.Event(), asyncio.Event()

    async def handler(request):
        entered.set()
        try:
            await asyncio.sleep(60)
        finally:
            cancelled.set()

    original_stop = admission.stop

    def stop():
        assert cancelled.is_set()
        original_stop()

    monkeypatch.setattr(admission, "stop", stop)
    with pytest.raises(ValueError):
        async with httpx.AsyncClient(
            transport=admission.async_transport(mock=httpx.MockTransport(handler))
        ) as http:
            task = asyncio.create_task(_post_inside_dispatch(admission, http))
            await entered.wait()
            admission._clock = lambda: NOW + timedelta(minutes=6)
            await task
    assert admission.snapshot()["stopped"]


async def _post_inside_dispatch(admission, http):
    with admission.dispatch(scope()):
        await http.post(ENDPOINT, json=body())


def test_helper_self_terminates_without_parent_watchdog_or_network():
    import subprocess
    import sys

    command = (
        "import time; from knora.evaluation.provider_request import _arm_deadline; "
        "_arm_deadline(time.time()+.15); time.sleep(60)"
    )
    result = subprocess.run([sys.executable, "-c", command], timeout=3, capture_output=True)
    assert result.returncode == 2 and result.stdout == b"" and result.stderr == b""


@pytest.mark.parametrize("nested", [False, True])
def test_duplicate_json_keys_cannot_hide_unapproved_bytes(tmp_path, nested):
    import json

    admission = gate(tmp_path)
    approved = json.dumps(body())
    if nested:
        content = approved.replace(
            '"content": "synthetic"', '"content": "PRIVATE", "content": "synthetic"'
        )
    else:
        content = '{"messages": [{"role":"user","content":"PRIVATE"}],' + approved[1:]
    sent = []
    with (
        pytest.raises(ValueError, match="LIVE_REQUEST_UNAPPROVED"),
        admission.dispatch(scope()),
        client(admission, lambda r: sent.append(r)) as http,
    ):
        http.post(ENDPOINT, content=content, headers={"Content-Type": "application/json"})
    assert sent == [] and admission.snapshot()["attempts"] == 0
