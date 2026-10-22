"""Map existing Ragas review packets to unapproved PDF Builder cases."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass
from typing import Literal

from knora.evaluation.contracts import (
    Case,
    EvidenceAnchor,
    EvidenceGroup,
    canonical_json,
    digest_json,
)
from knora.evaluation.datasets import (
    Dataset,
    DatasetSource,
    ExtractionSnapshot,
    extraction_checksum,
)
from knora.evaluation.live_admission import LiveAdmission


@dataclass(frozen=True)
class ProposalProfile:
    profile_id: str
    kind: Literal["offline", "live"]
    model: str
    prompt_version: str
    generate: Callable[[list[dict], dict, str, int], Awaitable[dict]]
    admission: LiveAdmission | None = None
    provider_client: object | None = None


def ragas_proposal_profile(
    profile_id, kind, model, prompt_version, provider, approval
) -> ProposalProfile:
    """Reuse #158's pinned adapter with an explicit provider and exact input approval."""

    async def generate(chunks, identity, language, count):
        from evals.runners.ragas_review import generate_review_packet

        return await generate_review_packet(
            chunks,
            identity,
            provider=provider,
            approval=approval,
            model=model,
            prompt_version=prompt_version,
            language=language,
            count=count,
        )

    return ProposalProfile(profile_id, kind, model, prompt_version, generate)


def export_pdf_pages(
    dataset: Dataset, sources: tuple[tuple[DatasetSource, ExtractionSnapshot], ...]
) -> tuple[list[dict], dict]:
    """Use exact saved pages, independently of runtime retrieval chunking."""
    chunks, provenance = [], []
    versions = set()
    if not sources:
        raise ValueError("SOURCE_EXPORT_MISMATCH")
    for source, snapshot in sources:
        if (
            source.dataset_id != dataset.id
            or source.status != "READY"
            or source.document_version_id in versions
            or source.snapshot_id != snapshot.id
            or snapshot.source_id != source.id
            or not snapshot.pages
            or snapshot.extraction_sha256 != extraction_checksum(snapshot.pages)
            or len({p.page_number for p in snapshot.pages}) != len(snapshot.pages)
        ):
            raise ValueError("SOURCE_EXPORT_MISMATCH")
        versions.add(source.document_version_id)
        pages = []
        for page in snapshot.pages:
            if (
                page.page_number < 1
                or page.content_checksum != hashlib.sha256(page.text.encode()).hexdigest()
            ):
                raise ValueError("SOURCE_EXPORT_MISMATCH")
            if not page.text.strip():
                continue
            ref = f"{source.document_version_id}#page-{page.page_number}"
            chunks.append(
                {
                    "source_key": source.document_version_id,
                    "chunk_ref": ref,
                    "content": page.text,
                    "content_sha256": page.content_checksum,
                    "locator": f"PDF physical page {page.page_number}; snapshot {snapshot.id}",
                }
            )
            pages.append({"chunk_ref": ref, "physical_page": page.page_number})
        provenance.append(
            {
                "source_id": source.id,
                "document_id": source.document_id,
                "document_version_id": source.document_version_id,
                "raw_sha256": source.raw_sha256,
                "extraction_snapshot_id": snapshot.id,
                "configuration_sha256": snapshot.configuration_sha256,
                "extraction_sha256": snapshot.extraction_sha256,
                "pages": pages,
            }
        )
    if len(chunks) < 2:
        raise ValueError("MULTIHOP_EVIDENCE_INSUFFICIENT")
    identity = {
        "workspace_id": dataset.workspace_id,
        "dataset_id": dataset.id,
        "dataset_revision": dataset.revision,
        "pdf_sources": provenance,
        "approved_source_keys": [s.document_version_id for s, _ in sources],
        "source_export_sha256": "sha256:"
        + hashlib.sha256(
            json.dumps(chunks, ensure_ascii=False, sort_keys=True).encode()
        ).hexdigest(),
    }
    identity["manifest_sha256"] = "sha256:" + digest_json(identity)
    return chunks, identity


