"""Workspace-scoped admission and persisted execution of native M3 selections."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal, Protocol
from uuid import uuid4

import httpx
from evals.runners.milestone_3 import (
    EvaluationEnvironmentBinding,
    M3Observation,
    ProductionM3Executor,
    VerifiedM3Environment,
    score_retrieval,
)

from knora.domain.access import WorkspacePrincipal
from knora.domain.errors import KnoraError
from knora.evaluation.access import authorize_evaluation
from knora.evaluation.catalog import Milestone3Catalog
from knora.evaluation.contracts import digest_json


class RunStore(Protocol):
    def save_preflight(self, value: dict) -> None: ...
    def get_preflight(self, workspace_id: str, preflight_id: str) -> dict | None: ...
    def create(self, run: dict, key: str) -> dict: ...
    def get(self, workspace_id: str, run_id: str) -> dict | None: ...
    def list(self, workspace_id: str) -> list[dict]: ...
    def claim(self, workspace_id: str, run_id: str) -> str | None: ...
    def checkpoint(
        self, workspace_id: str, run_id: str, attempt_id: str, case_id: str, observation: dict
    ) -> None: ...
    def finish(
        self, workspace_id: str, run_id: str, attempt_id: str, status: str, report: dict | None
    ) -> None: ...


@dataclass(frozen=True)
class RuntimeProfile:
    profile_id: str
    kind: Literal["offline", "live"]
    prepare: Callable[[], tuple[EvaluationEnvironmentBinding, object]]
    execute: Callable[[object, VerifiedM3Environment], Awaitable[M3Observation]]


def production_http_profile(
    *,
    profile_id: str,
    kind: Literal["offline", "live"],
    endpoint: str,
    api_key: str,
    trace_reader: object,
    client: httpx.AsyncClient,
    prepare: Callable[[], tuple[EvaluationEnvironmentBinding, object]],
) -> RuntimeProfile:
    """Register an owned Q&A runtime through the existing M3 executor."""

    async def execute(case: object, environment: VerifiedM3Environment) -> M3Observation:
        return await ProductionM3Executor(
            endpoint=endpoint,
            api_key=api_key,
            trace_reader=trace_reader,
            client=client,
            environment=environment,
        ).execute(case)

    return RuntimeProfile(profile_id, kind, prepare, execute)


class EvaluationRunService:
    def __init__(
        self,
        catalog: Milestone3Catalog,
        store: RunStore,
        profiles: tuple[RuntimeProfile, ...],
    ) -> None:
        if len({profile.profile_id for profile in profiles}) != len(profiles):
            raise ValueError("Duplicate runtime profile")
        self._catalog = catalog
        self._store = store
        self._profiles = {profile.profile_id: profile for profile in profiles}
        self._generation = 0

    def list_profiles(self, workspace_id: str, principal: WorkspacePrincipal) -> list[dict]:
        authorize_evaluation(workspace_id=workspace_id, principal=principal, action="read")
        return [
            {
                "profile_id": profile.profile_id,
                "kind": profile.kind,
                "status": "READY" if profile.kind == "offline" else "BLOCKED",
            }
            for profile in self._profiles.values()
        ] + [{"profile_id": "live", "kind": "live", "status": "BLOCKED"}]

    def preflight(
        self,
        workspace_id: str,
        principal: WorkspacePrincipal,
        dataset_id: str,
        case_ids: tuple[str, ...],
        profile_id: str,
    ) -> dict:
        authorize_evaluation(workspace_id=workspace_id, principal=principal, action="run")
        entry = self._catalog.get_dataset(workspace_id, dataset_id)
        cases = {case.id: case for case in entry.dataset.cases}
        if (
            not case_ids
            or len(case_ids) != len(set(case_ids))
            or any(id not in cases for id in case_ids)
        ):
            raise KnoraError("EVALUATION_SELECTION_INVALID")
        profile = self._profiles.get(profile_id)
        reasons: list[str] = []
        binding: EvaluationEnvironmentBinding | None = None
        if profile is None or profile.kind == "live":
            reasons.append(
                "PROVIDER_APPROVAL_REQUIRED"
                if profile_id == "live" or profile and profile.kind == "live"
                else "RUNTIME_PROFILE_UNAVAILABLE"
            )
        else:
            try:
                binding, corpus = profile.prepare()
                VerifiedM3Environment.prepare(binding=binding, corpus=corpus, manifest=entry.corpus)
                if binding.dataset_manifest_identity != entry.reference.dataset_id:
                    raise ValueError("Dataset binding mismatch")
            except Exception:
                reasons.append("RUNTIME_BINDING_UNAVAILABLE")
        preflight_id = uuid4().hex
        result = {
            "preflight_id": preflight_id,
            "status": "BLOCKED" if reasons else "READY",
            "reasons": reasons,
            "workspace_id": workspace_id,
            "dataset_id": dataset_id,
            "dataset_digest": entry.reference.native_digest,
            "case_ids": list(case_ids),
            "context_only_case_ids": [],
            "profile_id": profile_id,
            "expires_at": (datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
        }
        if not reasons:
            self._store.save_preflight(
                {
                    **result,
                    "generation": self._generation,
                    "binding": asdict(binding),
                }
            )
        return result

    def invalidate_preflights(self) -> None:
        self._generation += 1

    def start_run(
        self,
        workspace_id: str,
        principal: WorkspacePrincipal,
        preflight_id: str,
        idempotency_key: str,
    ) -> dict:
        authorize_evaluation(workspace_id=workspace_id, principal=principal, action="run")
        if not idempotency_key or len(idempotency_key) > 255:
            raise KnoraError("EVALUATION_IDEMPOTENCY_KEY_INVALID")
        preflight = self._store.get_preflight(workspace_id, preflight_id)
        if (
            preflight is None
            or preflight["workspace_id"] != workspace_id
            or preflight["generation"] != self._generation
            or datetime.fromisoformat(preflight["expires_at"]) <= datetime.now(UTC)
        ):
            raise KnoraError("EVALUATION_PREFLIGHT_STALE")
        entry = self._catalog.get_dataset(workspace_id, preflight["dataset_id"])
        if entry.reference.native_digest != preflight["dataset_digest"]:
            raise KnoraError("EVALUATION_PREFLIGHT_STALE")
        profile = self._profiles.get(preflight["profile_id"])
        if profile is None or profile.kind != "offline":
            raise KnoraError("EVALUATION_PREFLIGHT_STALE")
        try:
            binding, corpus = profile.prepare()
            VerifiedM3Environment.prepare(binding=binding, corpus=corpus, manifest=entry.corpus)
        except Exception as error:
            raise KnoraError("EVALUATION_PREFLIGHT_STALE") from error
        if asdict(binding) != preflight["binding"]:
            raise KnoraError("EVALUATION_PREFLIGHT_STALE")
        selection = {
            "reference": asdict(entry.reference),
            "selected_case_ids": preflight["case_ids"],
            "context_only_case_ids": preflight["context_only_case_ids"],
        }
        run = {
            "run_id": uuid4().hex,
            "workspace_id": workspace_id,
            "selection": selection,
            "selection_digest": digest_json(selection),
            "profile_id": profile.profile_id,
            "binding": asdict(binding),
            "execution_status": "QUEUED",
            "quality_status": "UNAVAILABLE",
            "observations": {case_id: {"status": "NOT_RUN"} for case_id in preflight["case_ids"]},
            "report": None,
            "request_digest": digest_json(
                {
                    "selection": selection,
                    "profile_id": profile.profile_id,
                    "binding": asdict(binding),
                }
            ),
        }
        return self._store.create(run, idempotency_key)

    def list_runs(self, workspace_id: str, principal: WorkspacePrincipal) -> list[dict]:
        authorize_evaluation(workspace_id=workspace_id, principal=principal, action="read")
        return self._store.list(workspace_id)

    def read_run(self, workspace_id: str, principal: WorkspacePrincipal, run_id: str) -> dict:
        authorize_evaluation(workspace_id=workspace_id, principal=principal, action="read")
        run = self._store.get(workspace_id, run_id)
        if run is None:
            raise KnoraError("EVALUATION_RUN_NOT_FOUND")
        return run

    async def process_run(self, workspace_id: str, run_id: str) -> bool:
        attempt_id = self._store.claim(workspace_id, run_id)
        if not attempt_id:
            return False
        run = self._store.get(workspace_id, run_id)
        if run is None:
            return False
        try:
            entry = self._catalog.get_dataset(
                workspace_id, run["selection"]["reference"]["dataset_id"]
            )
            if asdict(entry.reference) != run["selection"]["reference"]:
                raise ValueError("Dataset reference drift")
            profile = self._profiles.get(run["profile_id"])
            if profile is None or profile.kind != "offline":
                raise ValueError("Runtime profile unavailable")
            binding, corpus = profile.prepare()
            if asdict(binding) != run["binding"]:
                raise ValueError("Runtime binding drift")
            environment = VerifiedM3Environment.prepare(
                binding=binding, corpus=corpus, manifest=entry.corpus
            )
        except Exception:
            self._store.finish(workspace_id, run_id, attempt_id, "BLOCKED", None)
            return True
        by_id = {case.id: case for case in entry.dataset.cases}
        case_ids = run["selection"]["selected_case_ids"]
        observations: list[M3Observation] = []
        for case_id in case_ids:
            try:
                observation = await profile.execute(by_id[case_id], environment)
                if observation.case_id != case_id:
                    raise ValueError("Observation case mismatch")
            except Exception:
                self._store.finish(workspace_id, run_id, attempt_id, "INDETERMINATE", None)
                return True
            observations.append(observation)
            payload = asdict(observation)
            payload["status"] = "OBSERVED" if observation.is_success else "FAILED"
            self._store.checkpoint(workspace_id, run_id, attempt_id, case_id, payload)
        try:
            report = self._partial_report(
                tuple(by_id[case_id] for case_id in case_ids),
                tuple(observations),
                binding,
                run,
                len(entry.dataset.cases),
            )
        except Exception:
            self._store.finish(workspace_id, run_id, attempt_id, "INDETERMINATE", None)
            return True
        self._store.finish(workspace_id, run_id, attempt_id, "COMPLETED", report)
        return True

    @staticmethod
    def _partial_report(
        cases: tuple,
        observations: tuple[M3Observation, ...],
        binding: EvaluationEnvironmentBinding,
        run: dict,
        dataset_count: int,
    ) -> dict:
        # The complete M3 report requires semantic citations. This projection never claims it.
        return {
            "schema_version": 1,
            "report_kind": "deterministic_partial_m3",
            "quality_status": "SEMANTIC_PENDING",
            "run_id": run["run_id"],
            "workspace_id": run["workspace_id"],
            "selection_digest": run["selection_digest"],
            "dataset": run["selection"]["reference"],
            "binding": run["binding"],
            "population": {
                "dataset": dataset_count,
                "selected": len(cases),
                "context_only": 0,
                "attempted": len(observations),
                "observed": sum(observation.is_success for observation in observations),
            },
            "retrieval": score_retrieval(cases, observations, binding=binding),
            "cases": [
                {
                    "case_id": observation.case_id,
                    "status": "OBSERVED" if observation.is_success else "FAILED",
                    "trace_id": observation.trace_id,
                    "decision": observation.decision,
                    "refusal_correctness": observation.refusal_correctness,
                    "citation_correctness": observation.citation_correctness,
                    "semantic_citation_correctness": observation.semantic_citation_correctness,
                    "failure_code": observation.failure_code,
                }
                for observation in observations
            ],
        }
