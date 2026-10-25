"""Targeted source verification and finite recovery.

Performs a single bounded recovery pass when initial retrieval leaves required
subquestion groups unsupported. Verifies facts against authorized source text
and distinguishes found evidence from verified absence and operational uncertainty.
Refs #153 (Retrieval V3 Stage 7 Task 7).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import asdict, dataclass, replace
from typing import Any

from knora.answering.evidence_support import assess_evidence_support
from knora.answering.query_planning import Subquestion
from knora.answering.stores import RetrievalCandidate, RetrievalConfiguration


@dataclass(frozen=True, slots=True)
class GroupVerificationOutcome:
    """Outcome of targeted verification for a single missing subquestion group."""

    group_id: str
    status: str  # found, verified_absent, unverified
    recovered_chunk_ids: tuple[str, ...] = ()
    reason: str = ""
    checked_sections: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SourceVerificationResult:
    """Consolidated outcome of the single recovery pass."""

    outcomes: tuple[GroupVerificationOutcome, ...]
    recovered_candidates: tuple[RetrievalCandidate, ...]
    overall_status: str  # found, verified_absent, unverified, not_needed
    verification_digest: str

    def to_observation(self) -> dict[str, Any]:
        return {
            "overall_status": self.overall_status,
            "verification_digest": self.verification_digest,
            "recovered_candidates_count": len(self.recovered_candidates),
            "recovered_chunk_ids": [c.chunk_id for c in self.recovered_candidates],
            "outcomes": [asdict(o) for o in self.outcomes],
        }


async def verify_missing_sources(
    missing_subquestions: Sequence[Subquestion],
    store: Any | None,
    workspace_id: str,
    retrieval_configuration: RetrievalConfiguration,
    *,
    all_known_candidates: Sequence[RetrievalCandidate] | None = None,
    known_section_catalog: Sequence[str] | None = None,
    snapshot: Any | None = None,
) -> SourceVerificationResult:
    """Executes a single finite recovery pass to verify missing required subquestions."""
    if not missing_subquestions:
        return SourceVerificationResult(
            outcomes=(),
            recovered_candidates=(),
            overall_status="not_needed",
            verification_digest="not_needed",
        )

    outcomes: list[GroupVerificationOutcome] = []
    all_recovered: list[RetrievalCandidate] = []
    known_cids = {c.chunk_id for c in (all_known_candidates or ())}

    for sq in missing_subquestions:
        if store is None:
            outcomes.append(
                GroupVerificationOutcome(
                    group_id=sq.id,
                    status="unverified",
                    reason="Source store is unavailable for recovery pass",
                )
            )
            continue

        # Extract section constraints
        section_spans = [s.text for s in sq.protected_spans if s.category == "section"]
        query_text = section_spans[0] if section_spans else sq.text

        if (
            store is not None
            and hasattr(store, "read_canonical_chunks_for_scope")
            and snapshot is not None
        ):
            canon_res = read_canonical_source_scope(
                store=store,
                workspace_id=workspace_id,
                target_item=query_text,
                snapshot=snapshot,
                complete_catalog=known_section_catalog,
            )
            if canon_res.outcome == "FOUND":
                outcomes.append(
                    GroupVerificationOutcome(
                        group_id=sq.id,
                        status="found",
                        recovered_chunk_ids=tuple(c.chunk_id for c in canon_res.recovered_chunks),
                        reason=f"Recovered {len(canon_res.recovered_chunks)} chunks",
                        checked_sections=tuple(section_spans),
                    )
                )
                all_recovered.extend(canon_res.recovered_chunks)
                known_cids.update(c.chunk_id for c in canon_res.recovered_chunks)
                continue
            elif canon_res.outcome == "VERIFIED_ABSENT":
                outcomes.append(
                    GroupVerificationOutcome(
                        group_id=sq.id,
                        status="verified_absent",
                        reason=canon_res.reason,
                        checked_sections=tuple(section_spans),
                    )
                )
                continue
            elif canon_res.outcome == "AMBIGUOUS":
                outcomes.append(
                    GroupVerificationOutcome(
                        group_id=sq.id,
                        status="ambiguous",
                        reason=canon_res.reason,
                        checked_sections=tuple(section_spans),
                    )
                )
                continue

        try:
            # Execute targeted BM25 lookup (0 query embeddings)
            if retrieval_configuration.strategy != "bm25-only":
                lookup_config = replace(
                    retrieval_configuration,
                    strategy="bm25-only",
                    min_similarity=None,
                    fusion_policy_id=None,
                    fusion_policy_version=None,
                    lexical_policy_id=retrieval_configuration.lexical_policy_id
                    or "bm25-word-frozen47-population-v1",
                    candidate_k=max(20, retrieval_configuration.candidate_k),
                )
            else:
                lookup_config = retrieval_configuration

            retrieval_res = store.retrieve_candidates(
                workspace_id=workspace_id,
                query_text=query_text,
                query_vector=None,
                embedding_configuration=None,
                retrieval_configuration=lookup_config,
            )
            raw_cands = [c for c in retrieval_res.candidates if c.chunk_id not in known_cids]

            # Assess whether newly retrieved chunks satisfy the subquestion constraints
            support_res = assess_evidence_support([sq], raw_cands, purpose="candidate_support")
            ga = support_res.group_assessments[0]

            if ga.status == "supported" and ga.supporting_chunk_ids:
                matching_cands = [c for c in raw_cands if c.chunk_id in ga.supporting_chunk_ids]
                outcomes.append(
                    GroupVerificationOutcome(
                        group_id=sq.id,
                        status="found",
                        recovered_chunk_ids=tuple(c.chunk_id for c in matching_cands),
                        reason=f"Recovered {len(matching_cands)} supporting chunks in pass",
                        checked_sections=tuple(section_spans),
                    )
                )
                all_recovered.extend(matching_cands)
                known_cids.update(c.chunk_id for c in matching_cands)
            else:
                # Check for verified absence if catalog is provided
                if known_section_catalog is not None and section_spans:
                    cat_lower = [c.casefold() for c in known_section_catalog]
                    if not any(s.casefold() in cat_lower for s in section_spans):
                        outcomes.append(
                            GroupVerificationOutcome(
                                group_id=sq.id,
                                status="verified_absent",
                                reason=f"Section {section_spans[0]} is absent from catalog",
                                checked_sections=tuple(section_spans),
                            )
                        )
                        continue

                # Invariant Q6: empty search results do not prove absence without complete catalog
                if not raw_cands:
                    outcomes.append(
                        GroupVerificationOutcome(
                            group_id=sq.id,
                            status="unverified",
                            reason=(
                                "Targeted search returned zero candidates; absence cannot be "
                                "verified without complete section catalog (Q6)"
                            ),
                            checked_sections=tuple(section_spans),
                        )
                    )
                else:
                    outcomes.append(
                        GroupVerificationOutcome(
                            group_id=sq.id,
                            status="unverified",
                            reason="Candidates found in document did not satisfy facts",
                            checked_sections=tuple(section_spans),
                        )
                    )

        except Exception as exc:
            outcomes.append(
                GroupVerificationOutcome(
                    group_id=sq.id,
                    status="unverified",
                    reason=f"Recovery lookup encountered operational error: {exc}",
                )
            )

    # Determine overall status
    statuses = {o.status for o in outcomes}
    if statuses == {"found"}:
        overall = "found"
    elif "unverified" in statuses:
        overall = "unverified"
    elif statuses == {"verified_absent"}:
        overall = "verified_absent"
    else:
        overall = "unverified"

    # Deterministic digest
    digest_payload = {
        "workspace_id": workspace_id,
        "subquestions": [sq.id for sq in missing_subquestions],
        "outcomes": [(o.group_id, o.status, o.recovered_chunk_ids) for o in outcomes],
    }
    raw_digest = json.dumps(digest_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    verification_digest = hashlib.sha256(raw_digest).hexdigest()

    return SourceVerificationResult(
        outcomes=tuple(outcomes),
        recovered_candidates=tuple(all_recovered),
        overall_status=overall,
        verification_digest=verification_digest,
    )


@dataclass(frozen=True, slots=True)
class CanonicalScopeReadResult:
    """Outcome of reading canonical scope directly from PostgreSQL."""

    outcome: str  # FOUND, VERIFIED_ABSENT, UNVERIFIED, AMBIGUOUS
    recovered_chunks: tuple[RetrievalCandidate, ...] = ()
    facts: tuple[str, ...] = ()
    anchors: tuple[str, ...] = ()
    reason: str = ""


def read_canonical_source_scope(
    store: Any,
    workspace_id: str,
    target_item: str,
    snapshot: Any,
    *,
    cursor: int = 0,
    limits: int = 1024,
    authorized_sources: Sequence[str] | None = None,
    complete_catalog: Sequence[str] | None = None,
    is_partial: bool = False,
) -> CanonicalScopeReadResult:
    """Read canonical source scope directly from PG structure/chunks (F13)."""
    if is_partial:
        return CanonicalScopeReadResult(
            outcome="UNVERIFIED",
            reason="partial scope cannot verify absence",
        )

    if authorized_sources and len(authorized_sources) > 1:
        return CanonicalScopeReadResult(
            outcome="AMBIGUOUS",
            reason="multiple authorized sources possible",
        )

    if store is None or not snapshot:
        return CanonicalScopeReadResult(
            outcome="UNVERIFIED",
            reason="canonical store and non-empty snapshot are required for verification",
        )

    if hasattr(store, "read_canonical_chunks_for_scope"):
        matching = store.read_canonical_chunks_for_scope(
            workspace_id, target_item, snapshot, cursor=cursor, limit=limits
        )
        if isinstance(matching, (list, tuple)) and matching:
            return CanonicalScopeReadResult(
                outcome="FOUND",
                recovered_chunks=tuple(matching),
                facts=tuple(c.content for c in matching),
                anchors=tuple(c.chunk_id for c in matching),
            )

    if complete_catalog is not None and snapshot:
        cat_lower = [c.casefold() for c in complete_catalog]
        if target_item.casefold() not in cat_lower:
            return CanonicalScopeReadResult(
                outcome="VERIFIED_ABSENT",
                reason=f"{target_item} is absent from complete catalog",
            )
        return CanonicalScopeReadResult(
            outcome="UNVERIFIED",
            reason=f"{target_item} in catalog but not found in canonical chunks",
        )

    return CanonicalScopeReadResult(
        outcome="UNVERIFIED",
        reason="canonical scope unverified without complete catalog",
    )
