"""Typed Workspace-scoped PDF draft and source-review routes."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Header, Path, Request, Response, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict, Field

from knora.adapters.http.routes import require_operator_read
from knora.domain.access import WorkspacePrincipal
from knora.domain.errors import KnoraError
from knora.evaluation.datasets import DatasetService, DatasetSource

router = APIRouter(prefix="/v1/workspaces/{workspace_id}/evaluation", tags=["evaluation-datasets"])


def get_dataset_service(request: Request) -> DatasetService:
    return request.app.state.dataset_service


class CreateDatasetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)


class DatasetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workspace_id: str
    name: str
    status: Literal["DRAFT"]


class SourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    dataset_id: str
    document_id: str
    document_version_id: str
    filename: str
    raw_sha256: str
    byte_size: int
    status: Literal["PROCESSING", "READY", "FAILED"]
    failure_code: str | None
    snapshot_id: str | None


class DatasetDetailResponse(DatasetResponse):
    sources: list[SourceResponse]


class PageResponse(BaseModel):
    source_id: str
    document_version_id: str
    snapshot_id: str
    extraction_sha256: str
    configuration_sha256: str
    physical_page: int
    text: str
    content_checksum: str


def _source_response(source: DatasetSource) -> SourceResponse:
    return SourceResponse.model_validate(source, from_attributes=True)


@router.post("/datasets", status_code=201, response_model=DatasetResponse)
def create_dataset(
    workspace_id: str,
    payload: CreateDatasetRequest,
    response: Response,
    principal: Annotated[WorkspacePrincipal, Depends(require_operator_read)],
    service: Annotated[DatasetService, Depends(get_dataset_service)],
) -> DatasetResponse:
    response.headers["Cache-Control"] = "no-store"
    return DatasetResponse.model_validate(
        service.create_dataset(workspace_id, payload.name, principal), from_attributes=True
    )


@router.get("/datasets/{dataset_id}", response_model=DatasetDetailResponse)
def get_dataset(
    workspace_id: str,
    dataset_id: str,
    response: Response,
    principal: Annotated[WorkspacePrincipal, Depends(require_operator_read)],
    service: Annotated[DatasetService, Depends(get_dataset_service)],
) -> DatasetDetailResponse:
    dataset = service.get_dataset(workspace_id, dataset_id, principal)
    sources = service.list_sources(workspace_id, dataset_id, principal)
    response.headers["Cache-Control"] = "no-store"
    return DatasetDetailResponse(
        **DatasetResponse.model_validate(dataset, from_attributes=True).model_dump(),
        sources=[_source_response(source) for source in sources],
    )


@router.post("/datasets/{dataset_id}/sources", status_code=201, response_model=SourceResponse)
async def upload_source(
    workspace_id: str,
    dataset_id: str,
    response: Response,
    file: Annotated[UploadFile, File()],
    principal: Annotated[WorkspacePrincipal, Depends(require_operator_read)],
    service: Annotated[DatasetService, Depends(get_dataset_service)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> SourceResponse:
    if idempotency_key is None:
        raise KnoraError("MISSING_IDEMPOTENCY_KEY")
    source = await run_in_threadpool(
        service.upload_source,
        workspace_id,
        dataset_id,
        file.filename or "",
        file.content_type or "",
        file.file,
        idempotency_key,
        principal,
    )
    response.headers["Cache-Control"] = "no-store"
    return _source_response(source)


@router.get("/datasets/{dataset_id}/sources/{source_id}", response_model=SourceResponse)
def get_source(
    workspace_id: str,
    dataset_id: str,
    source_id: str,
    response: Response,
    principal: Annotated[WorkspacePrincipal, Depends(require_operator_read)],
    service: Annotated[DatasetService, Depends(get_dataset_service)],
) -> SourceResponse:
    source = service.get_source(workspace_id, dataset_id, source_id, principal)
    response.headers["Cache-Control"] = "no-store"
    return _source_response(source)


@router.post("/datasets/{dataset_id}/sources/{source_id}/retry", response_model=SourceResponse)
async def retry_extraction(
    workspace_id: str,
    dataset_id: str,
    source_id: str,
    response: Response,
    principal: Annotated[WorkspacePrincipal, Depends(require_operator_read)],
    service: Annotated[DatasetService, Depends(get_dataset_service)],
) -> SourceResponse:
    source = await run_in_threadpool(
        service.retry_extraction, workspace_id, dataset_id, source_id, principal
    )
    response.headers["Cache-Control"] = "no-store"
    return _source_response(source)


@router.get(
    "/datasets/{dataset_id}/sources/{source_id}/pages/{physical_page}", response_model=PageResponse
)
def get_source_page(
    workspace_id: str,
    dataset_id: str,
    source_id: str,
    physical_page: Annotated[int, Path(ge=1)],
    response: Response,
    principal: Annotated[WorkspacePrincipal, Depends(require_operator_read)],
    service: Annotated[DatasetService, Depends(get_dataset_service)],
) -> PageResponse:
    snapshot = service.get_snapshot(workspace_id, dataset_id, source_id, principal)
    source = service.get_source(workspace_id, dataset_id, source_id, principal)
    if snapshot is None:
        raise KnoraError("SOURCE_EXTRACTION_UNAVAILABLE")
    page = next((page for page in snapshot.pages if page.page_number == physical_page), None)
    if page is None:
        raise KnoraError("SOURCE_PAGE_NOT_FOUND")
    response.headers["Cache-Control"] = "no-store"
    return PageResponse(
        source_id=source.id,
        document_version_id=source.document_version_id,
        snapshot_id=snapshot.id,
        extraction_sha256=snapshot.extraction_sha256,
        configuration_sha256=snapshot.configuration_sha256,
        physical_page=page.page_number,
        text=page.text,
        content_checksum=page.content_checksum,
    )


@router.get("/datasets/{dataset_id}/sources/{source_id}/original", response_class=Response)
async def get_original(
    workspace_id: str,
    dataset_id: str,
    source_id: str,
    principal: Annotated[WorkspacePrincipal, Depends(require_operator_read)],
    service: Annotated[DatasetService, Depends(get_dataset_service)],
) -> Response:
    raw = await run_in_threadpool(
        service.read_original, workspace_id, dataset_id, source_id, principal
    )
    return Response(
        content=raw,
        media_type="application/pdf",
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )
