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


def package_manifest(tmp_path):
    from knora.evaluation.live_admission import reviewed_build_pins

    build = reviewed_build_pins()
    return {
        "package_id": "synthetic-package",
        "journal_path": str((tmp_path / "package.sqlite").resolve()),
        "code_sha": build["code_sha"],
        "reviewed_build": build,
        "gold_v1": {
            "dataset_id": "pdf-set",
            "dataset_digest": "5" * 64,
            "version": 1,
            "cases": {"ANSWER": "answer", "REFUSAL": "refusal"},
            "sources": {"version-1": {"document_id": "document-1", "raw_sha256": "a" * 64}},
        },
        "decision_reference": "owner-live-decision/test-only",
        "approved_by": "owner",
        "account_id": "a" * 32,
        "ownership": {"workspace_id": "w1", "resource_id": "owned-test-stack"},
        "live_approved_at": NOW.isoformat(),
        "package_deadline": (NOW + timedelta(hours=48)).isoformat(),
        "max_attempts": 33,
        "startup_cap": 3,
        "slots": {
            "corpus_prepare": 2,
            "qa_gold_v1_answer": 2,
            "qa_gold_v1_refusal": 2,
            "ragas_vi_draft": 1,
            "qa_ragas_answer": 2,
            "judge_gold_v1": 12,
            "judge_ragas": 12,
        },
    }


def slot_inputs(package, slot, policy, *, authority=None, **identities):
    from knora.evaluation.contracts import digest_json
    from knora.evaluation.live_admission import slot_authority_pins

    return {
        "input_digest": policy["scope"]["input_digest"],
        **slot_authority_pins(package._manifest, slot, policy, authority),
        "authority": authority,
        "identities": identities or {"request_id": slot},
        "ancestry": {
            parent: digest_json(package.slot_binding(parent)) for parent in package.parents(slot)
        },
    }


def test_package_requires_explicit_initialization_and_exact_path(tmp_path):
    from knora.evaluation.live_admission import LivePackage

    manifest = package_manifest(tmp_path)
    path = tmp_path / "package.sqlite"
    with pytest.raises(ValueError, match="LIVE_JOURNAL_MISSING"):
        LivePackage(manifest, path, clock=lambda: NOW)
    assert not path.exists()
    package = LivePackage.initialize(manifest, path, clock=lambda: NOW)
    assert package.snapshot()["attempts"] == 0
    with pytest.raises(ValueError):
        LivePackage.initialize(manifest, path, clock=lambda: NOW)
    with pytest.raises(ValueError, match="LIVE_PACKAGE_IDENTITY"):
        LivePackage(manifest, tmp_path / "moved.sqlite", clock=lambda: NOW)


@pytest.mark.parametrize("source_drift", [False, True, "large_body", "tokens_2049", "tokens_4096"])
def test_package_binding_and_transport_counts_survive_restart(tmp_path, source_drift):
    from contextlib import nullcontext

    from knora.evaluation.live_admission import LiveAdmission, LivePackage

    manifest = package_manifest(tmp_path)
    path = tmp_path / "package.sqlite"
    package = LivePackage.initialize(manifest, path, clock=lambda: NOW)
    policy = approval()
    policy["approval_id"] = package.approval_id("ragas_vi_draft")
    policy["scope"]["purpose"] = "proposals"
    policy["max_attempts"] = 1
    request_body = body()
    if source_drift == "large_body":
        request_body["messages"][0]["content"] = "x" * 8192
    elif isinstance(source_drift, str):
        request_body["max_tokens"] = int(source_drift.split("_")[1])
    payload = {
        "source": {
            "dataset_id": "pdf-set",
            "pdf_sources": [
                {
                    "document_version_id": "version-1",
                    "document_id": "document-1",
                    "raw_sha256": "a" * 64,
                    "extraction_snapshot_id": "snapshot",
                    "configuration_sha256": "b" * 64,
                    "extraction_sha256": "c" * 64,
                }
            ],
        }
    }
    from knora.evaluation.contracts import digest_json

    policy["scope"]["input_digest"] = digest_json(payload)
    policy["providers"][0].update(
        max_input_bytes=8192, max_output_tokens=2048, request_digests=[digest_json(request_body)]
    )
    effects = []
    cleanup = {
        "registration_id": "test-independent-cleanup",
        "scope": manifest["ownership"],
        "deadline": (NOW + timedelta(minutes=15)).isoformat(),
        "proof_digest": "e" * 64,
    }
    with (
        pytest.raises(ValueError) if isinstance(source_drift, str) else nullcontext(),
        package.window(
            scope=manifest["ownership"],
            cleanup=cleanup,
            start=lambda: effects.append("start"),
            stop=lambda: effects.append("stop"),
        ),
    ):
        corpus = approval()
        corpus["approval_id"] = package.approval_id("corpus_prepare")
        corpus["scope"]["purpose"] = "corpus_prepare"
        package.bind_slot("corpus_prepare", corpus, slot_inputs(package, "corpus_prepare", corpus))
        package.bind_execution("corpus_prepare", {"request_id": "corpus_prepare"})
        with package.operation("corpus_prepare"):
            package.record_result(
                "corpus_prepare",
                {
                    "sources": {}
                    if source_drift is True
                    else {"version-1": payload["source"]["pdf_sources"][0]}
                },
            )
        package.bind_slot(
            "ragas_vi_draft",
            policy,
            slot_inputs(
                package,
                "ragas_vi_draft",
                policy,
                authority=payload,
                request_id="proposal",
                dataset_id="pdf-set",
            ),
        )
        admission = LiveAdmission(
            policy, path, clock=lambda: NOW, package=package, slot="ragas_vi_draft"
        )
        admission.bind_execution(
            {"request_id": "proposal", "dataset_id": "pdf-set", "batch_id": "batch"}
        )
        if source_drift is True:
            with (
                pytest.raises(ValueError, match="LIVE_SLOT_ANCESTRY"),
                admission.dispatch(policy["scope"]),
                client(admission) as http,
            ):
                http.post(ENDPOINT, json=body())
            assert package.snapshot()["attempts"] == 0
            return
        with admission.dispatch(policy["scope"]), client(admission) as http:
            assert http.post(ENDPOINT, json=request_body).status_code == 200
    if isinstance(source_drift, str):
        assert package.snapshot()["attempts"] == 0
        assert package.snapshot()["stopped"]
        return
    assert effects == ["start", "stop"]
    reopened = LivePackage(manifest, path, clock=lambda: NOW)
    assert reopened.snapshot()["attempts"] == 1
    assert reopened.snapshot()["startups"] == 1
    assert reopened.snapshot()["slots"]["ragas_vi_draft"]["status"] == "COMPLETED"
    with pytest.raises(ValueError):
        reopened.bind_slot("ragas_vi_draft", policy, {"case_id": "different"})
    with pytest.raises(ValueError), admission.dispatch(policy["scope"]), client(admission) as http:
        http.post(ENDPOINT, json=body())


def test_slot_cannot_bind_without_completed_parent_or_with_foreign_approval(tmp_path):
    from knora.evaluation.live_admission import LivePackage

    manifest = package_manifest(tmp_path)
    package = LivePackage.initialize(manifest, tmp_path / "package.sqlite", clock=lambda: NOW)
    policy = approval()
    with pytest.raises(ValueError, match="LIVE_SLOT_APPROVAL"):
        package.bind_slot("qa_gold_v1_answer", policy, {})
    policy["approval_id"] = package.approval_id("qa_gold_v1_answer")
    with pytest.raises(ValueError, match="LIVE_SLOT_ANCESTRY"):
        inputs = slot_inputs(
            package,
            "qa_gold_v1_answer",
            policy,
            request_id="qa",
            case_id="answer",
            dataset_digest="5" * 64,
            selection_digest="6" * 64,
            binding_digest="7" * 64,
        )
        inputs["ancestry"] = {}
        package.bind_slot("qa_gold_v1_answer", policy, inputs)
    assert package.snapshot()["attempts"] == 0


