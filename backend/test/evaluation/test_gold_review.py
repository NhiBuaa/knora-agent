from dataclasses import replace
from io import BytesIO
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from knora.access.identity import Identity
from knora.adapters.object_store.filesystem import FileSystemObjectStore
from knora.adapters.pdf.pypdf import PypdfTextExtractor
from knora.adapters.postgres.database import Base
from knora.adapters.postgres.evaluation_datasets import PostgresDatasetStore
from knora.adapters.postgres.evaluation_datasets_tables import (
    DatasetDraftTable,
    DatasetSourceTable,
    EvaluationGoldVersionTable,
    ExtractionSnapshotTable,
)
from knora.adapters.postgres.tables import (
    DocumentTable,
    DocumentVersionTable,
    OriginalSourceObjectTable,
    WorkspaceTable,
)
from knora.domain.access import WorkspacePrincipal
from knora.domain.errors import KnoraError
from knora.evaluation.contracts import Case, EvidenceAnchor, EvidenceGroup, NoAnswerScope
from knora.evaluation.datasets import DatasetService
from knora.ingestion.pdf import PdfExtractionConfiguration

OWNER = WorkspacePrincipal(
    "w1",
    "owner",
    (
        "operator:read",
        "documents:read",
        "documents:write",
        "evaluations:write",
        "evaluations:approve",
    ),
)
IDENTITY = Identity("https://identity.example", "owner", OWNER.capabilities)


@pytest.fixture
def builder(tmp_path):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(
        engine,
        tables=[
            table.__table__
            for table in (
                WorkspaceTable,
                DocumentTable,
                DocumentVersionTable,
                OriginalSourceObjectTable,
                DatasetDraftTable,
                DatasetSourceTable,
                ExtractionSnapshotTable,
                EvaluationGoldVersionTable,
            )
        ],
    )
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory.begin() as session:
        session.add(WorkspaceTable(id="w1", name="workspace"))
    service = DatasetService(
        PostgresDatasetStore(factory),
        FileSystemObjectStore(tmp_path),
        PypdfTextExtractor(),
        PdfExtractionConfiguration.layout_preserving(),
    )
    dataset = service.create_dataset("w1", "Manual gold", OWNER)
    # Failed extraction intentionally remains eligible for original-PDF human verification.
    source = service.upload_source(
        "w1", dataset.id, "one.pdf", "application/pdf", BytesIO(b"%PDF-test"), "one", OWNER
    )
    case = Case(
        "answer",
        "What?",
        "ANSWER",
        "Answer",
        ("Answer",),
        "en",
        "single-hop",
        (EvidenceGroup((EvidenceAnchor(source.document_version_id, 1, "Answer"),)),),
    )
    return service, dataset.id, source, case


def review(service, dataset_id, case_id, decision="ACCEPTED"):
    draft = service.get_dataset("w1", dataset_id, OWNER)
    return service.review_case(
        "w1",
        dataset_id,
        case_id,
        decision,
        draft.revision,
        OWNER,
        identity=IDENTITY,
        note="Verified question, answer and evidence against original PDF.",
    )


def freeze(service, dataset_id):
    draft = service.get_dataset("w1", dataset_id, OWNER)
    gold = service.preview_gold("w1", dataset_id, OWNER)
    return service.freeze_dataset(
        "w1", dataset_id, draft.revision, OWNER, identity=IDENTITY, gold_digest=gold.digest
    )


