from dataclasses import replace
from hashlib import sha256

import pytest
from backend.test.evaluation.test_gold_review import OWNER, builder  # noqa: F401

from knora.evaluation.datasets import (
    Dataset,
    DatasetSource,
    ExtractionSnapshot,
    extraction_checksum,
)
from knora.evaluation.proposals import export_pdf_pages, map_review_packet
from knora.ingestion.pdf import NormalizedPdfPage


def inputs():
    dataset = Dataset("d1", "w1", "Review", "DRAFT", 2)
    pages = tuple(
        NormalizedPdfPage(n, text, sha256(text.encode()).hexdigest())
        for n, text in enumerate(("The garden opens in April.", "Members pay ten dollars."), 1)
    )
    source = DatasetSource(
        "s1",
        "d1",
        "doc1",
        "v1",
        "public.pdf",
        "a" * 64,
        20,
        "object",
        "upload",
        "READY",
        None,
        "snap1",
    )
    snapshot = ExtractionSnapshot("snap1", "s1", "b" * 64, extraction_checksum(pages), pages)
    return dataset, source, snapshot


def packet(chunks, identity):
    from evals.runners.ragas_review import build_review_packet

    return build_review_packet(
        [
            {
                "language": "vi",
                "question": "When and how much?",
                "reference_answer": "April; ten dollars.",
                "hops": [
                    {
                        "chunk_ref": chunks[0]["chunk_ref"],
                        "quote": "opens in April",
                        "necessary_claim": "Opens in April",
                    },
                    {
                        "chunk_ref": chunks[1]["chunk_ref"],
                        "quote": "ten dollars",
                        "necessary_claim": "Membership costs ten dollars",
                    },
                ],
            }
        ],
        chunks,
        identity,
        model="offline-fixture",
        prompt_version="v1",
    )


def test_pdf_export_and_ragas_packet_preserve_exact_source_and_offsets():
    dataset, source, snapshot = inputs()
    chunks, identity = export_pdf_pages(dataset, ((source, snapshot),))
    assert identity["workspace_id"] == "w1"
    assert identity["dataset_revision"] == 2
    assert identity["pdf_sources"][0]["raw_sha256"] == source.raw_sha256
    assert chunks[0]["chunk_ref"] == "v1#page-1"
    result = map_review_packet(packet(chunks, identity), chunks, identity, batch_id="batch1")
    assert result["diagnostics"] == []
    draft = result["drafts"][0]
    assert draft["review_status"] == "pending_owner_review"
    assert draft["case"]["category"] == "multi-hop"
    assert draft["case"]["expected"] == "ANSWER"
    assert len(draft["case"]["evidence_groups"]) == 2
    anchor = draft["case"]["evidence_groups"][0]["alternatives"][0]
    assert anchor["document_version_id"] == "v1"
    assert anchor["extraction_snapshot_id"] == "snap1"
    assert anchor["extraction_sha256"] == snapshot.extraction_sha256
    assert snapshot.pages[0].text[anchor["start_offset"] : anchor["end_offset"]] == anchor["quote"]
    assert result["generator"]["origin"] == "imported_candidates"
    assert dataset.cases == () and dataset.reviews == ()


@pytest.mark.parametrize("change", ["failed", "snapshot", "checksum", "page_checksum", "duplicate"])
def test_pdf_export_rejects_invalid_or_stale_sources(change):
    dataset, source, snapshot = inputs()
    if change == "failed":
        source = replace(source, status="FAILED")
    elif change == "snapshot":
        snapshot = replace(snapshot, id="other")
    elif change == "checksum":
        snapshot = replace(snapshot, extraction_sha256="c" * 64)
    elif change == "page_checksum":
        snapshot = replace(
            snapshot,
            pages=(replace(snapshot.pages[0], content_checksum="c" * 64), *snapshot.pages[1:]),
        )
    pairs = ((source, snapshot),) * (2 if change == "duplicate" else 1)
    with pytest.raises(ValueError, match="SOURCE_EXPORT_MISMATCH"):
        export_pdf_pages(dataset, pairs)


@pytest.mark.parametrize(
    "change,code",
    [
        ("identity", "SOURCE_EXPORT_MISMATCH"),
        ("unknown", "EVIDENCE_UNSUPPORTED"),
        ("quote", "EVIDENCE_UNSUPPORTED"),
        ("duplicate", "DUPLICATE_QUESTION"),
        ("count", "DRAFT_LIMIT"),
        ("language", "DRAFT_LANGUAGE_OR_SCHEMA_INVALID"),
    ],
)
def test_packet_mapping_reports_invalid_drafts_without_silent_drop(change, code):
    dataset, source, snapshot = inputs()
    chunks, identity = export_pdf_pages(dataset, ((source, snapshot),))
    review = packet(chunks, identity)
    if change == "identity":
        review["source"] = {**identity, "dataset_revision": 9}
    elif change == "unknown":
        review["drafts"][0]["proposed_necessary_hops"][0]["chunk_ref"] = "other#page-1"
    elif change == "quote":
        review["drafts"][0]["proposed_necessary_hops"][0]["quote"] = "not in the PDF"
    elif change == "duplicate":
        review["drafts"] *= 2
    elif change == "count":
        review["drafts"] *= 13
    elif change == "language":
        review["drafts"][0]["language"] = "fr"
    result = map_review_packet(review, chunks, identity, batch_id="batch1")
    assert any(item["code"] == code for item in result["diagnostics"])
    assert (
        len(result["drafts"]) == 0
        if change in {"identity", "count"}
        else len(result["drafts"]) == len(review["drafts"])
    )
    assert all(item.get("case") is None for item in result["drafts"] if item["status"] == "INVALID")


