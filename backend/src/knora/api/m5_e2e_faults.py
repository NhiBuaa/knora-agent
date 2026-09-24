from typing import Literal

from knora.domain.access import WorkspacePrincipal

M5E2EFaultScenario = Literal["provider_failure", "stream_interruption"]


class M5E2EFaultControllerError(Exception):
    """Raised when a principal already has an active E2E fault script."""


class M5E2EFaultController:
    """Keep one in-memory, one-shot E2E fault script per principal and Workspace."""

    def __init__(self) -> None:
        self._armed_scenarios: dict[tuple[str, str], M5E2EFaultScenario] = {}

    def arm(self, *, principal: WorkspacePrincipal, scenario: M5E2EFaultScenario) -> None:
        binding = self._binding_for(principal)
        if binding in self._armed_scenarios:
            raise M5E2EFaultControllerError
        self._armed_scenarios[binding] = scenario

    def consume(self, *, principal: WorkspacePrincipal) -> M5E2EFaultScenario | None:
        return self._armed_scenarios.pop(self._binding_for(principal), None)

    @staticmethod
    def _binding_for(principal: WorkspacePrincipal) -> tuple[str, str]:
        return principal.workspace_id, principal.key_id
