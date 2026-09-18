from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Header, Request, Response, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from knora.access.keycloak import KeycloakAuthenticator
from knora.adapters.http.schemas import (
    DocumentDeletionRequestResponse,
    DocumentListResponse,
    DocumentResponse,
    HealthResponse,
    IngestionJobStatusResponse,
    IngestionResponse,
    OperatorEvaluationResponse,
    OperatorOperationsResponse,
    OperatorTraceResponse,
    PdfSubmissionResponse,
    ReprocessRequest,
    ReprocessResponse,
    ToolLifecycleResponse,
)
from knora.application.operator_observability import OperatorObservability
from knora.domain.access import WorkspacePrincipal
from knora.domain.errors import KnoraError
from knora.ingestion.documents import DocumentLifecycleService, DocumentReader
from knora.ingestion.interface import IngestDocumentCommand
from knora.ingestion.jobs import (
    IngestionJobs,
    PdfSubmissionCommand,
    PdfSubmissionConfiguration,
    ReprocessDocumentVersionCommand,
)
from knora.ingestion.module import MAX_RAW_BYTES, IngestDocument
from knora.ingestion.processing import ChunkingConfiguration
from knora.providers.embedding import EmbeddingConfiguration
from knora.tools.lifecycle_projection import (
    ToolLifecycleListProjection,
    ToolLifecycleObservationFailure,
    ToolLifecycleProjectionReader,
    ToolLifecycleUnavailable,
)

router = APIRouter()


def get_authenticator(request: Request):
    return request.app.state.authenticator


def get_embedding_configuration(request: Request) -> EmbeddingConfiguration:
    return request.app.state.embedding_configuration


def get_ingestion_jobs(request: Request) -> IngestionJobs | None:
    return getattr(request.app.state, "ingestion_jobs", None)


def get_document_reader(request: Request):
    return request.app.state.document_reader


def get_document_lifecycle(request: Request):
    return request.app.state.document_lifecycle


def get_operator_observability(request: Request) -> OperatorObservability:
    return request.app.state.operator_observability


def get_tool_lifecycle_reader(request: Request) -> ToolLifecycleProjectionReader:
    return request.app.state.tool_lifecycle_reader


def authenticate_principal(
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    authenticator=Depends(get_authenticator),  # noqa: B008
) -> WorkspacePrincipal:
    if authorization and isinstance(authenticator, KeycloakAuthenticator):
        try:
            return authenticator.authenticate(authorization)
        except KnoraError:
            if authenticator.api_key_authenticator is not None:
                return authenticator.api_key_authenticator.authenticate(x_api_key)
            raise
    if authorization and hasattr(authenticator, "authenticate"):
        try:
            return authenticator.authenticate(authorization)
        except KnoraError:
            pass
    return authenticator.authenticate(x_api_key)


def require_operator_read(
    workspace_id: str,
    principal: Annotated[WorkspacePrincipal, Depends(authenticate_principal)],
) -> WorkspacePrincipal:
    if principal.workspace_id != workspace_id:
        raise KnoraError("WORKSPACE_ACCESS_DENIED")
    principal.require_capability("operator:read")
    return principal


def require_documents_read(
    workspace_id: str,
    principal: Annotated[WorkspacePrincipal, Depends(authenticate_principal)],
) -> WorkspacePrincipal:
    if principal.workspace_id != workspace_id:
        raise KnoraError("WORKSPACE_ACCESS_DENIED")
    principal.require_capability("documents:read")
    return principal


def require_documents_delete(
    workspace_id: str,
    principal: Annotated[WorkspacePrincipal, Depends(authenticate_principal)],
) -> WorkspacePrincipal:
    if principal.workspace_id != workspace_id:
        raise KnoraError("WORKSPACE_ACCESS_DENIED")
    principal.require_capability("documents:delete")
    return principal


def require_documents_write(
    workspace_id: str,
    principal: Annotated[WorkspacePrincipal, Depends(authenticate_principal)],
) -> WorkspacePrincipal:
    if principal.workspace_id != workspace_id:
        raise KnoraError("WORKSPACE_ACCESS_DENIED")
    principal.require_capability("documents:write")
    return principal


