"""Score normalization, weighted combination, and Maximal Marginal Relevance (MMR) selection.

Provides diverse, budget-constrained evidence selection over cross-encoder reranked
candidates while preserving source provenance and citation anchors.
Refs #153.
"""

from __future__ import annotations

import math
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import replace
from typing import Any

from knora.answering.evidence import CandidateDecision, EvidenceSelection, _is_redundant
from knora.answering.reranking_configuration import RerankingConfiguration
from knora.answering.stores import RetrievalCandidate


def normalize_scores(scores: Sequence[float], method: str = "min_max") -> list[float]:
    """Normalize a sequence of float scores according to the chosen method."""
    if not scores:
        return []

    if method == "none":
        return [float(s) for s in scores]

    if method == "sigmoid":
        results = []
        for s in scores:
            # Clamp to prevent overflow in exp
            clamped = max(-60.0, min(60.0, float(s)))
            results.append(1.0 / (1.0 + math.exp(-clamped)))
        return results

    if method == "min_max":
        min_val = min(scores)
        max_val = max(scores)
        if max_val > min_val:
            span = max_val - min_val
            return [(s - min_val) / span for s in scores]
        # Degenerate equal scores
        return [1.0 if max_val > 0.0 else 0.0 for _ in scores]

    raise ValueError(f"unsupported normalization method: {method}")


def _lexical_tokens(text: str) -> set[str]:
    """Extract normalized lowercase tokens from text."""
    norm = unicodedata.normalize("NFKC", text).lower()
    return {t.strip(".,!?;:()[]{}") for t in norm.split() if t.strip(".,!?;:()[]{}")}


def calculate_lexical_jaccard(text_a: str, text_b: str) -> float:
    """Calculate token Jaccard similarity between two text strings."""
    set_a = _lexical_tokens(text_a)
    set_b = _lexical_tokens(text_b)
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union > 0 else 0.0


def calculate_candidate_similarity(
    cand_a: RetrievalCandidate,
    cand_b: RetrievalCandidate,
    *,
    token_set_a: set[str] | None = None,
    token_set_b: set[str] | None = None,
) -> float:
    """Calculate pairwise similarity between two candidates.

    Uses cosine similarity if both have cosine distance or similarity metadata;
    otherwise falls back to lexical Jaccard similarity.
    """
    if token_set_a is not None and token_set_b is not None:
        if not token_set_a or not token_set_b:
            return 0.0
        intersection = len(token_set_a & token_set_b)
        union = len(token_set_a | token_set_b)
        return intersection / union if union > 0 else 0.0

    return calculate_lexical_jaccard(cand_a.content, cand_b.content)


def combine_reranking_scores(
    candidates: Sequence[RetrievalCandidate],
    rerank_scores_by_chunk: Mapping[str, float],
    config: RerankingConfiguration,
) -> list[RetrievalCandidate]:
    """Normalize and combine cross-encoder scores with baseline retrieval scores."""
    if not candidates:
        return []

    # Extract raw scores
    raw_rerank_scores = [float(rerank_scores_by_chunk.get(c.chunk_id, 0.0)) for c in candidates]
    raw_retrieval_scores = [
        float(c.sdm_score if c.sdm_score is not None else c.fusion_score) for c in candidates
    ]

    norm_rerank = normalize_scores(raw_rerank_scores, method=config.normalization)
    norm_retrieval = normalize_scores(raw_retrieval_scores, method="min_max")

    w_rerank = config.weight_reranker
    w_retrieval = config.weight_retrieval
    w_sum = w_rerank + w_retrieval

    scored_items: list[tuple[float, float, float, RetrievalCandidate]] = []
    for c, s_rerank, s_retrieval in zip(candidates, norm_rerank, norm_retrieval, strict=True):
        combined = (w_rerank * s_rerank + w_retrieval * s_retrieval) / w_sum
        scored_items.append((combined, s_rerank, s_retrieval, c))

    # Sort descending by combined score, tie-break by chunk_id ascending
    scored_items.sort(key=lambda item: (-item[0], item[3].chunk_id))

    updated_candidates = []
    for rank, (combined, s_rerank, s_retrieval, c) in enumerate(scored_items, start=1):
        contribution = {
            "policy_id": config.id,
            "model": config.model,
            "raw_rerank_score": rerank_scores_by_chunk.get(c.chunk_id, 0.0),
            "normalized_rerank_score": s_rerank,
            "normalized_retrieval_score": s_retrieval,
            "combined_score": combined,
            "weight_reranker": w_rerank,
            "weight_retrieval": w_retrieval,
        }
        updated = replace(
            c,
            rerank_score=combined,
            rerank_rank=rank,
            rerank_contribution=contribution,
        )
        updated_candidates.append(updated)

    return updated_candidates