@pytest.mark.parametrize(
    "reason",
    ["late_first", "expired_package", "bad_cleanup", "long_window", "startup_cap", "startup_crash"],
)
def test_package_startup_gates_run_before_side_effect_and_never_reset(tmp_path, reason):
    from knora.evaluation.live_admission import LivePackage

    manifest = package_manifest(tmp_path)
    clock = [NOW]
    path = tmp_path / "package.sqlite"
    package = LivePackage.initialize(manifest, path, clock=lambda: clock[0])
    cleanup = {
        "registration_id": "independent",
        "scope": manifest["ownership"],
        "deadline": (NOW + timedelta(minutes=15)).isoformat(),
        "proof_digest": "e" * 64,
    }
    effects = []
    if reason == "late_first":
        clock[0] += timedelta(hours=24, seconds=1)
        cleanup["deadline"] = (clock[0] + timedelta(minutes=15)).isoformat()
    elif reason == "expired_package":
        clock[0] += timedelta(hours=48)
    elif reason == "bad_cleanup":
        cleanup["scope"] = {"resource_id": "foreign"}
    elif reason == "long_window":
        cleanup["deadline"] = (NOW + timedelta(minutes=16)).isoformat()
    elif reason == "startup_cap":
        for _ in range(3):
            with package.window(
                scope=manifest["ownership"], cleanup=cleanup, start=lambda: None, stop=lambda: None
            ):
                pass
    elif reason == "startup_crash":
        with (
            pytest.raises(RuntimeError),
            package.window(
                scope=manifest["ownership"],
                cleanup=cleanup,
                start=lambda: (_ for _ in ()).throw(RuntimeError("startup failed")),
                stop=lambda: effects.append("cleanup"),
            ),
        ):
            pass
        assert package.snapshot()["startups"] == 1
        assert package.snapshot()["stopped"]
        effects.clear()
        package = LivePackage(manifest, path, clock=lambda: clock[0])
    with (
        pytest.raises(ValueError),
        package.window(
            scope=manifest["ownership"],
            cleanup=cleanup,
            start=lambda: effects.append("start"),
            stop=lambda: effects.append("stop"),
        ),
    ):
        pass
    assert effects == []


def test_package_started_slot_is_nonreplayable_and_missing_journal_is_never_recreated(tmp_path):
    import sqlite3

    from knora.evaluation.live_admission import LivePackage

    manifest = package_manifest(tmp_path)
    path = tmp_path / "package.sqlite"
    package = LivePackage.initialize(manifest, path, clock=lambda: NOW)
    policy = approval()
    policy["approval_id"] = package.approval_id("corpus_prepare")
    policy["scope"]["purpose"] = "corpus_prepare"
    package.bind_slot("corpus_prepare", policy, slot_inputs(package, "corpus_prepare", policy))
    with sqlite3.connect(path) as db:
        db.execute(
            "UPDATE slots SET status='STARTED',operation_id='crashed' WHERE name='corpus_prepare'"
        )
    db.close()
    reopened = LivePackage(manifest, path, clock=lambda: NOW)
    cleanup = {
        "registration_id": "independent",
        "scope": manifest["ownership"],
        "deadline": (NOW + timedelta(minutes=15)).isoformat(),
        "proof_digest": "e" * 64,
    }
    effects = []
    with (
        pytest.raises(ValueError, match="LIVE_SLOT_NONREPLAYABLE"),
        reopened.window(
            scope=manifest["ownership"],
            cleanup=cleanup,
            start=lambda: effects.append("start"),
            stop=lambda: effects.append("stop"),
        ),
        reopened.operation("corpus_prepare"),
    ):
        effects.append("replayed")
    assert "replayed" not in effects
    path.unlink()
    with pytest.raises(ValueError, match="LIVE_JOURNAL_MISSING"):
        reopened.snapshot()
    assert not path.exists()


