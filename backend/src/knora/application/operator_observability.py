"""Capability-guarded, secret-safe operator read projections."""

from collections.abc import Mapping
from typing import Protocol

from knora.domain.access import WorkspacePrincipal
from knora.domain.errors import KnoraError


class TraceReader(Protocol):
    def read_trace(self, *, trace_id: str, workspace_id: str) -> object: ...


class EvaluationReader(Protocol):
    def read_trace(self, *, trace_id: str, workspace_id: str) -> object: ...


class OperationsReader(Protocol):
    def snapshot(self) -> object: ...


_SENSITIVE_KEYS = {"api_key", "authorization", "access_token", "secret", "password"}


def _sanitize(value: object) -> object:
    if isinstance(value, Mapping):
        return {
            str(key): _sanitize(item)
            for key, item in value.items()
            if str(key).casefold() not in _SENSITIVE_KEYS
        }
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_sanitize(item) for item in value)
    if hasattr(value, "__dataclass_fields__"):
        from dataclasses import asdict

        materialized = asdict(value)
        sanitized = _sanitize(materialized)
        # Preserve typed projections (notably OperationalSnapshot) for callers that
        # consume their attributes, while still rebuilding records containing secrets.
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
        self, *, trace_id: str, workspace_id: str, principal: WorkspacePrincipal
    ) -> object:
        self._authorize(workspace_id=workspace_id, principal=principal)
        return _sanitize(
            self._evaluation_reader.read_trace(trace_id=trace_id, workspace_id=workspace_id)
        )

    def read_operations(self, *, workspace_id: str, principal: WorkspacePrincipal) -> object:
        self._authorize(workspace_id=workspace_id, principal=principal)
        return _sanitize(self._operations_reader.snapshot())
