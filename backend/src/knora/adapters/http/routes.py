from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Header, Request, Response, UploadFile
from starlette.concurrency import run_in_threadpool

from knora.access.api_keys import ApiKeyAuthenticator
from knora.adapters.http.schemas import HealthResponse, IngestionResponse, PdfSubmissionResponse
from knora.domain.access import WorkspacePrincipal
from knora.domain.errors import KnoraError
from knora.ingestion.interface import IngestDocumentCommand
from knora.ingestion.jobs import IngestionJobs, PdfSubmissionCommand, PdfSubmissionConfiguration
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
