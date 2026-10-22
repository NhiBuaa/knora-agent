"""Typed Workspace-scoped PDF draft and source-review routes."""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Header, Path, Query, Request, Response, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict, Field

from knora.access.identity import Identity
from knora.adapters.http.routes import require_operator_read
from knora.adapters.http.workspaces import private, require_identity
from knora.domain.access import WorkspacePrincipal
from knora.domain.errors import KnoraError
from knora.evaluation.contracts import Case
from knora.evaluation.datasets import Dataset, DatasetService, DatasetSource

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
    status: Literal["DRAFT", "FROZEN"]
    revision: int = 0
    cases: list[dict] = Field(default_factory=list)
    reviews: list[dict] = Field(default_factory=list)
    reference: dict | None = None
    proposal_batches: list[dict] = Field(default_factory=list)


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


class SaveCaseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case: dict
    expected_revision: int = Field(ge=0)


class ReviewCaseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["ACCEPTED", "REJECTED"]
    expected_revision: int = Field(ge=0)
    note: str = Field(min_length=1, max_length=2000)


class RevisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=0)


class FreezeRequest(RevisionRequest):
    gold_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class ProposalInputRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_ids: list[str] = Field(min_length=1)
    profile_id: str = Field(min_length=1, max_length=100)
    language: Literal["vi", "en"]
    count: int = Field(ge=1, le=12)


class GenerateProposalsRequest(ProposalInputRequest):
    expected_revision: int = Field(ge=0)
    input_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    request_id: str = Field(min_length=1, max_length=100)


class ImportProposalRequest(RevisionRequest):
    question: str | None = Field(default=None, min_length=1)
    reference_answer: str | None = Field(default=None, min_length=1)


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


def _dataset_response(dataset: Dataset) -> DatasetResponse:
    return DatasetResponse(
        id=dataset.id,
        workspace_id=dataset.workspace_id,
        name=dataset.name,
        status=dataset.status,
        revision=dataset.revision,
        cases=[asdict(case) for case in dataset.cases],
        reviews=[asdict(review) for review in dataset.reviews],
        reference=asdict(dataset.reference) if dataset.reference else None,
        proposal_batches=list(getattr(dataset, "proposal_batches", ())),
    )


@router.post("/datasets", status_code=201, response_model=DatasetResponse)
def create_dataset(
    workspace_id: str,
    payload: CreateDatasetRequest,
    response: Response,
    principal: Annotated[WorkspacePrincipal, Depends(require_operator_read)],
    service: Annotated[DatasetService, Depends(get_dataset_service)],
) -> DatasetResponse:
    response.headers["Cache-Control"] = "no-store"
    return _dataset_response(service.create_dataset(workspace_id, payload.name, principal))


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
        **_dataset_response(dataset).model_dump(),
        sources=[_source_response(source) for source in sources],
    )


@router.get("/datasets/{dataset_id}/proposals", response_model=dict)
def get_proposals(
    workspace_id: str,
    dataset_id: str,
    response: Response,
    principal: Annotated[WorkspacePrincipal, Depends(require_operator_read)],
    service: Annotated[DatasetService, Depends(get_dataset_service)],
) -> dict:
    private(response)
    profiles = service.proposal_profiles(workspace_id, principal)
    dataset = service.get_dataset(workspace_id, dataset_id, principal)
    return {"profiles": profiles, "batches": list(dataset.proposal_batches)}


@router.post("/datasets/{dataset_id}/proposals/preflight", response_model=dict)
def proposal_preflight(
    workspace_id: str,
    dataset_id: str,
    payload: ProposalInputRequest,
    response: Response,
    principal: Annotated[WorkspacePrincipal, Depends(require_operator_read)],
    service: Annotated[DatasetService, Depends(get_dataset_service)],
) -> dict:
    private(response)
    return service.proposal_preflight(
        workspace_id,
        dataset_id,
        tuple(payload.source_ids),
        payload.profile_id,
        payload.language,
        payload.count,
        principal,
    )


@router.post("/datasets/{dataset_id}/proposals", response_model=dict)
async def generate_proposals(
    workspace_id: str,
    dataset_id: str,
    payload: GenerateProposalsRequest,
    response: Response,
    principal: Annotated[WorkspacePrincipal, Depends(require_operator_read)],
    service: Annotated[DatasetService, Depends(get_dataset_service)],
) -> dict:
    private(response)
    return await service.generate_proposals(
        workspace_id,
        dataset_id,
        tuple(payload.source_ids),
        payload.profile_id,
        payload.language,
        payload.count,
        payload.expected_revision,
        payload.input_digest,
        payload.request_id,
        principal,
    )


