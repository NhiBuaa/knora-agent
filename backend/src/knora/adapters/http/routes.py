from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Header, Request, Response, UploadFile

from knora.access.api_keys import ApiKeyAuthenticator
from knora.adapters.http.schemas import HealthResponse, IngestionResponse
from knora.domain.access import WorkspacePrincipal
from knora.domain.errors import KnoraError
from knora.ingestion.interface import IngestDocumentCommand
from knora.ingestion.module import MAX_RAW_BYTES, IngestDocument
from knora.ingestion.processing import ChunkingConfiguration
from knora.providers.embedding import EmbeddingConfiguration

router = APIRouter()


def get_authenticator(request: Request) -> ApiKeyAuthenticator:
    return request.app.state.api_key_authenticator


def get_ingest_document(request: Request) -> IngestDocument:
    return request.app.state.ingest_document


def authenticate_principal(
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
    authenticator: Annotated[ApiKeyAuthenticator, Depends(get_authenticator)] = None,
) -> WorkspacePrincipal:
    return authenticator.authenticate(x_api_key)


def media_type_for_filename(filename: str) -> str:
    suffix = Path(filename).suffix.casefold()
    if suffix in {".md", ".markdown"}:
        return "text/markdown"
    if suffix in {"", ".txt", ".text"}:
        return "text/plain"
    raise KnoraError("UNSUPPORTED_DOCUMENT_TYPE")


def safe_source_name(filename: str) -> str:
    return filename.replace("\\", "/").rsplit("/", 1)[-1]


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="knora-agent")


@router.post("/v1/workspaces/{workspace_id}/documents", response_model=IngestionResponse)
async def ingest_document(
    workspace_id: str,
    response: Response,
    source_key: Annotated[str, Form()],
    file: Annotated[UploadFile, File()],
    principal: Annotated[WorkspacePrincipal, Depends(authenticate_principal)],
    service: Annotated[IngestDocument, Depends(get_ingest_document)],
) -> IngestionResponse:
    if principal.workspace_id != workspace_id:
        raise KnoraError("WORKSPACE_ACCESS_DENIED")

    filename = safe_source_name(file.filename or "")
    media_type = media_type_for_filename(filename)
    raw_content = await file.read(MAX_RAW_BYTES + 1)
    result = service.execute(
        IngestDocumentCommand(
            workspace_id=workspace_id,
            source_key=source_key,
            source_name=filename,
            media_type=media_type,
            raw_content=raw_content,
            chunking_configuration=ChunkingConfiguration.milestone_one(),
            embedding_configuration=EmbeddingConfiguration.milestone_one_local(),
        ),
        principal,
    )
    response.status_code = 201 if result.outcome == "created" else 200
    return IngestionResponse.model_validate(result, from_attributes=True)
