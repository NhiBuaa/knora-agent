from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class ResolutionState(StrEnum):
    ACTIVE = "ACTIVE"
    NO_ACTIVE_WORKSPACE = "NO_ACTIVE_WORKSPACE"


@dataclass(frozen=True, slots=True)
class WorkspaceView:
    id: str
    name: str
    archived: bool
    revision: int
    created_at: datetime


@dataclass(frozen=True, slots=True)
class WorkspaceResolution:
    state: ResolutionState
    workspace: WorkspaceView | None


@dataclass(frozen=True, slots=True)
class WorkspacePage:
    items: tuple[WorkspaceView, ...]
    next_cursor: str | None = None
