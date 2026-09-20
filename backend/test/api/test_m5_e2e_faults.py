import time
from dataclasses import dataclass, field

import pytest
from fastapi.testclient import TestClient

from knora.access.api_keys import ApiCredential, ApiKeyAuthenticator, hash_api_key
from knora.access.keycloak import KeycloakAuthenticator
from knora.api.m5_e2e_faults import M5E2EFaultController, M5E2EFaultControllerError
from knora.domain.access import WorkspacePrincipal
from knora.infrastructure.settings import Settings, settings
from knora.main import create_app

RAW_KEY = "m5-e2e-key"


@dataclass
class RecordingStreamService:
    calls: list[tuple[object, WorkspacePrincipal]] = field(default_factory=list)

    async def execute_stream(self, command, principal):
        self.calls.append((command, principal))
        raise AssertionError("an armed E2E fault must bypass the ordinary stream service")
        yield


@dataclass
class RecordingFaultController:
    arm_calls: list[tuple[WorkspacePrincipal, str]] = field(default_factory=list)
    consume_calls: list[WorkspacePrincipal] = field(default_factory=list)

    def arm(self, *, principal, scenario) -> None:
        self.arm_calls.append((principal, scenario))

    def consume(self, *, principal):
        self.consume_calls.append(principal)
        return None


def _api_key_authenticator() -> ApiKeyAuthenticator:
    return ApiKeyAuthenticator(
        (
            ApiCredential(
                key_id="m5-e2e-user",
                key_hash=hash_api_key(RAW_KEY),
                workspace_id="workspace-a",
                enabled=True,
            ),
        )
    )


def _enabled_client(monkeypatch, service=None) -> TestClient:
    monkeypatch.setattr(settings, "m5_e2e_faults_enabled", True)
    return TestClient(
        create_app(
            answer_question=service or RecordingStreamService(),
            api_key_authenticator=_api_key_authenticator(),
        )
    )


def _bearer_client(monkeypatch, *, capabilities=()) -> TestClient:
    monkeypatch.setattr(settings, "m5_e2e_faults_enabled", True)

    def validate(_token: str):
        return {
            "iss": "https://issuer",
            "aud": "knora-api",
            "exp": time.time() + 60,
            "sub": "m5-e2e-user",
            "workspace_id": "workspace-a",
            "capabilities": list(capabilities),
        }

    return TestClient(
        create_app(
            answer_question=RecordingStreamService(),
            api_key_authenticator=ApiKeyAuthenticator(()),
            keycloak_authenticator=KeycloakAuthenticator(
                issuer="https://issuer",
                audience="knora-api",
                token_validator=validate,
            ),
        )
    )


def test_provider_failure_is_consumed_once_by_its_armed_principal() -> None:
    controller = M5E2EFaultController()
    owner = WorkspacePrincipal("workspace-a", "owner")
    other_user = WorkspacePrincipal("workspace-a", "other-user")
    other_workspace = WorkspacePrincipal("workspace-b", "owner")

    controller.arm(principal=owner, scenario="provider_failure")

    assert controller.consume(principal=other_user) is None
    assert controller.consume(principal=other_workspace) is None
    assert controller.consume(principal=owner) == "provider_failure"
    assert controller.consume(principal=owner) is None


def test_stream_interruption_is_consumed_once_by_its_armed_principal() -> None:
    controller = M5E2EFaultController()
    owner = WorkspacePrincipal("workspace-a", "owner")

    controller.arm(principal=owner, scenario="stream_interruption")

    assert controller.consume(principal=owner) == "stream_interruption"
    assert controller.consume(principal=owner) is None


def test_duplicate_active_arm_for_the_same_principal_is_rejected() -> None:
    controller = M5E2EFaultController()
    owner = WorkspacePrincipal("workspace-a", "owner")

    controller.arm(principal=owner, scenario="provider_failure")

    with pytest.raises(M5E2EFaultControllerError):
        controller.arm(principal=owner, scenario="stream_interruption")


def test_fault_setting_defaults_off_and_reads_the_m5_environment(monkeypatch) -> None:
    monkeypatch.delenv("KNORA_M5_E2E_FAULTS_ENABLED", raising=False)
    assert Settings(_env_file=None).m5_e2e_faults_enabled is False

    monkeypatch.setenv("KNORA_M5_E2E_FAULTS_ENABLED", "true")
    assert Settings(_env_file=None).m5_e2e_faults_enabled is True


def test_normal_composition_has_no_fault_route_or_controller(monkeypatch) -> None:
    monkeypatch.setattr(settings, "m5_e2e_faults_enabled", False)
    app = create_app(api_key_authenticator=_api_key_authenticator())
    client = TestClient(app)

    response = client.post(
        "/m5-e2e/faults",
        headers={"X-API-Key": RAW_KEY},
        json={"workspace_id": "workspace-a", "scenario": "provider_failure"},
    )

    assert response.status_code == 404
    assert not hasattr(app.state, "m5_e2e_fault_controller")
    assert "/m5-e2e/faults" not in client.get("/openapi.json").json()["paths"]


