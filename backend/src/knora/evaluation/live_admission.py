"""Trusted-host authority; nothing in this module registers or enables a live profile."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import importlib.metadata
import json
import re
import sqlite3
import subprocess
import sys
from contextlib import closing, contextmanager, nullcontext
from contextvars import ContextVar, copy_context
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from math import isfinite
from pathlib import Path
from threading import Thread
from uuid import uuid4

import httpx

from knora.evaluation.contracts import digest_json

_dispatch = ContextVar("evaluation_live_dispatch", default=None)
_corpus_operation = ContextVar("evaluation_corpus_operation", default=None)
_corpus_dispatch = ContextVar("evaluation_corpus_dispatch", default=None)
_HEX = re.compile(r"[a-f0-9]{64}\Z")
_SLOTS = {
    "corpus_prepare": 2,
    "qa_gold_v1_answer": 2,
    "qa_gold_v1_refusal": 2,
    "ragas_vi_draft": 1,
    "qa_ragas_answer": 2,
    "judge_gold_v1": 12,
    "judge_ragas": 12,
}
_slot_operation = ContextVar("evaluation_package_slot", default=None)
_SLOT_PARENTS = {
    "corpus_prepare": (),
    "qa_gold_v1_answer": ("corpus_prepare",),
    "qa_gold_v1_refusal": ("corpus_prepare",),
    "ragas_vi_draft": ("corpus_prepare",),
    "qa_ragas_answer": ("corpus_prepare", "ragas_vi_draft"),
    "judge_gold_v1": ("qa_gold_v1_answer",),
    "judge_ragas": ("qa_ragas_answer",),
}
_SLOTS_V2 = {
    "corpus_prepare": 6,
    "qa_gold_v1_answer": 12,
    "ragas_vi_draft": 1,
    "judge_real": 72,
    "judge_synthetic": 48,
    "refusal_deterministic": 0,
}
_SLOT_PARENTS_V2 = {
    "corpus_prepare": (),
    "qa_gold_v1_answer": ("corpus_prepare",),
    "ragas_vi_draft": ("corpus_prepare",),
    "judge_real": ("qa_gold_v1_answer",),
    "judge_synthetic": ("judge_real",),
    "refusal_deterministic": (),
}


def _journal_schema(db):
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
    db.execute(
        "CREATE TABLE IF NOT EXISTS responses (approval_id TEXT, sequence INTEGER, "
        "payload TEXT NOT NULL, PRIMARY KEY(approval_id,sequence))"
    )


def response_authority_pins(kind):
    """Pin the installed builders, templates, response schemas and selector source."""
    import knora.answering.evidence as evidence
    import knora.providers.cloudflare.embedding as embedding
    import knora.providers.openai_compatible.answer_blocks as answer_blocks
    import knora.providers.openai_compatible.generation as generation
    import knora.providers.structured_generation as structured

    modules = [
        Path(__file__),
        Path(generation.__file__),
        Path(answer_blocks.__file__),
        Path(structured.__file__),
        Path(embedding.__file__),
        Path(evidence.__file__),
    ]
    versions = {}
    if kind == "deepeval":
        import deepeval
        import evals.scorers.deepeval_cloudflare as scorer

        version = importlib.metadata.version("deepeval")
        if version != "4.2.8":
            raise ValueError("LIVE_DEPENDENCY_DRIFT")
        versions["deepeval"] = version
        root = Path(deepeval.__file__).parent
        modules.append(Path(scorer.__file__))
        for directory in (
            "metrics/g_eval",
            "metrics/answer_relevancy",
            "metrics/faithfulness",
            "test_case",
            "models",
        ):
            modules.extend(sorted((root / directory).rglob("*.py")))
    elif kind != "qa":
        raise ValueError("LIVE_CHAIN_INVALID")
    return {
        "versions": versions,
        "source_digest": digest_json(
            [hashlib.sha256(p.read_text(encoding="utf-8").encode()).hexdigest() for p in modules]
        ),
    }


def reviewed_build_pins():
    """Host-derived revision and source pins, including an explicitly reviewed dirty build."""
    root = Path(__file__).resolve().parents[4]
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()
    extra_paths = [
        root / "evals/runners/ragas_review.py",
        root / "evals/runners/evaluation_review_packet.py",
        root / "evals/runners/run_deepeval_capture.py",
        root / "evals/runners/langfuse_bridge.py",
        root / "evals/scorers/deepeval_cloudflare.py",
    ]
    paths = sorted(
        {
            *root.joinpath("backend/src/knora").rglob("*.py"),
            *(p for p in extra_paths if p.is_file()),
        }
    )
    sources = {
        p.relative_to(root).as_posix(): hashlib.sha256(
            p.read_text(encoding="utf-8").encode()
        ).hexdigest()
        for p in paths
    }
    return {
        "code_sha": revision,
        "sources": sources,
        "qa": response_authority_pins("qa"),
        "deepeval": response_authority_pins("deepeval"),
        "ragas": sources["evals/runners/ragas_review.py"],
    }


def slot_authority_pins(manifest, slot, policy, authority):
    kind = (
        "qa"
        if slot.startswith("qa_") or slot in ("corpus_prepare", "refusal_deterministic")
        else "deepeval"
        if slot.startswith("judge_")
        else "ragas"
        if slot == "ragas_vi_draft"
        else "qa"
    )
    build = manifest["reviewed_build"]
    return {
        "source_digest": digest_json(manifest["gold_v1"]["sources"]),
        "configuration_digest": digest_json({"providers": policy["providers"], "input": authority}),
        "prompt_digest": digest_json({"kind": kind, "build": build[kind]}),
        "schema_digest": digest_json({"kind": kind, "sources": build["sources"]}),
    }


class LivePackage:
    """One explicitly initialized journal for the owner's seven-slot live decision."""

    @classmethod
    def initialize(cls, manifest, path, *, clock=lambda: datetime.now(UTC)):
        cls._validate_manifest(manifest, path)
        path = Path(path)
        if path.exists() or Path(str(path) + ".stops").exists():
            raise ValueError("LIVE_JOURNAL_EXISTS")
        # Exclusive creation prevents two initializers from replacing one another.
        with path.open("xb"):
            pass
        stops_path = Path(str(path) + ".stops")
        with stops_path.open("xb"):
            pass
        with closing(sqlite3.connect(stops_path)) as db, db:
            db.execute("CREATE TABLE stop_requests (approval_id TEXT PRIMARY KEY)")
        with closing(sqlite3.connect(path)) as db, db:
            db.execute("PRAGMA synchronous=FULL")
            _journal_schema(db)
            db.execute(
                "CREATE TABLE package (manifest TEXT NOT NULL, file_identity TEXT NOT NULL, "
                "attempts INTEGER NOT NULL DEFAULT 0, startups INTEGER NOT NULL DEFAULT 0, "
                "stopped INTEGER NOT NULL DEFAULT 0)"
            )
            db.execute(
                "INSERT INTO package(manifest,file_identity) VALUES(?,?)",
                (
                    digest_json(manifest),
                    cls._file_identity(path) + ":" + cls._file_identity(stops_path),
                ),
            )
            db.execute(
                "CREATE TABLE slots (name TEXT PRIMARY KEY, approval_id TEXT UNIQUE NOT NULL, "
                "cap INTEGER NOT NULL, input_json TEXT, policy_digest TEXT, status TEXT NOT NULL, "
                "operation_id TEXT, attempts INTEGER NOT NULL DEFAULT 0, "
                "execution_json TEXT, result_json TEXT)"
            )
            version = manifest.get("manifest_version", 1)
            slots_map = _SLOTS_V2 if version == 2 else _SLOTS
            skipped = set(manifest.get("skipped_slots", [])) if version == 2 else set()
            db.executemany(
                "INSERT INTO slots(name,approval_id,cap,status) VALUES(?,?,?,?)",
                [
                    (
                        name,
                        manifest["package_id"] + ":" + name,
                        cap,
                        "SKIPPED" if name in skipped else "WAITING",
                    )
                    for name, cap in slots_map.items()
                ],
            )
            db.execute(
                "CREATE TABLE startups (sequence INTEGER PRIMARY KEY, scope TEXT NOT NULL, "
                "cleanup TEXT NOT NULL, started_at TEXT NOT NULL, deadline TEXT NOT NULL, "
                "status TEXT NOT NULL)"
            )
        return cls(manifest, path, clock=clock)

    @staticmethod
    def _file_identity(path):
        stat = Path(path).stat()
        return f"{stat.st_dev}:{stat.st_ino}"

    @staticmethod
    def _validate_manifest(manifest, path):
        current = reviewed_build_pins()
        if (
            manifest.get("reviewed_build") != current
            or manifest.get("code_sha") != current["code_sha"]
        ):
            raise ValueError("LIVE_PACKAGE_BUILD")
        try:
            _require(Path(path).is_absolute())
            _require(str(Path(path).resolve()) == manifest["journal_path"])
            version = manifest.get("manifest_version", 1)
            _require(version in (1, 2) and type(version) is int)
            if version == 1:
                _require(manifest["max_attempts"] == 33 and type(manifest["max_attempts"]) is int)
                _require(manifest["startup_cap"] == 3 and type(manifest["startup_cap"]) is int)
                _require(manifest["slots"] == _SLOTS)
            else:
                _require(manifest["max_attempts"] == 139 and type(manifest["max_attempts"]) is int)
                _require(manifest["startup_cap"] == 2 and type(manifest["startup_cap"]) is int)
                _require(
                    manifest.get("window_cap", 8) == 8
                    and type(manifest.get("window_cap", 8)) is int
                )
                _require(manifest["slots"] == _SLOTS_V2)
                skipped = manifest.get("skipped_slots", [])
                _require(
                    isinstance(skipped, (list, tuple)) and all(s in _SLOTS_V2 for s in skipped)
                )

            _require(re.fullmatch(r"[a-f0-9]{40}", manifest["code_sha"]))
            _require(re.fullmatch(r"[a-f0-9]{32}", manifest["account_id"]))
            for key in ("package_id", "approved_by", "decision_reference"):
                _require(isinstance(manifest[key], str) and bool(manifest[key].strip()))
            _require(isinstance(manifest["ownership"], dict) and manifest["ownership"])
            _require(all(isinstance(v, str) and v.strip() for v in manifest["ownership"].values()))
            approved = datetime.fromisoformat(manifest["live_approved_at"])
            deadline = datetime.fromisoformat(manifest["package_deadline"])
            _require(approved.utcoffset() is not None and deadline.utcoffset() is not None)
            if version == 1:
                _require(deadline - approved == timedelta(hours=48))
            else:
                _require(deadline - approved == timedelta(days=7))
            gold = manifest["gold_v1"]
            _require(_HEX.fullmatch(gold["dataset_digest"]))
            _require(gold["version"] == 1 and gold["dataset_id"])
            if version == 1:
                _require(set(gold["cases"]) == {"ANSWER", "REFUSAL"})
                _require(all(isinstance(v, str) and v for v in gold["cases"].values()))
                _require(len(set(gold["cases"].values())) == 2)
                _require(gold["sources"])
            else:
                _require(isinstance(gold["sources"], dict) and 1 <= len(gold["sources"]) <= 6)
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("LIVE_PACKAGE_IDENTITY") from error

    def __init__(self, manifest, path, *, clock=lambda: datetime.now(UTC)):
        self._validate_manifest(manifest, path)
        self._manifest, self._path, self._clock = deepcopy(manifest), str(Path(path)), clock
        self._version = manifest.get("manifest_version", 1)
        self._window = None
        self._approved = datetime.fromisoformat(manifest["live_approved_at"])
        self._deadline = datetime.fromisoformat(manifest["package_deadline"])
        with self._db() as db:
            self._identity(db)

    @contextmanager
    def _db(self):
        if not Path(self._path).is_file() or not Path(self._path + ".stops").is_file():
            raise ValueError("LIVE_JOURNAL_MISSING")
        db = sqlite3.connect(Path(self._path).as_uri() + "?mode=rw", uri=True, timeout=5)
        try:
            db.execute("PRAGMA synchronous=FULL")
            with db:
                self._identity(db)
                yield db
        finally:
            db.close()

    def _identity(self, db):
        if db.in_transaction:
            return self._validate_identity(db)
        # All counters must be observed in one SQLite snapshot during concurrent commits.
        db.execute("BEGIN")
        try:
            self._validate_identity(db)
        finally:
            db.rollback()

    def _validate_identity(self, db):
        row = db.execute("SELECT manifest,file_identity FROM package").fetchall()
        if row != [
            (
                digest_json(self._manifest),
                self._file_identity(self._path) + ":" + self._file_identity(self._path + ".stops"),
            )
        ]:
            raise ValueError("LIVE_PACKAGE_IDENTITY")
        slots_map = _SLOTS_V2 if self._version == 2 else _SLOTS
        slots = db.execute("SELECT name,approval_id,cap FROM slots").fetchall()
        if set(slots) != {(s, self.approval_id(s), c) for s, c in slots_map.items()}:
            raise ValueError("LIVE_PACKAGE_IDENTITY")
        attempts, startups = db.execute("SELECT attempts,startups FROM package").fetchone()
        counts = db.execute("SELECT count(*),count(DISTINCT approval_id) FROM requests").fetchone()
        slot_total = db.execute("SELECT sum(attempts) FROM slots").fetchone()[0]
        approval_total = db.execute("SELECT coalesce(sum(attempts),0) FROM approvals").fetchone()[0]
        if attempts != counts[0] or attempts != slot_total or attempts != approval_total:
            raise ValueError("LIVE_PACKAGE_COUNTER_MISMATCH")
        if (
            self._version == 1
            and startups != db.execute("SELECT count(*) FROM startups").fetchone()[0]
        ):
            raise ValueError("LIVE_PACKAGE_COUNTER_MISMATCH")
        foreign = db.execute(
            "SELECT id FROM approvals WHERE id NOT IN (SELECT approval_id FROM slots)"
        ).fetchone()
        if foreign:
            raise ValueError("LIVE_PACKAGE_IDENTITY")
        for _slot, count, cap, policy_digest, approval_id in db.execute(
            "SELECT name,attempts,cap,policy_digest,approval_id FROM slots"
        ):
            row = db.execute(
                "SELECT digest,attempts,pending FROM approvals WHERE id=?", (approval_id,)
            ).fetchone()
            request_count, last = db.execute(
                "SELECT count(*),max(sequence) FROM requests WHERE approval_id=?", (approval_id,)
            ).fetchone()
            pending = db.execute(
                "SELECT sequence FROM requests WHERE approval_id=? AND status='PENDING'",
                (approval_id,),
            ).fetchall()
            if (
                count > cap
                or (row is None and (policy_digest is not None or count != 0))
                or (
                    row is not None
                    and (
                        row[0] != policy_digest
                        or row[1] != count
                        or row[2] != (pending[0][0] if len(pending) == 1 else None)
                    )
                )
                or len(pending) > 1
                or request_count != count
                or (last or 0) != count
            ):
                raise ValueError("LIVE_PACKAGE_COUNTER_MISMATCH")

    def approval_id(self, slot):
        slots_map = _SLOTS_V2 if self._version == 2 else _SLOTS
        if slot not in slots_map:
            raise ValueError("LIVE_SLOT_UNKNOWN")
        return self._manifest["package_id"] + ":" + slot

    def parents(self, slot):
        self.approval_id(slot)
        parents_map = _SLOT_PARENTS_V2 if self._version == 2 else _SLOT_PARENTS
        return parents_map[slot]

    def slot_binding(self, slot):
        self.approval_id(slot)
        with self._db() as db:
            self._identity(db)
            row = db.execute("SELECT input_json FROM slots WHERE name=?", (slot,)).fetchone()
            return json.loads(row[0]) if row[0] else None

    def slot_result(self, slot):
        self.approval_id(slot)
        with self._db() as db:
            row = db.execute(
                "SELECT status,result_json FROM slots WHERE name=?", (slot,)
            ).fetchone()
            if row[0] != "COMPLETED" or row[1] is None:
                raise ValueError("LIVE_SLOT_RESULT_REQUIRED")
            return json.loads(row[1])

    def record_result(self, slot, result):
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            self._check(db, window=True)
            row = db.execute(
                "SELECT status,operation_id,result_json FROM slots WHERE name=?", (slot,)
            ).fetchone()
            if (
                not row
                or row[0] != "STARTED"
                or _slot_operation.get() != (self, slot, row[1])
                or row[2] is not None
            ):
                raise ValueError("LIVE_SLOT_RESULT_IMMUTABLE")
            db.execute(
                "UPDATE slots SET result_json=? WHERE name=?",
                (json.dumps(result, sort_keys=True, allow_nan=False), slot),
            )

    def _check(self, db, *, window=False):
        if self._manifest["reviewed_build"] != reviewed_build_pins():
            raise ValueError("LIVE_PACKAGE_BUILD")
        self._identity(db)
        with closing(
            sqlite3.connect(Path(self._path + ".stops").as_uri() + "?mode=rw", uri=True)
        ) as stops:
            stopped = stops.execute("SELECT 1 FROM stop_requests LIMIT 1").fetchone()
        if stopped or db.execute("SELECT stopped FROM package").fetchone()[0]:
            raise ValueError("LIVE_PACKAGE_STOPPED")
        if not self._approved <= self._clock() < self._deadline:
            raise ValueError("LIVE_PACKAGE_EXPIRED")
        if db.execute("SELECT 1 FROM requests WHERE status='PENDING'").fetchone():
            raise ValueError("LIVE_REQUEST_PENDING")
        for slot, operation_id in db.execute(
            "SELECT name,operation_id FROM slots WHERE status='STARTED'"
        ):
            if _slot_operation.get() != (self, slot, operation_id):
                raise ValueError("LIVE_SLOT_NONREPLAYABLE")
        if window:
            active = db.execute(
                "SELECT deadline,status FROM startups WHERE sequence=?", (self._window,)
            ).fetchone()
            if (
                not active
                or active[1] != "STARTED"
                or self._clock() >= datetime.fromisoformat(active[0])
            ):
                raise ValueError("LIVE_STARTUP_REQUIRED")

    def snapshot(self):
        with self._db() as db:
            self._identity(db)
            attempts, startups, stopped = db.execute(
                "SELECT attempts,startups,stopped FROM package"
            ).fetchone()
            return dict(
                attempts=attempts,
                startups=startups,
                stopped=bool(stopped),
                slots={
                    name: dict(status=status, attempts=count)
                    for name, status, count in db.execute("SELECT name,status,attempts FROM slots")
                },
            )

    def bind_slot(self, slot, policy, inputs):
        if policy.get("approval_id") != self.approval_id(slot):
            raise ValueError("LIVE_SLOT_APPROVAL")
        if slot == "ragas_vi_draft":
            providers = policy.get("providers", [])
            endpoint = f"https://api.cloudflare.com/client/v4/accounts/{self._manifest['account_id']}/ai/v1/chat/completions"
            if len(providers) != 1 or any(
                p.get("endpoint") != endpoint
                or p.get("model") != "@cf/openai/gpt-oss-20b"
                or type(p.get("max_input_bytes")) is not int
                or not 0 < p["max_input_bytes"] <= 8192
                or type(p.get("max_output_tokens")) is not int
                or not 0 < p["max_output_tokens"] <= 2048
                for p in providers
            ):
                raise ValueError("LIVE_SLOT_PROVIDER")
        purpose = (
            "scoring"
            if slot.startswith("judge_")
            else "qa"
            if slot.startswith("qa_")
            else "proposals"
            if slot == "ragas_vi_draft"
            else "corpus_prepare"
        )
        slots_map = _SLOTS_V2 if self._version == 2 else _SLOTS
        slot_cap = slots_map[slot]
        attempts_valid = (
            (policy.get("max_attempts") == 0)
            if slot_cap == 0
            else (
                type(policy.get("max_attempts")) is int and 0 < policy["max_attempts"] <= slot_cap
            )
        )
        if (
            policy.get("account_id") != self._manifest["account_id"]
            or policy.get("scope", {}).get("purpose") != purpose
            or policy.get("scope", {}).get("workspace_id")
            != self._manifest["ownership"].get("workspace_id")
            or policy.get("approved_by") != self._manifest["approved_by"]
            or not attempts_valid
        ):
            raise ValueError("LIVE_SLOT_APPROVAL")
        observed = datetime.fromisoformat(policy["proof_observed_at"])
        deadline = datetime.fromisoformat(policy["deadline"])
        if (
            not self._approved
            <= observed
            <= self._clock()
            < deadline
            <= min(observed + timedelta(minutes=5), self._deadline)
        ):
            raise ValueError("LIVE_APPROVAL_EXPIRED")
        if not isinstance(inputs, dict) or not inputs:
            raise ValueError("LIVE_SLOT_INPUT")
        expected_keys = {
            "input_digest",
            "source_digest",
            "configuration_digest",
            "prompt_digest",
            "schema_digest",
            "identities",
            "ancestry",
            "authority",
        }
        extra_keys = set(inputs) - expected_keys
        if extra_keys and (
            self._version != 2 or not extra_keys.issubset({"saved_capture", "validation_origin"})
        ):
            raise ValueError("LIVE_SLOT_INPUT")
        if (
            not expected_keys.issubset(set(inputs))
            or inputs["input_digest"] != policy["scope"]["input_digest"]
            or any(
                not isinstance(inputs[k], str) or not _HEX.fullmatch(inputs[k])
                for k in ("source_digest", "configuration_digest", "prompt_digest", "schema_digest")
            )
            or not isinstance(inputs["identities"], dict)
            or not inputs["identities"]
            or any(not isinstance(v, str) or not v for v in inputs["identities"].values())
        ):
            raise ValueError("LIVE_SLOT_INPUT")
        required = {"request_id"}
        if slot.startswith("qa_"):
            required |= {"dataset_digest", "selection_digest", "binding_digest", "case_id"}
        elif slot.startswith("judge_"):
            required |= {
                "dataset_digest",
                "selection_digest",
                "run_id",
                "case_id",
                "trace_id",
                "capture_digest",
            }
        elif slot == "ragas_vi_draft":
            required |= {"dataset_id"}
        if not required.issubset(inputs["identities"]):
            raise ValueError("LIVE_SLOT_INPUT")
        for key, value in inputs["identities"].items():
            if key.endswith("_digest") and not _HEX.fullmatch(value):
                raise ValueError("LIVE_SLOT_INPUT")
        expected_pins = slot_authority_pins(self._manifest, slot, policy, inputs["authority"])
        if any(inputs[k] != v for k, v in expected_pins.items()):
            raise ValueError("LIVE_SLOT_AUTHORITY")
        if slot in {"qa_gold_v1_answer", "qa_gold_v1_refusal"}:
            role = "ANSWER" if slot.endswith("answer") else "REFUSAL"
            gold = self._manifest["gold_v1"]
            if self._version == 1 and (
                inputs["identities"]["case_id"] != gold["cases"][role]
                or inputs["identities"]["dataset_digest"] != gold["dataset_digest"]
            ):
                raise ValueError("LIVE_SLOT_CASE")
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            self._check(db)
            if db.execute("SELECT status FROM slots WHERE name=?", (slot,)).fetchone() != (
                "WAITING",
            ):
                raise ValueError("LIVE_SLOT_ALREADY_BOUND")
            parents = self.parents(slot)
            if set(inputs["ancestry"]) != set(parents):
                raise ValueError("LIVE_SLOT_ANCESTRY")
            for parent in parents:
                row = db.execute(
                    "SELECT status,input_json FROM slots WHERE name=?", (parent,)
                ).fetchone()
                if row[0] == "SKIPPED":
                    if inputs["ancestry"][parent] != "skipped" and not _HEX.fullmatch(
                        inputs["ancestry"][parent]
                    ):
                        raise ValueError("LIVE_SLOT_ANCESTRY")
                elif row[0] != "COMPLETED" or inputs["ancestry"][parent] != digest_json(
                    json.loads(row[1])
                ):
                    raise ValueError("LIVE_SLOT_ANCESTRY")
            if slot.startswith("judge_"):
                parent_status = db.execute(
                    "SELECT status FROM slots WHERE name=?", (parents[0],)
                ).fetchone()[0]
                if parent_status == "SKIPPED":
                    capture = inputs.get("saved_capture")
                    if not capture:
                        raise ValueError("LIVE_SLOT_ANCESTRY")
                    expected_digest = inputs.get("identities", {}).get("capture_digest")
                    if not expected_digest or digest_json(capture) != expected_digest:
                        raise ValueError("LIVE_SLOT_ANCESTRY")
                else:
                    result = self.slot_result(parents[0])
                    capture = result.get("capture")
                    expected = {
                        **result.get("identities", {}),
                        "capture_digest": digest_json(capture),
                    }
                    if not capture or any(
                        inputs["identities"].get(k) != expected.get(k)
                        for k in (
                            "dataset_digest",
                            "selection_digest",
                            "run_id",
                            "case_id",
                            "trace_id",
                            "capture_digest",
                        )
                    ):
                        raise ValueError("LIVE_SLOT_ANCESTRY")
            if slot == "judge_synthetic":
                validation_origin = inputs.get("validation_origin")
                if (
                    not isinstance(validation_origin, dict)
                    or validation_origin.get("origin_type") != "synthetic_control"
                    or validation_origin.get("variant_id")
                    not in (
                        "wrong-fact",
                        "off-topic",
                        "unsupported",
                        "missing-exception",
                    )
                    or not _HEX.fullmatch(validation_origin.get("parent_capture_sha256", ""))
                    or not _HEX.fullmatch(validation_origin.get("transformation_digest", ""))
                ):
                    raise ValueError("LIVE_SYNTHETIC_ORIGIN_INVALID")
            for (saved,) in db.execute("SELECT input_json FROM slots WHERE input_json IS NOT NULL"):
                if json.loads(saved)["source_digest"] != inputs["source_digest"]:
                    raise ValueError("LIVE_SLOT_SOURCE_DRIFT")
            db.execute(
                "INSERT INTO approvals(id,digest,policy) VALUES(?,?,?)",
                (policy["approval_id"], digest_json(policy), json.dumps(policy, sort_keys=True)),
            )
            db.execute(
                "UPDATE slots SET input_json=?,policy_digest=?,status='BOUND' WHERE name=?",
                (json.dumps(inputs, sort_keys=True), digest_json(policy), slot),
            )

    def validate_authority(self, slot, authority):
        saved = self.slot_binding(slot)
        if saved is None or digest_json(saved["authority"]) != digest_json(authority):
            raise ValueError("LIVE_SLOT_AUTHORITY")

    def bind_execution(self, slot, identity):
        if not identity or any(not isinstance(v, str) or not v for v in identity.values()):
            raise ValueError("LIVE_EXECUTION_IDENTITY")
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            self._check(db)
            row = db.execute(
                "SELECT status,execution_json,input_json FROM slots WHERE name=?", (slot,)
            ).fetchone()
            if not row or row[0] != "BOUND" or row[1] is not None:
                raise ValueError("LIVE_EXECUTION_ALREADY_BOUND")
            expected = json.loads(row[2])["identities"]
            if any(identity.get(k) != v for k, v in expected.items()):
                raise ValueError("LIVE_EXECUTION_IDENTITY")
            required = {"request_id"}
            if slot.startswith("qa_"):
                required |= {"run_id", "case_id", "attempt_id"}
            elif slot.startswith("judge_"):
                required |= {"run_id", "case_id", "batch_id"}
            elif slot == "ragas_vi_draft":
                required |= {"dataset_id", "batch_id"}
            if not required.issubset(identity):
                raise ValueError("LIVE_EXECUTION_IDENTITY")
            db.execute(
                "UPDATE slots SET execution_json=? WHERE name=?",
                (json.dumps(identity, sort_keys=True), slot),
            )

    @contextmanager
    def window(self, *, scope, cleanup, start, stop, stack_startup=None):
        deadline = datetime.fromisoformat(cleanup["deadline"])
        max_duration = timedelta(minutes=60 if self._version == 2 else 15)
        if (
            scope != self._manifest["ownership"]
            or cleanup.get("scope") != scope
            or not isinstance(cleanup.get("registration_id"), str)
            or not cleanup["registration_id"]
            or not _HEX.fullmatch(cleanup.get("proof_digest", ""))
            or not self._clock() < deadline <= min(self._clock() + max_duration, self._deadline)
        ):
            raise ValueError("LIVE_CLEANUP_UNPROVEN")
        is_stack = (
            True
            if self._version == 1
            else (stack_startup if stack_startup is not None else scope.get("runtime_stack", False))
        )
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            self._check(db)
            total_windows = db.execute("SELECT count(*) FROM startups").fetchone()[0]
            max_windows = self._manifest.get("window_cap", 8) if self._version == 2 else 3
            if total_windows >= max_windows:
                raise ValueError("LIVE_WINDOW_CAP" if self._version == 2 else "LIVE_STARTUP_CAP")
            count = db.execute("SELECT startups FROM package").fetchone()[0]
            if not self._clock() < deadline <= min(self._clock() + max_duration, self._deadline):
                raise ValueError("LIVE_CLEANUP_UNPROVEN")
            if is_stack and count >= self._manifest["startup_cap"]:
                raise ValueError("LIVE_STARTUP_CAP")
            if total_windows == 0 and self._clock() > self._approved + timedelta(hours=24):
                raise ValueError("LIVE_FIRST_START_EXPIRED")
            if db.execute("SELECT 1 FROM startups WHERE status!='COMPLETED'").fetchone():
                raise ValueError("LIVE_STARTUP_INDETERMINATE")
            self._window = total_windows + 1
            if is_stack:
                db.execute("UPDATE package SET startups=startups+1")
            db.execute(
                "INSERT INTO startups VALUES(?,?,?,?,?,'STARTED')",
                (
                    self._window,
                    json.dumps(scope, sort_keys=True),
                    json.dumps(cleanup, sort_keys=True),
                    self._clock().isoformat(),
                    deadline.isoformat(),
                ),
            )
        try:
            with self._db() as db:
                self._check(db, window=True)
            if self._clock() >= deadline:
                raise ValueError("LIVE_CLEANUP_EXPIRED")
            start()
            yield self._window
            with self._db() as db:
                self._check(db, window=True)
        except BaseException:
            self.stop()
            raise
        finally:
            try:
                stop()
                if self._clock() >= deadline:
                    raise ValueError("LIVE_CLEANUP_EXPIRED")
                with self._db() as db:
                    db.execute(
                        "UPDATE startups SET status='COMPLETED' WHERE sequence=?", (self._window,)
                    )
            except BaseException:
                self.stop()
                raise
            finally:
                self._window = None

    def stop(self):
        with self._db():
            pass
        with (
            closing(
                sqlite3.connect(Path(self._path + ".stops").as_uri() + "?mode=rw", uri=True)
            ) as db,
            db,
        ):
            db.execute(
                "INSERT OR IGNORE INTO stop_requests VALUES(?)", (self._manifest["package_id"],)
            )
        with self._db() as db:
            db.execute("UPDATE package SET stopped=1")

    @contextmanager
    def operation(self, slot):
        operation_id = uuid4().hex
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            self._check(db, window=True)
            status = db.execute(
                "SELECT status,execution_json FROM slots WHERE name=?", (slot,)
            ).fetchone()
            if status is None or status[0] != "BOUND":
                raise ValueError("LIVE_SLOT_NONREPLAYABLE")
            if status[1] is None:
                raise ValueError("LIVE_EXECUTION_REQUIRED")
            db.execute(
                "UPDATE slots SET status='STARTED',operation_id=? WHERE name=?",
                (operation_id, slot),
            )
        token = _slot_operation.set((self, slot, operation_id))
        try:
            yield
            with self._db() as db:
                db.execute("BEGIN IMMEDIATE")
                self._check(db, window=True)
                db.execute(
                    "UPDATE slots SET status='COMPLETED' WHERE name=? AND operation_id=?",
                    (slot, operation_id),
                )
        except BaseException:
            self.stop()
            raise
        finally:
            _slot_operation.reset(token)

    def reserve(self, db, slot):
        self._check(db, window=True)
        context = _slot_operation.get()
        row = db.execute(
            "SELECT status,operation_id,attempts,cap FROM slots WHERE name=?", (slot,)
        ).fetchone()
        if not row or context != (self, slot, row[1]) or row[0] != "STARTED":
            raise ValueError("LIVE_SLOT_NONREPLAYABLE")
        if (
            row[2] >= row[3]
            or db.execute("SELECT attempts FROM package").fetchone()[0]
            >= self._manifest["max_attempts"]
        ):
            raise ValueError("LIVE_PACKAGE_CAP")
        db.execute("UPDATE package SET attempts=attempts+1")
        db.execute("UPDATE slots SET attempts=attempts+1 WHERE name=?", (slot,))

    def valid_until(self):
        with self._db() as db:
            row = db.execute(
                "SELECT deadline,status FROM startups WHERE sequence=?", (self._window,)
            ).fetchone()
            if row is None or row[1] != "STARTED":
                raise ValueError("LIVE_STARTUP_REQUIRED")
            return min(self._deadline, datetime.fromisoformat(row[0]))


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

    def __init__(
        self,
        approval: dict,
        path: Path,
        *,
        clock=lambda: datetime.now(UTC),
        package=None,
        slot=None,
        response_inputs=None,
        qa_store=None,
    ):
        self._policy = deepcopy(approval)
        self._clock, self._path = clock, str(path)
        self._package, self._slot = package, slot
        self._response_inputs, self._qa_store = deepcopy(response_inputs), qa_store
        self._chain = self._policy.get("response_chain")
        self._qa_evidence = None
        self._execution = None
        if package is not None:
            if str(Path(path).resolve()) != package._manifest["journal_path"] or approval.get(
                "approval_id"
            ) != package.approval_id(slot):
                raise ValueError("LIVE_PACKAGE_IDENTITY")
            with package._db() as db:
                package._identity(db)
                if db.execute(
                    "SELECT policy_digest FROM slots WHERE name=?", (slot,)
                ).fetchone() != (digest_json(approval),):
                    raise ValueError("LIVE_SLOT_APPROVAL")
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
                _require(isinstance(provider["request_digests"], list))
                _require(bool(provider["request_digests"]) != bool(self._chain))
                _require(all(_HEX.fullmatch(v) for v in provider["request_digests"]))
            if self._chain:
                _require(scope["purpose"] in {"qa", "scoring"})
                _require(set(self._chain) == {"kind", "input_digest", "pins"})
                _require(self._chain["kind"] == ("qa" if scope["purpose"] == "qa" else "deepeval"))
                _require(self._chain["input_digest"] == digest_json(response_inputs))
                _require(self._chain["pins"] == response_authority_pins(self._chain["kind"]))
                if scope["purpose"] == "scoring":
                    _require(digest_json(response_inputs) == scope["input_digest"])
                    cases = response_inputs["cases"]
                    _require(len(cases) == 1 and cases[0]["status"] == "READY")
                    self._capture = deepcopy(cases[0]["capture"])
                    _require(self._capture["case_id"] == cases[0]["case_id"])
                    for key in (
                        "run_id",
                        "case_id",
                        "trace_id",
                        "question",
                        "answer",
                        "reference_answer",
                    ):
                        _require(isinstance(self._capture[key], str) and bool(self._capture[key]))
                    _require(
                        self._capture["evidence_status"] == "exact"
                        and bool(self._capture["generation_evidence"])
                    )
                    _require(len(p["providers"]) == 1 and p["max_attempts"] <= 12)
                else:
                    self._validate_qa_inputs()
                for provider in p["providers"]:
                    _require(
                        provider["model"]
                        in {"@cf/openai/gpt-oss-20b", "@cf/qwen/qwen3-embedding-0.6b"}
                    )
                    _require(
                        provider["max_input_bytes"]
                        <= (8192 if provider["max_output_tokens"] else 4096)
                    )
                    _require(provider["max_output_tokens"] in {0, 2048})
                    _require(
                        provider["model"]
                        == (
                            "@cf/openai/gpt-oss-20b"
                            if provider["max_output_tokens"]
                            else "@cf/qwen/qwen3-embedding-0.6b"
                        )
                    )
        except (KeyError, TypeError, ValueError, AssertionError) as error:
            raise ValueError("LIVE_APPROVAL_INVALID") from error
        if package is not None and scope["purpose"] in {"qa", "scoring"}:
            _require(self._chain is not None)
            package.validate_authority(slot, response_inputs)
            identities = package.slot_binding(slot)["identities"]
            if self._chain["kind"] == "qa":
                selected = response_inputs["payload"]["selection"]
                expected = {
                    "dataset_digest": selected["reference"]["digest"],
                    "selection_digest": digest_json(selected),
                    "binding_digest": self._binding["approval"]["binding_digest"],
                    "case_id": self._case.case_id,
                }
                corpus = package.slot_result("corpus_prepare")
                ready = {
                    v: s for v, s in self._binding["sources"].items() if s["status"] == "READY"
                }
                if (
                    set(ready) != set(corpus["sources"])
                    or corpus["embedding_configuration_id"]
                    != self._binding["embedding_configuration_id"]
                ):
                    raise ValueError("LIVE_SLOT_ANCESTRY")
                for version, source in ready.items():
                    actual = corpus["sources"][version]
                    if source["raw_sha256"] != actual["raw_sha256"] or sorted(
                        response_inputs["chunk_digests"][c] for c in source["chunk_ids"]
                    ) != sorted(actual["chunk_digests"]):
                        raise ValueError("LIVE_SLOT_ANCESTRY")
                frozen = response_inputs["frozen"]
                gold = package._manifest["gold_v1"]
                if slot == "qa_ragas_answer":
                    result = package.slot_result("ragas_vi_draft")
                    proposal = package.slot_binding("ragas_vi_draft")
                    with package._db() as db:
                        execution = json.loads(
                            db.execute(
                                "SELECT execution_json FROM slots WHERE name='ragas_vi_draft'"
                            ).fetchone()[0]
                        )
                    original = result["cases"].get(self._case.case_id)
                    if (
                        original is None
                        or digest_json(original["case"]) != original["case_digest"]
                        or result["identities"] != execution
                        or execution["dataset_id"] != gold["dataset_id"]
                        or self._case.case_id != f"ragas-{execution['batch_id']}-01"
                        or result["source"] != proposal["authority"]["source"]
                        or frozen["reference"]["version"] != 2
                        or frozen["reference"]["dataset_id"] != gold["dataset_id"]
                        or self._case.expected != "ANSWER"
                    ):
                        raise ValueError("LIVE_SLOT_ANCESTRY")
                    # The owner may edit the imported draft. The case identity and saved
                    # generated case remain its provenance; existing freeze/binding
                    # approval validates the newly reviewed digest independently.
                elif (
                    frozen["reference"]["version"] != 1
                    or frozen["reference"]["dataset_id"] != gold["dataset_id"]
                    or frozen["reference"]["digest"] != gold["dataset_digest"]
                    or self._case.expected != ("ANSWER" if slot.endswith("answer") else "REFUSAL")
                ):
                    raise ValueError("LIVE_SLOT_CASE")
            else:
                expected = {
                    "dataset_digest": response_inputs["dataset"]["digest"],
                    "selection_digest": response_inputs["selection_digest"],
                    "run_id": self._capture["run_id"],
                    "case_id": self._capture["case_id"],
                    "trace_id": self._capture["trace_id"],
                    "capture_digest": digest_json(self._capture),
                }
            if any(identities.get(k) != v for k, v in expected.items()):
                raise ValueError("LIVE_EXECUTION_IDENTITY")
        self._digest = digest_json(p)
        if package is not None:
            return
        with self._db() as db:
            if db.execute("SELECT 1 FROM sqlite_master WHERE name='package'").fetchone():
                raise ValueError("LIVE_PACKAGE_REQUIRED")
            _journal_schema(db)
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

    def _validate_qa_inputs(self):
        from knora.answering.stores import RetrievalConfiguration
        from knora.evaluation.contracts import DatasetSelection, FrozenDataset, canonical_json
        from knora.evaluation.pdf_runtime import validate_pdf_binding
        from knora.providers.embedding import EmbeddingConfiguration
        from knora.providers.openai_compatible.generation import CLOUDFLARE_PROMPT_VERSION

        inputs = self._response_inputs
        _require(digest_json(inputs["payload"]) == self._policy["scope"]["input_digest"])
        frozen = FrozenDataset.from_json(canonical_json(inputs["frozen"]))
        selection = DatasetSelection.from_json(
            canonical_json(inputs["payload"]["selection"]), frozen
        )
        _require(len(selection.selected_case_ids) == 1 and not selection.context_only_case_ids)
        self._case = next(
            c for c in frozen.gold.cases if c.case_id == selection.selected_case_ids[0]
        )
        _require(not self._case.context_dependencies)
        self._binding = inputs["payload"]["binding"]
        validate_pdf_binding(frozen, self._binding)
        self._retrieval = RetrievalConfiguration(**inputs["retrieval_configuration"])
        _require(self._retrieval.id == self._binding["retrieval_configuration_id"])
        _require(self._binding["candidate_budget"] == self._retrieval.candidate_k)
        _require(
            self._binding["embedding_configuration_id"]
            == EmbeddingConfiguration.cloudflare_qwen3_06b().id
        )
        _require(
            self._binding["generation"]
            == {
                "provider": "cloudflare-workers-ai",
                "model": "@cf/openai/gpt-oss-20b",
                "prompt_version": CLOUDFLARE_PROMPT_VERSION,
            }
        )
        _require(self._qa_store is not None and self._policy["max_attempts"] <= 2)
        _require(
            set(inputs["chunk_digests"])
            == {
                c
                for s in self._binding["sources"].values()
                if s["status"] == "READY"
                for c in s["chunk_ids"]
            }
        )
        _require(all(_HEX.fullmatch(d) for d in inputs["chunk_digests"].values()))

    def _saved_responses(self):
        with self._db() as db:
            return [
                json.loads(row[0])
                for row in db.execute(
                    "SELECT payload FROM responses WHERE approval_id=? ORDER BY sequence",
                    (self._policy["approval_id"],),
                )
            ]

    def _expected_request(self):
        if self._chain["pins"] != response_authority_pins(self._chain["kind"]):
            raise ValueError("LIVE_AUTHORITY_DRIFT")
        responses = self._saved_responses()
        if self._chain["kind"] == "deepeval":
            from evals.scorers.deepeval_cloudflare import next_capture_request

            capture = {
                **self._capture,
                "data_classification": self._policy["classification"],
                "egress_approved": True,
            }
            return next_capture_request(
                capture,
                [r["choices"][0]["message"]["content"] for r in responses],
                model=self._policy["providers"][0]["model"],
                max_tokens=2048,
            )
        return self._qa_request(responses), None

    def _qa_request(self, responses):
        import unicodedata

        from knora.answering.evidence import select_evidence
        from knora.answering.stores import RetrievalResult
        from knora.providers.cloudflare.embedding import QUERY_INSTRUCTION
        from knora.providers.embedding import EmbeddingConfiguration
        from knora.providers.generation import GenerationEvidence
        from knora.providers.openai_compatible.answer_blocks import ANSWER_BLOCK_SCHEMA
        from knora.providers.openai_compatible.generation import CLOUDFLARE_SYSTEM_PROMPT
        from knora.providers.structured_generation import user_message

        if not responses:
            return {
                "queries": [unicodedata.normalize("NFKC", self._case.question)],
                "instruction": QUERY_INSTRUCTION,
            }
        if len(responses) != 1:
            raise ValueError("LIVE_CHAIN_COMPLETE")
        vector = responses[0]["result"]["data"][0]
        result = self._qa_store.retrieve_candidates(
            workspace_id=self._policy["scope"]["workspace_id"],
            query_text=self._case.question,
            query_vector=tuple(vector),
            embedding_configuration=EmbeddingConfiguration.cloudflare_qwen3_06b(),
            retrieval_configuration=self._retrieval,
        )
        candidates = result.candidates if isinstance(result, RetrievalResult) else tuple(result)
        _require(len(candidates) <= self._binding["candidate_budget"])
        _require(len({c.chunk_id for c in candidates}) == len(candidates))
        for c in candidates:
            source = self._binding["sources"].get(c.document_version_id)
            if (
                not source
                or source["status"] != "READY"
                or c.chunk_id not in source["chunk_ids"]
                or c.chunk_set_id != source["chunk_set_id"]
                or c.embedding_set_id != source["embedding_set_id"]
                or c.embedding_configuration_id != self._binding["embedding_configuration_id"]
                or hashlib.sha256(c.content.encode()).hexdigest()
                != self._response_inputs["chunk_digests"].get(c.chunk_id)
            ):
                raise ValueError("LIVE_EVIDENCE_DRIFT")
        selected = select_evidence(candidates, self._retrieval).selected
        if not selected:
            self._qa_evidence = []
            return None
        self._qa_evidence = [
            [f"E{i}", item.candidate.content] for i, item in enumerate(selected, 1)
        ]
        return {
            "model": "@cf/openai/gpt-oss-20b",
            "max_tokens": 2048,
            "messages": [
                {"role": "system", "content": CLOUDFLARE_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": user_message(
                        self._case.question,
                        tuple(GenerationEvidence(a, c) for a, c in self._qa_evidence),
                    ),
                },
            ],
            "response_format": {"type": "json_schema", "json_schema": ANSWER_BLOCK_SCHEMA},
        }

    def validate_capture(self, capture):
        if self._chain and (self._chain["kind"] != "deepeval" or capture != self._capture):
            raise ValueError("LIVE_CAPTURE_DRIFT")

    def bind_execution(self, identity):
        if self._chain:
            case_id = (
                self._case.case_id if self._chain["kind"] == "qa" else self._capture["case_id"]
            )
            if identity.get("case_id") != case_id or (
                self._chain["kind"] == "deepeval"
                and identity.get("run_id") != self._capture["run_id"]
            ):
                raise ValueError("LIVE_EXECUTION_IDENTITY")
        if self._package is not None:
            pins = self._package.slot_binding(self._slot)["identities"]
            if any(k in identity and identity[k] != v for k, v in pins.items()):
                raise ValueError("LIVE_EXECUTION_IDENTITY")
            identity = {**pins, **identity}
            self._package.bind_execution(self._slot, identity)
        self._execution = deepcopy(identity)

    def validate_scoring_result(self, result):
        if self._chain and any(
            m.get("status") != "scored" for m in result.get("metrics", {}).values()
        ):
            raise ValueError("LIVE_JUDGE_FAILED")
        if self._package is not None:
            self._package.record_result(self._slot, result)

    def validate_qa_observation(self, observation):
        if not self._chain:
            return
        if (
            self._chain["kind"] != "qa"
            or observation.get("status") != "OBSERVED"
            or observation.get("case_id") != self._case.case_id
        ):
            raise ValueError("LIVE_OBSERVATION_INVALID")
        responses = self._saved_responses()
        if len(responses) == 1 and self._qa_evidence is None:
            self._qa_request(responses)
        if observation.get("generation_evidence") != (self._qa_evidence or []):
            raise ValueError("LIVE_TRACE_EVIDENCE_DRIFT")
        if self._package is not None:
            if not self._execution or not observation.get("trace_id"):
                raise ValueError("LIVE_EXECUTION_IDENTITY")
            capture = None
            if observation.get("decision") == "ANSWER":
                generated = json.loads(responses[-1]["choices"][0]["message"]["content"])
                if generated.get("decision") != "ANSWER":
                    raise ValueError("LIVE_OBSERVATION_INVALID")
                if "answer" in generated:
                    expected_answer = generated["answer"]
                else:
                    from knora.providers.generation import GenerationEvidence
                    from knora.providers.openai_compatible.answer_blocks import compose_answer

                    evidence = tuple(GenerationEvidence(a, c) for a, c in (self._qa_evidence or []))
                    expected_answer, _ = compose_answer(generated, evidence)
                if observation.get("public_answer") != expected_answer:
                    raise ValueError("LIVE_OBSERVATION_INVALID")
                capture = {
                    "run_id": self._execution["run_id"],
                    "case_id": self._case.case_id,
                    "attempt": 1,
                    "trace_id": observation["trace_id"],
                    "question": self._case.question,
                    "answer": observation["public_answer"],
                    "reference_answer": self._case.reference_answer,
                    "generation_evidence": [
                        {"alias": a, "content": c} for a, c in self._qa_evidence
                    ],
                    "evidence_status": "exact",
                }
            self._package.record_result(
                self._slot,
                {
                    "identities": {**self._execution, "trace_id": observation["trace_id"]},
                    "capture": capture,
                },
            )

    def record_corpus_result(self, sources, embedding_configuration_id):
        if self._package is not None:
            self._package.record_result(
                self._slot,
                {"sources": sources, "embedding_configuration_id": embedding_configuration_id},
            )

    def validate_proposal_inputs(self, payload):
        if self._package is None:
            return
        self._package.validate_authority(self._slot, payload)
        if (
            not isinstance(payload, dict)
            or digest_json(payload) != self._policy["scope"]["input_digest"]
        ):
            raise ValueError("LIVE_SLOT_AUTHORITY")
        source = payload["source"]
        gold = self._package._manifest["gold_v1"]
        corpus = self._package.slot_result("corpus_prepare")["sources"]
        if (
            source["dataset_id"] != gold["dataset_id"]
            or not source["pdf_sources"]
            or set(corpus) != set(gold["sources"])
            or set(corpus) != {p["document_version_id"] for p in source["pdf_sources"]}
        ):
            raise ValueError("LIVE_SLOT_ANCESTRY")
        for pin in source["pdf_sources"]:
            version = pin["document_version_id"]
            expected = corpus[version]
            approved = gold["sources"].get(version)
            if (
                approved is None
                or any(
                    pin.get(k) != expected.get(k)
                    for k in (
                        "document_id",
                        "raw_sha256",
                        "extraction_snapshot_id",
                        "configuration_sha256",
                        "extraction_sha256",
                    )
                )
                or any(pin.get(k) != v for k, v in approved.items())
            ):
                raise ValueError("LIVE_SLOT_ANCESTRY")

    def record_proposal_result(self, result):
        if self._package is not None:
            self._package.record_result(
                self._slot,
                {
                    "identities": self._execution,
                    "source": result["source"],
                    "cases": {
                        d["case"]["case_id"]: {"case": d["case"], "case_digest": d["case_digest"]}
                        for d in result["drafts"]
                        if d["status"] == "READY_FOR_REVIEW"
                    },
                    "case_ids": [
                        d["case"]["case_id"]
                        for d in result["drafts"]
                        if d["status"] == "READY_FOR_REVIEW"
                    ],
                },
            )

    @contextmanager
    def _db(self, *, stop_requests=False):
        path = self._path + (".stops" if stop_requests else "")
        if self._package is not None:
            if not Path(path).is_file():
                raise ValueError("LIVE_JOURNAL_MISSING")
            db = sqlite3.connect(Path(path).as_uri() + "?mode=rw", uri=True, timeout=5)
        else:
            db = sqlite3.connect(path, timeout=5)
        try:
            db.execute("PRAGMA synchronous=FULL")
            with db:
                if self._package is not None and not stop_requests:
                    self._package._identity(db)
                yield db
        finally:
            db.close()

    def _state(self, db):
        if self._package is not None:
            self._package._identity(db)
        row = db.execute(
            "SELECT attempts,pending,stopped FROM approvals WHERE id=?",
            (self._policy["approval_id"],),
        ).fetchone()
        with self._db(stop_requests=True) as stops:
            requested = stops.execute(
                "SELECT 1 FROM stop_requests WHERE approval_id=?", (self._policy["approval_id"],)
            ).fetchone()
            if self._package is not None:
                requested = stops.execute("SELECT 1 FROM stop_requests LIMIT 1").fetchone()
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
        if (
            self._package is not None
            and _slot_operation.get() is not None
            and self._clock() >= self._package.valid_until()
        ):
            raise ValueError("LIVE_STARTUP_EXPIRED")

    def verify(self, scope):
        if scope != self._policy["scope"]:
            raise ValueError("LIVE_SCOPE_MISMATCH")
        self._check(self.snapshot())
        if self._package is not None:
            if scope["purpose"] == "proposals":
                self.validate_proposal_inputs(self._package.slot_binding(self._slot)["authority"])
            with self._db() as db:
                self._package._check(db)
                status = db.execute(
                    "SELECT status,operation_id FROM slots WHERE name=?", (self._slot,)
                ).fetchone()
                if status[0] != "BOUND" and (
                    status[0] != "STARTED"
                    or _slot_operation.get() != (self._package, self._slot, status[1])
                ):
                    raise ValueError("LIVE_SLOT_NONREPLAYABLE")
        return dict(
            approval_id=self._policy["approval_id"],
            approval_digest=self._digest,
            scope_digest=digest_json(scope),
        )

    def stop(self):
        if self._package is not None:
            self._package.stop()
            return
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
        deadline = min(self._deadline, self._observed + timedelta(minutes=5))
        return (
            min(deadline, self._package.valid_until())
            if self._package is not None and _slot_operation.get() is not None
            else deadline
        )

    def remaining_seconds(self):
        return max(0.0, (self.valid_until - self._clock()).total_seconds())

    def check_mutation(self, scope):
        with self._db() as db:
            self._check_corpus(db, scope)

    def check_corpus_progress(self, scope):
        """Observe the active derivation while its own provider request is pending."""
        with self._db() as db:
            self._check_corpus(db, scope, pending=False)

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

    def _check_corpus(self, db, scope, *, pending=True):
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
        self._check(self._state(db), capacity=False, pending=pending)

    @contextmanager
    def corpus_mutation(self, scope):
        """Serialize stop with a bounded host transaction, including its commit."""
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            self._check_corpus(db, scope)
            yield

    @contextmanager
    def corpus_operation(self, scope, payload):
        if self._package is not None:
            self._package.validate_authority(self._slot, payload)
            self.bind_execution({"request_id": scope["input_digest"]})
        operation = (
            self._package.operation(self._slot) if self._package is not None else nullcontext()
        )
        with operation, self._corpus_operation_impl(scope, payload):
            yield

    @contextmanager
    def _corpus_operation_impl(self, scope, payload):
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
    def operation(self):
        """Keep the package slot open through the caller's durable result commit."""
        with self._package.operation(self._slot) if self._package is not None else nullcontext():
            yield

    @contextmanager
    def dispatch(self, scope):
        self.verify(scope)
        token = _dispatch.set((self, deepcopy(scope)))
        try:
            with (
                self._package.operation(self._slot)
                if self._package is not None and _slot_operation.get() is None
                else nullcontext()
            ):
                yield
                self._check(self.snapshot(), capacity=False)
                if self._chain:
                    if self._chain["kind"] == "deepeval":
                        if self._expected_request()[0] is not None:
                            raise ValueError("LIVE_CHAIN_INCOMPLETE")
                    else:
                        responses = self._saved_responses()
                        if not responses or (
                            len(responses) == 1 and self._qa_request(responses) is not None
                        ):
                            raise ValueError("LIVE_CHAIN_INCOMPLETE")
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
            expected = self._expected_request()[0] if self._chain else None
            if (self._chain and payload != expected) or (
                not self._chain and digest_json(payload) not in provider["request_digests"]
            ):
                raise ValueError("LIVE_REQUEST_UNAPPROVED")
            if self._chain and (
                str(request.url).endswith("chat/completions") != ("messages" in expected)
            ):
                raise ValueError("LIVE_REQUEST_UNAPPROVED")
            if self._package is not None:
                if self._policy["scope"]["purpose"] == "qa" and str(request.url).endswith(
                    "chat/completions"
                ) != (state["attempts"] == 1):
                    raise ValueError("LIVE_QA_SEQUENCE")
                self._package.reserve(db, self._slot)
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
        try:
            sequence, provider = self._reserve(request, content)
        except BaseException:
            context = _dispatch.get()
            if context is not None and context[0] is self:
                self.stop()
            raise
        remaining = self.remaining_seconds()
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
                    self.valid_until.timestamp(),
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
            payload = json.loads(response.content, object_pairs_hook=_unique_object)
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
            if self._chain:
                self._validate_chain_response(payload)
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
                if self._chain:
                    db.execute(
                        "INSERT INTO responses VALUES(?,?,?)",
                        (
                            self._policy["approval_id"],
                            sequence,
                            json.dumps(payload, sort_keys=True),
                        ),
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

    def _validate_chain_response(self, payload):
        expected, schema = self._expected_request()
        if self._chain["kind"] == "deepeval":
            from evals.scorers.deepeval_cloudflare import next_capture_request

            content = payload["choices"][0]["message"]["content"]
            value = json.loads(content, object_pairs_hook=_unique_object)
            if (
                schema is None
                or schema.model_validate_json(content, strict=True).model_dump(exclude_unset=True)
                != value
            ):
                raise ValueError("LIVE_RESPONSE_SCHEMA_INVALID")
            capture = {
                **self._capture,
                "data_classification": self._policy["classification"],
                "egress_approved": True,
            }
            prior = [r["choices"][0]["message"]["content"] for r in self._saved_responses()]
            next_capture_request(
                capture,
                prior + [content],
                model=self._policy["providers"][0]["model"],
                max_tokens=2048,
            )
        elif "queries" in expected:
            result = payload["result"]
            data = result["data"]
            if (
                result["shape"] != [1, 1024]
                or len(data) != 1
                or len(data[0]) != 1024
                or any(type(v) not in (int, float) or not isfinite(v) for v in data[0])
            ):
                raise ValueError("LIVE_RESPONSE_SCHEMA_INVALID")
        else:
            from knora.answering.generation_validation import validate_generation
            from knora.providers.generation import GenerationEvidence, GenerationResult
            from knora.providers.openai_compatible.answer_blocks import (
                ANSWER_BLOCK_SCHEMA,
                compose_answer,
            )
            from knora.providers.structured_generation import STRUCTURED_RESULT_SCHEMA

            content = json.loads(
                payload["choices"][0]["message"]["content"], object_pairs_hook=_unique_object
            )
            available_ids = tuple(a for a, _ in self._qa_evidence)
            if "before" in content:
                if set(content) != set(ANSWER_BLOCK_SCHEMA["required"]):
                    raise ValueError("LIVE_RESPONSE_SCHEMA_INVALID")
                try:
                    evidence_tuples = tuple(GenerationEvidence(a, c) for a, c in self._qa_evidence)
                    answer, cited_ids = compose_answer(content, evidence_tuples)
                except Exception:
                    raise ValueError("LIVE_RESPONSE_SCHEMA_INVALID") from None
                result = GenerationResult(
                    decision=content["decision"],
                    answer=answer,
                    cited_evidence_ids=cited_ids,
                    refusal_reason=content["refusal_reason"],
                    provider="cloudflare-workers-ai",
                    model=payload["model"],
                    prompt_version=self._binding["generation"]["prompt_version"],
                )
            else:
                if (
                    set(content) != set(STRUCTURED_RESULT_SCHEMA["required"])
                    or not isinstance(content["cited_evidence_ids"], list)
                    or any(not isinstance(a, str) for a in content["cited_evidence_ids"])
                ):
                    raise ValueError("LIVE_RESPONSE_SCHEMA_INVALID")
                content["cited_evidence_ids"] = tuple(content["cited_evidence_ids"])
                result = GenerationResult(
                    **content,
                    provider="cloudflare-workers-ai",
                    model=payload["model"],
                    prompt_version=self._binding["generation"]["prompt_version"],
                )
            validate_generation(result, available_evidence_ids=available_ids)

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
