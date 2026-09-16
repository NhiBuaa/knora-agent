"""Capability-guarded, secret-safe operator read projections."""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal, Protocol

from knora.domain.access import WorkspacePrincipal
from knora.domain.errors import KnoraError


class TraceReader(Protocol):
    def read_trace(self, *, trace_id: str, workspace_id: str) -> object: ...


class EvaluationReader(Protocol):
    def read_evaluation(
        self, *, report_id: str, workspace_id: str
    ) -> "OperatorEvaluationResponse": ...


class OperationsReader(Protocol):
    def snapshot(self, *, workspace_id: str) -> object: ...


@dataclass(frozen=True)
class OperatorEvaluationResponse:
    """Explicit response when persisted evaluation reports are not available."""

    report_id: str
    workspace_id: str
    availability: Literal["unavailable"] = "unavailable"
    observation_failure: Literal["EVALUATION_REPORT_UNAVAILABLE"] = (
        "EVALUATION_REPORT_UNAVAILABLE"
    )


_SENSITIVE_KEYS = {"api_key", "authorization", "access_token", "secret", "password"}
_SENSITIVE_KEY_PARTS = (
    "api_key",
    "access_token",
    "authorization",
    "key_hash",
    "raw_token",
    "secret",
    "password",
    "token",
)


def _is_sensitive_key(key: object) -> bool:
    normalized = re.sub(r"(?<!^)(?=[A-Z])", "_", str(key)).casefold()
    normalized = re.sub(r"[^a-z0-9]+", "_", normalized).strip("_")
    return normalized in _SENSITIVE_KEYS or any(
        part in normalized for part in _SENSITIVE_KEY_PARTS
    )


def _sanitize(value: object) -> object:
    if isinstance(value, Mapping):
        return {
            str(key): _sanitize(item)
            for key, item in value.items()
            if not _is_sensitive_key(key)
        }
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_sanitize(item) for item in value)
    if hasattr(value, "__dataclass_fields__"):
        from dataclasses import asdict

        materialized = asdict(value)
        sanitized = _sanitize(materialized)
        # Preserve typed projections when no secret was present; public HTTP schemas
        # validate the materialized mapping when sanitization removed a field.
        return value if sanitized == materialized else sanitized
    return value


class OperatorObservability:
    def __init__(
        self,
        *,
        trace_reader: TraceReader,
        operations_reader: OperationsReader,
        evaluation_reader: EvaluationReader | None = None,
    ) -> None:
        self._trace_reader = trace_reader
        self._evaluation_reader = evaluation_reader or trace_reader
        self._operations_reader = operations_reader

    @staticmethod
    def _authorize(*, workspace_id: str, principal: WorkspacePrincipal) -> None:
        if principal.workspace_id != workspace_id:
            raise KnoraError("WORKSPACE_ACCESS_DENIED")
        principal.require_capability("operator:read")

    def read_trace(
        self, *, trace_id: str, workspace_id: str, principal: WorkspacePrincipal
    ) -> object:
        self._authorize(workspace_id=workspace_id, principal=principal)
        return _sanitize(
            self._trace_reader.read_trace(trace_id=trace_id, workspace_id=workspace_id)
        )

    def read_evaluation(
        self, *, report_id: str, workspace_id: str, principal: WorkspacePrincipal
    ) -> OperatorEvaluationResponse:
        self._authorize(workspace_id=workspace_id, principal=principal)
        return _sanitize(
            self._evaluation_reader.read_evaluation(
                report_id=report_id, workspace_id=workspace_id
            )
        )

    def read_operations(self, *, workspace_id: str, principal: WorkspacePrincipal) -> object:
        self._authorize(workspace_id=workspace_id, principal=principal)
        return _sanitize(self._operations_reader.snapshot(workspace_id=workspace_id))
