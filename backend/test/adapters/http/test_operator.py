from dataclasses import dataclass

from fastapi.testclient import TestClient

from knora.access.api_keys import ApiCredential, ApiKeyAuthenticator, hash_api_key
from knora.main import create_app
from knora.tools.lifecycle_projection import (
    ToolLifecycleListProjection,
    ToolLifecycleObservationFailure,
    ToolLifecycleUnavailable,
)


@dataclass(frozen=True)
class FakeOperator:
    def read_trace(self, *, trace_id, workspace_id, principal):
        if trace_id == "missing":
            raise LookupError("evaluation trace not found")
        return {
            "trace_id": trace_id,
            "workspace_id": workspace_id,
            "retrieval_configuration_id": "retrieval-m1-v1",
            "embedding_configuration_id": "embedding-local-m1-v2",
            "candidates": [],
            "alias_mapping": {},
            "provider_metadata": {"safe": "value"},
            "retrieval_latency_ms": 1.0,
            "trace_schema_version": 2,
            "branch_observation_schema_version": 1,
            "fusion_policy_version": None,
            "embedding_set_ids": [],
            "chunk_set_ids": [],
            "candidate_decisions": [],
            "branch_observations": [],
            "decision": "REFUSAL",
            "answer": None,
            "refusal_reason": "no evidence",
            "parsed_markers": [],
            "validation_outcome": "valid",
        }

    def read_evaluation(self, *, report_id, workspace_id, principal):
        return {
            "report_id": report_id,
            "workspace_id": workspace_id,
            "availability": "unavailable",
            "observation_failure": "EVALUATION_REPORT_UNAVAILABLE",
        }

    def read_operations(self, *, workspace_id, principal):
        return {
            "workspace_id": workspace_id,
            "metrics": {"queue_depth": 0},
            "configuration_version": "metrics-v1",
            "histograms": {},
        }


@dataclass(frozen=True)
class FakeLifecycle:
    result: object
    calls: list[int] | None = None

    def read_lifecycle(self, *, workspace_id, principal):
        if self.calls is not None:
            self.calls.append(1)
        return self.result


def _client(*, lifecycle=None) -> tuple[TestClient, str]:
    raw_key = "operator-route-key"
    app = create_app(
        api_key_authenticator=ApiKeyAuthenticator(
            (
                ApiCredential(
                    key_id="operator-route",
                    key_hash=hash_api_key(raw_key),
                    workspace_id="workspace-a",
                    enabled=True,
                ),
            )
        ),
        operator_observability=FakeOperator(),
        tool_lifecycle_reader=lifecycle,
    )
    return TestClient(app), raw_key


def test_operator_routes_use_typed_workspace_scoped_projections() -> None:
    client, raw_key = _client()
    headers = {"X-API-Key": raw_key}

    trace = client.get(
        "/v1/workspaces/workspace-a/operator/traces/trace-a", headers=headers
    )
    assert trace.status_code == 200
    assert trace.json()["workspace_id"] == "workspace-a"
    assert "api_key" not in trace.text

    evaluation = client.get(
        "/v1/workspaces/workspace-a/operator/evaluations/report-a", headers=headers
    )
    assert evaluation.status_code == 200
    assert evaluation.json() == {
        "report_id": "report-a",
        "workspace_id": "workspace-a",
        "availability": "unavailable",
        "observation_failure": "EVALUATION_REPORT_UNAVAILABLE",
    }

    operations = client.get(
        "/v1/workspaces/workspace-a/operator/operations", headers=headers
    )
    assert operations.status_code == 200
    assert operations.json()["workspace_id"] == "workspace-a"


def test_operator_routes_reject_cross_workspace_and_map_missing_resource() -> None:
    client, raw_key = _client()
    denied = client.get(
        "/v1/workspaces/workspace-b/operator/traces/trace-a",
        headers={"X-API-Key": raw_key},
    )
    assert denied.status_code == 403

    missing = client.get(
        "/v1/workspaces/workspace-a/operator/traces/missing",
        headers={"X-API-Key": raw_key},
    )
    assert missing.status_code == 404

    unauthenticated = client.get("/v1/workspaces/workspace-a/operator/operations")
    assert unauthenticated.status_code == 401


def test_tool_lifecycle_route_returns_unavailable_projection() -> None:
    client, raw_key = _client(lifecycle=FakeLifecycle(ToolLifecycleUnavailable()))
    response = client.get(
        "/v1/workspaces/workspace-a/operator/tool-lifecycle",
        headers={"X-API-Key": raw_key},
    )
    assert response.status_code == 200
    assert response.json() == {"availability": "unavailable", "items": [], "code": None}


def test_tool_lifecycle_route_denies_cross_workspace_before_reader() -> None:
    calls: list[int] = []
    lifecycle = FakeLifecycle(ToolLifecycleListProjection(items=()), calls)
    client, raw_key = _client(lifecycle=lifecycle)
    response = client.get(
        "/v1/workspaces/workspace-b/operator/tool-lifecycle",
        headers={"X-API-Key": raw_key},
    )
    assert response.status_code == 403
    assert calls == []


def test_tool_lifecycle_route_exposes_observation_failure_without_private_fields() -> None:
    client, raw_key = _client(lifecycle=FakeLifecycle(ToolLifecycleObservationFailure()))
    response = client.get(
        "/v1/workspaces/workspace-a/operator/tool-lifecycle",
        headers={"X-API-Key": raw_key},
    )
    assert response.status_code == 200
    assert response.json() == {
        "availability": "observation_failure",
        "items": [],
        "code": "TOOL_LIFECYCLE_OBSERVATION_FAILED",
    }