def select_evidence_mmr(
    candidates: Sequence[RetrievalCandidate],
    config: RerankingConfiguration,
    overlap_policy: str = "adjacent-content-containment-v1",
) -> EvidenceSelection:
    """Select evidence using Maximal Marginal Relevance (MMR) with budget guards."""
    if not candidates:
        return EvidenceSelection(selected=(), decisions=())

    selected_decisions: list[CandidateDecision] = []
    all_decisions: list[CandidateDecision] = []
    selected_tokens = 0

    remaining = list(candidates)
    selected_candidates: list[RetrievalCandidate] = []
    token_sets = {c.chunk_id: _lexical_tokens(c.content) for c in candidates}

    mmr_lambda = config.mmr_lambda if config.mmr_enabled else 1.0

    while remaining and len(selected_candidates) < config.max_evidence_chunks:
        # Score each candidate by MMR
        best_cand: RetrievalCandidate | None = None
        best_mmr_score = -float("inf")
        best_idx = -1

        for idx, cand in enumerate(remaining):
            rel_score = cand.rerank_score if cand.rerank_score is not None else cand.fusion_score

            if not selected_candidates:
                mmr_score = float(rel_score)
            else:
                cand_tokens = token_sets[cand.chunk_id]
                max_sim = max(
                    calculate_candidate_similarity(
                        cand, s, token_set_a=cand_tokens, token_set_b=token_sets[s.chunk_id]
                    )
                    for s in selected_candidates
                )
                mmr_score = mmr_lambda * float(rel_score) - (1.0 - mmr_lambda) * float(max_sim)

            # Tie-break by chunk_id ascending if mmr_score is equal
            if mmr_score > best_mmr_score or (
                math.isclose(mmr_score, best_mmr_score, rel_tol=1e-9)
                and best_cand is not None
                and cand.chunk_id < best_cand.chunk_id
            ):
                best_mmr_score = mmr_score
                best_cand = cand
                best_idx = idx

        assert best_cand is not None
        candidate = remaining.pop(best_idx)

        # Check redundancy
        budget_evidence: dict[str, Any] | None = None
        if any(_is_redundant(candidate, s, overlap_policy) for s in selected_candidates):
            outcome = "REDUNDANT_OVERLAP"
        elif len(selected_candidates) >= config.max_evidence_chunks:
            outcome = "CHUNK_COUNT_LIMIT"
            budget_evidence = {
                "max_evidence_chunks": config.max_evidence_chunks,
                "max_evidence_tokens": config.max_evidence_tokens,
                "selected_chunk_count": len(selected_candidates),
                "selected_token_count": selected_tokens,
                "candidate_token_count": candidate.token_count,
                "token_total": selected_tokens + candidate.token_count,
            }
        elif selected_tokens + candidate.token_count > config.max_evidence_tokens:
            outcome = "TOKEN_BUDGET_EXCEEDED"
            budget_evidence = {
                "max_evidence_chunks": config.max_evidence_chunks,
                "max_evidence_tokens": config.max_evidence_tokens,
                "selected_chunk_count": len(selected_candidates),
                "selected_token_count": selected_tokens,
                "candidate_token_count": candidate.token_count,
                "token_total": selected_tokens + candidate.token_count,
            }
        else:
            outcome = "SELECTED"

        decision = CandidateDecision(
            candidate=candidate,
            outcome=outcome,
            budget_evidence=budget_evidence,
        )
        all_decisions.append(decision)

        if outcome == "SELECTED":
            selected_candidates.append(candidate)
            selected_decisions.append(decision)
            selected_tokens += candidate.token_count

    # Any remaining candidates after reaching chunk limit or token exhaust
    for candidate in remaining:
        outcome = "CHUNK_COUNT_LIMIT"
        budget_evidence = {
            "max_evidence_chunks": config.max_evidence_chunks,
            "max_evidence_tokens": config.max_evidence_tokens,
            "selected_chunk_count": len(selected_candidates),
            "selected_token_count": selected_tokens,
            "candidate_token_count": candidate.token_count,
            "token_total": selected_tokens + candidate.token_count,
        }
        all_decisions.append(
            CandidateDecision(
                candidate=candidate,
                outcome=outcome,
                budget_evidence=budget_evidence,
            )
        )

    return EvidenceSelection(
        selected=tuple(selected_decisions),
        decisions=tuple(all_decisions),
    )
