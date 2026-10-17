"""Workspace-scoped admission and persisted execution of native M3 selections."""

from __future__ import annotations

import json
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
from knora.evaluation.contracts import (
    DatasetReference,
    DatasetSelection,
    canonical_json,
    digest_json,
    select_cases,
)
from knora.evaluation.datasets import DatasetService
from knora.evaluation.pdf_metrics import score_pdf_run
from knora.evaluation.pdf_runtime import PdfRuntimeProfile, pdf_case_readiness, validate_pdf_binding


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
        *,
        datasets: DatasetService | None = None,
        pdf_profiles: tuple[PdfRuntimeProfile, ...] = (),
    ) -> None:
        if len({profile.profile_id for profile in (*profiles, *pdf_profiles)}) != len(
            profiles
        ) + len(pdf_profiles):
            raise ValueError("Duplicate runtime profile")
        self._catalog = catalog
        self._store = store
        self._profiles = {profile.profile_id: profile for profile in profiles}
        self._datasets = datasets
        self._pdf_profiles = {profile.profile_id: profile for profile in pdf_profiles}
        self._generation = 0

    def list_profiles(self, workspace_id: str, principal: WorkspacePrincipal) -> list[dict]:
        authorize_evaluation(workspace_id=workspace_id, principal=principal, action="read")
        return [
            {
                "profile_id": profile.profile_id,
                "kind": profile.kind,
                "status": "READY" if profile.kind == "offline" else "BLOCKED",
            }
            for profile in (*self._profiles.values(), *self._pdf_profiles.values())
        ] + [{"profile_id": "live", "kind": "live", "status": "BLOCKED"}]

    def preflight(
        self,
        workspace_id: str,
        principal: WorkspacePrincipal,
        dataset_id: str,
        case_ids: tuple[str, ...],
        profile_id: str,
        dataset_reference: dict | None = None,
    ) -> dict:
        authorize_evaluation(workspace_id=workspace_id, principal=principal, action="run")
        if dataset_reference is not None:
            return self._pdf_preflight(
                workspace_id, principal, dataset_id, case_ids, profile_id, dataset_reference
            )
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
            or preflight.get("purpose", "qa") != "qa"
            or preflight["workspace_id"] != workspace_id
            or preflight["generation"] != self._generation
            or datetime.fromisoformat(preflight["expires_at"]) <= datetime.now(UTC)
        ):
            raise KnoraError("EVALUATION_PREFLIGHT_STALE")
        if preflight.get("dataset_reference") is not None:
            return self._start_pdf_run(workspace_id, principal, preflight, idempotency_key)
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

    def saved_gold_cases(self, run: dict, principal: WorkspacePrincipal) -> dict[str, dict]:
        """Resolve saved-run gold without preparing or dispatching a Q&A runtime."""
        workspace_id = run["workspace_id"]
        authorize_evaluation(workspace_id=workspace_id, principal=principal, action="read")
        reference = run["selection"]["reference"]
        if reference["format"] == "pdf-gold-v1":
            authorize_evaluation(
                workspace_id=workspace_id, principal=principal, action="read_source"
            )
            frozen = self._pdf_gold(workspace_id, principal, reference)
            return {
                case.case_id: {
                    "question": case.question,
                    "expected": case.expected,
                    "reference_answer": case.reference_answer,
                }
                for case in frozen.gold.cases
            }
        if reference["format"] != "m3-native-v1":
            raise KnoraError("EVALUATION_SCORING_NOT_READY")
        entry = self._catalog.get_dataset(workspace_id, reference["dataset_id"])
        if asdict(entry.reference) != reference:
            raise KnoraError("EVALUATION_SCORING_NOT_READY")
        return {
            case.id: {
                "question": case.question,
                "expected": case.expected_behavior,
                "reference_answer": case.answer_expectations.reference_answer,
            }
            for case in entry.dataset.cases
        }

    async def process_run(self, workspace_id: str, run_id: str) -> bool:
        attempt_id = self._store.claim(workspace_id, run_id)
        if not attempt_id:
            return False
        run = self._store.get(workspace_id, run_id)
        if run is None:
            return False
        if run["selection"]["reference"]["format"] == "pdf-gold-v1":
            return await self._process_pdf_run(workspace_id, run, attempt_id)
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

    def _pdf_gold(self, workspace_id: str, principal: WorkspacePrincipal, reference: dict):
        try:
            parsed = DatasetReference.from_dict(reference)
            if parsed.workspace_id != workspace_id or self._datasets is None:
                raise ValueError("PDF dataset unavailable")
            frozen = self._datasets.get_frozen_dataset(
                workspace_id, parsed.dataset_id, principal, version=parsed.version
            )
            if asdict(frozen.reference) != reference:
                raise ValueError("Frozen reference mismatch")
            return frozen
        except (ValueError, TypeError) as error:
            raise KnoraError("EVALUATION_SELECTION_INVALID") from error

    def _pdf_preflight(self, workspace_id, principal, dataset_id, case_ids, profile_id, reference):
        frozen = self._pdf_gold(workspace_id, principal, reference)
        try:
            if dataset_id != frozen.reference.dataset_id:
                raise ValueError("Dataset ID mismatch")
            selection = select_cases(frozen, case_ids)
        except ValueError as error:
            raise KnoraError("EVALUATION_SELECTION_INVALID") from error
        reasons = []
        profile = self._pdf_profiles.get(profile_id)
        binding = None
        readiness = []
        if any(case.context_dependencies for case in frozen.gold.cases if case.case_id in case_ids):
            reasons.append("CONTEXT_EXECUTION_UNSUPPORTED")
        if profile is None or profile.kind != "offline":
            reasons.append(
                "PROVIDER_APPROVAL_REQUIRED"
                if profile_id == "live" or profile and profile.kind == "live"
                else "RUNTIME_PROFILE_UNAVAILABLE"
            )
        else:
            try:
                binding = profile.prepare(frozen)
                validate_pdf_binding(frozen, binding)
                readiness = pdf_case_readiness(frozen, selection, binding)
            except Exception:
                reasons.append("RUNTIME_BINDING_UNAVAILABLE")
        result = {
            "preflight_id": uuid4().hex,
            "status": "BLOCKED" if reasons else "READY",
            "reasons": reasons,
            "workspace_id": workspace_id,
            "dataset_id": dataset_id,
            "dataset_digest": frozen.reference.digest,
            "dataset_reference": asdict(frozen.reference),
            "case_ids": list(selection.selected_case_ids),
            "source_preparation": self._pdf_sources(workspace_id, principal, frozen),
            "context_only_case_ids": list(selection.context_only_case_ids),
            "case_readiness": readiness,
            "profile_id": profile_id,
            "expires_at": (datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
        }
        if not reasons:
            self._store.save_preflight(
                {**result, "generation": self._generation, "binding": binding}
            )
        return result

    def _pdf_sources(self, workspace_id, principal, frozen):
        sources = {
            source.document_version_id: source
            for source in self._datasets.list_sources(
                workspace_id, frozen.reference.dataset_id, principal
            )
        }
        result = []
        for gold in frozen.gold.sources:
            source = sources.get(gold.document_version_id)
            matches = source is not None and source.raw_sha256 == gold.raw_sha256
            result.append(
                {
                    "source_id": source.id if matches else None,
                    "document_version_id": gold.document_version_id,
                    "raw_sha256": gold.raw_sha256,
                    "status": source.status if matches else "MISSING",
                    "failure_code": source.failure_code
                    if matches
                    else "SOURCE_IDENTITY_UNAVAILABLE",
                    "snapshot_id": source.snapshot_id if matches else None,
                }
            )
        return result

    def _start_pdf_run(self, workspace_id, principal, preflight, key):
        try:
            frozen = self._pdf_gold(workspace_id, principal, preflight["dataset_reference"])
            selection = select_cases(frozen, tuple(preflight["case_ids"]))
            profile = self._pdf_profiles[preflight["profile_id"]]
            if profile.kind != "offline" or any(
                "CONTEXT_EXECUTION_UNSUPPORTED" in item["reasons"]
                for item in preflight["case_readiness"]
            ):
                raise ValueError("Profile unavailable")
            binding = profile.prepare(frozen)
            validate_pdf_binding(frozen, binding)
            if binding != preflight["binding"]:
                raise ValueError("Binding drift")
        except Exception as error:
            raise KnoraError("EVALUATION_PREFLIGHT_STALE") from error
        selected = json.loads(selection.to_json())
        run = {
            "run_id": uuid4().hex,
            "workspace_id": workspace_id,
            "selection": selected,
            "selection_digest": digest_json(selected),
            "profile_id": profile.profile_id,
            "binding": binding,
            "execution_status": "QUEUED",
            "quality_status": "UNAVAILABLE",
            "observations": {
                case_id: {"status": "NOT_RUN"} for case_id in selection.selected_case_ids
            },
            "report": None,
            "request_digest": digest_json(
                {"selection": selected, "profile_id": profile.profile_id, "binding": binding}
            ),
        }
        run["report"] = score_pdf_run(
            frozen,
            selection,
            binding["anchors"],
            run["observations"],
            run_id=run["run_id"],
            binding_digest=binding["approval"]["binding_digest"],
        )
        run["report"]["binding"] = binding
        run["report"]["source_preparation"] = self._pdf_sources(workspace_id, principal, frozen)
        run["quality_status"] = "SEMANTIC_PENDING"
        return self._store.create(run, key)

    async def _process_pdf_run(self, workspace_id, run, attempt_id):
        run_id = run["run_id"]
        # Only admitted data is read here. Execution never grants new user capabilities.
        principal = WorkspacePrincipal(workspace_id, "evaluation-worker", ("operator:read",))
        try:
            frozen = self._pdf_gold(workspace_id, principal, run["selection"]["reference"])
            selection = DatasetSelection.from_json(canonical_json(run["selection"]), frozen)
            profile = self._pdf_profiles[run["profile_id"]]
            if profile.kind != "offline":
                raise ValueError("Live approval required")
            binding = profile.prepare(frozen)
            validate_pdf_binding(frozen, binding)
            if binding != run["binding"]:
                raise ValueError("Binding drift")
        except Exception:
            report = run["report"]
            for case_id in run["selection"]["selected_case_ids"]:
                self._store.checkpoint(
                    workspace_id,
                    run_id,
                    attempt_id,
                    case_id,
                    {"status": "BLOCKED", "failure_code": "RUNTIME_BINDING_UNAVAILABLE"},
                )
            report = {
                **report,
                "cases": [
                    {
                        **case,
                        "status": "BLOCKED",
                        "failure_code": "RUNTIME_BINDING_UNAVAILABLE",
                        "reasons": ["OBSERVATION_BLOCKED", "RUNTIME_BINDING_UNAVAILABLE"],
                    }
                    for case in report["cases"]
                ],
            }
            self._store.finish(workspace_id, run_id, attempt_id, "BLOCKED", report)
            return True
        by_id = {case.case_id: case for case in frozen.gold.cases}
        readiness = {
            item["case_id"]: item for item in pdf_case_readiness(frozen, selection, binding)
        }
        status = "COMPLETED"
        observations = dict(run["observations"])
        for case_id in selection.selected_case_ids:
            ready = readiness[case_id]
            uncertain = False
            if ready["status"] == "BLOCKED":
                observation = {"status": "BLOCKED", "failure_code": ";".join(ready["reasons"])}
            else:
                try:
                    observation = await profile.execute(by_id[case_id], binding)
                    if observation.get("case_id") != case_id or observation.get("status") not in {
                        "OBSERVED",
                        "FAILED",
                    }:
                        raise ValueError("Invalid case observation")
                except Exception:
                    observation = {
                        "status": "INDETERMINATE",
                        "failure_code": "EVALUATION_OBSERVATION_INDETERMINATE",
                    }
                    uncertain = True
            observations[case_id] = observation
            self._store.checkpoint(workspace_id, run_id, attempt_id, case_id, observation)
            if uncertain:
                status = "INDETERMINATE"
                break
        report = score_pdf_run(
            frozen,
            selection,
            binding["anchors"],
            observations,
            run_id=run_id,
            binding_digest=binding["approval"]["binding_digest"],
        )
        report["binding"] = binding
        report["source_preparation"] = run["report"]["source_preparation"]
        self._store.finish(workspace_id, run_id, attempt_id, status, report)
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
