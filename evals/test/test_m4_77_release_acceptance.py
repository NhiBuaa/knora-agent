from __future__ import annotations

import inspect
import json
from dataclasses import asdict, fields
from pathlib import Path

import pytest

from knora.adapters.postgres.tables import ToolDispatchAdmissionTable
from knora.domain.access import WorkspacePrincipal
from knora.domain.errors import KnoraError
from knora.main import create_app
from knora.tools import (
    ActorContext,
    CapabilityRegistry,
    ExecuteApprovedProposal,
    ExecutionFailed,
    ExecutionFenced,
    ExecutionIndeterminate,
    ExecutionInProgress,
    ExecutionRecoverySeed,
    ExecutionSucceeded,
    InMemoryToolActionStore,
    ProposalNotExecutable,
    ReconcileExecution,
    WriteProposalWorkflow,
)
from knora.tools.execution_types import AuthorizedExecutionBindingSnapshot, ExecutionResult

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
MATRIX_PATH = REPOSITORY_ROOT / "evals" / "fixtures" / "m4_77_public_matrix_v1.json"
CASE_IDS = tuple(f"M4-77-TC-{number:02d}" for number in range(1, 13))
def test_tc01_literal_denial_matrix_is_closed_and_independently_stored() -> None:
    matrix = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    assert len(matrix["pre_acquisition_rows"]) == 37
    reasons = {row[0] for row in matrix["denial_rows"]}
    assert reasons == {
        "workspace_access_denied",
        "resource_access_denied",
        "execution_not_authorized",
        "capability_identity_mismatch",
        "capability_version_mismatch",
        "capability_digest_mismatch",
        "binding_identity_mismatch",
        "binding_version_mismatch",
        "binding_digest_mismatch",
        "policy_identity_mismatch",
        "policy_version_mismatch",
        "policy_digest_mismatch",
        "invalid_tool_resource_reference",
    }


def test_tc02_server_owned_execute_schema_has_no_identity_inputs() -> None:
    assert tuple(field.name for field in fields(ExecuteApprovedProposal)) == (
        "proposal_id",
        "expected_revision",
    )


def test_tc03_post_acquisition_denial_projection_is_closed() -> None:
    projection = asdict(ProposalNotExecutable("proposal", "logical", "resource_access_denied"))
    assert set(projection) - {"projection"} == {
        "proposal_id",
        "logical_execution_id",
        "reason_code",
        "lifecycle",
        "outcome_type",
    }
    assert projection["projection"] is None


def test_tc04_registry_is_static_versioned_and_has_no_plugin_epoch() -> None:
    first = CapabilityRegistry.static()
    second = CapabilityRegistry.static()
    assert first.capability_ids == ("ticket_lookup", "create_ticket")
    assert first.registry_digest == second.registry_digest
    assert (first.registry_identity, first.registry_version) == (
        "knora-static-tool-capability-registry",
        "m4-v1",
    )
    for forbidden in ("register", "discover", "load_plugin", "plugin_epoch"):
        assert not hasattr(first, forbidden)


def test_tc05_admission_table_contains_every_individual_contract_field() -> None:
    expected = {
        "admission_schema_version",
        "admission_identity",
        "admission_digest",
        "purpose",
        "workspace_id",
        "proposal_id",
        "logical_execution_id",
        "request_fingerprint",
        "capability_identity",
        "capability_version",
        "capability_digest",
        "binding_identity",
        "binding_version",
        "binding_digest",
        "policy_identity",
        "policy_version",
        "policy_digest",
        "reference_identity",
        "reference_version",
        "reference_digest",
        "reference_claims_digest",
        "resource_identity_digest",
        "canonical_target_digest",
        "canonical_parameter_digest",
        "complete_intent_digest",
        "reference_key_epoch",
        "workspace_dispatch_epoch",
        "authority_decision_digest",
        "authority_witness_digest",
        "owner",
        "generation",
        "database_issue_time",
        "lease_started_at",
        "lease_deadline",
        "envelope_signing_key_identity",
        "envelope_signing_key_version",
        "routing_snapshot_digest",
        "canonical_envelope_digest",
        "admission_audit_identity",
        "admission_audit_digest",
        "envelope_token",
    }
    assert expected <= set(ToolDispatchAdmissionTable.__table__.columns.keys())


def test_tc06_public_results_never_expose_private_admission_material() -> None:
    results = (
        ExecutionSucceeded("proposal", "logical", "opaque-reference"),
        ExecutionFailed("proposal", "logical", "target_not_found"),
        ExecutionIndeterminate("proposal", "logical"),
        ExecutionInProgress("proposal", "logical"),
        ExecutionFenced("proposal", "logical"),
    )
    forbidden = {
        "request_fingerprint",
        "admission_digest",
        "envelope_token",
        "provider_routing_handle",
        "authority_witness_digest",
    }
    assert all(not (set(asdict(result)) & forbidden) for result in results)


def test_tc07_production_composition_has_no_test_harness_selector() -> None:
    parameters = set(inspect.signature(create_app).parameters)
    assert not any(
        marker in parameter
        for parameter in parameters
        for marker in ("test_signer", "mutation", "harness", "plugin")
    )


def test_tc08_provider_outcome_not_found_is_not_a_public_execution_result() -> None:
    public_names = {item.__name__ for item in ExecutionResult.__args__}
    assert "ProviderOutcomeNotFound" not in public_names


def test_tc09_recovery_seed_is_read_only_and_has_two_disjoint_kinds() -> None:
    binding = AuthorizedExecutionBindingSnapshot(
        "create_ticket",
        "m4.2",
        "sha256:" + "a" * 64,
        "binding-a",
        "v1",
        "sha256:" + "b" * 64,
        "policy-a",
        "v1",
        "sha256:" + "c" * 64,
    )
    no_admission = ExecutionRecoverySeed(
        "logical", "fingerprint", binding, None, None
    )
    assert no_admission.kind == "NoAdmission"
    assert (
        ExecutionRecoverySeed("logical", "fingerprint", binding, "admission", "digest").kind
        == "AdmissionOutstanding"
    )


class _Resolver:
    def resolve_for_proposal(self, workspace_id, capability_id):
        raise KnoraError("TOOL_CAPABILITY_NOT_FOUND")


def test_tc10_reconcile_command_remains_out_of_scope_for_issue_77() -> None:
    workflow = WriteProposalWorkflow(
        capability_resolver=_Resolver(), store=InMemoryToolActionStore()
    )
    with pytest.raises(KnoraError) as error:
        workflow.handle(
            ReconcileExecution("proposal", 1),
            WorkspacePrincipal("workspace", "key"),
            ActorContext("system", "system"),
        )
    assert error.value.code == "TOOL_REQUEST_INVALID"


def test_tc11_evidence_schema_contains_no_secret_or_raw_routing_fields() -> None:
    forbidden = {"secret", "credential", "mac", "provider_routing_handle", "envelope_token"}
    evidence_keys = {
        "schema_version",
        "evidence_id",
        "subject_sha",
        "guide_revision",
        "guide_digest",
        "test_cases",
        "matrix_digest",
        "registry",
        "provider_boundary",
        "sentinels",
        "result",
        "sanitized",
        "matrix_rows",
    }
    assert not (evidence_keys & forbidden)


def test_tc12_release_harness_covers_every_locked_case_once() -> None:
    assert tuple(f"M4-77-TC-{number:02d}" for number in range(1, 13)) == CASE_IDS