def get_ingest_document(
    request: Request,
    _principal: Annotated[WorkspacePrincipal, Depends(require_documents_write)],
) -> IngestDocument:
    return request.app.state.ingest_document


def media_type_for_filename(filename: str) -> str:
    suffix = Path(filename).suffix.casefold()
    if suffix in {".md", ".markdown"}:
        return "text/markdown"
    if suffix == ".pdf":
        return "application/pdf"
    if suffix in {"", ".txt", ".text"}:
        return "text/plain"
    raise KnoraError("UNSUPPORTED_DOCUMENT_TYPE")


def safe_source_name(filename: str) -> str:
    return filename.replace("\\", "/").rsplit("/", 1)[-1]


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="knora-agent")


@router.post(
    "/v1/workspaces/{workspace_id}/documents",
    response_model=IngestionResponse | PdfSubmissionResponse,
)
async def ingest_document(
    workspace_id: str,
    response: Response,
    source_key: Annotated[str, Form()],
    file: Annotated[UploadFile, File()],
    principal: Annotated[WorkspacePrincipal, Depends(require_documents_write)],
    service: Annotated[IngestDocument, Depends(get_ingest_document)],
    ingestion_jobs: Annotated[IngestionJobs | None, Depends(get_ingestion_jobs)],
    embedding_configuration: Annotated[
        EmbeddingConfiguration, Depends(get_embedding_configuration)
    ],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> IngestionResponse | PdfSubmissionResponse:
    filename = safe_source_name(file.filename or "")
    media_type = media_type_for_filename(filename)
    declared_media_type = (file.content_type or "").split(";", 1)[0].casefold()
    if declared_media_type == "application/pdf" and media_type != "application/pdf":
        raise KnoraError("UNSUPPORTED_DOCUMENT_TYPE")
    if media_type == "application/pdf":
        if idempotency_key is None:
            raise KnoraError("MISSING_IDEMPOTENCY_KEY")
        if declared_media_type != "application/pdf":
            raise KnoraError("UNSUPPORTED_DOCUMENT_TYPE")
        if ingestion_jobs is None:
            raise KnoraError("PDF_INGESTION_NOT_CONFIGURED")
        result = await run_in_threadpool(
            ingestion_jobs.submit_pdf,
            PdfSubmissionCommand(
                workspace_id=workspace_id,
                source_key=source_key,
                source_name=filename,
                media_type=media_type,
                stream=file.file,
                idempotency_key=idempotency_key,
                configuration=PdfSubmissionConfiguration.milestone_two(
                    embedding_configuration=embedding_configuration,
                ),
            ),
            principal,
        )
        terminal_statuses = {"succeeded", "superseded", "failed"}
        response.status_code = (
            200
            if result.submission_outcome != "created" and result.status in terminal_statuses
            else 202
        )
        return PdfSubmissionResponse.model_validate(result, from_attributes=True)
    raw_content = await file.read(MAX_RAW_BYTES + 1)
    command = IngestDocumentCommand(
        workspace_id=workspace_id,
        source_key=source_key,
        source_name=filename,
        media_type=media_type,
        raw_content=raw_content,
        chunking_configuration=ChunkingConfiguration.milestone_one(),
        embedding_configuration=embedding_configuration,
    )
    result = await run_in_threadpool(service.execute, command, principal)
    response.status_code = 201 if result.outcome == "created" else 200
    return IngestionResponse.model_validate(result, from_attributes=True)


@router.get("/v1/workspaces/{workspace_id}/documents", response_model=DocumentListResponse)
def list_documents(
    workspace_id: str,
    principal: Annotated[WorkspacePrincipal, Depends(require_documents_read)],
    reader: Annotated[DocumentReader, Depends(get_document_reader)],
) -> DocumentListResponse:
    projection = reader.list_documents(workspace_id=workspace_id, principal=principal)
    return DocumentListResponse(
        documents=[
            DocumentResponse.model_validate(item, from_attributes=True)
            for item in projection.documents
        ]
    )


@router.get(
    "/v1/workspaces/{workspace_id}/documents/{document_id}", response_model=DocumentResponse
)
def read_document(
    workspace_id: str,
    document_id: str,
    principal: Annotated[WorkspacePrincipal, Depends(require_documents_read)],
    reader: Annotated[DocumentReader, Depends(get_document_reader)],
) -> DocumentResponse:
    projection = reader.read_document(
        workspace_id=workspace_id,
        document_id=document_id,
        principal=principal,
    )
    return DocumentResponse.model_validate(projection, from_attributes=True)


@router.post(
    "/v1/workspaces/{workspace_id}/documents/{document_id}/archive", response_model=DocumentResponse
)
def archive_document(
    workspace_id: str,
    document_id: str,
    principal: Annotated[WorkspacePrincipal, Depends(require_documents_write)],
    lifecycle: Annotated[DocumentLifecycleService, Depends(get_document_lifecycle)],
    revision: Annotated[int | None, Header(alias="If-Match")] = None,
) -> DocumentResponse:
    projection = lifecycle.archive(workspace_id, document_id, principal, revision)
    return DocumentResponse.model_validate(projection, from_attributes=True)


@router.post(
    "/v1/workspaces/{workspace_id}/documents/{document_id}/unarchive",
    response_model=DocumentResponse,
)
def unarchive_document(
    workspace_id: str,
    document_id: str,
    principal: Annotated[WorkspacePrincipal, Depends(require_documents_write)],
    lifecycle: Annotated[DocumentLifecycleService, Depends(get_document_lifecycle)],
    revision: Annotated[int | None, Header(alias="If-Match")] = None,
) -> DocumentResponse:
    projection = lifecycle.unarchive(workspace_id, document_id, principal, revision)
    return DocumentResponse.model_validate(projection, from_attributes=True)


@router.post(
    "/v1/workspaces/{workspace_id}/documents/{document_id}/deletion-request",
    response_model=DocumentDeletionRequestResponse,
    status_code=202,
)
def request_document_deletion(
    workspace_id: str,
    document_id: str,
    principal: Annotated[WorkspacePrincipal, Depends(require_documents_delete)],
    lifecycle: Annotated[DocumentLifecycleService, Depends(get_document_lifecycle)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> DocumentDeletionRequestResponse:
    if not idempotency_key:
        raise KnoraError("MISSING_IDEMPOTENCY_KEY")
    projection = lifecycle.request_deletion(
        workspace_id,
        document_id,
        principal,
        idempotency_key,
    )
    return DocumentDeletionRequestResponse.model_validate(projection, from_attributes=True)


@router.get(
    "/v1/workspaces/{workspace_id}/operator/traces/{trace_id}",
    response_model=OperatorTraceResponse,
)
def read_operator_trace(
    workspace_id: str,
    trace_id: str,
    principal: Annotated[WorkspacePrincipal, Depends(require_operator_read)],
    service: Annotated[OperatorObservability, Depends(get_operator_observability)],
) -> OperatorTraceResponse:
    try:
        projection = service.read_trace(
            trace_id=trace_id, workspace_id=workspace_id, principal=principal
        )
    except LookupError as error:
        raise KnoraError(
            "OPERATOR_OBSERVATION_NOT_FOUND"
            if "not found" in str(error).casefold()
            else "OPERATOR_OBSERVATION_FAILED"
        ) from error
    except (RuntimeError, ValueError) as error:
        raise KnoraError("OPERATOR_OBSERVATION_FAILED") from error
    return OperatorTraceResponse.model_validate(projection, from_attributes=True)


@router.get(
    "/v1/workspaces/{workspace_id}/operator/evaluations/{report_id}",
    response_model=OperatorEvaluationResponse,
)
def read_operator_evaluation(
    workspace_id: str,
    report_id: str,
    principal: Annotated[WorkspacePrincipal, Depends(require_operator_read)],
    service: Annotated[OperatorObservability, Depends(get_operator_observability)],
) -> OperatorEvaluationResponse:
    try:
        projection = service.read_evaluation(
            report_id=report_id, workspace_id=workspace_id, principal=principal
        )
    except LookupError as error:
        raise KnoraError(
            "OPERATOR_OBSERVATION_NOT_FOUND"
            if "not found" in str(error).casefold()
            else "OPERATOR_OBSERVATION_FAILED"
        ) from error
    except (RuntimeError, ValueError) as error:
        raise KnoraError("OPERATOR_OBSERVATION_FAILED") from error
    return OperatorEvaluationResponse.model_validate(projection, from_attributes=True)


@router.get(
    "/v1/workspaces/{workspace_id}/operator/operations",
    response_model=OperatorOperationsResponse,
)
def read_operator_operations(
    workspace_id: str,
    principal: Annotated[WorkspacePrincipal, Depends(require_operator_read)],
    service: Annotated[OperatorObservability, Depends(get_operator_observability)],
) -> OperatorOperationsResponse:
    try:
        snapshot = service.read_operations(workspace_id=workspace_id, principal=principal)
    except LookupError as error:
        raise KnoraError("OPERATOR_OBSERVATION_NOT_FOUND") from error
    except (RuntimeError, ValueError) as error:
        raise KnoraError("OPERATOR_OBSERVATION_FAILED") from error
    if isinstance(snapshot, dict):
        return OperatorOperationsResponse.model_validate(snapshot)
    return OperatorOperationsResponse(
        workspace_id=workspace_id,
        metrics=snapshot.metrics,
        configuration_version=snapshot.configuration_version,
        histograms={
            name: {
                "count": histogram.count,
                "sum": histogram.sum,
                "buckets": list(histogram.buckets),
            }
            for name, histogram in snapshot.histograms.items()
        },
    )


def _tool_lifecycle_payload(result) -> dict[str, object]:
    if isinstance(result, ToolLifecycleUnavailable):
        return {"availability": "unavailable", "items": [], "code": None}
    if isinstance(result, ToolLifecycleObservationFailure):
        return {"availability": "observation_failure", "items": [], "code": result.code}
    if not isinstance(result, ToolLifecycleListProjection):
        raise KnoraError("OPERATOR_OBSERVATION_FAILED")
    return {
        "availability": "available",
        "code": None,
        "items": [
            {
                "proposal": {
                    "proposal_id": item.proposal.proposal_id,
                    "state": item.proposal.state,
                    "revision": item.proposal.revision,
                },
                "approval": {
                    "decision": item.approval.decision,
                    "decided_at": item.approval.decided_at,
                    "actor_kind": item.approval.actor_kind,
                },
                "execution": (
                    {
                        "lifecycle": item.execution.lifecycle,
                        "revision": item.execution.revision,
                        "generation": item.execution.generation,
                        "observations": [
                            {
                                "sequence": observation.sequence,
                                "observation_type": observation.observation_type,
                                "failure_code": observation.failure_code,
                                "observed_at": observation.observed_at,
                            }
                            for observation in item.execution.observations
                        ],
                        "failure_code": item.execution.failure_code,
                        "finalized_at": item.execution.finalized_at,
                    }
                    if item.execution is not None
                    else None
                ),
                "reconciliation": (
                    {
                        "status": item.reconciliation.status,
                        "observation_type": item.reconciliation.observation_type,
                        "failure_code": item.reconciliation.failure_code,
                        "observed_at": item.reconciliation.observed_at,
                    }
                    if item.reconciliation is not None
                    else None
                ),
            }
            for item in result.items
        ],
    }


@router.get(
    "/v1/workspaces/{workspace_id}/operator/tool-lifecycle",
    response_model=ToolLifecycleResponse,
)
def read_tool_lifecycle(
    workspace_id: str,
    principal: Annotated[WorkspacePrincipal, Depends(require_operator_read)],
    reader: Annotated[ToolLifecycleProjectionReader, Depends(get_tool_lifecycle_reader)],
) -> ToolLifecycleResponse:
    try:
        result = reader.read_lifecycle(workspace_id=workspace_id, principal=principal)
    except KnoraError:
        raise
    except Exception as error:
        raise KnoraError("OPERATOR_OBSERVATION_FAILED") from error
    return ToolLifecycleResponse.model_validate(_tool_lifecycle_payload(result))


def _job_status_payload(projection) -> dict[str, object]:
    payload: dict[str, object] = {
        "ingestion_job_id": projection.ingestion_job_id,
        "status": projection.status,
        "attempt_count": projection.attempt_count,
        "max_attempts": projection.max_attempts,
        "created_at": projection.created_at,
        "started_at": projection.started_at,
        "updated_at": projection.updated_at,
        "terminal_at": projection.terminal_at,
        "target_document_version_id": projection.target_document_version_id,
        "current_document_version_id": projection.current_document_version_id,
        "served_document_version_id": projection.served_document_version_id,
        "serving_state": projection.serving_state,
        "failure_reason": projection.failure_reason,
        "error_code": projection.error_code,
        "replacement_document_version_id": projection.replacement_document_version_id,
        "replacement_ingestion_job_id": projection.replacement_ingestion_job_id,
        "reprocess_of_job_id": projection.reprocess_of_job_id,
        "poll_after_seconds": (
            5 if projection.status in {"queued", "processing", "retry_scheduled"} else 0
        ),
    }
    if projection.next_attempt_at is not None:
        payload["next_attempt_at"] = projection.next_attempt_at
    if projection.result_document_version_id is not None:
        payload["result"] = {"document_version_id": projection.result_document_version_id}
    return payload


@router.get(
    "/v1/workspaces/{workspace_id}/ingestion-jobs/{ingestion_job_id}",
    response_model=IngestionJobStatusResponse,
    response_model_exclude_none=False,
)
@router.get(
    "/v1/workspaces/{workspace_id}/jobs/{ingestion_job_id}",
    response_model=IngestionJobStatusResponse,
    response_model_exclude_none=False,
    include_in_schema=False,
)
async def get_ingestion_job_status(
    workspace_id: str,
    ingestion_job_id: str,
    response: Response,
    principal: Annotated[WorkspacePrincipal, Depends(require_documents_read)],
    ingestion_jobs: Annotated[IngestionJobs | None, Depends(get_ingestion_jobs)],
) -> JSONResponse:
    if ingestion_jobs is None:
        raise KnoraError("PDF_INGESTION_NOT_CONFIGURED")
    projection = await run_in_threadpool(
        ingestion_jobs.get_job_status,
        ingestion_job_id=ingestion_job_id,
        principal=principal,
    )
    response.headers["Cache-Control"] = "no-store"
    return JSONResponse(
        content=jsonable_encoder(_job_status_payload(projection)),
        headers={"Cache-Control": "no-store"},
    )


@router.post(
    "/v1/workspaces/{workspace_id}/document-versions/{document_version_id}/reprocess",
    response_model=ReprocessResponse,
)
async def reprocess_document_version(
    workspace_id: str,
    document_version_id: str,
    payload: ReprocessRequest,
    response: Response,
    principal: Annotated[WorkspacePrincipal, Depends(require_documents_write)],
    ingestion_jobs: Annotated[IngestionJobs | None, Depends(get_ingestion_jobs)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> ReprocessResponse:
    if ingestion_jobs is None:
        raise KnoraError("PDF_INGESTION_NOT_CONFIGURED")
    result = await run_in_threadpool(
        ingestion_jobs.reprocess_document_version,
        ReprocessDocumentVersionCommand(
            workspace_id=workspace_id,
            document_version_id=document_version_id,
            config_mode=payload.config_mode,
            config_source_job_id=payload.config_source_job_id,
            idempotency_key=idempotency_key or "",
        ),
        principal,
    )
    response.status_code = (
        200
        if result.outcome != "created" and result.status in {"succeeded", "superseded", "failed"}
        else 202
    )
    return ReprocessResponse(
        ingestion_job_id=result.ingestion_job_id,
        document_version_id=result.document_version_id,
        outcome=result.outcome,
        status=result.status,
    )
