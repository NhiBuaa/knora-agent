"""Trusted-host authority; nothing in this module registers or enables a live profile."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import re
import sqlite3
import sys
from contextlib import contextmanager, nullcontext
from contextvars import ContextVar, copy_context
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Thread

import httpx

from knora.evaluation.contracts import digest_json

_dispatch = ContextVar("evaluation_live_dispatch", default=None)
_corpus_operation = ContextVar("evaluation_corpus_operation", default=None)
_corpus_dispatch = ContextVar("evaluation_corpus_dispatch", default=None)
_HEX = re.compile(r"[a-f0-9]{64}\Z")


def _require(condition):
    if not condition:
        raise ValueError("LIVE_APPROVAL_INVALID")


def _unique_object(pairs):
    result = dict(pairs)
    if len(result) != len(pairs):
        raise ValueError("LIVE_REQUEST_UNAPPROVED")
    return result


def live_scope(purpose, profile_id, workspace_id, payload):
    return dict(
        purpose=purpose,
        profile_id=profile_id,
        workspace_id=workspace_id,
        input_digest=digest_json(payload),
    )


def profile_authority(profile, scope):
    if profile.kind == "offline":
        return None
    if (
        profile.kind != "live"
        or profile.admission is None
        or getattr(profile, "provider_client", None) is None
        or getattr(profile.provider_client, "_knora_live_admission", None) is not profile.admission
    ):
        raise ValueError("LIVE_APPROVAL_REQUIRED")
    return profile.admission.verify(scope)


def profile_dispatch(profile, scope, provenance):
    if profile_authority(profile, scope) != provenance:
        raise ValueError("LIVE_APPROVAL_CHANGED")
    return nullcontext() if profile.kind == "offline" else profile.admission.dispatch(scope)


def admitted_binding(profile, workspace_id, selection, binding):
    if "live_admission" in binding:
        raise ValueError("LIVE_BINDING_RESERVED_KEY")
    scope = live_scope(
        "qa", profile.profile_id, workspace_id, dict(selection=selection, binding=binding)
    )
    provenance = profile_authority(profile, scope)
    return (
        binding
        if provenance is None
        else {**binding, "live_admission": dict(scope=scope, provenance=provenance)}
    )


def binding_dispatch(profile, binding):
    saved = binding.get("live_admission", {})
    return profile_dispatch(profile, saved.get("scope"), saved.get("provenance"))


class LiveAdmission:
    """An immutable host decision and a local, shared, fail-closed request journal.

    The host must inject these transports at the actual provider boundary. Exact
    canonical request digests prevent corpus drift from authorizing new egress.
    This is a trusted composition contract, not a sandbox for arbitrary callbacks.
    """

    def __init__(self, approval: dict, path: Path, *, clock=lambda: datetime.now(UTC)):
        self._policy = deepcopy(approval)
        self._clock, self._path = clock, str(path)
        try:
            p = self._policy
            self._observed = datetime.fromisoformat(p["proof_observed_at"])
            self._deadline = datetime.fromisoformat(p["deadline"])
            scope = p["scope"]
            _require(set(scope) == {"purpose", "profile_id", "workspace_id", "input_digest"})
            _require(scope["purpose"] in {"qa", "scoring", "proposals", "corpus_prepare"})
            _require(all(isinstance(v, str) and v for v in scope.values()))
            _require(_HEX.fullmatch(scope["input_digest"]))
            _require(
                all(
                    isinstance(p[k], str) and p[k].strip()
                    for k in ("approval_id", "approved_by", "decision_reference")
                )
            )
            _require(p["classification"] in {"public", "synthetic"})
            _require(p["egress_approved"] is True and p["plan"] == "Workers Free")
            _require(type(p["paid_budget_usd"]) in (int, float) and p["paid_budget_usd"] == 0)
            _require(re.fullmatch(r"[a-f0-9]{32}", p["account_id"]))
            _require(_HEX.fullmatch(p["proof_digest"]))
            _require(
                self._observed.utcoffset() is not None and self._deadline.utcoffset() is not None
            )
            _require(timedelta(0) < self._deadline - self._observed <= timedelta(hours=1))
            for key in ("max_attempts", "quota_remaining_neurons", "max_neurons_per_attempt"):
                _require(type(p[key]) is int and p[key] > 0)
            _require(
                p["quota_remaining_neurons"] >= p["max_attempts"] * p["max_neurons_per_attempt"]
            )
            _require(isinstance(p["providers"], list) and p["providers"])
            endpoints = set()
            for provider in p["providers"]:
                endpoint = provider["endpoint"]
                if scope["purpose"] == "corpus_prepare":
                    _require(endpoint.endswith("/ai/run/@cf/qwen/qwen3-embedding-0.6b"))
                    _require(provider["model"] == "@cf/qwen/qwen3-embedding-0.6b")
                base = f"https://api.cloudflare.com/client/v4/accounts/{p['account_id']}/ai/"
                _require(
                    endpoint
                    in {base + "v1/chat/completions", base + "run/@cf/qwen/qwen3-embedding-0.6b"}
                )
                _require(endpoint not in endpoints)
                endpoints.add(endpoint)
                _require(
                    isinstance(provider["model"], str) and provider["model"].startswith("@cf/")
                )
                _require(_HEX.fullmatch(provider["compatibility_digest"]))
                _require(
                    type(provider["max_input_bytes"]) is int
                    and 0 < provider["max_input_bytes"] <= 4_194_304
                )
                _require(
                    type(provider["max_output_tokens"]) is int
                    and provider["max_output_tokens"] >= 0
                )
                _require(
                    bool(provider["max_output_tokens"]) == endpoint.endswith("chat/completions")
                )
                _require(
                    isinstance(provider["request_digests"], list) and provider["request_digests"]
                )
                _require(all(_HEX.fullmatch(v) for v in provider["request_digests"]))
        except (KeyError, TypeError, ValueError, AssertionError) as error:
            raise ValueError("LIVE_APPROVAL_INVALID") from error
        self._digest = digest_json(p)
        with self._db() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS approvals (id TEXT PRIMARY KEY, digest TEXT NOT NULL, "
                "policy TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, pending INTEGER, "
                "stopped INTEGER NOT NULL DEFAULT 0)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS requests (approval_id TEXT, sequence INTEGER, "
                "body_digest TEXT NOT NULL, endpoint TEXT NOT NULL, model TEXT NOT NULL, "
                "reserved_at TEXT NOT NULL, finished_at TEXT, status TEXT NOT NULL, "
                "PRIMARY KEY(approval_id, sequence))"
            )
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT digest FROM approvals WHERE id=?", (p["approval_id"],)
            ).fetchone()
            if row and row[0] != self._digest:
                raise ValueError("LIVE_APPROVAL_CONFLICT")
            db.execute(
                "INSERT OR IGNORE INTO approvals(id,digest,policy) VALUES(?,?,?)",
                (p["approval_id"], self._digest, json.dumps(p, sort_keys=True)),
            )
        with self._db(stop_requests=True) as db:
            db.execute("CREATE TABLE IF NOT EXISTS stop_requests (approval_id TEXT PRIMARY KEY)")

    @contextmanager
    def _db(self, *, stop_requests=False):
        db = sqlite3.connect(self._path + (".stops" if stop_requests else ""), timeout=5)
        try:
            db.execute("PRAGMA synchronous=FULL")
            with db:
                yield db
        finally:
            db.close()

    def _state(self, db):
        row = db.execute(
            "SELECT attempts,pending,stopped FROM approvals WHERE id=?",
            (self._policy["approval_id"],),
        ).fetchone()
        with self._db(stop_requests=True) as stops:
            requested = stops.execute(
                "SELECT 1 FROM stop_requests WHERE approval_id=?", (self._policy["approval_id"],)
            ).fetchone()
        return dict(attempts=row[0], pending=row[1], stopped=bool(row[2] or requested))

    def snapshot(self):
        with self._db() as db:
            return self._state(db)

    def _check(self, state, *, capacity=True, pending=True):
        if state["stopped"]:
            raise ValueError("LIVE_STOPPED")
        if pending and state["pending"] is not None:
            raise ValueError("LIVE_REQUEST_PENDING")
        now = self._clock()
        if not self._observed <= now < min(self._deadline, self._observed + timedelta(minutes=5)):
            raise ValueError("LIVE_APPROVAL_EXPIRED")
        if capacity and state["attempts"] >= self._policy["max_attempts"]:
            raise ValueError("LIVE_ATTEMPT_CAP")

    def verify(self, scope):
        if scope != self._policy["scope"]:
            raise ValueError("LIVE_SCOPE_MISMATCH")
        self._check(self.snapshot())
        return dict(
            approval_id=self._policy["approval_id"],
            approval_digest=self._digest,
            scope_digest=digest_json(scope),
        )

    def stop(self):
        # Persist intent independently; serialize completion with the mutation transaction.
        with self._db(stop_requests=True) as db:
            db.execute(
                "INSERT OR IGNORE INTO stop_requests VALUES(?)", (self._policy["approval_id"],)
            )
        while True:
            try:
                with self._db() as db:
                    db.execute(
                        "UPDATE approvals SET stopped=1 WHERE id=?", (self._policy["approval_id"],)
                    )
                return
            except sqlite3.OperationalError as error:
                if getattr(error, "sqlite_errorcode", None) not in (
                    sqlite3.SQLITE_BUSY,
                    sqlite3.SQLITE_LOCKED,
                ):
                    raise

    @property
    def valid_until(self):
        return min(self._deadline, self._observed + timedelta(minutes=5))

    def remaining_seconds(self):
        return max(0.0, (self.valid_until - self._clock()).total_seconds())

    def check_mutation(self, scope):
        with self._db() as db:
            self._check_corpus(db, scope)

    def check_corpus_envelope(self, scope, *, request_digests, max_calls, max_retries):
        if scope.get("purpose") != "corpus_prepare":
            raise ValueError("CORPUS_AUTHORITY_REQUIRED")
        self.verify(scope)
        providers = self._policy["providers"]
        if (
            len(providers) != 1
            or not providers[0]["endpoint"].endswith("/ai/run/@cf/qwen/qwen3-embedding-0.6b")
            or set(providers[0]["request_digests"]) != set(request_digests)
            or self._policy["max_attempts"] != max_calls
            or max_retries != 0
        ):
            raise ValueError("CORPUS_ENVELOPE_MISMATCH")

    def _check_corpus(self, db, scope):
        if scope.get("purpose") != "corpus_prepare":
            raise ValueError("CORPUS_AUTHORITY_REQUIRED")
        if scope != self._policy["scope"]:
            raise ValueError("LIVE_SCOPE_MISMATCH")
        if _corpus_operation.get() != (self, scope):
            raise ValueError("CORPUS_OPERATION_REQUIRED")
        row = db.execute(
            "SELECT status FROM corpus_operations WHERE approval_id=?",
            (self._policy["approval_id"],),
        ).fetchone()
        if row != ("STARTED",):
            raise ValueError("CORPUS_OPERATION_REQUIRED")
        self._check(self._state(db), capacity=False)

    @contextmanager
    def corpus_mutation(self, scope):
        """Serialize stop with a bounded host transaction, including its commit."""
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            self._check_corpus(db, scope)
            yield

    @contextmanager
    def corpus_operation(self, scope, payload):
        if scope.get("purpose") != "corpus_prepare":
            raise ValueError("CORPUS_AUTHORITY_REQUIRED")
        if digest_json(payload) != scope.get("input_digest"):
            raise ValueError("LIVE_SCOPE_MISMATCH")
        self.verify(scope)
        approval_id = self._policy["approval_id"]
        with self._db() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS corpus_operations "
                "(approval_id TEXT PRIMARY KEY, input_json TEXT NOT NULL, "
                "started_at TEXT NOT NULL, finished_at TEXT, status TEXT NOT NULL)"
            )
            db.execute("BEGIN IMMEDIATE")
            self._check(self._state(db))
            if db.execute(
                "SELECT 1 FROM corpus_operations WHERE approval_id=?", (approval_id,)
            ).fetchone():
                raise ValueError("CORPUS_OPERATION_EXISTS")
            db.execute(
                "INSERT INTO corpus_operations VALUES(?,?,?,NULL,'STARTED')",
                (approval_id, json.dumps(payload, sort_keys=True), self._clock().isoformat()),
            )
        token = _corpus_operation.set((self, deepcopy(scope)))
        try:
            self.check_mutation(scope)
            yield
            with self._db() as db:
                db.execute("BEGIN IMMEDIATE")
                self._check_corpus(db, scope)
                db.execute(
                    "UPDATE corpus_operations SET status='COMPLETED',finished_at=? "
                    "WHERE approval_id=?",
                    (self._clock().isoformat(), approval_id),
                )
        except BaseException:
            self.stop()
            with self._db() as db:
                db.execute(
                    "UPDATE corpus_operations SET status='STOPPED',finished_at=? "
                    "WHERE approval_id=?",
                    (self._clock().isoformat(), approval_id),
                )
            raise
        finally:
            _corpus_operation.reset(token)

    def async_client(self, *, mock=None, **kwargs):
        client = httpx.AsyncClient(transport=self.async_transport(mock=mock), **kwargs)
        client._knora_live_admission = self
        return client

    def sync_client(self, *, mock=None, **kwargs):
        client = httpx.Client(transport=self.transport(mock=mock), **kwargs)
        client._knora_live_admission = self
        return client

    @contextmanager
    def dispatch(self, scope):
        self.verify(scope)
        token = _dispatch.set((self, deepcopy(scope)))
        try:
            yield
            self._check(self.snapshot(), capacity=False)
        except BaseException:
            self.stop()
            raise
        finally:
            _dispatch.reset(token)

    @contextmanager
    def corpus_dispatch(self, scope, validate):
        self.check_mutation(scope)
        token = _corpus_dispatch.set((self, validate))
        try:
            with self.dispatch(scope):
                yield
        finally:
            _corpus_dispatch.reset(token)

    def _reserve(self, request, content):
        context = _dispatch.get()
        if context is None or context[0] is not self:
            raise ValueError("LIVE_DISPATCH_REQUIRED")
        if context[1]["purpose"] == "corpus_prepare":
            self.check_mutation(context[1])
            validator = _corpus_dispatch.get()
            if validator is None or validator[0] is not self:
                raise ValueError("CORPUS_DISPATCH_REQUIRED")
            validator[1]()
        self.verify(context[1])
        provider = next(
            (p for p in self._policy["providers"] if p["endpoint"] == str(request.url)), None
        )
        if (
            provider is None
            or request.method != "POST"
            or len(content) > provider["max_input_bytes"]
        ):
            raise ValueError("LIVE_REQUEST_UNAPPROVED")
        try:
            payload = json.loads(content, object_pairs_hook=_unique_object)
            if digest_json(payload) not in provider["request_digests"]:
                raise ValueError("LIVE_REQUEST_UNAPPROVED")
            if str(request.url).endswith("chat/completions"):
                tokens = payload.get("max_tokens")
                if (
                    payload.get("model") != provider["model"]
                    or type(tokens) is not int
                    or not 0 < tokens <= provider["max_output_tokens"]
                    or payload.get("stream", False) is not False
                ):
                    raise ValueError("LIVE_REQUEST_UNAPPROVED")
        except (TypeError, json.JSONDecodeError) as error:
            raise ValueError("LIVE_REQUEST_UNAPPROVED") from error
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            state = self._state(db)
            self._check(state)
            sequence = state["attempts"] + 1
            db.execute(
                "UPDATE approvals SET attempts=?,pending=? WHERE id=?",
                (sequence, sequence, self._policy["approval_id"]),
            )
            db.execute(
                "INSERT INTO requests(approval_id,sequence,body_digest,endpoint,model,"
                "reserved_at,status) VALUES(?,?,?,?,?,?,?)",
                (
                    self._policy["approval_id"],
                    sequence,
                    hashlib.sha256(content).hexdigest(),
                    str(request.url),
                    provider["model"],
                    self._clock().isoformat(),
                    "PENDING",
                ),
            )
        return sequence, provider

    async def _send(self, request, mock):
        content = await request.aread()
        sequence, provider = self._reserve(request, content)
        remaining = (
            min(self._deadline, self._observed + timedelta(minutes=5)) - self._clock()
        ).total_seconds()
        timeout = request.extensions.get("timeout", {})
        request.extensions["timeout"] = {
            key: min(value, remaining) if value is not None else remaining
            for key, value in {
                "connect": remaining,
                "read": remaining,
                "write": remaining,
                "pool": remaining,
                **timeout,
            }.items()
        }

        async def exchange():
            if mock is None:
                self._check(self.snapshot(), capacity=False, pending=False)
                return await _provider_exchange(
                    request,
                    content,
                    remaining,
                    min(self._deadline, self._observed + timedelta(minutes=5)).timestamp(),
                )
            async with mock:
                response = await mock.handle_async_request(request)
                try:
                    data = bytearray()
                    async for chunk in response.aiter_bytes():
                        data.extend(chunk)
                        if len(data) > 1_048_576:
                            raise ValueError("LIVE_RESPONSE_LIMIT")
                    return httpx.Response(
                        response.status_code,
                        headers=response.headers,
                        content=bytes(data),
                        request=request,
                    )
                finally:
                    await response.aclose()

        async def monitor():
            while True:
                await asyncio.sleep(0.05)
                self._check(self.snapshot(), capacity=False, pending=False)

        operation = asyncio.create_task(exchange())
        watchdog = asyncio.create_task(monitor())
        failed = False
        try:
            done, _ = await asyncio.wait(
                (operation, watchdog), timeout=remaining, return_when=asyncio.FIRST_COMPLETED
            )
            if operation not in done:
                if watchdog in done:
                    watchdog.result()
                raise httpx.ReadTimeout("LIVE_DEADLINE", request=request)
            response = operation.result()
            self._check(self.snapshot(), capacity=False, pending=False)
            payload = response.json()
            if response.status_code != 200:
                raise ValueError("LIVE_PROVIDER_ERROR")
            if str(request.url).endswith("chat/completions"):
                choices = payload.get("choices", [])
                usage = payload.get("usage", {}).get("completion_tokens")
                if (
                    payload.get("model") != provider["model"]
                    or not choices
                    or any(c.get("finish_reason") != "stop" for c in choices)
                    or type(usage) is not int
                    or not 0 <= usage <= provider["max_output_tokens"]
                ):
                    raise ValueError("LIVE_PROVIDER_RESULT_INVALID")
            elif payload.get("success") is not True:
                raise ValueError("LIVE_PROVIDER_RESULT_INVALID")
            with self._db() as db:
                db.execute("BEGIN IMMEDIATE")
                self._check(self._state(db), capacity=False, pending=False)
                db.execute(
                    "UPDATE requests SET status='COMPLETED',finished_at=? "
                    "WHERE approval_id=? AND sequence=?",
                    (self._clock().isoformat(), self._policy["approval_id"], sequence),
                )
                db.execute(
                    "UPDATE approvals SET pending=NULL WHERE id=?", (self._policy["approval_id"],)
                )
            return response
        except BaseException:
            failed = True
            raise
        finally:
            for task in (operation, watchdog):
                task.cancel()
            try:
                await asyncio.gather(operation, watchdog, return_exceptions=True)
            finally:
                if failed:
                    # Reap the provider child/socket before a contended journal write.
                    self.stop()

    def transport(self, *, mock=None):
        if mock is not None and not isinstance(mock, httpx.MockTransport):
            raise ValueError("Only offline MockTransport injection is supported")
        admission = self

        class Transport(httpx.BaseTransport):
            def handle_request(self, request):
                # Real sockets live in a killable helper; cancelling a thread is insufficient.
                context, result = copy_context(), []

                def run():
                    try:
                        result.append(asyncio.run(admission._send(request, mock)))
                    except BaseException as error:
                        result.append(error)

                thread = Thread(target=lambda: context.run(run))
                thread.start()
                thread.join()
                if isinstance(result[0], BaseException):
                    raise result[0]
                return result[0]

        return Transport()

    def async_transport(self, *, mock=None):
        if mock is not None and not isinstance(mock, httpx.MockTransport):
            raise ValueError("Only offline MockTransport injection is supported")
        admission = self

        class Transport(httpx.AsyncBaseTransport):
            async def handle_async_request(self, request):
                return await admission._send(request, mock)

        return Transport()


def _helper_command():
    return (sys.executable, "-m", "knora.evaluation.provider_request")


async def _provider_exchange(request, content, remaining, deadline):
    process = await asyncio.create_subprocess_exec(
        *_helper_command(),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        data = json.dumps(
            dict(
                url=str(request.url),
                headers=dict(request.headers),
                content=base64.b64encode(content).decode(),
                timeout=remaining,
                deadline=deadline,
            )
        ).encode()
        output, _ = await process.communicate(data)
        if process.returncode:
            raise ValueError("LIVE_PROVIDER_TRANSPORT_ERROR")
        result = json.loads(output)
        return httpx.Response(
            result["status"], content=base64.b64decode(result["content"]), request=request
        )
    finally:
        if process.returncode is None:
            process.kill()
        await process.communicate()
