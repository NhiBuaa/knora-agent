from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WorkspacePrincipal:
    workspace_id: str
    key_id: str
    capabilities: tuple[str, ...] = ()

    @property
    def subject(self) -> str:
        return self.key_id

    def has_capability(self, capability: str) -> bool:
        return capability in self.capabilities

    def require_capability(self, capability: str) -> None:
        if self.capabilities and capability not in self.capabilities:
            from knora.domain.errors import KnoraError
            raise KnoraError("CAPABILITY_ACCESS_DENIED")
