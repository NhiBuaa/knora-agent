from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Header, Request, Response, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from knora.access.api_keys import ApiKeyAuthenticator
from knora.adapters.http.schemas import (
    HealthResponse,
    IngestionJobStatusResponse,
    IngestionResponse,
    PdfSubmissionResponse,
    ReprocessRequest,
    ReprocessResponse,
)
from knora.domain.access import WorkspacePrincipal
from knora.domain.errors import KnoraError
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

router = APIRouter()


def get_authenticator(request: Request) -> ApiKeyAuthenticator:
    return request.app.state.api_key_authenticator


def get_ingest_document(request: Request) -> IngestDocument:
    return request.app.state.ingest_document


def get_embedding_configuration(request: Request) -> EmbeddingConfiguration:
    return request.app.state.embedding_configuration


def get_ingestion_jobs(request: Request) -> IngestionJobs | None:
    return getattr(request.app.state, "ingestion_jobs", None)


def authenticate_principal(
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
    authenticator: Annotated[ApiKeyAuthenticator, Depends(get_authenticator)] = None,
) -> WorkspacePrincipal:
    return authenticator.authenticate(x_api_key)


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
    principal: Annotated[WorkspacePrincipal, Depends(authenticate_principal)],
    service: Annotated[IngestDocument, Depends(get_ingest_document)],
    ingestion_jobs: Annotated[IngestionJobs | None, Depends(get_ingestion_jobs)],
    embedding_configuration: Annotated[
        EmbeddingConfiguration, Depends(get_embedding_configuration)
    ],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> IngestionResponse | PdfSubmissionResponse:
    if principal.workspace_id != workspace_id:
        raise KnoraError("WORKSPACE_ACCESS_DENIED")

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
    principal: Annotated[WorkspacePrincipal, Depends(authenticate_principal)],
    ingestion_jobs: Annotated[IngestionJobs | None, Depends(get_ingestion_jobs)],
) -> JSONResponse:
    if principal.workspace_id != workspace_id:
        raise KnoraError("WORKSPACE_ACCESS_DENIED")
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
    principal: Annotated[WorkspacePrincipal, Depends(authenticate_principal)],
    ingestion_jobs: Annotated[IngestionJobs | None, Depends(get_ingestion_jobs)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> ReprocessResponse:
    if principal.workspace_id != workspace_id:
        raise KnoraError("WORKSPACE_ACCESS_DENIED")
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
    response.status_code = 200 if result.outcome != "created" and result.status in {
        "succeeded", "superseded", "failed"
    } else 202
    return ReprocessResponse(
        ingestion_job_id=result.ingestion_job_id,
        document_version_id=result.document_version_id,
        outcome=result.outcome,
        status=result.status,
    )