def test_enabled_control_route_rejects_unauthenticated_before_controller_arm(
    monkeypatch,
) -> None:
    client = _enabled_client(monkeypatch)
    controller = RecordingFaultController()
    client.app.state.m5_e2e_fault_controller = controller

    response = client.post(
        "/m5-e2e/faults",
        json={"workspace_id": "workspace-a", "scenario": "provider_failure"},
    )

    assert response.status_code == 401
    assert response.json() == {"error": {"code": "UNAUTHENTICATED"}}
    assert controller.arm_calls == []


def test_enabled_control_route_rejects_cross_workspace_before_controller_arm(
    monkeypatch,
) -> None:
    client = _enabled_client(monkeypatch)
    controller = RecordingFaultController()
    client.app.state.m5_e2e_fault_controller = controller

    response = client.post(
        "/m5-e2e/faults",
        headers={"X-API-Key": RAW_KEY},
        json={"workspace_id": "workspace-b", "scenario": "provider_failure"},
    )

    assert response.status_code == 403
    assert response.json() == {"error": {"code": "WORKSPACE_ACCESS_DENIED"}}
    assert controller.arm_calls == []


def test_enabled_control_route_requires_questions_capability_before_controller_arm(
    monkeypatch,
) -> None:
    client = _bearer_client(monkeypatch)
    controller = RecordingFaultController()
    client.app.state.m5_e2e_fault_controller = controller

    response = client.post(
        "/m5-e2e/faults",
        headers={"Authorization": "Bearer valid"},
        json={"workspace_id": "workspace-a", "scenario": "provider_failure"},
    )

    assert response.status_code == 403
    assert response.json() == {"error": {"code": "CAPABILITY_ACCESS_DENIED"}}
    assert controller.arm_calls == []


def test_enabled_control_route_rejects_arbitrary_scenarios_and_payload(monkeypatch) -> None:
    client = _enabled_client(monkeypatch)

    arbitrary_scenario = client.post(
        "/m5-e2e/faults",
        headers={"X-API-Key": RAW_KEY},
        json={"workspace_id": "workspace-a", "scenario": "arbitrary"},
    )
    arbitrary_payload = client.post(
        "/m5-e2e/faults",
        headers={"X-API-Key": RAW_KEY},
        json={
            "workspace_id": "workspace-a",
            "scenario": "provider_failure",
            "error_code": "SECRET_FAILURE",
        },
    )

    assert arbitrary_scenario.status_code == 422
    assert arbitrary_payload.status_code == 422


def test_provider_failure_uses_safe_terminal_stream_serialization(monkeypatch) -> None:
    service = RecordingStreamService()
    client = _enabled_client(monkeypatch, service)

    setup = client.post(
        "/m5-e2e/faults",
        headers={"X-API-Key": RAW_KEY},
        json={"workspace_id": "workspace-a", "scenario": "provider_failure"},
    )
    response = client.post(
        "/v1/questions/stream",
        headers={"X-API-Key": RAW_KEY},
        json={"workspace_id": "workspace-a", "question": "What is the policy?"},
    )

    assert setup.status_code == 200
    assert setup.json() == {"status": "armed"}
    assert RAW_KEY not in setup.text
    assert response.status_code == 200
    assert response.text == (
        'event: failure\ndata: {"error_code":"PROVIDER_REQUEST_FAILED"}\n\n'
    )
    assert "final_validated" not in response.text
    assert service.calls == []


def test_stream_interruption_emits_started_then_closes_without_terminal_event(
    monkeypatch,
) -> None:
    service = RecordingStreamService()
    client = _enabled_client(monkeypatch, service)

    setup = client.post(
        "/m5-e2e/faults",
        headers={"X-API-Key": RAW_KEY},
        json={"workspace_id": "workspace-a", "scenario": "stream_interruption"},
    )
    response = client.post(
        "/v1/questions/stream",
        headers={"X-API-Key": RAW_KEY},
        json={"workspace_id": "workspace-a", "question": "What is the policy?"},
    )

    assert setup.status_code == 200
    assert response.status_code == 200
    assert response.text == "event: started\ndata: {}\n\n"
    assert all(
        stage not in response.text
        for stage in ("failure", "final_validated", "refusal")
    )
    assert service.calls == []


def test_question_stream_authorizes_before_fault_controller_consumption(monkeypatch) -> None:
    client = _bearer_client(monkeypatch, capabilities=("questions:ask",))
    controller = RecordingFaultController()
    client.app.state.m5_e2e_fault_controller = controller

    response = client.post(
        "/v1/questions/stream",
        headers={"Authorization": "Bearer valid"},
        json={"workspace_id": "workspace-b", "question": "What is the policy?"},
    )

    assert response.status_code == 403
    assert response.json() == {"error": {"code": "WORKSPACE_ACCESS_DENIED"}}
    assert controller.consume_calls == []
