from dataclasses import dataclass
from typing import Literal, Protocol

from knora.domain.access import WorkspacePrincipal
from knora.domain.errors import KnoraError
from knora.workspaces.ports import WorkspaceAdmissionStore

DeletionState = Literal["requested", "blocked", "processing", "succeeded", "failed"]
ServingState = Literal["unavailable", "current", "previous"]


@dataclass(frozen=True, slots=True)
class DocumentProjection:
    document_id: str
    workspace_id: str
    source_key: str
    source_name: str
    archived: bool
    revision: int
    current_document_version_id: str | None = None
    serving_state: ServingState = "unavailable"
    ingestion_job_id: str | None = None
    ingestion_status: str | None = None


@dataclass(frozen=True, slots=True)
class DocumentListProjection:
    documents: tuple[DocumentProjection, ...]


@dataclass(frozen=True, slots=True)
class DocumentDeletionRequestProjection:
    request_id: str
    document_id: str
    state: DeletionState
    failure_reason: str | None = None


class DocumentReader(Protocol):
    def list_documents(
        self, *, workspace_id: str, principal: WorkspacePrincipal
    ) -> DocumentListProjection: ...

    def read_document(
        self, *, workspace_id: str, document_id: str, principal: WorkspacePrincipal
    ) -> DocumentProjection: ...


class DocumentLifecycle(Protocol):
    def archive(
        self,
        *,
        workspace_id: str,
        document_id: str,
        principal: WorkspacePrincipal,
        expected_revision: int | None = None,
    ) -> DocumentProjection: ...

    def unarchive(
        self,
        *,
        workspace_id: str,
        document_id: str,
        principal: WorkspacePrincipal,
        expected_revision: int | None = None,
    ) -> DocumentProjection: ...

    def request_deletion(
        self,
        *,
        workspace_id: str,
        document_id: str,
        principal: WorkspacePrincipal,
        idempotency_key: str,
    ) -> DocumentDeletionRequestProjection: ...


class DocumentLifecycleService:
    def __init__(
        self,
        lifecycle: DocumentLifecycle,
        admission_store: WorkspaceAdmissionStore | None = None,
    ) -> None:
        self._lifecycle = lifecycle
        self._admission_store = admission_store

    @staticmethod
    def _authorize(workspace_id: str, principal: WorkspacePrincipal, capability: str) -> None:
        if principal.workspace_id != workspace_id:
            raise KnoraError("WORKSPACE_ACCESS_DENIED")
        principal.require_capability(capability)

    def _admit(self, principal: WorkspacePrincipal, operation: str, operation_id: str) -> None:
        if self._admission_store is not None:
            self._admission_store.admit(
                principal=principal,
                operation=operation,
                operation_id=operation_id,
            )

    def archive(
        self,
        workspace_id: str,
        document_id: str,
        principal: WorkspacePrincipal,
        expected_revision: int | None = None,
    ) -> DocumentProjection:
        self._authorize(workspace_id, principal, "documents:write")
        self._admit(principal, "archive_document", f"{document_id}:{expected_revision}")
        return self._lifecycle.archive(
            workspace_id=workspace_id,
            document_id=document_id,
            principal=principal,
            expected_revision=expected_revision,
        )

    def unarchive(
        self,
        workspace_id: str,
        document_id: str,
        principal: WorkspacePrincipal,
        expected_revision: int | None = None,
    ) -> DocumentProjection:
        self._authorize(workspace_id, principal, "documents:write")
        self._admit(principal, "unarchive_document", f"{document_id}:{expected_revision}")
        return self._lifecycle.unarchive(
            workspace_id=workspace_id,
            document_id=document_id,
            principal=principal,
            expected_revision=expected_revision,
        )

    def request_deletion(
        self,
        workspace_id: str,
        document_id: str,
        principal: WorkspacePrincipal,
        idempotency_key: str,
    ) -> DocumentDeletionRequestProjection:
        self._authorize(workspace_id, principal, "documents:delete")
        if not idempotency_key:
            raise KnoraError("MISSING_IDEMPOTENCY_KEY")
        self._admit(principal, "request_document_deletion", idempotency_key)
        return self._lifecycle.request_deletion(
            workspace_id=workspace_id,
            document_id=document_id,
            principal=principal,
            idempotency_key=idempotency_key,
        )