def test_repeated_quote_is_explicitly_ambiguous():
    dataset, source, snapshot = inputs()
    pages = (
        replace(
            snapshot.pages[0],
            text="opens in April and opens in April",
            content_checksum=sha256(b"opens in April and opens in April").hexdigest(),
        ),
        snapshot.pages[1],
    )
    snapshot = replace(snapshot, pages=pages, extraction_sha256=extraction_checksum(pages))
    chunks, identity = export_pdf_pages(dataset, ((source, snapshot),))
    result = map_review_packet(packet(chunks, identity), chunks, identity, batch_id="b")
    assert result["drafts"][0]["status"] == "INVALID"
    assert result["diagnostics"][0]["code"] == "EVIDENCE_AMBIGUOUS"


def test_duplicate_with_existing_gold_draft_needs_manual_resolution():
    dataset, source, snapshot = inputs()
    chunks, identity = export_pdf_pages(dataset, ((source, snapshot),))
    review = packet(chunks, identity)
    result = map_review_packet(
        review, chunks, identity, batch_id="b", existing_questions=("  WHEN and HOW much? ",)
    )
    assert result["drafts"][0]["status"] == "INVALID"
    assert result["diagnostics"][0]["code"] == "DUPLICATE_QUESTION"


def prepared_builder(builder):  # noqa: F811
    from knora.ingestion.pdf import PdfExtractionResult

    service, dataset_id, source, _ = builder
    _, _, snapshot = inputs()
    configuration = service._configuration
    result = PdfExtractionResult(
        snapshot.pages,
        (),
        configuration.parser_version,
        configuration.extraction_options_version,
        configuration.normalizer_version,
        configuration.tokenizer_name,
        configuration.tokenizer_version,
        configuration.chunking_policy_version,
        configuration.derivation_identity,
    )
    source = service._store.record_extraction(source, result, None)
    return service, dataset_id, source


@pytest.mark.asyncio
async def test_generation_is_saved_idempotent_and_import_requires_separate_review(builder):  # noqa: F811
    from knora.evaluation.proposals import ProposalProfile

    service, dataset_id, source = prepared_builder(builder)
    calls = []

    async def generate(chunks, identity, language, count):
        calls.append((language, count))
        return packet(chunks, identity)

    service._proposal_profiles = {
        "fixture": ProposalProfile("fixture", "offline", "offline-fixture", "v1", generate)
    }
    preflight = service.proposal_preflight(
        "w1", dataset_id, (source.id,), "fixture", "vi", 1, OWNER
    )
    assert preflight["status"] == "READY"
    revision = preflight["expected_revision"]
    batch = await service.generate_proposals(
        "w1",
        dataset_id,
        (source.id,),
        "fixture",
        "vi",
        1,
        revision,
        preflight["input_digest"],
        "request-1",
        OWNER,
    )
    assert batch["status"] == "COMPLETED"
    assert calls == [("vi", 1)]
    assert service.get_dataset("w1", dataset_id, OWNER).cases == ()
    replay = await service.generate_proposals(
        "w1",
        dataset_id,
        (source.id,),
        "fixture",
        "vi",
        1,
        revision,
        preflight["input_digest"],
        "request-1",
        OWNER,
    )
    assert replay == batch and len(calls) == 1
    draft = service.get_dataset("w1", dataset_id, OWNER)
    imported = service.import_proposal(
        "w1", dataset_id, batch["id"], "draft-01", draft.revision, OWNER
    )
    assert len(imported.cases) == 1 and imported.reviews == ()
    with pytest.raises(Exception, match="EVALUATION_GOLD_NOT_READY"):
        service.preview_gold("w1", dataset_id, OWNER)
    assert (
        service.get_dataset("w1", dataset_id, OWNER).proposal_batches[0]["result"]["source"][
            "pdf_sources"
        ][0]["raw_sha256"]
        == source.raw_sha256
    )


