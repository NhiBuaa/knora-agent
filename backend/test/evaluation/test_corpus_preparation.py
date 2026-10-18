"""Corpus mutation authority is separate from evaluation execution."""

from contextlib import nullcontext
from datetime import timedelta

import pytest
from test_live_admission import NOW, approval

from knora.evaluation.contracts import digest_json
from knora.evaluation.live_admission import LiveAdmission, live_scope


def corpus_gate(tmp_path, *, clock=lambda: NOW, purpose="corpus_prepare"):
    tmp_path.mkdir(parents=True, exist_ok=True)
    payload = {"sources": ["synthetic-1", "synthetic-2"]}
    scope = live_scope(purpose, "corpus-test", "w1", payload)
    policy = {**approval(), "scope": scope}
    if purpose == "corpus_prepare":
        policy["providers"] = [
            {
                **policy["providers"][0],
                "endpoint": "https://api.cloudflare.com/client/v4/accounts/"
                + "a" * 32
                + "/ai/run/@cf/qwen/qwen3-embedding-0.6b",
                "model": "@cf/qwen/qwen3-embedding-0.6b",
                "max_output_tokens": 0,
                "request_digests": [digest_json({"documents": ["The sky is blue."]})],
            }
        ]
    return LiveAdmission(policy, tmp_path / "corpus.sqlite", clock=clock), scope, payload


def test_corpus_operation_is_durable_and_cannot_replay(tmp_path):
    admission, scope, payload = corpus_gate(tmp_path)
    with admission.corpus_operation(scope, payload):
        admission.check_mutation(scope)
    restored, _, _ = corpus_gate(tmp_path)
    with (
        pytest.raises(ValueError, match="CORPUS_OPERATION_EXISTS"),
        restored.corpus_operation(scope, payload),
    ):
        pytest.fail("a completed mutation must not replay")
    import sqlite3

    with sqlite3.connect(tmp_path / "corpus.sqlite") as db:
        row = db.execute("SELECT input_json,status FROM corpus_operations").fetchone()
    import json

    assert digest_json(json.loads(row[0])) == scope["input_digest"]
    assert row[1] == "COMPLETED"


def test_corpus_requires_exact_input_and_purpose(tmp_path):
    admission, scope, payload = corpus_gate(tmp_path)
    with (
        pytest.raises(ValueError, match="LIVE_SCOPE_MISMATCH"),
        admission.corpus_operation(scope, {**payload, "extra": True}),
    ):
        pytest.fail("changed plan must be denied")
    qa, qa_scope, _ = corpus_gate(tmp_path / "qa", purpose="qa")
    with pytest.raises(ValueError, match="CORPUS_AUTHORITY_REQUIRED"):
        qa.check_mutation(qa_scope)


def test_copied_context_cannot_mutate_after_operation_completes(tmp_path):
    from contextvars import copy_context

    admission, scope, payload = corpus_gate(tmp_path)
    with admission.corpus_operation(scope, payload):
        copied = copy_context()
    with pytest.raises(ValueError, match="CORPUS_OPERATION_REQUIRED"):
        copied.run(admission.check_mutation, scope)


def test_corpus_cannot_grant_generation_authority(tmp_path):
    _, scope, _ = corpus_gate(tmp_path)
    with pytest.raises(ValueError, match="LIVE_APPROVAL_INVALID"):
        LiveAdmission({**approval(), "scope": scope}, tmp_path / "bad.sqlite", clock=lambda: NOW)


@pytest.mark.parametrize("change", ["digests", "calls", "retries"])
def test_corpus_rejects_provider_envelope_drift(tmp_path, change):
    admission, scope, _ = corpus_gate(tmp_path)
    envelope = dict(
        request_digests=[digest_json({"documents": ["The sky is blue."]})],
        max_calls=2,
        max_retries=0,
    )
    envelope[
        {"digests": "request_digests", "calls": "max_calls", "retries": "max_retries"}[change]
    ] = {"digests": ["f" * 64], "calls": 3, "retries": 1}[change]
    with pytest.raises(ValueError, match="CORPUS_ENVELOPE_MISMATCH"):
        admission.check_corpus_envelope(scope, **envelope)
    assert admission.snapshot()["attempts"] == 0


def test_corpus_egress_requires_dispatch_validation(tmp_path):
    import httpx

    admission, scope, payload = corpus_gate(tmp_path)
    with (
        pytest.raises(ValueError, match="CORPUS_DISPATCH_REQUIRED"),
        admission.corpus_operation(scope, payload),
        admission.dispatch(scope),
        admission.sync_client(
            mock=httpx.MockTransport(lambda r: pytest.fail("unvalidated egress"))
        ) as client,
    ):
        client.post(
            "https://api.cloudflare.com/client/v4/accounts/"
            + "a" * 32
            + "/ai/run/@cf/qwen/qwen3-embedding-0.6b",
            json={"text": ["synthetic"]},
        )


@pytest.mark.parametrize("condition", ["stop", "expiry", "exhausted"])
def test_mutation_rechecks_stop_expiry_without_requiring_unused_http_budget(tmp_path, condition):
    now = [NOW]
    admission, scope, payload = corpus_gate(tmp_path, clock=lambda: now[0])
    expected = (
        nullcontext()
        if condition == "exhausted"
        else pytest.raises(ValueError, match="LIVE_STOPPED|LIVE_APPROVAL_EXPIRED")
    )
    with expected, admission.corpus_operation(scope, payload):
        if condition == "stop":
            admission.stop()
        elif condition == "expiry":
            now[0] += timedelta(minutes=6)
        else:
            with admission._db() as db:
                db.execute("UPDATE approvals SET attempts=2")
        admission.check_mutation(scope)


def test_stop_request_is_durable_while_mutation_holds_journal_lock(tmp_path):
    from threading import Event, Thread
    from time import monotonic, sleep

    admission, scope, payload = corpus_gate(tmp_path)
    finished, errors = Event(), []

    def stop():
        try:
            admission.stop()
        except BaseException as error:
            errors.append(error)
        finally:
            finished.set()

    with (
        pytest.raises(ValueError, match="LIVE_STOPPED"),
        admission.corpus_operation(scope, payload),
        admission.corpus_mutation(scope),
    ):
        thread = Thread(target=stop)
        thread.start()
        deadline = monotonic() + 1
        while not admission.snapshot()["stopped"] and monotonic() < deadline:
            sleep(0.01)
        assert admission.snapshot()["stopped"] is True
        assert not finished.is_set()
        admission.check_mutation(scope)
    assert finished.wait(6)
    thread.join()
    assert errors == []
    restored, _, _ = corpus_gate(tmp_path)
    assert restored.snapshot()["stopped"] is True
