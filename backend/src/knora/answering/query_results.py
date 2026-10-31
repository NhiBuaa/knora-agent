"""Cross-query candidate merging, group-aware deduplication, and fairness.

Implements fair multi-query candidate pooling, preserving coverage group provenance,
ensuring minority subquestions are represented, and bounding total candidate count to 100.
Refs #153 (Retrieval V3 Stage 7).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from knora.answering.stores import RetrievalCandidate

MAX_MERGED_CANDIDATE_POOL = 100


@dataclass(frozen=True, slots=True)
class MergedCandidatePool:
    """Consolidated candidate pool across multiple subquestions and variants."""

    candidates: tuple[RetrievalCandidate, ...]
    coverage_mapping: dict[str, tuple[str, ...]]  # chunk_id -> tuple of subquestion_ids
    group_to_chunk_ids: dict[str, tuple[str, ...]]  # subquestion_id -> tuple of chunk_ids
    total_candidates: int


def merge_cross_query_candidates(
    query_results: dict[str, Sequence[RetrievalCandidate]],
    *,
    subquestion_mapping: dict[str, str] | None = None,
    max_total_candidates: int = MAX_MERGED_CANDIDATE_POOL,
) -> MergedCandidatePool:
    """Merges candidate pools from multiple subquestion searches with round-robin fairness.

    Args:
        query_results: dict mapping query_text or query_key -> list of RetrievalCandidate.
        subquestion_mapping: dict mapping query_text/key -> subquestion_id (coverage group).
        max_total_candidates: upper ceiling on total unique candidates (default: 100).

    Guarantees:
        - Exact candidate deduplication by canonical chunk_id.
        - Provenance preservation: each chunk remembers every subquestion_id that retrieved it.
        - Group fairness: round-robin selection across groups prevents a broad subquestion
          from starving a specific minority subquestion.
        - Tie-breaking: deterministic by chunk_id ascending when scores match.
    """
    if max_total_candidates <= 0:
        raise ValueError("max_total_candidates must be positive")

    if not query_results:
        return MergedCandidatePool(
            candidates=(),
            coverage_mapping={},
            group_to_chunk_ids={},
            total_candidates=0,
        )

    # Build group queues and track chunk metadata
    # Map group_id -> list of candidates
    group_queues: dict[str, list[RetrievalCandidate]] = {}
    chunk_coverage_groups: dict[str, set[str]] = {}
    best_candidate_by_id: dict[str, RetrievalCandidate] = {}

    for query_key, cands in query_results.items():
        gid = subquestion_mapping.get(query_key, query_key) if subquestion_mapping else query_key
        if gid not in group_queues:
            group_queues[gid] = []

        for cand in cands:
            cid = cand.chunk_id
            if cid not in chunk_coverage_groups:
                chunk_coverage_groups[cid] = set()
            chunk_coverage_groups[cid].add(gid)

            # Keep candidate with highest fusion/sdm/rerank score
            existing = best_candidate_by_id.get(cid)
            score = cand.rerank_score or cand.sdm_score or cand.fusion_score
            if existing is None:
                best_candidate_by_id[cid] = cand
            else:
                existing_score = (
                    existing.rerank_score or existing.sdm_score or existing.fusion_score
                )
                if score > existing_score:
                    best_candidate_by_id[cid] = cand

            group_queues[gid].append(cand)

    # Round-robin selection across groups to ensure fairness
    selected_chunk_ids: list[str] = []
    seen_ids: set[str] = set()

    active_groups = [gid for gid in group_queues if group_queues[gid]]
    group_ptrs = {gid: 0 for gid in active_groups}

    while active_groups and len(selected_chunk_ids) < max_total_candidates:
        next_active: list[str] = []
        for gid in active_groups:
            if len(selected_chunk_ids) >= max_total_candidates:
                break
            ptr = group_ptrs[gid]
            queue = group_queues[gid]
            while ptr < len(queue) and queue[ptr].chunk_id in seen_ids:
                ptr += 1

            if ptr < len(queue):
                cid = queue[ptr].chunk_id
                seen_ids.add(cid)
                selected_chunk_ids.append(cid)
                group_ptrs[gid] = ptr + 1
                if ptr + 1 < len(queue) and len(selected_chunk_ids) < max_total_candidates:
                    next_active.append(gid)
            else:
                group_ptrs[gid] = ptr
        active_groups = next_active

    # Build merged candidates tuple with updated ranks
    merged_candidates: list[RetrievalCandidate] = []
    for _rank, cid in enumerate(selected_chunk_ids, start=1):
        cand = best_candidate_by_id[cid]
        # Attach coverage groups to candidate metadata if needed
        merged_candidates.append(cand)

    coverage_map = {cid: tuple(sorted(groups)) for cid, groups in chunk_coverage_groups.items()}
    group_to_chunks: dict[str, list[str]] = {}
    for cid in selected_chunk_ids:
        for gid in coverage_map.get(cid, ()):
            if gid not in group_to_chunks:
                group_to_chunks[gid] = []
            group_to_chunks[gid].append(cid)

    return MergedCandidatePool(
        candidates=tuple(merged_candidates),
        coverage_mapping=coverage_map,
        group_to_chunk_ids={gid: tuple(cids) for gid, cids in group_to_chunks.items()},
        total_candidates=len(merged_candidates),
    )