def test_rejected_case_is_visible_in_draft_but_not_frozen_gold(builder):
    service, dataset_id, source, case = builder
    service.save_case("w1", dataset_id, case, 1, OWNER)
    refusal = Case(
        "reject",
        "Unknown?",
        "REFUSAL",
        None,
        (),
        "en",
        "no-answer",
        (),
        no_answer_scope=NoAnswerScope(
            (source.document_version_id,), "Searched entire original PDF"
        ),
    )
    service.save_case("w1", dataset_id, refusal, 2, OWNER)
    review(service, dataset_id, "answer")
    review(service, dataset_id, "reject", "REJECTED")
    frozen = freeze(service, dataset_id)
    assert [case.case_id for case in frozen.gold.cases] == ["answer"]
    assert len(service.get_dataset("w1", dataset_id, OWNER).cases) == 2
    assert frozen.approval.owner_issuer == "https://identity.example"
    assert frozen.approval.owner_subject == "owner"
    assert source.status == "FAILED"


def test_stale_digest_cannot_approve_different_gold(builder):
    service, dataset_id, _, case = builder
    service.save_case("w1", dataset_id, case, 1, OWNER)
    draft = review(service, dataset_id, "answer")
    with pytest.raises(KnoraError, match="EVALUATION_GOLD_DIGEST_CONFLICT"):
        service.freeze_dataset(
            "w1", dataset_id, draft.revision, OWNER, identity=IDENTITY, gold_digest="0" * 64
        )
    assert service.get_dataset("w1", dataset_id, OWNER).status == "DRAFT"


def test_review_requires_approve_and_matching_authenticated_actor_before_lookup(builder):
    service, dataset_id, _, _ = builder
    writer = replace(OWNER, capabilities=("operator:read", "evaluations:write"))
    with pytest.raises(KnoraError, match="CAPABILITY_ACCESS_DENIED"):
        service.review_case(
            "w1", "missing", "missing", "ACCEPTED", 0, writer, identity=IDENTITY, note="reviewed"
        )
    with pytest.raises(KnoraError, match="WORKSPACE_ACCESS_DENIED"):
        service.review_case(
            "w1",
            dataset_id,
            "missing",
            "ACCEPTED",
            0,
            OWNER,
            identity=replace(IDENTITY, subject="other"),
            note="reviewed",
        )


def test_source_addition_invalidates_review_and_freeze_revision(builder):
    service, dataset_id, _, case = builder
    service.save_case("w1", dataset_id, case, 1, OWNER)
    reviewed = review(service, dataset_id, "answer")
    service.upload_source(
        "w1", dataset_id, "two.pdf", "application/pdf", BytesIO(b"%PDF-two"), "two", OWNER
    )
    draft = service.get_dataset("w1", dataset_id, OWNER)
    assert draft.revision == reviewed.revision + 1
    assert not draft.reviews
    with pytest.raises(KnoraError, match="EVALUATION_GOLD_NOT_READY"):
        service.preview_gold("w1", dataset_id, OWNER)


def test_new_revision_keeps_previous_frozen_version_byte_for_byte(builder):
    service, dataset_id, _, case = builder
    service.save_case("w1", dataset_id, case, 1, OWNER)
    review(service, dataset_id, "answer")
    first = freeze(service, dataset_id)
    first_bytes = first.to_json()
    draft = service.get_dataset("w1", dataset_id, OWNER)
    draft = service.reopen_dataset("w1", dataset_id, draft.revision, OWNER)
    assert not draft.reviews
    service.save_case("w1", dataset_id, replace(case, question="Changed?"), draft.revision, OWNER)
    review(service, dataset_id, "answer")
    second = freeze(service, dataset_id)
    assert second.reference.version == 2
    assert service.get_frozen_dataset("w1", dataset_id, OWNER, version=1).to_json() == first_bytes
    assert first.reference.digest != second.reference.digest


def test_deleting_a_context_case_cannot_leave_a_dangling_dependency(builder):
    service, dataset_id, _, case = builder
    service.save_case("w1", dataset_id, case, 1, OWNER)
    dependent = replace(case, case_id="follow", context_dependencies=("answer",))
    service.save_case("w1", dataset_id, dependent, 2, OWNER)
    with pytest.raises(KnoraError, match="EVALUATION_CASE_INVALID"):
        service.delete_case("w1", dataset_id, "answer", 3, OWNER)
    assert len(service.get_dataset("w1", dataset_id, OWNER).cases) == 2