def test_real_independent_processes_cannot_exceed_three_startup_reservations(tmp_path):
    import json
    import subprocess
    import sys

    from knora.evaluation.live_admission import LivePackage

    manifest = package_manifest(tmp_path)
    path = tmp_path / "package.sqlite"
    package = LivePackage.initialize(manifest, path, clock=lambda: NOW)
    manifest_file = tmp_path / "approved-package.json"
    manifest_file.write_text(json.dumps(manifest))
    script = """
import json,sys,time
from datetime import datetime,timedelta
from pathlib import Path
from knora.evaluation.live_admission import LivePackage
m=json.loads(Path(sys.argv[1]).read_text())
now=datetime.fromisoformat(m['live_approved_at'])
p=LivePackage(m,Path(m['journal_path']),clock=lambda:now)
proof=dict(registration_id='independent',scope=m['ownership'],
           deadline=(now+timedelta(minutes=15)).isoformat(),proof_digest='e'*64)
try:
    with p.window(scope=m['ownership'],cleanup=proof,
                  start=lambda:print('START',flush=True),stop=lambda:None):
        time.sleep(.05)
except ValueError:
    print('DENIED')
"""
    workers = [
        subprocess.Popen(
            [sys.executable, "-c", script, str(manifest_file)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for _ in range(8)
    ]
    outputs = [p.communicate(timeout=30) for p in workers]
    assert all(p.returncode == 0 for p in workers), outputs
    starts = sum(output.count("START") for output, _ in outputs)
    assert 1 <= starts <= 3
    assert package.snapshot()["startups"] == starts


def test_deepeval_next_request_depends_only_on_pinned_capture_and_prior_response():
    import json

    from evals.scorers.deepeval_cloudflare import next_capture_request

    capture = {
        "run_id": "saved-run",
        "case_id": "saved-case",
        "trace_id": "saved-trace",
        "attempt": 1,
        "question": "Color?",
        "answer": "Blue.",
        "reference_answer": "Blue.",
        "generation_evidence": [{"alias": "E1", "content": "Blue."}],
        "evidence_status": "exact",
        "data_classification": "synthetic",
        "egress_approved": True,
    }
    first, schema = next_capture_request(capture, [], model=MODEL, max_tokens=2048)
    assert first["response_format"]["json_schema"]["name"] == "Steps"
    one, _ = next_capture_request(
        capture, [json.dumps({"steps": ["Compare facts."]})], model=MODEL, max_tokens=2048
    )
    two, _ = next_capture_request(
        capture, [json.dumps({"steps": ["Compare every claim."]})], model=MODEL, max_tokens=2048
    )
    assert one != two
    assert schema.model_validate_json('{"steps":["Compare facts."]}').steps == ["Compare facts."]
    with pytest.raises(ValueError):
        next_capture_request(capture, ['{"steps":true}'], model=MODEL, max_tokens=2048)


@pytest.mark.parametrize("malformed", [False, True])
def test_response_chain_uses_actual_saved_responses_and_rejects_malformed_at_egress(
    tmp_path, malformed
):

    from evals.scorers.deepeval_cloudflare import next_capture_request

    from knora.evaluation.contracts import digest_json
    from knora.evaluation.live_admission import LiveAdmission, response_authority_pins

    capture = {
        "run_id": "run",
        "case_id": "case",
        "trace_id": "trace",
        "attempt": 1,
        "question": "Color?",
        "answer": "Blue",
        "reference_answer": "Blue",
        "generation_evidence": [{"alias": "E1", "content": "Blue"}],
        "evidence_status": "exact",
    }
    inputs = {"cases": [{"case_id": "case", "status": "READY", "capture": capture}]}
    policy = approval()
    policy["scope"] = {**scope(), "purpose": "scoring", "input_digest": digest_json(inputs)}
    policy["providers"][0].update(max_input_bytes=8192, max_output_tokens=2048, request_digests=[])
    policy["response_chain"] = {
        "kind": "deepeval",
        "input_digest": digest_json(inputs),
        "pins": response_authority_pins("deepeval"),
    }
    admission = LiveAdmission(
        policy, tmp_path / "chain.sqlite", clock=lambda: NOW, response_inputs=inputs
    )
    approved_capture = {**capture, "data_classification": "synthetic", "egress_approved": True}
    first, _ = next_capture_request(approved_capture, [], model=MODEL, max_tokens=2048)
    response_text = '{"steps":true}' if malformed else '{"steps":["Check every fact."]}'

    def exchange(request):
        return httpx.Response(
            200,
            json={
                "model": MODEL,
                "usage": {"completion_tokens": 4},
                "choices": [{"finish_reason": "stop", "message": {"content": response_text}}],
            },
        )

    if malformed:
        with (
            pytest.raises(ValueError),
            admission.dispatch(policy["scope"]),
            client(admission, exchange) as http,
        ):
            http.post(ENDPOINT, json=first)
        assert admission.snapshot()["stopped"]
    else:
        expected, _ = next_capture_request(
            approved_capture, [response_text], model=MODEL, max_tokens=2048
        )
        with (
            pytest.raises(ValueError, match="LIVE_REQUEST_UNAPPROVED"),
            admission.dispatch(policy["scope"]),
            client(admission, exchange) as http,
        ):
            http.post(ENDPOINT, json=first)
            http.post(
                ENDPOINT,
                json={**expected, "messages": [{"role": "user", "content": "foreign capture"}]},
            )
        assert admission.snapshot()["attempts"] == 1


def test_helper_self_terminates_without_parent_watchdog_or_network():
    import subprocess
    import sys

    command = (
        "import time; from knora.evaluation.provider_request import _arm_deadline; "
        "_arm_deadline(time.time()+.15); time.sleep(60)"
    )
    result = subprocess.run([sys.executable, "-c", command], timeout=3, capture_output=True)
    assert result.returncode == 2 and result.stdout == b"" and result.stderr == b""


@pytest.mark.parametrize("drift", ["capture", "case", "template", "schema", "model", "endpoint"])
def test_response_authority_drift_never_reaches_transport(tmp_path, monkeypatch, drift):
    from evals.scorers.deepeval_cloudflare import next_capture_request

    from knora.evaluation import live_admission as module
    from knora.evaluation.contracts import digest_json

    capture = {
        "run_id": "run",
        "case_id": "case",
        "trace_id": "trace",
        "attempt": 1,
        "question": "Color?",
        "answer": "Blue",
        "reference_answer": "Blue",
        "generation_evidence": [{"alias": "E1", "content": "Blue"}],
        "evidence_status": "exact",
    }
    inputs = {"cases": [{"case_id": "case", "status": "READY", "capture": capture}]}
    policy = approval()
    policy["scope"] = {**scope(), "purpose": "scoring", "input_digest": digest_json(inputs)}
    policy["providers"][0].update(max_input_bytes=8192, max_output_tokens=2048, request_digests=[])
    policy["response_chain"] = {
        "kind": "deepeval",
        "input_digest": digest_json(inputs),
        "pins": module.response_authority_pins("deepeval"),
    }
    admission = module.LiveAdmission(
        policy, tmp_path / "chain.sqlite", clock=lambda: NOW, response_inputs=inputs
    )
    first, _ = next_capture_request(
        {**capture, "data_classification": "synthetic", "egress_approved": True},
        [],
        model=MODEL,
        max_tokens=2048,
    )
    endpoint = ENDPOINT
    sent = []
    if drift == "template":
        monkeypatch.setattr(
            module, "response_authority_pins", lambda _: {"source_digest": "0" * 64}
        )
    elif drift == "schema":
        first["response_format"]["json_schema"]["schema"] = {"type": "object"}
    elif drift == "model":
        first["model"] = "@cf/foreign/model"
    elif drift == "endpoint":
        endpoint += "?foreign=1"
    with (
        pytest.raises(ValueError),
        admission.dispatch(policy["scope"]),
        client(admission, lambda r: sent.append(r)) as http,
    ):
        if drift == "capture":
            admission.validate_capture({**capture, "trace_id": "foreign"})
        elif drift == "case":
            admission.bind_execution({"run_id": "run", "case_id": "foreign"})
        else:
            http.post(endpoint, json=first)
    assert sent == [] and admission.snapshot()["attempts"] == 0
    assert admission.snapshot()["stopped"]


def test_package_stop_journal_replacement_cannot_restore_live_authority(tmp_path):
    import sqlite3

    from knora.evaluation.live_admission import LivePackage

    manifest = package_manifest(tmp_path)
    path = tmp_path / "package.sqlite"
    package = LivePackage.initialize(manifest, path, clock=lambda: NOW)
    stops = tmp_path / "package.sqlite.stops"
    stops.rename(tmp_path / "original-stops")
    with sqlite3.connect(stops) as db:
        db.execute("CREATE TABLE stop_requests (approval_id TEXT PRIMARY KEY)")
    with pytest.raises(ValueError, match="LIVE_PACKAGE_IDENTITY"):
        package.snapshot()


def test_package_nested_window_does_not_lose_cleanup_or_consume_startup(tmp_path):
    from knora.evaluation.live_admission import LivePackage

    manifest = package_manifest(tmp_path)
    package = LivePackage.initialize(manifest, tmp_path / "package.sqlite", clock=lambda: NOW)
    cleanup = {
        "registration_id": "independent",
        "scope": manifest["ownership"],
        "deadline": (NOW + timedelta(minutes=15)).isoformat(),
        "proof_digest": "e" * 64,
    }
    effects = []
    with (
        package.window(
            scope=manifest["ownership"],
            cleanup=cleanup,
            start=lambda: effects.append("start"),
            stop=lambda: effects.append("cleanup"),
        ),
        pytest.raises(ValueError),
        package.window(
            scope=manifest["ownership"],
            cleanup=cleanup,
            start=lambda: effects.append("second-start"),
            stop=lambda: effects.append("second-cleanup"),
        ),
    ):
        pass
    assert effects == ["start", "cleanup"]
    assert package.snapshot()["startups"] == 1


def test_caught_invalid_egress_still_stops_the_admission(tmp_path):
    admission = gate(tmp_path)
    sent = []

    def exchange(request):
        sent.append(request)
        return success(request)

    with (
        pytest.raises(ValueError),
        admission.dispatch(scope()),
        client(admission, exchange) as http,
    ):
        with pytest.raises(ValueError, match="LIVE_REQUEST_UNAPPROVED"):
            http.post(ENDPOINT, json=body(model="foreign"))
        http.post(ENDPOINT, json=body())
    assert sent == []
    assert admission.snapshot() == {"attempts": 0, "pending": None, "stopped": True}


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


@pytest.mark.parametrize("slot", ["qa_gold_v1_answer", "judge_gold_v1", "ragas_vi_draft"])
def test_package_rejects_incomplete_slot_identities_before_binding(tmp_path, slot):
    from knora.evaluation.live_admission import LivePackage

    package = LivePackage.initialize(
        package_manifest(tmp_path), tmp_path / "package.sqlite", clock=lambda: NOW
    )
    policy = approval()
    policy["approval_id"] = package.approval_id(slot)
    policy["scope"]["purpose"] = (
        "scoring" if slot.startswith("judge") else "qa" if slot.startswith("qa") else "proposals"
    )
    policy["max_attempts"] = 1
    with pytest.raises(ValueError, match="LIVE_SLOT_INPUT"):
        package.bind_slot(slot, policy, slot_inputs(package, slot, policy, workspace_id="w1"))
    assert package.slot_binding(slot) is None


@pytest.mark.parametrize(
    "drift",
    [None, "run_id", "case_id", "trace_id", "capture_digest", "dataset_digest", "selection_digest"],
)
def test_judge_slot_requires_its_completed_qa_capture(tmp_path, drift):
    from knora.evaluation.contracts import digest_json
    from knora.evaluation.live_admission import LivePackage

    manifest = package_manifest(tmp_path)
    package = LivePackage.initialize(manifest, tmp_path / "package.sqlite", clock=lambda: NOW)
    cleanup = {
        "registration_id": "test-only",
        "scope": manifest["ownership"],
        "proof_digest": "e" * 64,
        "deadline": (NOW + timedelta(minutes=15)).isoformat(),
    }
    capture = {
        "run_id": "saved-run",
        "case_id": "answer",
        "trace_id": "saved-trace",
        "attempt": 1,
        "question": "Color?",
        "answer": "Blue",
        "reference_answer": "Blue",
        "generation_evidence": [{"alias": "E1", "content": "Blue"}],
        "evidence_status": "exact",
    }
    pins = {
        "request_id": "qa",
        "dataset_digest": "5" * 64,
        "selection_digest": "6" * 64,
        "binding_digest": "7" * 64,
        "case_id": "answer",
    }
    with package.window(
        scope=manifest["ownership"], cleanup=cleanup, start=lambda: None, stop=lambda: None
    ):
        for slot in ("corpus_prepare", "qa_gold_v1_answer"):
            policy = approval()
            policy["approval_id"] = package.approval_id(slot)
            policy["scope"]["purpose"] = "corpus_prepare" if slot == "corpus_prepare" else "qa"
            identities = {"request_id": slot} if slot == "corpus_prepare" else pins
            package.bind_slot(slot, policy, slot_inputs(package, slot, policy, **identities))
            execution = {**identities, "run_id": "saved-run", "attempt_id": "attempt"}
            package.bind_execution(slot, execution)
            with package.operation(slot):
                if slot == "qa_gold_v1_answer":
                    package.record_result(
                        slot,
                        {
                            "identities": {**execution, "trace_id": "saved-trace"},
                            "capture": capture,
                        },
                    )
        policy = approval()
        policy["approval_id"] = package.approval_id("judge_gold_v1")
        policy["scope"]["purpose"] = "scoring"
        identities = {
            **pins,
            "request_id": "judge",
            "run_id": "saved-run",
            "trace_id": "saved-trace",
            "capture_digest": digest_json(capture),
        }
        if drift:
            identities[drift] = "f" * 64 if drift.endswith("_digest") else "foreign"
        inputs = slot_inputs(package, "judge_gold_v1", policy, **identities)
        if drift:
            with pytest.raises(ValueError, match="LIVE_SLOT_ANCESTRY"):
                package.bind_slot("judge_gold_v1", policy, inputs)
            assert package.slot_binding("judge_gold_v1") is None
        else:
            package.bind_slot("judge_gold_v1", policy, inputs)
    assert package.snapshot()["attempts"] == 0


def test_response_chain_revalidates_after_an_independent_connection_commits(tmp_path, monkeypatch):
    import json
    from contextlib import contextmanager
    from threading import Event

    from evals.scorers.deepeval_cloudflare import next_capture_request

    from knora.evaluation.contracts import digest_json
    from knora.evaluation.live_admission import LiveAdmission, response_authority_pins

    capture = {
        "run_id": "run",
        "case_id": "case",
        "trace_id": "trace",
        "attempt": 1,
        "question": "Color?",
        "answer": "Blue",
        "reference_answer": "Blue",
        "generation_evidence": [{"alias": "E1", "content": "Blue"}],
        "evidence_status": "exact",
    }
    inputs = {"cases": [{"case_id": "case", "status": "READY", "capture": capture}]}
    policy = approval()
    policy["scope"] = {**scope(), "purpose": "scoring", "input_digest": digest_json(inputs)}
    policy["providers"][0].update(max_input_bytes=8192, max_output_tokens=2048, request_digests=[])
    policy["response_chain"] = {
        "kind": "deepeval",
        "input_digest": digest_json(inputs),
        "pins": response_authority_pins("deepeval"),
    }
    path = tmp_path / "chain.sqlite"
    first = LiveAdmission(policy, path, clock=lambda: NOW, response_inputs=inputs)
    stale = LiveAdmission(policy, path, clock=lambda: NOW, response_inputs=inputs)
    prepared, release = Event(), Event()
    original_db = stale._db

    @contextmanager
    def delayed_db(**kwargs):
        with original_db(**kwargs) as connection:

            class DelayedConnection:
                def __getattr__(self, name):
                    return getattr(connection, name)

                def execute(self, sql, *args):
                    if sql == "BEGIN IMMEDIATE":
                        prepared.set()
                        assert release.wait(10)
                    return connection.execute(sql, *args)

            yield DelayedConnection()

    monkeypatch.setattr(stale, "_db", delayed_db)
    request, _ = next_capture_request(
        {**capture, "data_classification": "synthetic", "egress_approved": True},
        [],
        model=MODEL,
        max_tokens=2048,
    )
    sent = []

    def exchange(request):
        sent.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "model": MODEL,
                "usage": {"completion_tokens": 4},
                "choices": [
                    {"finish_reason": "stop", "message": {"content": '{"steps":["Check facts."]}'}}
                ],
            },
        )

    def late_request():
        with (
            pytest.raises(ValueError),
            stale.dispatch(policy["scope"]),
            client(stale, exchange) as http,
        ):
            http.post(ENDPOINT, json=request)

    with (
        ThreadPoolExecutor(max_workers=1) as pool,
        pytest.raises(ValueError),
        first.dispatch(policy["scope"]),
        client(first, exchange) as http,
    ):
        late = pool.submit(late_request)
        assert prepared.wait(10)
        try:
            http.post(ENDPOINT, json=request)
        finally:
            release.set()
        late.result(timeout=10)
    assert len(sent) == 1
    assert first.snapshot() == {"attempts": 1, "pending": None, "stopped": True}


