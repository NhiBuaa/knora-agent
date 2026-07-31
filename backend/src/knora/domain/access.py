from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WorkspacePrincipal:
    workspace_id: str
    key_id: str
