from typing import Protocol

BASELINE_CAPABILITIES: tuple[str, ...] = (
    "documents:read",
    "documents:write",
    "questions:ask",
)


class IdentityAccessStore(Protocol):
    def get_or_create_baseline(self, issuer: str, subject: str) -> tuple[str, ...]: ...


class SupabaseSessionReader(Protocol):
    def is_active(self, subject: str, session_id: str) -> bool: ...
