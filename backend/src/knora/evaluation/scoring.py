"""Supplement saved Knora captures; never prepares a runtime or re-answers a question."""

from __future__ import annotations

from asyncio import to_thread
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from math import isfinite
from typing import Literal
from uuid import uuid4

from knora.domain.errors import KnoraError
from knora.evaluation.access import authorize_evaluation
from knora.evaluation.contracts import digest_json

METRICS = ("correctness", "answer_relevancy", "faithfulness")


@dataclass(frozen=True)
class ScoringProfile:
    profile_id: str
    kind: Literal["offline", "live"]
    model: str
    prompt_version: str
    config: dict
    measure: Callable[[dict], dict]

    def provenance(self) -> dict:
        return {
            "profile_id": self.profile_id,
            "kind": self.kind,
            "model": self.model,
            "prompt_version": self.prompt_version,
            "config": deepcopy(self.config),
            "tool": "deepeval-4.2.8",
        }


def capture_saved_cases(runs, run, principal, case_ids: tuple[str, ...]) -> list[dict]:
    selection = run["selection"]
    if (
        not case_ids
        or len(case_ids) != len(set(case_ids))
        or not set(case_ids).issubset(selection["selected_case_ids"])
        or digest_json(selection) != run["selection_digest"]
    ):
        raise KnoraError("EVALUATION_SELECTION_INVALID")
    if selection["reference"]["format"] not in {"m3-native-v1", "pdf-gold-v1"}:
        return [
            {
                "case_id": case_id,
                "status": "UNAVAILABLE",
                "reason": "UNSUPPORTED_DATASET_MAPPING",
                "capture": None,
            }
            for case_id in case_ids
        ]
    gold = runs.saved_gold_cases(run, principal)
    result = []
    for case_id in case_ids:
        case = gold.get(case_id)
        observation = run["observations"].get(case_id, {})
        reason = None
        status = "UNAVAILABLE"
        capture = None
        if case is None:
            reason = "GOLD_CASE_UNAVAILABLE"
        elif case["expected"] == "REFUSAL":
            status, reason = "NOT_APPLICABLE", "REFUSAL_USES_DETERMINISTIC_CHECKS"
        elif observation.get("status") != "OBSERVED":
            reason = "OBSERVATION_" + observation.get("status", "UNAVAILABLE")
        elif observation.get("decision") != "ANSWER":
            status, reason = "NOT_APPLICABLE", "NO_ANSWER_TO_SCORE"
        elif not isinstance(observation.get("trace_id"), str) or not observation["trace_id"]:
            reason = "CAPTURE_TRACE_UNAVAILABLE"
        elif (
            not isinstance(observation.get("public_answer"), str)
            or not observation["public_answer"]
        ):
            reason = "CAPTURE_ANSWER_UNAVAILABLE"
        else:
            evidence = observation.get("generation_evidence", [])
            if (
                not isinstance(evidence, (list, tuple))
                or any(
                    not isinstance(item, (list, tuple))
                    or len(item) != 2
                    or any(not isinstance(value, str) or not value for value in item)
                    for item in evidence
                )
                or len({item[0] for item in evidence}) != len(evidence)
            ):
                reason = "CAPTURE_EVIDENCE_INVALID"
            else:
                status = "READY"
                capture = {
                    "run_id": run["run_id"],
                    "case_id": case_id,
                    "attempt": 1,
                    "trace_id": observation["trace_id"],
                    "question": case["question"],
                    "answer": observation["public_answer"],
                    "reference_answer": case["reference_answer"],
                    "generation_evidence": [{"alias": a, "content": c} for a, c in evidence],
                    "evidence_status": "exact" if evidence else "unavailable",
                }
        result.append({"case_id": case_id, "status": status, "reason": reason, "capture": capture})
    return result


def _applicable(name: str, capture: dict) -> bool:
    return not (
        name == "correctness"
        and not capture["reference_answer"]
        or name == "faithfulness"
        and not capture["generation_evidence"]
    )