def test_stale_edit_and_frozen_mutation_preserve_approved_gold(builder):
    service, dataset_id, _, case = builder
    service.save_case("w1", dataset_id, case, 1, OWNER)
    reviewed = review(service, dataset_id, "answer")
    with pytest.raises(KnoraError, match="EVALUATION_DATASET_REVISION_CONFLICT"):
        service.save_case("w1", dataset_id, replace(case, question="Changed?"), 2, OWNER)
    assert service.get_dataset("w1", dataset_id, OWNER) == reviewed
    frozen = freeze(service, dataset_id)
    with pytest.raises(KnoraError, match="EVALUATION_DATASET_FROZEN"):
        service.save_case(
            "w1", dataset_id, replace(case, question="Changed?"), reviewed.revision + 1, OWNER
        )
    with pytest.raises(KnoraError, match="EVALUATION_DATASET_FROZEN"):
        service.upload_source(
            "w1", dataset_id, "two.pdf", "application/pdf", BytesIO(b"%PDF-two"), "two", OWNER
        )
    assert len(service.list_sources("w1", dataset_id, OWNER)) == 1
    assert service.get_frozen_dataset("w1", dataset_id, OWNER).to_json() == frozen.to_json()


def test_accepted_followup_cannot_omit_rejected_context_from_gold(builder):
    service, dataset_id, _, case = builder
    service.save_case("w1", dataset_id, case, 1, OWNER)
    service.save_case(
        "w1",
        dataset_id,
        replace(case, case_id="follow", context_dependencies=("answer",)),
        2,
        OWNER,
    )
    review(service, dataset_id, "answer", "REJECTED")
    review(service, dataset_id, "follow")
    with pytest.raises(KnoraError, match="EVALUATION_CASE_INVALID"):
        service.preview_gold("w1", dataset_id, OWNER)


def test_anchored_offsets_must_match_exact_extraction_snapshot(builder):
    service, dataset_id, _, case = builder
    pdf = Path(__file__).resolve().parents[3] / "docs/assets/readme/community-garden-guide.pdf"
    source = service.upload_source(
        "w1", dataset_id, "guide.pdf", "application/pdf", BytesIO(pdf.read_bytes()), "guide", OWNER
    )
    snapshot = service.get_snapshot("w1", dataset_id, source.id, OWNER)
    page = snapshot.pages[0]
    anchor = EvidenceAnchor(
        source.document_version_id,
        page.page_number,
        page.text[:10],
        snapshot.id,
        snapshot.extraction_sha256,
        0,
        10,
    )
    anchored = replace(case, evidence_groups=(EvidenceGroup((anchor,)),))
    saved = service.save_case("w1", dataset_id, anchored, 2, OWNER)
    with pytest.raises(KnoraError, match="EVALUATION_GOLD_NOT_READY"):
        service.save_case(
            "w1",
            dataset_id,
            replace(
                anchored, evidence_groups=(EvidenceGroup((replace(anchor, quote="wrong text"),)),)
            ),
            saved.revision,
            OWNER,
        )
    assert service.get_dataset("w1", dataset_id, OWNER) == saved

    beyond_page = replace(anchor, quote=page.text, end_offset=len(page.text) + 10)
    with pytest.raises(KnoraError, match="EVALUATION_GOLD_NOT_READY"):
        service.save_case(
            "w1",
            dataset_id,
            replace(anchored, evidence_groups=(EvidenceGroup((beyond_page,)),)),
            saved.revision,
            OWNER,
        )


def test_cross_workspace_denial_precedes_draft_lookup(builder):
    service, dataset_id, _, case = builder
    with pytest.raises(KnoraError, match="WORKSPACE_ACCESS_DENIED"):
        service.save_case("other", dataset_id, case, 1, OWNER)
    assert not service.get_dataset("w1", dataset_id, OWNER).cases