@pytest.mark.parametrize("crash", [False, True])
def test_real_process_reservations_preserve_consumed_requests_on_restart(tmp_path, crash):
    import json
    import subprocess
    import sys

    from knora.evaluation.live_admission import LiveAdmission

    policy = approval()
    path = tmp_path / "requests.sqlite"
    LiveAdmission(policy, path, clock=lambda: NOW)
    inputs = tmp_path / "synthetic-request.json"
    inputs.write_text(json.dumps({"policy": policy, "body": body()}))
    script = """
import json,os,sys,time
from datetime import datetime
from pathlib import Path
import httpx
from knora.evaluation.live_admission import LiveAdmission
data=json.loads(Path(sys.argv[1]).read_text())
p=data['policy']
now=datetime.fromisoformat(p['proof_observed_at'])
a=LiveAdmission(p,sys.argv[2],clock=lambda:now)
def reply(request):
    if sys.argv[3]=='crash':
        os._exit(0)
    time.sleep(.05)
    print('EGRESS',flush=True)
    return httpx.Response(200,json={
        'model':p['providers'][0]['model'],'usage':{'completion_tokens':2},
        'choices':[{'finish_reason':'stop','message':{'content':'OK'}}]})
try:
    with a.dispatch(p['scope']),a.sync_client(mock=httpx.MockTransport(reply)) as client:
        client.post(p['providers'][0]['endpoint'],json=data['body'])
        client.post(p['providers'][0]['endpoint'],json=data['body'])
except ValueError:
    print('DENIED',flush=True)
"""
    count = 1 if crash else 8
    workers = [
        subprocess.Popen(
            [sys.executable, "-c", script, str(inputs), str(path), "crash" if crash else "race"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for _ in range(count)
    ]
    outputs = [worker.communicate(timeout=30) for worker in workers]
    assert all(worker.returncode == 0 for worker in workers), outputs
    reopened = LiveAdmission(policy, path, clock=lambda: NOW)
    state = reopened.snapshot()
    assert 1 <= state["attempts"] <= 2
    if crash:
        assert state["attempts"] == state["pending"] == 1
    else:
        assert sum(out.count("EGRESS") for out, _ in outputs) == state["attempts"]
        if state["attempts"] == 1:
            assert state["stopped"] and state["pending"] == 1
            assert any("DENIED" in out for out, _ in outputs)
    with pytest.raises(ValueError):
        reopened.verify(policy["scope"])
    assert reopened.snapshot()["attempts"] == state["attempts"]


@pytest.mark.parametrize("expires", ["lock_wait", "before_start"])
def test_startup_deadline_is_rechecked_before_side_effect(tmp_path, monkeypatch, expires):
    from contextlib import contextmanager

    from knora.evaluation.live_admission import LivePackage

    now = [NOW]
    manifest = package_manifest(tmp_path)
    package = LivePackage.initialize(manifest, tmp_path / "package.sqlite", clock=lambda: now[0])
    cleanup = {
        "registration_id": "test-only",
        "scope": manifest["ownership"],
        "proof_digest": "e" * 64,
        "deadline": (NOW + timedelta(seconds=1)).isoformat(),
    }
    original = package._db

    @contextmanager
    def waiting_db():
        with original() as db:

            class Connection:
                def __getattr__(self, name):
                    return getattr(db, name)

                def execute(self, sql, *args):
                    if sql == "BEGIN IMMEDIATE" and expires == "lock_wait":
                        now[0] += timedelta(seconds=2)
                    return db.execute(sql, *args)

            yield Connection()
        if expires == "before_start":
            now[0] += timedelta(seconds=2)

    monkeypatch.setattr(package, "_db", waiting_db)
    effects = []
    with (
        pytest.raises(ValueError),
        package.window(
            scope=manifest["ownership"],
            cleanup=cleanup,
            start=lambda: effects.append("start"),
            stop=lambda: effects.append("stop"),
        ),
    ):
        pass
    assert "start" not in effects


@pytest.mark.parametrize(
    "field,value",
    [("max_output_tokens", 4096), ("max_input_bytes", 8193), ("model", "@cf/foreign/model")],
)
def test_package_proposal_rejects_envelope_beyond_approved_limit(tmp_path, field, value):
    from knora.evaluation.live_admission import LivePackage

    manifest = package_manifest(tmp_path)
    package = LivePackage.initialize(manifest, tmp_path / "package.sqlite", clock=lambda: NOW)
    policy = approval()
    policy.update(approval_id=package.approval_id("ragas_vi_draft"), max_attempts=1)
    parent = approval()
    parent["approval_id"] = package.approval_id("corpus_prepare")
    parent["scope"]["purpose"] = "corpus_prepare"
    package.bind_slot("corpus_prepare", parent, slot_inputs(package, "corpus_prepare", parent))
    package.bind_execution("corpus_prepare", {"request_id": "corpus_prepare"})
    cleanup = {
        "registration_id": "test-only",
        "scope": manifest["ownership"],
        "proof_digest": "e" * 64,
        "deadline": (NOW + timedelta(minutes=15)).isoformat(),
    }
    with (
        package.window(
            scope=manifest["ownership"], cleanup=cleanup, start=lambda: None, stop=lambda: None
        ),
        package.operation("corpus_prepare"),
    ):
        package.record_result("corpus_prepare", {"sources": {}})
    policy["scope"]["purpose"] = "proposals"
    policy["providers"][0].update(max_input_bytes=8192, max_output_tokens=2048)
    policy["providers"][0][field] = value
    with pytest.raises(ValueError, match="LIVE_SLOT_PROVIDER"):
        package.bind_slot(
            "ragas_vi_draft",
            policy,
            slot_inputs(
                package, "ragas_vi_draft", policy, request_id="proposal", dataset_id="dataset"
            ),
        )
    assert package.snapshot()["attempts"] == 0


@pytest.mark.parametrize("drift", ["code_sha", "reviewed_build"])
def test_package_rejects_unreviewed_build_identity_before_initialization(tmp_path, drift):
    from knora.evaluation.live_admission import LivePackage

    manifest = package_manifest(tmp_path)
    if drift == "code_sha":
        manifest["code_sha"] = "e" * 40
    else:
        manifest["reviewed_build"] = {"source_digest": "f" * 64}
    with pytest.raises(ValueError, match="LIVE_PACKAGE_BUILD"):
        LivePackage.initialize(manifest, tmp_path / "package.sqlite", clock=lambda: NOW)
    assert not (tmp_path / "package.sqlite").exists()


@pytest.mark.parametrize("pin", ["configuration_digest", "prompt_digest", "schema_digest"])
def test_slot_rejects_well_formed_digest_unrelated_to_actual_authority(tmp_path, pin):
    from knora.evaluation.live_admission import LivePackage

    package = LivePackage.initialize(
        package_manifest(tmp_path), tmp_path / "package.sqlite", clock=lambda: NOW
    )
    policy = approval()
    policy.update(approval_id=package.approval_id("corpus_prepare"))
    policy["scope"]["purpose"] = "corpus_prepare"
    inputs = slot_inputs(package, "corpus_prepare", policy)
    inputs[pin] = "f" * 64
    with pytest.raises(ValueError, match="LIVE_SLOT_AUTHORITY"):
        package.bind_slot("corpus_prepare", policy, inputs)
    assert package.slot_binding("corpus_prepare") is None


def test_startup_waiting_for_an_independent_connection_never_runs_after_deadline(
    tmp_path, monkeypatch
):
    import sqlite3
    from contextlib import contextmanager
    from threading import Event

    from knora.evaluation.live_admission import LivePackage

    now = [NOW]
    manifest = package_manifest(tmp_path)
    package = LivePackage.initialize(manifest, tmp_path / "package.sqlite", clock=lambda: now[0])
    waiting = Event()
    original = package._db

    @contextmanager
    def observed_db():
        with original() as db:

            class Connection:
                def __getattr__(self, name):
                    return getattr(db, name)

                def execute(self, sql, *args):
                    if sql == "BEGIN IMMEDIATE":
                        waiting.set()
                    return db.execute(sql, *args)

            yield Connection()

    monkeypatch.setattr(package, "_db", observed_db)
    cleanup = {
        "registration_id": "test-only",
        "scope": manifest["ownership"],
        "proof_digest": "e" * 64,
        "deadline": (NOW + timedelta(seconds=1)).isoformat(),
    }
    effects = []

    def attempt():
        with (
            pytest.raises(ValueError),
            package.window(
                scope=manifest["ownership"],
                cleanup=cleanup,
                start=lambda: effects.append("start"),
                stop=lambda: effects.append("stop"),
            ),
        ):
            pass

    with sqlite3.connect(package._path) as blocker, ThreadPoolExecutor(max_workers=1) as workers:
        blocker.execute("BEGIN IMMEDIATE")
        work = workers.submit(attempt)
        assert waiting.wait(timeout=5)
        now[0] += timedelta(seconds=2)
        blocker.commit()
        work.result(timeout=10)
    assert effects == []
    assert package.snapshot()["startups"] == 0


@pytest.mark.parametrize("crash", [False, True])
def test_package_request_reservation_is_atomic_across_real_processes(tmp_path, crash):
    import json
    import sqlite3
    import subprocess
    import sys

    from knora.evaluation.contracts import digest_json
    from knora.evaluation.live_admission import LivePackage

    manifest = package_manifest(tmp_path)
    path = tmp_path / "package.sqlite"
    package = LivePackage.initialize(manifest, path, clock=lambda: NOW)
    cleanup = {
        "registration_id": "test-only",
        "scope": manifest["ownership"],
        "proof_digest": "e" * 64,
        "deadline": (NOW + timedelta(minutes=15)).isoformat(),
    }
    corpus = approval()
    corpus.update(approval_id=package.approval_id("corpus_prepare"))
    corpus["scope"]["purpose"] = "corpus_prepare"
    package.bind_slot("corpus_prepare", corpus, slot_inputs(package, "corpus_prepare", corpus))
    package.bind_execution("corpus_prepare", {"request_id": "corpus_prepare"})
    payload = {
        "source": {
            "dataset_id": "pdf-set",
            "pdf_sources": [
                {
                    "document_version_id": "version-1",
                    "document_id": "document-1",
                    "raw_sha256": "a" * 64,
                    "extraction_snapshot_id": "snapshot",
                    "configuration_sha256": "b" * 64,
                    "extraction_sha256": "c" * 64,
                }
            ],
        }
    }
    with (
        package.window(
            scope=manifest["ownership"], cleanup=cleanup, start=lambda: None, stop=lambda: None
        ),
        package.operation("corpus_prepare"),
    ):
        package.record_result(
            "corpus_prepare", {"sources": {"version-1": payload["source"]["pdf_sources"][0]}}
        )
    policy = approval()
    policy.update(approval_id=package.approval_id("ragas_vi_draft"), max_attempts=1)
    policy["scope"].update(purpose="proposals", input_digest=digest_json(payload))
    package.bind_slot(
        "ragas_vi_draft",
        policy,
        slot_inputs(
            package,
            "ragas_vi_draft",
            policy,
            authority=payload,
            dataset_id="pdf-set",
            request_id="process",
        ),
    )
    package.bind_execution(
        "ragas_vi_draft", {"dataset_id": "pdf-set", "request_id": "process", "batch_id": "batch"}
    )
    inputs = tmp_path / "process-input.json"
    inputs.write_text(
        json.dumps({"manifest": manifest, "policy": policy, "cleanup": cleanup, "body": body()})
    )
    script = """
import json,os,sys,time
from datetime import datetime
from pathlib import Path
import httpx
from knora.evaluation.live_admission import LiveAdmission,LivePackage
data=json.loads(Path(sys.argv[1]).read_text())
now=datetime.fromisoformat(data['policy']['proof_observed_at'])
p=LivePackage(data['manifest'],sys.argv[2],clock=lambda:now)
a=LiveAdmission(data['policy'],sys.argv[2],clock=lambda:now,package=p,slot='ragas_vi_draft')
def exchange(request):
    print('EGRESS',flush=True)
    if sys.argv[3]=='crash': os._exit(0)
    time.sleep(.1)
    return httpx.Response(200,json={'model':data['body']['model'],
        'usage':{'completion_tokens':2},'choices':[{'finish_reason':'stop','message':{'content':'OK'}}]})
try:
    with p.window(scope=data['manifest']['ownership'],cleanup=data['cleanup'],
                  start=lambda:None,stop=lambda:None):
        with a.dispatch(data['policy']['scope']),a.sync_client(
                mock=httpx.MockTransport(exchange)) as client:
            client.post(data['policy']['providers'][0]['endpoint'],json=data['body'])
            client.post(data['policy']['providers'][0]['endpoint'],json=data['body'])
except ValueError:
    print('DENIED',flush=True)
"""
    workers = [
        subprocess.Popen(
            [sys.executable, "-c", script, str(inputs), str(path), "crash" if crash else "race"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for _ in range(1 if crash else 3)
    ]
    outputs = [worker.communicate(timeout=40) for worker in workers]
    assert all(worker.returncode == 0 for worker in workers), outputs
    assert sum(out.count("EGRESS") for out, _ in outputs) == 1
    reopened = LivePackage(manifest, path, clock=lambda: NOW)
    assert reopened.snapshot()["attempts"] == 1
    assert reopened.snapshot()["slots"]["ragas_vi_draft"] == {"status": "STARTED", "attempts": 1}
    with sqlite3.connect(path) as db:
        assert db.execute(
            "SELECT attempts,pending FROM approvals WHERE id=?", (policy["approval_id"],)
        ).fetchone() == (1, 1 if crash else None)
        assert db.execute("SELECT COUNT(*) FROM requests").fetchone() == (1,)
    from knora.evaluation.live_admission import LiveAdmission

    with pytest.raises(ValueError):
        LiveAdmission(
            policy, path, clock=lambda: NOW, package=reopened, slot="ragas_vi_draft"
        ).verify(policy["scope"])


@pytest.mark.parametrize(
    "relative",
    [
        "backend/src/knora/adapters/postgres/corpus_preparation.py",
        "backend/src/knora/adapters/postgres/ingestion_jobs/coordination.py",
        "backend/src/knora/ingestion/job_processing.py",
    ],
)
def test_reviewed_build_tracks_runtime_content(monkeypatch, relative):
    from pathlib import Path

    import knora.evaluation.live_admission as live

    root = Path(live.__file__).resolve().parents[4]
    before = live.reviewed_build_pins()
    assert relative in before["sources"]
    original_read = Path.read_text
    target = (root / relative).resolve()

    def drifted_read(path, *args, **kwargs):
        text = original_read(path, *args, **kwargs)
        return text + "\n# synthetic source drift\n" if path.resolve() == target else text

    monkeypatch.setattr(Path, "read_text", drifted_read)
    after = live.reviewed_build_pins()
    assert after["code_sha"] == before["code_sha"]
    assert after["sources"][relative] != before["sources"][relative]


def test_package_initialize_and_window_reject_content_drift(monkeypatch, tmp_path):
    from pathlib import Path

    import knora.evaluation.live_admission as live
    from knora.evaluation.live_admission import LivePackage

    root = Path(live.__file__).resolve().parents[4]
    target = (root / "backend/src/knora/adapters/postgres/corpus_preparation.py").resolve()
    original_read = Path.read_text

    manifest = package_manifest(tmp_path)
    journal_path = tmp_path / "package.sqlite"
    package = LivePackage.initialize(manifest, journal_path, clock=lambda: NOW)

    def drifted_read(path, *args, **kwargs):
        text = original_read(path, *args, **kwargs)
        return text + "\n# synthetic source drift\n" if path.resolve() == target else text

    monkeypatch.setattr(Path, "read_text", drifted_read)

    unborn_journal = tmp_path / "unborn.sqlite"
    with pytest.raises(ValueError, match="LIVE_PACKAGE_BUILD"):
        LivePackage.initialize(manifest, unborn_journal, clock=lambda: NOW)
    assert not unborn_journal.exists()

    cleanup = {
        "registration_id": "independent",
        "scope": manifest["ownership"],
        "deadline": (NOW + timedelta(minutes=15)).isoformat(),
        "proof_digest": "e" * 64,
    }
    effects = []
    with (
        pytest.raises(ValueError, match="LIVE_PACKAGE_BUILD"),
        package.window(
            scope=manifest["ownership"],
            cleanup=cleanup,
            start=lambda: effects.append("start"),
            stop=lambda: effects.append("stop"),
        ),
    ):
        pass
    assert effects == []
    assert package.snapshot()["startups"] == 0


def test_package_fails_closed_when_pinned_file_unreadable(monkeypatch, tmp_path):
    from pathlib import Path

    import knora.evaluation.live_admission as live
    from knora.evaluation.live_admission import LivePackage

    root = Path(live.__file__).resolve().parents[4]
    target = (root / "backend/src/knora/adapters/postgres/corpus_preparation.py").resolve()
    original_read = Path.read_text

    manifest = package_manifest(tmp_path)
    journal_path = tmp_path / "package.sqlite"
    package = LivePackage.initialize(manifest, journal_path, clock=lambda: NOW)

    def failing_read(path, *args, **kwargs):
        if path.resolve() == target:
            raise OSError("unreadable pinned file")
        return original_read(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", failing_read)

    cleanup = {
        "registration_id": "independent",
        "scope": manifest["ownership"],
        "deadline": (NOW + timedelta(minutes=15)).isoformat(),
        "proof_digest": "e" * 64,
    }
    effects = []
    with (
        pytest.raises(OSError, match="unreadable pinned file"),
        package.window(
            scope=manifest["ownership"],
            cleanup=cleanup,
            start=lambda: effects.append("start"),
            stop=lambda: effects.append("stop"),
        ),
    ):
        pass
    assert effects == []
    assert package.snapshot()["startups"] == 0


def package_manifest_v2(tmp_path):
    from knora.evaluation.live_admission import _SLOTS_V2, reviewed_build_pins

    build = reviewed_build_pins()
    return {
        "manifest_version": 2,
        "package_id": "acceptance-v2-package",
        "journal_path": str((tmp_path / "package_v2.sqlite").resolve()),
        "code_sha": build["code_sha"],
        "reviewed_build": build,
        "gold_v1": {
            "dataset_id": "pdf-set-v2",
            "dataset_digest": "6" * 64,
            "version": 1,
            "cases": {"ANSWER": "answer", "REFUSAL": "refusal"},
            "sources": {
                "version-1": {"document_id": "document-1", "raw_sha256": "a" * 64},
                "version-2": {"document_id": "document-2", "raw_sha256": "b" * 64},
            },
        },
        "decision_reference": "issue158/evaluation-tools-acceptance",
        "approved_by": "owner",
        "account_id": "a" * 32,
        "ownership": {"workspace_id": "w1", "resource_id": "owned-test-stack-v2"},
        "live_approved_at": NOW.isoformat(),
        "package_deadline": (NOW + timedelta(days=7)).isoformat(),
        "max_attempts": 139,
        "startup_cap": 2,
        "window_cap": 8,
        "slots": dict(_SLOTS_V2),
        "skipped_slots": ["corpus_prepare", "qa_gold_v1_answer"],
    }


def test_package_v2_initialization_and_table_driven_checks(tmp_path):
    from copy import deepcopy

    from knora.evaluation.live_admission import LivePackage

    manifest = package_manifest_v2(tmp_path)
    path = tmp_path / "package_v2.sqlite"
    package = LivePackage.initialize(manifest, path, clock=lambda: NOW)
    snap = package.snapshot()
    assert snap["attempts"] == 0
    assert snap["startups"] == 0
    assert snap["slots"]["corpus_prepare"]["status"] == "SKIPPED"
    assert snap["slots"]["qa_gold_v1_answer"]["status"] == "SKIPPED"
    assert snap["slots"]["judge_real"]["status"] == "WAITING"

    # Rejection of invalid limits for V2
    for mod_key, mod_val in (
        ("max_attempts", 140),
        ("max_attempts", 33),
        ("startup_cap", 3),
        ("window_cap", 9),
        ("manifest_version", 3),
        ("package_deadline", (NOW + timedelta(hours=48)).isoformat()),
        ("skipped_slots", ["unknown_slot"]),
    ):
        bad_manifest = deepcopy(manifest)
        bad_manifest[mod_key] = mod_val
        bad_manifest["journal_path"] = str((tmp_path / f"bad_{mod_key}.sqlite").resolve())
        with pytest.raises(ValueError, match="LIVE_PACKAGE_IDENTITY"):
            LivePackage.initialize(bad_manifest, bad_manifest["journal_path"], clock=lambda: NOW)


def test_package_v2_window_and_startup_limits(tmp_path):
    from knora.evaluation.live_admission import LivePackage

    manifest = package_manifest_v2(tmp_path)
    path = tmp_path / "package_v2.sqlite"
    package = LivePackage.initialize(manifest, path, clock=lambda: NOW)

    # 60 minute window is accepted in V2
    cleanup_60 = {
        "registration_id": "test-v2",
        "scope": manifest["ownership"],
        "deadline": (NOW + timedelta(minutes=60)).isoformat(),
        "proof_digest": "f" * 64,
    }
    with package.window(
        scope=manifest["ownership"],
        cleanup=cleanup_60,
        start=lambda: None,
        stop=lambda: None,
        stack_startup=False,
    ):
        pass
    assert package.snapshot()["startups"] == 0

    # 61 minute window is rejected
    cleanup_61 = {
        "registration_id": "test-v2-long",
        "scope": manifest["ownership"],
        "deadline": (NOW + timedelta(minutes=61)).isoformat(),
        "proof_digest": "f" * 64,
    }
    with (
        pytest.raises(ValueError, match="LIVE_CLEANUP_UNPROVEN"),
        package.window(
            scope=manifest["ownership"], cleanup=cleanup_61, start=lambda: None, stop=lambda: None
        ),
    ):
        pass

    # Up to 8 windows are accepted
    for i in range(7):
        c = {
            "registration_id": f"window-{i}",
            "scope": manifest["ownership"],
            "deadline": (NOW + timedelta(minutes=10)).isoformat(),
            "proof_digest": "f" * 64,
        }
        with package.window(
            scope=manifest["ownership"],
            cleanup=c,
            start=lambda: None,
            stop=lambda: None,
            stack_startup=False,
        ):
            pass

    # 9th window is rejected
    c9 = {
        "registration_id": "window-9",
        "scope": manifest["ownership"],
        "deadline": (NOW + timedelta(minutes=10)).isoformat(),
        "proof_digest": "f" * 64,
    }
    with (
        pytest.raises(ValueError, match="LIVE_WINDOW_CAP"),
        package.window(
            scope=manifest["ownership"],
            cleanup=c9,
            start=lambda: None,
            stop=lambda: None,
            stack_startup=False,
        ),
    ):
        pass


def test_package_v2_stack_startup_cap(tmp_path):
    from knora.evaluation.live_admission import LivePackage

    manifest = package_manifest_v2(tmp_path)
    path = tmp_path / "package_v2_stack.sqlite"
    manifest["journal_path"] = str(path.resolve())
    package = LivePackage.initialize(manifest, path, clock=lambda: NOW)

    # Stack startup 1
    c1 = {
        "registration_id": "s1",
        "scope": manifest["ownership"],
        "deadline": (NOW + timedelta(minutes=10)).isoformat(),
        "proof_digest": "f" * 64,
    }
    with package.window(
        scope=manifest["ownership"],
        cleanup=c1,
        start=lambda: None,
        stop=lambda: None,
        stack_startup=True,
    ):
        pass
    assert package.snapshot()["startups"] == 1

    # Stack startup 2
    c2 = {
        "registration_id": "s2",
        "scope": manifest["ownership"],
        "deadline": (NOW + timedelta(minutes=10)).isoformat(),
        "proof_digest": "f" * 64,
    }
    with package.window(
        scope=manifest["ownership"],
        cleanup=c2,
        start=lambda: None,
        stop=lambda: None,
        stack_startup=True,
    ):
        pass
    assert package.snapshot()["startups"] == 2

    # Stack startup 3 rejected
    c3 = {
        "registration_id": "s3",
        "scope": manifest["ownership"],
        "deadline": (NOW + timedelta(minutes=10)).isoformat(),
        "proof_digest": "f" * 64,
    }
    with (
        pytest.raises(ValueError, match="LIVE_STARTUP_CAP"),
        package.window(
            scope=manifest["ownership"],
            cleanup=c3,
            start=lambda: None,
            stop=lambda: None,
            stack_startup=True,
        ),
    ):
        pass


def test_package_v2_saved_branch_judge_binding_and_synthetic_origin(tmp_path):
    from knora.evaluation.contracts import digest_json
    from knora.evaluation.live_admission import LivePackage, slot_authority_pins

    manifest = package_manifest_v2(tmp_path)
    path = tmp_path / "package_v2_saved.sqlite"
    manifest["journal_path"] = str(path.resolve())
    package = LivePackage.initialize(manifest, path, clock=lambda: NOW)

    saved_capture = {
        "run_id": "run-001",
        "case_id": "004",
        "trace_id": "trace-001",
        "attempt": 2,
        "attempt_id": "run-001:004:2",
        "question": "Q4",
        "answer": "A4",
    }
    capture_digest = digest_json(saved_capture)

    # Bind judge_real with skipped parent qa_gold_v1_answer
    judge_policy = approval()
    judge_policy.update(approval_id=package.approval_id("judge_real"), max_attempts=12)
    judge_policy["scope"].update(purpose="scoring", input_digest=digest_json({"saved": 1}))

    inputs = {
        "input_digest": judge_policy["scope"]["input_digest"],
        **slot_authority_pins(package._manifest, "judge_real", judge_policy, {"saved": 1}),
        "authority": {"saved": 1},
        "identities": {
            "request_id": "judge_real",
            "batch_id": "batch-1",
            "dataset_digest": manifest["gold_v1"]["dataset_digest"],
            "selection_digest": "a" * 64,
            "run_id": "run-001",
            "case_id": "004",
            "trace_id": "trace-001",
            "capture_digest": capture_digest,
        },
        "ancestry": {"qa_gold_v1_answer": "skipped"},
        "saved_capture": saved_capture,
    }
    package.bind_slot("judge_real", judge_policy, inputs)
    assert package.snapshot()["slots"]["judge_real"]["status"] == "BOUND"

    # Complete judge_real so judge_synthetic can bind
    package.bind_execution("judge_real", inputs["identities"])
    cleanup = {
        "registration_id": "w1",
        "scope": manifest["ownership"],
        "deadline": (NOW + timedelta(minutes=10)).isoformat(),
        "proof_digest": "f" * 64,
    }
    with (
        package.window(
            scope=manifest["ownership"],
            cleanup=cleanup,
            start=lambda: None,
            stop=lambda: None,
            stack_startup=False,
        ),
        package.operation("judge_real"),
    ):
        package.record_result(
            "judge_real", {"capture": saved_capture, "identities": inputs["identities"]}
        )

    # Bind judge_synthetic with valid synthetic origin
    synth_policy = approval()
    synth_policy.update(approval_id=package.approval_id("judge_synthetic"), max_attempts=12)
    synth_policy["scope"].update(purpose="scoring", input_digest=digest_json({"synth": 1}))

    synth_inputs = {
        "input_digest": synth_policy["scope"]["input_digest"],
        **slot_authority_pins(package._manifest, "judge_synthetic", synth_policy, {"synth": 1}),
        "authority": {"synth": 1},
        "identities": {
            "request_id": "judge_synthetic",
            "batch_id": "batch-2",
            "dataset_digest": manifest["gold_v1"]["dataset_digest"],
            "selection_digest": "a" * 64,
            "run_id": "run-001",
            "case_id": "004",
            "trace_id": "trace-001",
            "capture_digest": capture_digest,
        },
        "ancestry": {"judge_real": digest_json(inputs)},
        "validation_origin": {
            "origin_type": "synthetic_control",
            "variant_id": "wrong-fact",
            "parent_capture_sha256": "a" * 64,
            "transformation_digest": "b" * 64,
        },
    }
    package.bind_slot("judge_synthetic", synth_policy, synth_inputs)
    assert package.snapshot()["slots"]["judge_synthetic"]["status"] == "BOUND"


def package_manifest_v3(tmp_path):
    from knora.evaluation.live_admission import _SLOTS_V2, reviewed_build_pins

    build = reviewed_build_pins()
    items = []
    # 6 real items
    for case_id in ("004", "005", "012", "014", "032", "045"):
        items.append(
            {
                "item_id": case_id,
                "slot": "judge_real",
                "cap": 12,
                "input_digest": "a" * 64,
                "native_identity": {
                    "case_id": case_id,
                    "run_id": f"run-{case_id}",
                    "attempt_id": f"att-{case_id}",
                    "attempt": 1,
                    "trace_id": f"tr-{case_id}",
                    "workspace_id": "w1",
                },
            }
        )
    # 4 synthetic controls
    for variant in ("wrong-fact", "off-topic", "unsupported", "missing-exception"):
        items.append(
            {
                "item_id": f"control-{variant}",
                "slot": "judge_synthetic",
                "cap": 12,
                "input_digest": "b" * 64,
                "native_identity": {
                    "case_id": f"control-{variant}",
                    "run_id": f"run-{variant}",
                    "attempt_id": f"att-{variant}",
                    "attempt": 1,
                    "trace_id": f"tr-{variant}",
                    "workspace_id": "w1",
                },
            }
        )
    # 2 refusals
    for refusal_id in ("053", "002"):
        items.append(
            {
                "item_id": f"refusal-{refusal_id}",
                "slot": "refusal_deterministic",
                "cap": 0,
                "input_digest": "c" * 64,
                "native_identity": {
                    "case_id": refusal_id,
                    "run_id": f"run-{refusal_id}",
                    "attempt_id": f"att-{refusal_id}",
                    "attempt": 1,
                    "trace_id": f"tr-{refusal_id}",
                    "workspace_id": "w1",
                },
            }
        )

    return {
        "manifest_version": 3,
        "package_id": "acceptance-v3-package",
        "journal_path": str((tmp_path / "package_v3.sqlite").resolve()),
        "code_sha": build["code_sha"],
        "reviewed_build": build,
        "gold_v1": {
            "dataset_id": "pdf-set-v3",
            "dataset_digest": "6" * 64,
            "version": 1,
            "cases": {"ANSWER": "answer", "REFUSAL": "refusal"},
            "sources": {
                "version-1": {"document_id": "document-1", "raw_sha256": "a" * 64},
                "version-2": {"document_id": "document-2", "raw_sha256": "b" * 64},
            },
        },
        "decision_reference": "issue158/evaluation-tools-acceptance-v3",
        "approved_by": "owner",
        "account_id": "a" * 32,
        "ownership": {"workspace_id": "w1", "resource_id": "owned-test-stack-v3"},
        "live_approved_at": NOW.isoformat(),
        "package_deadline": (NOW + timedelta(days=7)).isoformat(),
        "max_attempts": 121,
        "startup_cap": 0,
        "window_cap": 8,
        "slots": dict(_SLOTS_V2),
        "skipped_slots": ["corpus_prepare", "qa_gold_v1_answer"],
        "items": items,
    }


def test_package_v3_initialization_and_schema(tmp_path):
    import sqlite3
    from contextlib import closing
    from copy import deepcopy

    from knora.evaluation.live_admission import LivePackage

    manifest = package_manifest_v3(tmp_path)
    path = tmp_path / "package_v3.sqlite"
    package = LivePackage.initialize(manifest, path, clock=lambda: NOW)
    snap = package.snapshot()
    assert snap["attempts"] == 0
    assert snap["startups"] == 0
    assert snap["slots"]["corpus_prepare"]["status"] == "SKIPPED"
    assert snap["slots"]["judge_real"]["status"] == "WAITING"

    # Verify tables in journal
    with closing(sqlite3.connect(path)) as db:
        items = db.execute("SELECT item_id, slot_name, cap, attempts, status FROM items").fetchall()
        assert len(items) == 12
        assert db.execute("SELECT first_dispatch_at FROM package").fetchone()[0] is None
        assert db.execute("SELECT count(*) FROM proofs").fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM checkpoints").fetchone()[0] == 0

    # Table-driven rejection for V3
    for mod_key, mod_val in (
        ("max_attempts", 140),
        ("startup_cap", 3),
        ("window_cap", 9),
        ("manifest_version", 4),
        ("package_deadline", (NOW + timedelta(hours=48)).isoformat()),
    ):
        bad_manifest = deepcopy(manifest)
        bad_manifest[mod_key] = mod_val
        bad_manifest["journal_path"] = str((tmp_path / f"bad_{mod_key}.sqlite").resolve())
        with pytest.raises(ValueError, match="LIVE_PACKAGE_IDENTITY"):
            LivePackage.initialize(bad_manifest, bad_manifest["journal_path"], clock=lambda: NOW)


def test_package_v3_per_item_cap_and_counter_isolation(tmp_path):
    import sqlite3
    from contextlib import closing

    from knora.evaluation.contracts import digest_json
    from knora.evaluation.live_admission import LivePackage, slot_authority_pins

    manifest = package_manifest_v3(tmp_path)
    path = tmp_path / "package_v3.sqlite"
    package = LivePackage.initialize(manifest, path, clock=lambda: NOW)

    # Bind item 004
    item_policy = approval()
    item_policy.update(
        approval_id=package.approval_id("judge_real", item_id="004"),
        max_attempts=12,
        item_id="004",
    )
    item_policy["scope"].update(purpose="scoring", input_digest=digest_json({"case": "004"}))
    inputs = {
        "input_digest": item_policy["scope"]["input_digest"],
        **slot_authority_pins(package._manifest, "judge_real", item_policy, {"case": "004"}),
        "authority": {"case": "004"},
        "identities": {
            "request_id": "req-004",
            "batch_id": "batch-1",
            "dataset_digest": manifest["gold_v1"]["dataset_digest"],
            "selection_digest": "a" * 64,
            "run_id": "run-004",
            "case_id": "004",
            "trace_id": "trace-004",
            "capture_digest": "c" * 64,
        },
        "ancestry": {"qa_gold_v1_answer": "skipped"},
        "saved_capture": {
            "run_id": "run-004",
            "case_id": "004",
            "trace_id": "trace-004",
            "question": "q",
            "answer": "a",
            "reference_answer": "r",
            "generation_evidence": [{"alias": "E1", "content": "c"}],
            "evidence_status": "exact",
        },
    }
    inputs["identities"]["capture_digest"] = digest_json(inputs["saved_capture"])

    package.bind_item("judge_real", "004", item_policy, inputs)

    cleanup = {
        "registration_id": "w1",
        "scope": manifest["ownership"],
        "deadline": (NOW + timedelta(minutes=10)).isoformat(),
        "proof_digest": "f" * 64,
    }
    # Simulate reserving up to 12 attempts
    with (
        package.window(
            scope=manifest["ownership"],
            cleanup=cleanup,
            start=lambda: None,
            stop=lambda: None,
            stack_startup=False,
        ),
        package.operation("judge_real"),
        package._db() as db,
    ):
        for i in range(12):
            package.reserve(db, "judge_real", item_id="004")
            seq = i + 1
            db.execute(
                "INSERT INTO requests(approval_id,sequence,body_digest,endpoint,model,"
                "reserved_at,status,item_id) VALUES(?,?,?,?,?,?,?,?)",
                (
                    item_policy["approval_id"],
                    seq,
                    "d" * 64,
                    ENDPOINT,
                    MODEL,
                    NOW.isoformat(),
                    "COMPLETED",
                    "004",
                ),
            )
            db.execute(
                "UPDATE approvals SET attempts=? WHERE id=?", (seq, item_policy["approval_id"])
            )

        # 13th call on the same item MUST fail
        with pytest.raises(ValueError, match="LIVE_ITEM_CAP"):
            package.reserve(db, "judge_real", item_id="004")

    # Item attempts count is exactly 12
    with closing(sqlite3.connect(path)) as db:
        attempts = db.execute("SELECT attempts FROM items WHERE item_id='004'").fetchone()[0]
        assert attempts == 12


def test_package_v3_atomic_first_dispatch_anchoring(tmp_path):
    import sqlite3
    from contextlib import closing

    from knora.evaluation.contracts import digest_json
    from knora.evaluation.live_admission import LivePackage, slot_authority_pins

    manifest = package_manifest_v3(tmp_path)
    path = tmp_path / "package_v3.sqlite"
    package = LivePackage.initialize(manifest, path, clock=lambda: NOW)

    with closing(sqlite3.connect(path)) as db:
        assert db.execute("SELECT first_dispatch_at FROM package").fetchone()[0] is None

    # Bind and reserve 1 attempt
    item_policy = approval()
    item_policy.update(
        approval_id=package.approval_id("judge_real", item_id="004"),
        max_attempts=12,
        item_id="004",
    )
    item_policy["scope"].update(purpose="scoring", input_digest=digest_json({"case": "004"}))
    inputs = {
        "input_digest": item_policy["scope"]["input_digest"],
        **slot_authority_pins(package._manifest, "judge_real", item_policy, {"case": "004"}),
        "authority": {"case": "004"},
        "identities": {
            "request_id": "req-004",
            "batch_id": "batch-1",
            "dataset_digest": manifest["gold_v1"]["dataset_digest"],
            "selection_digest": "a" * 64,
            "run_id": "run-004",
            "case_id": "004",
            "trace_id": "trace-004",
            "capture_digest": "c" * 64,
        },
        "ancestry": {"qa_gold_v1_answer": "skipped"},
        "saved_capture": {
            "run_id": "run-004",
            "case_id": "004",
            "trace_id": "trace-004",
            "question": "q",
            "answer": "a",
            "reference_answer": "r",
            "generation_evidence": [{"alias": "E1", "content": "c"}],
            "evidence_status": "exact",
        },
    }
    inputs["identities"]["capture_digest"] = digest_json(inputs["saved_capture"])
    package.bind_item("judge_real", "004", item_policy, inputs)

    cleanup = {
        "registration_id": "w1",
        "scope": manifest["ownership"],
        "deadline": (NOW + timedelta(minutes=10)).isoformat(),
        "proof_digest": "f" * 64,
    }
    with (
        package.window(
            scope=manifest["ownership"],
            cleanup=cleanup,
            start=lambda: None,
            stop=lambda: None,
            stack_startup=False,
        ),
        package.operation("judge_real"),
        package._db() as db,
    ):
        package.reserve(db, "judge_real", item_id="004")
        db.execute(
            "INSERT INTO requests(approval_id,sequence,body_digest,endpoint,model,"
            "reserved_at,status,item_id) VALUES(?,?,?,?,?,?,?,?)",
            (
                item_policy["approval_id"],
                1,
                "d" * 64,
                ENDPOINT,
                MODEL,
                NOW.isoformat(),
                "COMPLETED",
                "004",
            ),
        )
        db.execute("UPDATE approvals SET attempts=1 WHERE id=?", (item_policy["approval_id"],))

    with closing(sqlite3.connect(path)) as db:
        first_dispatch = db.execute("SELECT first_dispatch_at FROM package").fetchone()[0]
        assert first_dispatch == NOW.isoformat()

    # Reopen package: first_dispatch_at survives
    LivePackage(manifest, path, clock=lambda: NOW + timedelta(hours=1))
    with closing(sqlite3.connect(path)) as db:
        assert db.execute("SELECT first_dispatch_at FROM package").fetchone()[0] == NOW.isoformat()


def test_package_v3_append_only_proofs_and_checkpoints(tmp_path):
    import sqlite3
    from contextlib import closing

    from knora.evaluation.live_admission import LivePackage

    manifest = package_manifest_v3(tmp_path)
    path = tmp_path / "package_v3.sqlite"
    package = LivePackage.initialize(manifest, path, clock=lambda: NOW)

    proof_id = package.record_proof(
        proof_type="workers_free_quota",
        account="a" * 32,
        proof_digest="e" * 64,
        details={"quota_remaining": 10000},
    )
    assert isinstance(proof_id, str) and len(proof_id) == 32

    checkpoint_id = package.record_checkpoint(
        item_id="004",
        next_ordinal=1,
        chain_digest="c" * 64,
        details={"step": "prepared"},
    )
    assert isinstance(checkpoint_id, str) and len(checkpoint_id) == 32

    with closing(sqlite3.connect(path)) as db:
        p_row = db.execute(
            "SELECT proof_type, account FROM proofs WHERE proof_id=?", (proof_id,)
        ).fetchone()
        assert p_row == ("workers_free_quota", "a" * 32)
        cp_row = db.execute(
            "SELECT next_ordinal, chain_digest FROM checkpoints WHERE checkpoint_id=?",
            (checkpoint_id,),
        ).fetchone()
        assert cp_row == (1, "c" * 64)
        item_status = db.execute("SELECT status FROM items WHERE item_id='004'").fetchone()[0]
        assert item_status == "CHECKPOINTED"


def test_package_v3_copied_or_tampered_journal_fails_closed(tmp_path):
    import shutil
    import sqlite3
    from contextlib import closing

    from knora.evaluation.live_admission import LivePackage

    manifest = package_manifest_v3(tmp_path)
    path = tmp_path / "package_v3.sqlite"
    LivePackage.initialize(manifest, path, clock=lambda: NOW)

    # 1. Copied journal with wrong file identity must fail
    copied_path = tmp_path / "copied.sqlite"
    shutil.copy2(path, copied_path)
    shutil.copy2(str(path) + ".stops", str(copied_path) + ".stops")
    copied_manifest = dict(manifest, journal_path=str(copied_path.resolve()))
    with pytest.raises(ValueError, match="LIVE_PACKAGE_IDENTITY"):
        LivePackage(copied_manifest, copied_path, clock=lambda: NOW)

    # 2. Tampered counter in items table must fail identity verification
    with closing(sqlite3.connect(path)) as db:
        # Illegally increment attempts in items table without matching requests
        db.execute("UPDATE items SET attempts=1 WHERE item_id='004'")
        db.commit()

    with pytest.raises(ValueError, match="LIVE_PACKAGE_COUNTER_MISMATCH"):
        LivePackage(manifest, path, clock=lambda: NOW)