def map_review_packet(
    packet: dict,
    chunks: list[dict],
    identity: dict,
    *,
    batch_id: str,
    existing_questions: tuple[str, ...] = (),
) -> dict:
    """Retain invalid draft diagnostics; valid proposals still require human review."""
    from evals.runners.ragas_review import RagasDraftError, build_review_packet

    result = {
        "source": identity,
        "generator": packet.get("generator"),
        "drafts": [],
        "diagnostics": [],
    }
    if packet.get("source") != identity:
        result["diagnostics"].append({"code": "SOURCE_EXPORT_MISMATCH"})
        return result
    drafts = packet.get("drafts")
    if not isinstance(drafts, list) or not 1 <= len(drafts) <= 12:
        result["diagnostics"].append({"code": "DRAFT_LIMIT"})
        return result
    by_ref = {chunk["chunk_ref"]: chunk for chunk in chunks}
    locations = {
        page["chunk_ref"]: (source, page["physical_page"])
        for source in identity["pdf_sources"]
        for page in source["pages"]
    }
    seen = {" ".join(q.split()).casefold() for q in existing_questions}
    for index, draft in enumerate(drafts, 1):
        item = {
            "draft_id": f"draft-{index:02d}",
            "status": "INVALID",
            "case": None,
            "review_status": "pending_owner_review",
            "proposal": draft,
        }
        try:
            if not isinstance(draft, dict):
                raise ValueError("DRAFT_LANGUAGE_OR_SCHEMA_INVALID")
            hops = draft.get("proposed_necessary_hops", [])
            if not isinstance(hops, list) or any(not isinstance(h, dict) for h in hops):
                raise ValueError("DRAFT_LANGUAGE_OR_SCHEMA_INVALID")
            candidate = {
                "language": draft.get("language"),
                "question": draft.get("question"),
                "reference_answer": draft.get("reference_answer"),
                "hops": [
                    {k: h.get(k) for k in ("chunk_ref", "quote", "necessary_claim")} for h in hops
                ],
            }
            build_review_packet(
                [candidate],
                chunks,
                identity,
                model="mapping-validation",
                prompt_version="pdf-pages-v1",
            )
            question = " ".join(draft["question"].split()).casefold()
            if question in seen:
                raise ValueError("DUPLICATE_QUESTION")
            seen.add(question)
            groups, facts = [], []
            for hop in hops:
                ref, quote = hop["chunk_ref"], hop["quote"]
                text = by_ref[ref]["content"]
                start = text.find(quote)
                if text.find(quote, start + 1) != -1:
                    raise ValueError("EVIDENCE_AMBIGUOUS")
                source, page = locations[ref]
                groups.append(
                    EvidenceGroup(
                        (
                            EvidenceAnchor(
                                source["document_version_id"],
                                page,
                                quote,
                                source["extraction_snapshot_id"],
                                source["extraction_sha256"],
                                start,
                                start + len(quote),
                            ),
                        )
                    )
                )
                facts.append(hop["necessary_claim"])
            case = Case(
                f"ragas-{batch_id}-{index:02d}",
                draft["question"],
                "ANSWER",
                draft["reference_answer"],
                tuple(facts),
                draft["language"],
                "multi-hop",
                tuple(groups),
            )
            item.update(
                status="READY_FOR_REVIEW",
                case=json.loads(canonical_json(asdict(case))),
                case_digest=digest_json(asdict(case)),
            )
        except (RagasDraftError, ValueError, KeyError, TypeError) as error:
            code = (
                str(error) if isinstance(error, ValueError) else "DRAFT_LANGUAGE_OR_SCHEMA_INVALID"
            )
            item["reason"] = code
            result["diagnostics"].append({"draft_id": item["draft_id"], "code": code})
        result["drafts"].append(item)
    return result