@pytest.mark.asyncio
async def test_generation_stale_live_and_read_only_do_not_dispatch(builder):  # noqa: F811
    from knora.domain.access import WorkspacePrincipal
    from knora.domain.errors import KnoraError
    from knora.evaluation.proposals import ProposalProfile

    service, dataset_id, source = prepared_builder(builder)

    async def forbidden(*args):
        raise AssertionError("must not dispatch")

    service._proposal_profiles = {
        "fixture": ProposalProfile("fixture", "offline", "fixture", "v1", forbidden),
        "live": ProposalProfile("live", "live", "cloudflare", "v1", forbidden),
    }
    assert (
        service.proposal_preflight("w1", dataset_id, (source.id,), "live", "en", 1, OWNER)["status"]
        == "BLOCKED"
    )
    preflight = service.proposal_preflight(
        "w1", dataset_id, (source.id,), "fixture", "en", 1, OWNER
    )
    for profile, digest in (("fixture", "0" * 64), ("live", preflight["input_digest"])):
        with pytest.raises(KnoraError):
            await service.generate_proposals(
                "w1",
                dataset_id,
                (source.id,),
                profile,
                "en",
                1,
                preflight["expected_revision"],
                digest,
                profile,
                OWNER,
            )
    reader = WorkspacePrincipal("w1", "reader", ("operator:read", "documents:read"))
    with pytest.raises(KnoraError):
        await service.generate_proposals(
            "w1",
            dataset_id,
            (source.id,),
            "fixture",
            "en",
            1,
            preflight["expected_revision"],
            preflight["input_digest"],
            "read",
            reader,
        )
    assert service.get_dataset("w1", dataset_id, OWNER).proposal_batches == ()


@pytest.mark.asyncio
async def test_uncertain_generation_is_retained_and_never_retried(builder):  # noqa: F811
    from knora.evaluation.proposals import ProposalProfile

    service, dataset_id, source = prepared_builder(builder)
    calls = []

    async def timeout(*args):
        calls.append(1)
        raise TimeoutError("private provider details must not be returned")

    service._proposal_profiles = {
        "fixture": ProposalProfile("fixture", "offline", "fixture", "v1", timeout)
    }
    preflight = service.proposal_preflight(
        "w1", dataset_id, (source.id,), "fixture", "en", 1, OWNER
    )
    args = (
        "w1",
        dataset_id,
        (source.id,),
        "fixture",
        "en",
        1,
        preflight["expected_revision"],
        preflight["input_digest"],
        "request",
        OWNER,
    )
    result = await service.generate_proposals(*args)
    assert result["status"] == "INDETERMINATE"
    assert "private provider" not in str(result)
    assert await service.generate_proposals(*args) == result
    assert calls == [1]


@pytest.mark.asyncio
async def test_real_ragas_prompt_pdf_draft_review_freeze_keeps_proposal_provenance(builder):  # noqa: F811
    from backend.test.evaluation.test_gold_review import freeze, review
    from evals.test.test_ragas_review import MockProvider

    from knora.evaluation.proposals import ragas_proposal_profile

    service, dataset_id, source = prepared_builder(builder)
    dataset, chunks, identity = service._proposal_input("w1", dataset_id, (source.id,), OWNER)
    proposed = packet(chunks, identity)["drafts"][0]
    provider = MockProvider(
        {
            "drafts": [
                {
                    "language": "vi",
                    "question": proposed["question"],
                    "reference_answer": proposed["reference_answer"],
                    "hops": proposed["proposed_necessary_hops"],
                }
            ]
        }
    )
    approval = {
        "ragas_generation_approved": True,
        "data_classification": "synthetic",
        "egress_approved": True,
        "manifest_sha256": identity["manifest_sha256"],
        "source_export_sha256": identity["source_export_sha256"],
        "approved_source_keys": identity["approved_source_keys"],
        "model": "offline-fixture",
    }
    service._proposal_profiles = {
        "fixture": ragas_proposal_profile(
            "fixture", "offline", "offline-fixture", "v1", provider, approval
        )
    }
    preflight = service.proposal_preflight(
        "w1", dataset_id, (source.id,), "fixture", "vi", 1, OWNER
    )
    batch = await service.generate_proposals(
        "w1",
        dataset_id,
        (source.id,),
        "fixture",
        "vi",
        1,
        dataset.revision,
        preflight["input_digest"],
        "real-ragas",
        OWNER,
    )
    assert batch["status"] == "COMPLETED"
    assert len(provider.prompts) == 1
    assert batch["result"]["generator"]["origin"] == "ragas_pydantic_prompt"
    draft = service.get_dataset("w1", dataset_id, OWNER)
    imported = service.import_proposal(
        "w1",
        dataset_id,
        batch["id"],
        "draft-01",
        draft.revision,
        OWNER,
        question="When does the garden open and what membership fee applies?",
        reference_answer="It opens in April; membership costs ten dollars.",
    )
    review(service, dataset_id, imported.cases[0].case_id)
    frozen = freeze(service, dataset_id)
    assert frozen.gold.cases[0].question != proposed["question"]
    assert len(frozen.gold.cases[0].evidence_groups) == 2
    assert (
        service.get_dataset("w1", dataset_id, OWNER).proposal_batches[0]["result"]["drafts"][0][
            "proposal"
        ]["question"]
        == proposed["question"]
    )