@router.post(
    "/datasets/{dataset_id}/proposals/{batch_id}/drafts/{draft_id}/import",
    response_model=DatasetResponse,
)
def import_proposal(
    workspace_id: str,
    dataset_id: str,
    batch_id: str,
    draft_id: str,
    payload: ImportProposalRequest,
    response: Response,
    principal: Annotated[WorkspacePrincipal, Depends(require_operator_read)],
    service: Annotated[DatasetService, Depends(get_dataset_service)],
) -> DatasetResponse:
    private(response)
    return _dataset_response(
        service.import_proposal(
            workspace_id,
            dataset_id,
            batch_id,
            draft_id,
            payload.expected_revision,
            principal,
            question=payload.question,
            reference_answer=payload.reference_answer,
        )
    )


@router.put("/datasets/{dataset_id}/cases/{case_id}", response_model=DatasetResponse)
def save_case(
    workspace_id: str,
    dataset_id: str,
    case_id: str,
    payload: SaveCaseRequest,
    response: Response,
    principal: Annotated[WorkspacePrincipal, Depends(require_operator_read)],
    service: Annotated[DatasetService, Depends(get_dataset_service)],
) -> DatasetResponse:
    private(response)
    if payload.case.get("case_id") != case_id:
        raise KnoraError("EVALUATION_CASE_INVALID")
    try:
        case = Case.from_dict(payload.case)
    except (TypeError, ValueError) as error:
        raise KnoraError("EVALUATION_CASE_INVALID") from error
    return _dataset_response(
        service.save_case(workspace_id, dataset_id, case, payload.expected_revision, principal)
    )


@router.delete("/datasets/{dataset_id}/cases/{case_id}", response_model=DatasetResponse)
def delete_case(
    workspace_id: str,
    dataset_id: str,
    case_id: str,
    response: Response,
    expected_revision: Annotated[int, Header(alias="If-Match-Revision", ge=0)],
    principal: Annotated[WorkspacePrincipal, Depends(require_operator_read)],
    service: Annotated[DatasetService, Depends(get_dataset_service)],
) -> DatasetResponse:
    private(response)
    return _dataset_response(
        service.delete_case(workspace_id, dataset_id, case_id, expected_revision, principal)
    )


@router.post("/datasets/{dataset_id}/cases/{case_id}/review", response_model=DatasetResponse)
def review_case(
    workspace_id: str,
    dataset_id: str,
    case_id: str,
    payload: ReviewCaseRequest,
    response: Response,
    principal: Annotated[WorkspacePrincipal, Depends(require_operator_read)],
    identity: Annotated[Identity, Depends(require_identity)],
    service: Annotated[DatasetService, Depends(get_dataset_service)],
) -> DatasetResponse:
    private(response)
    return _dataset_response(
        service.review_case(
            workspace_id,
            dataset_id,
            case_id,
            payload.decision,
            payload.expected_revision,
            principal,
            identity=identity,
            note=payload.note,
        )
    )


@router.post("/datasets/{dataset_id}/freeze", response_model=dict)
def freeze_dataset(
    workspace_id: str,
    dataset_id: str,
    payload: FreezeRequest,
    response: Response,
    principal: Annotated[WorkspacePrincipal, Depends(require_operator_read)],
    identity: Annotated[Identity, Depends(require_identity)],
    service: Annotated[DatasetService, Depends(get_dataset_service)],
) -> dict:
    private(response)
    return json.loads(
        service.freeze_dataset(
            workspace_id,
            dataset_id,
            payload.expected_revision,
            principal,
            identity=identity,
            gold_digest=payload.gold_digest,
        ).to_json()
    )


@router.get("/datasets/{dataset_id}/gold", response_model=dict)
def get_frozen_gold(
    workspace_id: str,
    dataset_id: str,
    response: Response,
    principal: Annotated[WorkspacePrincipal, Depends(require_operator_read)],
    service: Annotated[DatasetService, Depends(get_dataset_service)],
    version: Annotated[int | None, Query(ge=1)] = None,
) -> dict:
    private(response)
    return json.loads(
        service.get_frozen_dataset(workspace_id, dataset_id, principal, version=version).to_json()
    )


@router.get("/datasets/{dataset_id}/gold-preview", response_model=dict)
def preview_gold(
    workspace_id: str,
    dataset_id: str,
    response: Response,
    principal: Annotated[WorkspacePrincipal, Depends(require_operator_read)],
    service: Annotated[DatasetService, Depends(get_dataset_service)],
) -> dict:
    private(response)
    gold = service.preview_gold(workspace_id, dataset_id, principal)
    return {"gold": gold.to_dict(), "digest": gold.digest}


@router.post("/datasets/{dataset_id}/revisions", response_model=DatasetResponse)
def reopen_dataset(
    workspace_id: str,
    dataset_id: str,
    payload: RevisionRequest,
    response: Response,
    principal: Annotated[WorkspacePrincipal, Depends(require_operator_read)],
    service: Annotated[DatasetService, Depends(get_dataset_service)],
) -> DatasetResponse:
    private(response)
    return _dataset_response(
        service.reopen_dataset(workspace_id, dataset_id, payload.expected_revision, principal)
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
