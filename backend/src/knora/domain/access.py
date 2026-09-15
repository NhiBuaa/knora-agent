from dataclasses import dataclass

from knora.domain.errors import KnoraError


@dataclass(frozen=True, slots=True)
class WorkspacePrincipal:
    workspace_id: str
    key_id: str
    capabilities: tuple[str, ...] | None = None

    def require_capability(self, capability: str) -> None:
        """Require a capability for bearer principals.

        ``None`` denotes a legacy API-key principal, which retains its existing
        workspace-scoped behavior. Bearer principals always carry an explicit
        capability set (possibly empty), so missing capabilities fail closed.
        """
        if self.capabilities is not None and capability not in self.capabilities:
            raise KnoraError("CAPABILITY_ACCESS_DENIED")

    @property
    def subject(self) -> str:
        return self.key_id

    def has_capability(self, capability: str) -> bool:
        return self.capabilities is None or capability in self.capabilities
