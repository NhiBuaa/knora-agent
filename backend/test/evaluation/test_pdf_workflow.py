"""Builder/Runner integration; Q&A transport is offline, never a live-quality acceptance."""

from dataclasses import asdict
from io import BytesIO
from pathlib import Path

import pytest
from test_gold_review import OWNER, builder, freeze, review  # noqa: F401
from test_runs import MemoryStore

from knora.domain.access import WorkspacePrincipal
from knora.evaluation.catalog import Milestone3Catalog
from knora.evaluation.contracts import (
    Case,
    EvidenceAnchor,
    EvidenceGroup,
    NoAnswerScope,
    digest_json,
)
from knora.evaluation.pdf_runtime import PdfRuntimeProfile
from knora.evaluation.runs import EvaluationRunService


@pytest.mark.asyncio
async def test_retained_pdf_to_reviewed_gold_to_new_observations_and_report(builder):  # noqa: F811
    datasets, dataset_id, _, _ = builder
    root = Path(__file__).resolve().parents[3]
    source = datasets.upload_source(
        "w1",
        dataset_id,
        "public.pdf",
        "application/pdf",
        BytesIO((root / "docs/assets/readme/community-garden-guide.pdf").read_bytes()),
        "public",
        OWNER,
    )
    assert source.status == "READY"
    snapshot = datasets.get_snapshot("w1", dataset_id, source.id, OWNER)
    page = snapshot.pages[0]
    quote = page.text[:40]
    anchor = EvidenceAnchor(
        source.document_version_id,
        page.page_number,
        quote,
        snapshot.id,
        snapshot.extraction_sha256,
        0,
        len(quote),
    )
    cases = (
        Case(
            "answer",
            "Quote the opening text of this guide.",
            "ANSWER",
            quote,
            (quote,),
            "en",
            "single-hop",
            (EvidenceGroup((anchor,)),),
        ),
        Case(
            "refusal",
            "Give an unspecified private password.",
            "REFUSAL",
            None,
            (),
            "en",
            "no-answer",
            (),
            no_answer_scope=NoAnswerScope(
                (source.document_version_id,), "Synthetic fixture scope reviewed for this test only"
            ),
        ),
    )
    for case in cases:
        draft = datasets.get_dataset("w1", dataset_id, OWNER)
        datasets.save_case("w1", dataset_id, case, draft.revision, OWNER)
    for case in cases:
        review(datasets, dataset_id, case.case_id)
    frozen = freeze(datasets, dataset_id)
    immutable = frozen.to_json()
    calls = []

    def prepare(gold):
        sources = {
            s.document_version_id: {
                "raw_sha256": s.raw_sha256,
                "status": "READY"
                if s.document_version_id == source.document_version_id
                else "FAILED",
                "chunk_set_id": "chunks"
                if s.document_version_id == source.document_version_id
                else None,
                "embedding_set_id": "embeddings"
                if s.document_version_id == source.document_version_id
                else None,
                "chunk_ids": ["chunk"]
                if s.document_version_id == source.document_version_id
                else [],
            }
            for s in gold.gold.sources
        }
        binding = {
            "schema_version": 1,
            "binding_id": "reviewed-test-binding",
            "reference": asdict(gold.reference),
            "retrieval_configuration_id": "retrieval-test",
            "embedding_configuration_id": "embedding-test",
            "generation_configuration_id": "generation-test",
            "generation": {"provider": "offline", "model": "fixture", "prompt_version": "prompt-1"},
            "candidate_budget": 8,
            "sources": sources,
            "anchors": {digest_json(asdict(anchor)): {"status": "READY", "chunk_ids": ["chunk"]}},
        }
        return {
            **binding,
            "approval": {
                "owner_issuer": "fixture",
                "owner_subject": "owner",
                "binding_digest": digest_json(binding),
            },
        }

    async def execute(case, _):
        calls.append(case.case_id)
        return {
            "case_id": case.case_id,
            "status": "OBSERVED",
            "trace_id": "trace-" + case.case_id,
            "decision": case.expected,
            "public_answer": quote if case.expected == "ANSWER" else None,
            "candidate_chunk_ids": ["chunk"],
            "generation_chunk_ids": ["chunk"] if case.expected == "ANSWER" else [],
            "citation_correctness": True,
        }

    runner = EvaluationRunService(
        Milestone3Catalog(root),
        MemoryStore(),
        (),
        datasets=datasets,
        pdf_profiles=(PdfRuntimeProfile("offline", "offline", prepare, execute),),
    )
    principal = WorkspacePrincipal(
        "w1", "owner", (*OWNER.capabilities, "evaluations:run", "questions:ask")
    )
    ready = runner.preflight(
        "w1", principal, dataset_id, ("answer", "refusal"), "offline", asdict(frozen.reference)
    )
    assert ready["status"] == "READY"
    run = runner.start_run("w1", principal, ready["preflight_id"], "workflow")
    await runner.process_run("w1", run["run_id"])
    saved = runner.read_run("w1", principal, run["run_id"])
    assert calls == ["answer", "refusal"]
    assert saved["report"]["population"]["selected"] == 2
    assert saved["report"]["retrieval"]["value"] == 1
    assert saved["report"]["cases"][1]["retrieval"]["value"] is None
    assert (
        saved["report"]["cases"][0]["evidence_groups"][0]["alternatives"][0][
            "extraction_snapshot_id"
        ]
        == snapshot.id
    )
    assert datasets.get_frozen_dataset("w1", dataset_id, OWNER, version=1).to_json() == immutable