def _pending(item: dict) -> dict:
    capture = item["capture"]
    metrics = {}
    for name in METRICS:
        if capture:
            status = "not_run" if _applicable(name, capture) else "not_applicable"
        else:
            status = "not_applicable" if item["status"] == "NOT_APPLICABLE" else "unavailable"
        metrics[name] = {"status": status, "score": None}
    return {
        "case_id": item["case_id"],
        "status": "NOT_RUN" if capture else item["status"],
        "reason": item["reason"],
        "trace_id": capture["trace_id"] if capture else None,
        "metrics": metrics,
    }


class EvaluationScoringService:
    def __init__(self, runs, store, profiles: tuple[ScoringProfile, ...] = ()):
        self._runs, self._store = runs, store
        if len({p.profile_id for p in profiles}) != len(profiles):
            raise ValueError("Duplicate scoring profile")
        self._profiles = {p.profile_id: p for p in profiles}

    def read(self, workspace_id, principal, run_id):
        run = self._runs.read_run(workspace_id, principal, run_id)
        return {
            "profiles": [p.provenance() for p in self._profiles.values()],
            "batches": run.get("scoring_batches", []),
        }

    def _input(self, workspace_id, principal, run_id, case_ids, profile_id):
        run = self._runs.read_run(workspace_id, principal, run_id)
        cases = capture_saved_cases(self._runs, run, principal, case_ids)
        profile = self._profiles.get(profile_id)
        reasons = []
        if run["execution_status"] not in {"COMPLETED", "BLOCKED", "INDETERMINATE"}:
            reasons.append("Q_AND_A_STILL_RUNNING")
        if profile is None:
            reasons.append("JUDGE_PROFILE_UNAVAILABLE")
        elif profile.kind != "offline":
            reasons.append("JUDGE_APPROVAL_REQUIRED")
        if not any(case["capture"] for case in cases):
            reasons.append("NO_APPLICABLE_CASES")
        payload = {
            "run_id": run_id,
            "workspace_id": workspace_id,
            "selection_digest": run["selection_digest"],
            "dataset": run["selection"]["reference"],
            "cases": cases,
            "binding": run["binding"],
            "scorer": profile.provenance() if profile else None,
        }
        return payload, reasons

    def preflight(self, workspace_id, principal, run_id, case_ids, profile_id):
        authorize_evaluation(workspace_id=workspace_id, principal=principal, action="score")
        payload, reasons = self._input(workspace_id, principal, run_id, case_ids, profile_id)
        result = {
            "preflight_id": uuid4().hex,
            "status": "BLOCKED" if reasons else "READY",
            "reasons": reasons,
            "input_digest": digest_json(payload),
            "cases": [_pending(c) for c in payload["cases"]],
            "scorer": payload["scorer"],
            "quality_status": "UNCALIBRATED",
            "release_gate": False,
            "expires_at": (datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
        }
        if not reasons:
            self._store.save_preflight(
                {
                    **result,
                    "workspace_id": workspace_id,
                    "run_id": run_id,
                    "purpose": "scoring",
                    "case_ids": list(case_ids),
                    "profile_id": profile_id,
                }
            )
        return result

    async def score(self, workspace_id, principal, run_id, preflight_id, request_id):
        authorize_evaluation(workspace_id=workspace_id, principal=principal, action="score")
        if not isinstance(request_id, str) or not request_id or len(request_id) > 255:
            raise KnoraError("EVALUATION_IDEMPOTENCY_KEY_INVALID")
        run = self._runs.read_run(workspace_id, principal, run_id)
        request_digest = digest_json({"preflight_id": preflight_id, "run_id": run_id})
        for previous in run.get("scoring_batches", []):
            if previous["request_id"] == request_id:
                if previous["request_digest"] != request_digest:
                    raise KnoraError("EVALUATION_IDEMPOTENCY_CONFLICT")
                return previous
        preflight = self._store.get_preflight(workspace_id, preflight_id)
        if (
            preflight is None
            or preflight.get("purpose") != "scoring"
            or preflight["run_id"] != run_id
            or datetime.fromisoformat(preflight["expires_at"]) <= datetime.now(UTC)
        ):
            raise KnoraError("EVALUATION_SCORING_NOT_READY")
        payload, reasons = self._input(
            workspace_id, principal, run_id, tuple(preflight["case_ids"]), preflight["profile_id"]
        )
        if reasons or digest_json(payload) != preflight["input_digest"]:
            raise KnoraError("EVALUATION_SCORING_NOT_READY")
        batch = {
            "id": uuid4().hex,
            "run_id": run_id,
            "request_id": request_id,
            "request_digest": request_digest,
            "input_digest": preflight["input_digest"],
            "dataset": payload["dataset"],
            "selection_digest": payload["selection_digest"],
            "scorer": payload["scorer"],
            "created_at": datetime.now(UTC).isoformat(),
            "status": "INDETERMINATE",
            "quality_status": "UNCALIBRATED",
            "release_gate": False,
            "results": {item["case_id"]: _pending(item) for item in payload["cases"]},
        }
        batch, reserved = self._store.reserve_scoring_batch(workspace_id, run_id, batch)
        if not reserved:
            return batch
        profile = self._profiles[preflight["profile_id"]]
        for item in payload["cases"]:
            if item["capture"] is None:
                continue
            case_id = item["case_id"]
            uncertain = {
                **_pending(item),
                "status": "INDETERMINATE",
                "reason": "JUDGE_RESULT_UNAVAILABLE",
                "metrics": {
                    name: {
                        "status": "indeterminate"
                        if _applicable(name, item["capture"])
                        else "not_applicable",
                        "score": None,
                    }
                    for name in METRICS
                },
            }
            batch = {**batch, "results": {**batch["results"], case_id: uncertain}}
            self._store.checkpoint_scoring_batch(workspace_id, run_id, batch)
            try:
                result = deepcopy(await to_thread(profile.measure, deepcopy(item["capture"])))
                self._validate_result(item["capture"], result, profile)
                value = {
                    **result,
                    "status": "ERROR"
                    if any(m["status"] == "error" for m in result["metrics"].values())
                    else "COMPLETED",
                }
            except Exception:
                value = uncertain
            batch = {**batch, "results": {**batch["results"], case_id: value}}
            self._store.checkpoint_scoring_batch(workspace_id, run_id, batch)
            if value["status"] == "INDETERMINATE":
                return batch
        batch = {
            **batch,
            "status": "COMPLETED_WITH_ERRORS"
            if any(r["status"] == "ERROR" for r in batch["results"].values())
            else "COMPLETED",
            "finished_at": datetime.now(UTC).isoformat(),
        }
        return self._store.checkpoint_scoring_batch(workspace_id, run_id, batch)

    @staticmethod
    def _validate_result(capture, result, profile):
        from evals.scorers.deepeval_cloudflare import _scoring_input_sha256

        if (
            any(
                result.get(key) != capture[key]
                for key in ("run_id", "case_id", "trace_id", "attempt")
            )
            or result.get("model") != profile.model
            or result.get("tool") != "deepeval-4.2.8"
            or result.get("method") != profile.prompt_version
            or result.get("input_sha256") != _scoring_input_sha256(capture)
            or set(result.get("metrics", {})) != set(METRICS)
        ):
            raise ValueError("Judge identity mismatch")
        for name, metric in result["metrics"].items():
            applicable = _applicable(name, capture)
            if (
                metric.get("status")
                not in ({"scored", "error"} if applicable else {"not_applicable"})
                or metric.get("status") == "scored"
                and (
                    type(metric.get("score")) not in (int, float)
                    or not isfinite(metric["score"])
                    or not 0 <= metric["score"] <= 1
                )
                or metric.get("status") != "scored"
                and metric.get("score") is not None
            ):
                raise ValueError("Invalid judge metric")
