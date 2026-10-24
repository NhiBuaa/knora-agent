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


def judge_request_body(prompt, schema, *, model, max_tokens):
    body = {
        "model": model,
        "temperature": 0,
        "max_tokens": max_tokens,
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
    return body


def next_capture_request(capture, responses, *, model, max_tokens):
    """Replay pinned DeepEval builders without I/O, stopping before the next request."""

    class NextRequest(BaseException):
        pass

    class ReplayJudge(DeepEvalBaseLLM):
        def __init__(self):
            super().__init__(model=model)
            self.index = 0
            self.ledger = self
            self.max_output_tokens = max_tokens
            self.next = None

        def load_model(self):
            return model

        def get_model_name(self):
            return model

        def count(self):
            return self.index

        def generate(self, prompt, schema=None):
            if self.index == len(responses):
                self.next = (
                    judge_request_body(prompt, schema, model=model, max_tokens=max_tokens),
                    schema,
                )
                raise NextRequest()
            content = responses[self.index]
            self.index += 1
            if schema is None:
                raise JudgeError("JUDGE_SCHEMA_REQUIRED")
            parsed = schema.model_validate_json(content, strict=True)
            if parsed.model_dump(exclude_unset=True) != json.loads(content):
                raise JudgeError("JUDGE_RESPONSE_INVALID")
            return parsed

        async def a_generate(self, prompt, schema=None):
            return self.generate(prompt, schema)

    judge = ReplayJudge()
    try:
        result = score_capture(capture, judge)
    except NextRequest:
        return judge.next
    if judge.index != len(responses) or any(
        m["status"] != "scored" for m in result["metrics"].values()
    ):
        raise JudgeError("JUDGE_CHAIN_INVALID")
    return None, None


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
        max_output_tokens: int,
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
            or type(max_output_tokens) is not int
            or max_output_tokens < 1
        ):
            raise JudgeError("JUDGE_CONFIGURATION_INVALID")
        super().__init__(model=model)
        self.endpoint, self.token, self.ledger = endpoint, token, ledger
        self.max_output_tokens = max_output_tokens
        self.client = client or httpx.Client(timeout=30, follow_redirects=False)

    def load_model(self):
        return "@cf/openai/gpt-oss-20b"

    def get_model_name(self) -> str:
        return self.model

    def generate(self, prompt: str, schema: type[BaseModel] | None = None):
        self.ledger.reserve()
        body = judge_request_body(
            prompt, schema, model=self.model, max_tokens=self.max_output_tokens
        )
        try:
            timeout = self.client.timeout if self.client is not None else 30
            response = self.client.post(
                self.endpoint,
                headers={"Authorization": f"Bearer {self.token}"},
                json=body,
                timeout=timeout,
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


SYNTHETIC_CONTROLS = {
    "wrong-fact": {
        "parent_case_id": "pdf-v3-004",
        "answer": "Cảnh báo P1 phải báo trực trong 150 phút.",
        "target_rejected_metric": "correctness",
        "transformation_version": "v1",
        "description": "Thay đáp án bằng 'Cảnh báo P1 phải báo trực trong 150 phút.'",
    },
    "off-topic": {
        "parent_case_id": "pdf-v3-005",
        "answer": "Màu yêu thích của tôi là xanh dương. Tôi thích thời tiết đẹp.",
        "target_rejected_metric": "answer_relevancy",
        "transformation_version": "v1",
        "description": (
            "Thay đáp án bằng 'Màu yêu thích của tôi là xanh dương. Tôi thích thời tiết đẹp.'"
        ),
    },
    "unsupported": {
        "parent_case_id": "pdf-v3-014",
        "answer": (
            "Evidence means approval by the Tokyo office within 3 minutes. "
            "Citation means a mandatory payment of 500 USD to that office."
        ),
        "target_rejected_metric": "faithfulness",
        "transformation_version": "v1",
        "description": (
            "Thay đáp án bằng 'Evidence means approval by the Tokyo office within 3 minutes. "
            "Citation means a mandatory payment of 500 USD to that office.'; "
            "xác minh các claim này không có trong exact evidence."
        ),
    },
    "missing-exception": {
        "parent_case_id": "pdf-v3-012",
        "answer": "Bản nháp thường giữ 30 ngày. Hồ sơ tranh chấp không có quy định riêng.",
        "target_rejected_metric": "correctness",
        "transformation_version": "v1",
        "description": (
            "Thay đáp án bằng 'Bản nháp thường giữ 30 ngày. "
            "Hồ sơ tranh chấp không có quy định riêng.'; bỏ và phủ nhận ngoại lệ 90 ngày."
        ),
    },
}


def build_synthetic_control(
    parent_capture: dict, variant_id: str, parent_capture_bytes: bytes | None = None
) -> dict:
    from copy import deepcopy

    if variant_id not in SYNTHETIC_CONTROLS:
        raise JudgeError(f"UNKNOWN_SYNTHETIC_VARIANT: {variant_id}")
    spec = SYNTHETIC_CONTROLS[variant_id]
    if parent_capture.get("case_id") != spec["parent_case_id"]:
        raise JudgeError("PARENT_CASE_MISMATCH")
    if parent_capture_bytes is not None:
        parent_sha = "sha256:" + hashlib.sha256(parent_capture_bytes).hexdigest()
    else:
        parent_sha = (
            "sha256:"
            + hashlib.sha256(
                json.dumps(parent_capture, sort_keys=True, ensure_ascii=False).encode("utf-8")
            ).hexdigest()
        )
    answer_bytes = spec["answer"].encode("utf-8")
    transformation_digest = "sha256:" + hashlib.sha256(answer_bytes).hexdigest()
    validation_origin = {
        "validation_variant_id": variant_id,
        "parent_case_id": spec["parent_case_id"],
        "parent_capture_sha256": parent_sha,
        "transformation_version": spec["transformation_version"],
        "transformation_digest": transformation_digest,
        "target_rejected_metric": spec["target_rejected_metric"],
        "description": spec["description"],
    }
    control = dict(deepcopy(parent_capture))
    control["case_id"] = f"{spec['parent_case_id']}-ctrl-{variant_id}"
    control["answer"] = spec["answer"]
    control["validation_origin"] = validation_origin
    return control


def _scoring_input_sha256(capture: dict) -> str:
    payload = {
        key: capture.get(key)
        for key in (
            "question",
            "answer",
            "reference_answer",
            "generation_evidence",
            "evidence_status",
        )
    }
    if "validation_origin" in capture:
        payload["validation_origin"] = capture["validation_origin"]
    return (
        "sha256:"
        + hashlib.sha256(
            json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
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
    res = {
        "run_id": capture.get("run_id"),
        "case_id": capture.get("case_id"),
        "trace_id": capture.get("trace_id"),
        "attempt": capture.get("attempt"),
        "metrics": metrics,
        "tool": "deepeval-4.2.8",
        "method": "direct-measure-v1",
        "model": judge.get_model_name(),
        "requested_max_output_tokens": getattr(judge, "max_output_tokens", None),
        "input_status": capture.get("evidence_status"),
        "input_sha256": _scoring_input_sha256(capture),
        "http_attempts": judge.ledger.count() - attempts_before if measure else 0,
    }
    if "attempt_id" in capture:
        res["attempt_id"] = capture["attempt_id"]
    if "validation_origin" in capture:
        res["validation_origin"] = capture["validation_origin"]
    return res


def derive_captures(
    source: dict, cases: list | tuple, *, run_id: str, capture_format: str = "m3-native-v1"
) -> list[dict]:
    """Build scorer inputs solely from the bound dataset and persisted observations."""
    by_case = {getattr(c, "case_id", getattr(c, "id", None)): c for c in cases}
    observations = source.get("observations")
    if isinstance(observations, dict):
        observations = list(observations.values())
    if (
        not run_id
        or not isinstance(observations, list)
        or len({item.get("case_id") for item in observations}) != len(observations)
        or set(by_case) != {item.get("case_id") for item in observations}
    ):
        raise JudgeError("CAPTURE_CASE_MISMATCH")
    captures = []
    for item in observations:
        if item.get("status") not in {"observed", "OBSERVED"} or item.get("decision") != "ANSWER":
            continue
        case = by_case[item["case_id"]]
        if not isinstance(item.get("public_answer"), str):
            raise JudgeError("CAPTURE_TRACE_MISMATCH")
        raw_evidence = item.get("generation_evidence")
        if "generation_evidence_status" in item:
            evidence = (
                raw_evidence
                if item.get("generation_evidence_status") == "exact"
                and isinstance(raw_evidence, list)
                else []
            )
        elif isinstance(raw_evidence, list) and raw_evidence:
            evidence = raw_evidence
        else:
            evidence = []
        if not isinstance(evidence, list) or any(
            not isinstance(e, (dict, list, tuple))
            or (
                isinstance(e, dict)
                and (not isinstance(e.get("alias"), str) or not isinstance(e.get("content"), str))
            )
            or (
                isinstance(e, (list, tuple))
                and (len(e) != 2 or not isinstance(e[0], str) or not isinstance(e[1], str))
            )
            for e in evidence
        ):
            raise JudgeError("CAPTURE_EVIDENCE_INVALID")
        normalized_evidence = []
        for e in evidence:
            if isinstance(e, dict):
                normalized_evidence.append({"alias": e["alias"], "content": e["content"]})
            else:
                normalized_evidence.append({"alias": e[0], "content": e[1]})
        if hasattr(case, "answer_expectations"):
            ref_answer = case.answer_expectations.reference_answer
        elif hasattr(case, "reference_answer"):
            ref_answer = case.reference_answer
        elif isinstance(case, dict):
            ref_answer = case.get(
                "reference_answer", case.get("answer_expectations", {}).get("reference_answer")
            )
        else:
            ref_answer = None

        question = case.question if hasattr(case, "question") else case.get("question")
        attempt = item.get("attempt", 1)
        attempt_id = item.get("attempt_id") or f"{run_id}:{item['case_id']}:{attempt}"
        cap = {
            "run_id": run_id,
            "case_id": item["case_id"],
            "attempt": attempt,
            "attempt_id": attempt_id,
            "trace_id": item["trace_id"],
            "question": question,
            "answer": item["public_answer"],
            "reference_answer": ref_answer,
            "generation_evidence": normalized_evidence,
            "evidence_status": "exact" if normalized_evidence else "unavailable",
        }
        if "validation_origin" in item:
            cap["validation_origin"] = item["validation_origin"]
        if "workspace_id" in item:
            cap["workspace_id"] = item["workspace_id"]
        captures.append(cap)
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
            and type(record["max_output_tokens"]) is int
            and record["max_output_tokens"] > 0
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
    raw_obs = source.get("observations", [])
    observed = raw_obs if isinstance(raw_obs, dict) else {item["case_id"]: item for item in raw_obs}
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
        if (
            "attempt_id" in capture
            and result.get("attempt_id") is not None
            and result.get("attempt_id") != capture["attempt_id"]
        ):
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
