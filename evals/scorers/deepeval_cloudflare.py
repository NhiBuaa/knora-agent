"""Optional DeepEval scorer for an approved, captured Knora observation."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from math import isfinite
from pathlib import Path

import httpx
from evals.runners.evaluation import write_report_atomic
from pydantic import BaseModel

os.environ["DEEPEVAL_DISABLE_DOTENV"] = "1"
os.environ["DEEPEVAL_DISABLE_LEGACY_KEYFILE"] = "1"
os.environ["DEEPEVAL_TELEMETRY_OPT_OUT"] = "1"
os.environ["DEEPEVAL_UPDATE_WARNING_OPT_IN"] = "0"

from deepeval.metrics import AnswerRelevancyMetric, FaithfulnessMetric, GEval  # noqa: E402
from deepeval.models import DeepEvalBaseLLM  # noqa: E402
from deepeval.test_case import LLMTestCase, SingleTurnParams  # noqa: E402


class JudgeError(ValueError):
    pass


class AttemptLedger:
    def __init__(self, path: Path, *, run_id: str, deadline: datetime, cap: int) -> None:
        now = datetime.now(UTC)
        if (
            not run_id
            or deadline.tzinfo is None
            or not now < deadline <= now + timedelta(minutes=60)
            or not 1 <= cap <= 24
        ):
            raise JudgeError("ATTEMPT_POLICY_INVALID")
        self.path, self.run_id = path, run_id
        self.deadline, self.cap = deadline.astimezone(UTC).isoformat(), cap
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS runs (run_id TEXT PRIMARY KEY, "
                "deadline TEXT NOT NULL, cap INTEGER NOT NULL, attempts INTEGER NOT NULL)"
            )
            db.execute(
                "INSERT OR IGNORE INTO runs VALUES (?, ?, ?, 0)", (run_id, self.deadline, cap)
            )
            if db.execute(
                "SELECT deadline, cap FROM runs WHERE run_id=?", (run_id,)
            ).fetchone() != (self.deadline, cap):
                raise JudgeError("ATTEMPT_POLICY_MISMATCH")

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.execute("PRAGMA synchronous = FULL")
        try:
            with db:
                yield db
        finally:
            db.close()

    def reserve(self) -> int:
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            deadline, cap, attempts = db.execute(
                "SELECT deadline, cap, attempts FROM runs WHERE run_id=?", (self.run_id,)
            ).fetchone()
            if datetime.now(UTC) >= datetime.fromisoformat(deadline):
                raise JudgeError("ATTEMPT_DEADLINE_REACHED")
            if attempts >= cap:
                raise JudgeError("ATTEMPT_CAP_REACHED")
            db.execute("UPDATE runs SET attempts=attempts+1 WHERE run_id=?", (self.run_id,))
            return attempts + 1

    def count(self) -> int:
        with self._connect() as db:
            return db.execute(
                "SELECT attempts FROM runs WHERE run_id=?", (self.run_id,)
            ).fetchone()[0]


class CloudflareJudge(DeepEvalBaseLLM):
    def __init__(
        self,
        *,
        endpoint: str,
        token: str,
        model: str,
        ledger: AttemptLedger,
        client: httpx.Client | None = None,
    ) -> None:
        if (
            not re.fullmatch(
                r"https://api\.cloudflare\.com/client/v4/accounts/[a-f0-9]{32}/ai/v1/chat/completions",
                endpoint,
            )
            or not token
            or model != "@cf/openai/gpt-oss-20b"
        ):
            raise JudgeError("JUDGE_CONFIGURATION_INVALID")
        super().__init__(model=model)
        self.endpoint, self.token, self.ledger = endpoint, token, ledger
        self.client = client or httpx.Client(timeout=30, follow_redirects=False)

    def load_model(self):
        return "@cf/openai/gpt-oss-20b"

    def get_model_name(self) -> str:
        return self.model

    def generate(self, prompt: str, schema: type[BaseModel] | None = None):
        self.ledger.reserve()
        body = {
            "model": self.model,
            "temperature": 0,
            "messages": [{"role": "user", "content": prompt}],
        }
        if schema is not None:
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": schema.__name__,
                    "strict": True,
                    "schema": schema.model_json_schema(),
                },
            }
        try:
            response = self.client.post(
                self.endpoint,
                headers={"Authorization": f"Bearer {self.token}"},
                json=body,
                timeout=30,
                follow_redirects=False,
            )
            response.raise_for_status()
            choice = response.json()["choices"][0]
            if choice.get("finish_reason") != "stop":
                raise JudgeError("JUDGE_RESPONSE_TRUNCATED")
            content = choice["message"]["content"]
            if not isinstance(content, str):
                raise JudgeError("JUDGE_RESPONSE_INVALID")
            return schema.model_validate_json(content) if schema else content
        except JudgeError:
            raise
        except httpx.TimeoutException as error:
            raise JudgeError("JUDGE_TIMEOUT") from error
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as error:
            raise JudgeError("JUDGE_RESPONSE_INVALID") from error

    async def a_generate(self, prompt: str, schema: type[BaseModel] | None = None):
        return self.generate(prompt, schema)


def _scoring_input_sha256(capture: dict) -> str:
    return (
        "sha256:"
        + hashlib.sha256(
            json.dumps(
                {
                    key: capture.get(key)
                    for key in (
                        "question",
                        "answer",
                        "reference_answer",
                        "generation_evidence",
                        "evidence_status",
                    )
                },
                sort_keys=True,
                ensure_ascii=False,
            ).encode()
        ).hexdigest()
    )


def score_capture(capture: dict, judge, *, measure: bool = True) -> dict:
    if measure and (
        capture.get("data_classification") not in {"public", "synthetic"}
        or capture.get("egress_approved") is not True
    ):
        raise JudgeError("EGRESS_NOT_APPROVED")
    metrics = {
        name: {"status": "not_run", "score": None, "rationale": None}
        for name in ("correctness", "answer_relevancy", "faithfulness")
    }
    if not capture.get("reference_answer"):
        metrics["correctness"]["status"] = "not_applicable"
    if capture.get("evidence_status") != "exact" or not capture.get("generation_evidence"):
        metrics["faithfulness"]["status"] = "not_applicable"
    attempts_before = judge.ledger.count() if measure else 0
    if measure:
        if not isinstance(capture.get("trace_id"), str) or not capture["trace_id"]:
            raise JudgeError("CAPTURE_TRACE_MISMATCH")
        evidence = capture.get("generation_evidence", [])
        if metrics["faithfulness"]["status"] != "not_applicable" and (
            not isinstance(evidence, list)
            or any(not isinstance(item.get("content"), str) for item in evidence)
        ):
            raise JudgeError("CAPTURE_EVIDENCE_INVALID")
        case = LLMTestCase(
            input=capture["question"],
            actual_output=capture["answer"],
            expected_output=capture.get("reference_answer"),
            retrieval_context=[item["content"] for item in evidence]
            if metrics["faithfulness"]["status"] != "not_applicable"
            else None,
        )
        scorers = {
            "correctness": GEval(
                name="Correctness",
                criteria="Compare the actual answer's facts with the reference answer.",
                evaluation_params=[
                    SingleTurnParams.INPUT,
                    SingleTurnParams.ACTUAL_OUTPUT,
                    SingleTurnParams.EXPECTED_OUTPUT,
                ],
                model=judge,
                async_mode=False,
            ),
            "answer_relevancy": AnswerRelevancyMetric(
                model=judge, eval_mode="llm", async_mode=False
            ),
            "faithfulness": FaithfulnessMetric(model=judge, eval_mode="llm", async_mode=False),
        }
        for name, scorer in scorers.items():
            if metrics[name]["status"] == "not_applicable":
                continue
            try:
                scorer.measure(case)
                if (
                    isinstance(scorer.score, bool)
                    or not isinstance(scorer.score, (int, float))
                    or not isfinite(scorer.score)
                    or not 0 <= scorer.score <= 1
                ):
                    raise JudgeError("JUDGE_SCORE_INVALID")
                metrics[name] = {
                    "status": "scored",
                    "score": scorer.score,
                    "rationale": scorer.reason,
                }
            except JudgeError as error:
                metrics[name] = {
                    "status": "error",
                    "score": None,
                    "rationale": None,
                    "error": str(error),
                }
    return {
        "run_id": capture.get("run_id"),
        "case_id": capture.get("case_id"),
        "trace_id": capture.get("trace_id"),
        "attempt": capture.get("attempt"),
        "metrics": metrics,
        "tool": "deepeval-4.2.8",
        "method": "direct-measure-v1",
        "model": judge.get_model_name(),
        "input_status": capture.get("evidence_status"),
        "input_sha256": _scoring_input_sha256(capture),
        "http_attempts": judge.ledger.count() - attempts_before if measure else 0,
    }


def derive_captures(source: dict, cases: list | tuple, *, run_id: str) -> list[dict]:
    """Build scorer inputs solely from the bound dataset and persisted observations."""
    by_case = {case.id: case for case in cases}
    observations = source.get("observations")
    if (
        not run_id
        or not isinstance(observations, list)
        or len({item.get("case_id") for item in observations}) != len(observations)
        or set(by_case) != {item.get("case_id") for item in observations}
    ):
        raise JudgeError("CAPTURE_CASE_MISMATCH")
    captures = []
    for item in observations:
        if item.get("status") != "observed" or item.get("decision") != "ANSWER":
            continue
        case = by_case[item["case_id"]]
        if not isinstance(item.get("public_answer"), str):
            raise JudgeError("CAPTURE_TRACE_MISMATCH")
        evidence = (
            item.get("generation_evidence")
            if item.get("generation_evidence_status") == "exact"
            else []
        )
        if not isinstance(evidence, list):
            raise JudgeError("CAPTURE_EVIDENCE_INVALID")
        captures.append(
            {
                "run_id": run_id,
                "case_id": case.id,
                "attempt": 1,
                "trace_id": item["trace_id"],
                "question": case.question,
                "answer": item["public_answer"],
                "reference_answer": case.answer_expectations.reference_answer,
                "generation_evidence": evidence,
                "evidence_status": "exact" if evidence else "unavailable",
            }
        )
    return captures


def validate_free_preflight(record: dict, *, run_id: str, capture_sha256: str) -> str:
    """Require a recent human-reviewed same-account Free-plan/quota statement."""
    try:
        observed = datetime.fromisoformat(record["observed_at_utc"])
        started = datetime.fromisoformat(record["trial_started_at_utc"])
        reset = datetime.fromisoformat(record["quota_resets_at_utc"])
        age = datetime.now(UTC) - observed
        valid = (
            record["run_id"] == run_id
            and record["capture_sha256"] == capture_sha256
            and re.fullmatch(r"[a-f0-9]{32}", record["account_id"]) is not None
            and record["plan"] == "Workers Free"
            and record["approved_data_classification"] in {"public", "synthetic"}
            and record["zero_paid_budget_confirmed"] is True
            and type(record["used_neurons_today"]) is int
            and record["used_neurons_today"] >= 0
            and type(record["remaining_neurons_today"]) is int
            and record["remaining_neurons_today"] > 0
            and observed.tzinfo is not None
            and started.tzinfo is not None
            and reset.tzinfo is not None
            and reset > datetime.now(UTC)
            and isinstance(record["reviewed_by"], str)
            and bool(record["reviewed_by"])
            and started <= observed
            and datetime.now(UTC) < started + timedelta(minutes=60)
            and timedelta(0) <= age <= timedelta(minutes=15)
        )
    except (KeyError, TypeError, ValueError):
        valid = False
    if not valid:
        raise JudgeError("FREE_PREFLIGHT_UNVERIFIED")
    return record["account_id"]


def publish_supplement(path: Path, source: dict, captures: list[dict], results: list[dict]) -> dict:
    observed = {item["case_id"]: item for item in source.get("observations", [])}
    if any(
        item.get("case_id") not in observed
        or item.get("trace_id") != observed[item["case_id"]].get("trace_id")
        for item in captures
    ):
        raise JudgeError("CAPTURE_TRACE_MISMATCH")
    by_case = {item["case_id"]: item for item in results}
    if len(by_case) != len(results) or set(by_case) != {item["case_id"] for item in captures}:
        raise JudgeError("RESULT_CASE_MISMATCH")
    cases = []
    for capture in captures:
        result = by_case[capture["case_id"]]
        if any(result.get(key) != capture[key] for key in ("run_id", "attempt", "trace_id")):
            raise JudgeError("RESULT_IDENTITY_MISMATCH")
        if result.get("input_sha256") != _scoring_input_sha256(capture):
            raise JudgeError("RESULT_INPUT_MISMATCH")
        cases.append(result)
    report = {
        "schema_version": 1,
        "source_provenance": source.get("provenance"),
        "capture_sha256": "sha256:"
        + hashlib.sha256(
            json.dumps(captures, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest(),
        "run_ids": sorted({item["run_id"] for item in captures}),
        "cases": cases,
        "release_gate": False,
    }
    write_report_atomic(path, report)
    return report
