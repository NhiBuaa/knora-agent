"""Workspace and capability admission for Evaluation Workbench application seams."""

from typing import Literal

from knora.domain.access import WorkspacePrincipal
from knora.domain.errors import KnoraError

EvaluationAction = Literal["read", "read_source", "write", "upload", "approve", "run"]

_CAPABILITIES = {
    "read": ("operator:read",),
    "read_source": ("operator:read", "documents:read"),
    "write": ("operator:read", "evaluations:write"),
    "upload": ("operator:read", "evaluations:write", "documents:write"),
    "approve": ("operator:read", "evaluations:approve"),
    "run": ("operator:read", "evaluations:run", "questions:ask"),
}


def authorize_evaluation(
    *, workspace_id: str, principal: WorkspacePrincipal, action: EvaluationAction
) -> None:
    """Check before lookup; callers additionally verify owner and exact approval bindings."""
    if principal.workspace_id != workspace_id:
        raise KnoraError("WORKSPACE_ACCESS_DENIED")
    if action not in _CAPABILITIES:
        raise ValueError("Unknown evaluation action")
    # Legacy keys keep read compatibility, but do not acquire new execution/write authority.
    if action in {"write", "upload", "approve", "run"} and principal.capabilities is None:
        raise KnoraError("CAPABILITY_ACCESS_DENIED")
    for capability in _CAPABILITIES[action]:
        principal.require_capability(capability)
