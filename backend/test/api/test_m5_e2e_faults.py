import pytest

from knora.api.m5_e2e_faults import M5E2EFaultController, M5E2EFaultControllerError
from knora.domain.access import WorkspacePrincipal


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
