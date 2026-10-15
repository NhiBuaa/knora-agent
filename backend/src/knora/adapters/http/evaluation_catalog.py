"""One workspace-scoped listing for Builder drafts and native evaluation datasets."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field

from knora.adapters.http.routes import require_operator_read
from knora.domain.access import WorkspacePrincipal
from knora.evaluation.contracts import DatasetReference, LegacyDatasetReference

router = APIRouter(prefix="/v1/workspaces/{workspace_id}/evaluation", tags=["evaluation-datasets"])


class CatalogCaseResponse(BaseModel):
    id: str
    question: str
    expected_behavior: Literal["ANSWER", "REFUSAL"]
    category: str


class CatalogDatasetResponse(BaseModel):
    id: str
    workspace_id: str
    name: str
    status: Literal["DRAFT", "FROZEN"]
    format: str
    reference: DatasetReference | LegacyDatasetReference | None
    case_count: int
    cases: list[CatalogCaseResponse] = Field(default_factory=list)


class CatalogResponse(BaseModel):
    items: list[CatalogDatasetResponse]


@router.get("/datasets", response_model=CatalogResponse)
def list_datasets(
    workspace_id: str,
    request: Request,
    response: Response,
    principal: Annotated[WorkspacePrincipal, Depends(require_operator_read)],
) -> CatalogResponse:
    drafts = request.app.state.dataset_service.list_datasets(workspace_id, principal)
    items = []
    for draft in drafts:
        frozen = (
            request.app.state.dataset_service.get_frozen_dataset(workspace_id, draft.id, principal)
            if draft.status == "FROZEN"
            else None
        )
        cases = frozen.gold.cases if frozen else draft.cases
        items.append(
            CatalogDatasetResponse(
                id=draft.id,
                workspace_id=draft.workspace_id,
                name=draft.name,
                status=draft.status,
                format="pdf-gold-v1",
                reference=frozen.reference if frozen else None,
                case_count=len(cases),
                cases=[
                    CatalogCaseResponse(
                        id=case.case_id,
                        question=case.question,
                        expected_behavior=case.expected,
                        category=case.category,
                    )
                    for case in cases
                ],
            )
        )
    for entry in request.app.state.evaluation_catalog.list_datasets(workspace_id):
        reference = entry.reference
        items.append(
            CatalogDatasetResponse(
                id=reference.dataset_id,
                workspace_id=reference.workspace_id,
                name=reference.dataset_id,
                status="FROZEN",
                format=reference.format,
                reference=reference,
                case_count=len(entry.dataset.cases),
                cases=[
                    CatalogCaseResponse(
                        id=case.id,
                        question=case.question,
                        expected_behavior=case.expected_behavior,
                        category=case.category,
                    )
                    for case in entry.dataset.cases
                ],
            )
        )
    response.headers["Cache-Control"] = "no-store"
    return CatalogResponse(items=items)
