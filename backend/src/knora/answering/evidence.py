from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from knora.answering.stores import RetrievalCandidate, RetrievalConfiguration


@dataclass(frozen=True, slots=True)
class CandidateDecision:
    candidate: RetrievalCandidate
    outcome: str
    budget_evidence: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class EvidenceSelection:
    selected: tuple[CandidateDecision, ...]
    decisions: tuple[CandidateDecision, ...]
    support_assessment: Any | None = None


def _tokens(content: str) -> set[str]:
    return {token.casefold().strip(".,!?;:()[]{}") for token in content.split() if token}


def _is_redundant(candidate: RetrievalCandidate, selected: RetrievalCandidate, policy: str) -> bool:
    if candidate.chunk_set_id != selected.chunk_set_id:
        return False
    if abs(candidate.chunk_ordinal - selected.chunk_ordinal) != 1:
        return False
    if policy == "adjacent-content-containment-v1":
        # Preserve order, repetitions, case and punctuation; only whitespace is normalized.
        # Partial overlap cannot establish that the candidate adds no information.
        needle = candidate.content.split()
        haystack = selected.content.split()
        return bool(needle) and any(
            haystack[start : start + len(needle)] == needle
            for start in range(len(haystack) - len(needle) + 1)
        )
    candidate_tokens = _tokens(candidate.content)
    selected_tokens = _tokens(selected.content)
    smaller = min(len(candidate_tokens), len(selected_tokens))
    return bool(smaller) and len(candidate_tokens & selected_tokens) / smaller >= 0.5


def compute_reserved_chunks(
    candidates: Sequence[RetrievalCandidate],
    support_assessment: Any,
    max_evidence_chunks: int,
    max_evidence_tokens: int,
) -> set[str]:
    """Computes a greedy minimal subset of candidate chunk_ids covering all supported groups."""
    candidate_map = {c.chunk_id: c for c in candidates}
    # Find all supported groups
    supported_groups = [
        ga
        for ga in support_assessment.group_assessments
        if ga.status == "supported" and ga.supporting_chunk_ids
    ]
    if not supported_groups:
        return set()

    uncovered_group_ids = {ga.group_id for ga in supported_groups}
    reserved: list[str] = []
    total_tokens = 0

    while uncovered_group_ids and len(reserved) < max_evidence_chunks:
        # Find candidate that covers the maximum number of uncovered groups
        best_cid = None
        best_covered: set[str] = set()
        best_score = -float("inf")

        for cand in candidates:
            cid = cand.chunk_id
            if cid in reserved:
                continue
            cand_tokens = cand.token_count
            if total_tokens + cand_tokens > max_evidence_tokens:
                continue

            covered = {
                ga.group_id
                for ga in supported_groups
                if ga.group_id in uncovered_group_ids and cid in ga.supporting_chunk_ids
            }
            if not covered:
                continue

            score = cand.rerank_score or cand.similarity or 0.0
            if (len(covered) > len(best_covered)) or (
                len(covered) == len(best_covered) and score > best_score
            ):
                best_cid = cid
                best_covered = covered
                best_score = score

        if best_cid is None:
            break

        reserved.append(best_cid)
        total_tokens += candidate_map[best_cid].token_count
        uncovered_group_ids -= best_covered

    return set(reserved)


def select_evidence(
    candidates: tuple[RetrievalCandidate, ...] | Sequence[RetrievalCandidate],
    configuration: RetrievalConfiguration,
    reranking_configuration: Any | None = None,
    *,
    subquestions: Sequence[Any] | None = None,
    candidate_support: Any | None = None,
) -> EvidenceSelection:
    if configuration.overlap_policy not in {
        "adjacent-token-overlap-v1",
        "adjacent-content-containment-v1",
    }:
        raise ValueError("unsupported overlap policy")

    reserved_chunk_ids: set[str] = set()
    initial_support: Any | None = None

    if subquestions:
        from knora.answering.evidence_support import assess_evidence_support

        initial_support = candidate_support or assess_evidence_support(
            subquestions, candidates, purpose="candidate_support"
        )
        reserved_chunk_ids = compute_reserved_chunks(
            candidates,
            initial_support,
            configuration.max_evidence_chunks,
            configuration.max_evidence_tokens,
        )

    if reranking_configuration is not None and getattr(
        reranking_configuration, "mmr_enabled", False
    ):
        from knora.answering.reranking import select_evidence_mmr

        selection = select_evidence_mmr(
            candidates,
            reranking_configuration,
            overlap_policy=configuration.overlap_policy,
            reserved_chunk_ids=reserved_chunk_ids if reserved_chunk_ids else None,
        )
    else:
        # Standard or reserved selection
        selected: list[CandidateDecision] = []
        decisions: list[CandidateDecision] = []
        selected_tokens = 0
        selected_ids: set[str] = set()

        # Step 1: select reserved candidates first if any
        if reserved_chunk_ids:
            reserved_cands = [c for c in candidates if c.chunk_id in reserved_chunk_ids]
            for candidate in reserved_cands:
                budget_evidence: dict[str, Any] | None = None
                if any(
                    _is_redundant(candidate, item.candidate, configuration.overlap_policy)
                    for item in selected
                ):
                    outcome = "REDUNDANT_OVERLAP"
                elif len(selected) >= configuration.max_evidence_chunks:
                    outcome = "CHUNK_COUNT_LIMIT"
                    budget_evidence = {
                        "max_evidence_chunks": configuration.max_evidence_chunks,
                        "max_evidence_tokens": configuration.max_evidence_tokens,
                        "selected_chunk_count": len(selected),
                        "selected_token_count": selected_tokens,
                        "candidate_token_count": candidate.token_count,
                        "token_total": selected_tokens + candidate.token_count,
                    }
                elif selected_tokens + candidate.token_count > configuration.max_evidence_tokens:
                    outcome = "TOKEN_BUDGET_EXCEEDED"
                    budget_evidence = {
                        "max_evidence_chunks": configuration.max_evidence_chunks,
                        "max_evidence_tokens": configuration.max_evidence_tokens,
                        "selected_chunk_count": len(selected),
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
                decisions.append(decision)
                if outcome == "SELECTED":
                    selected.append(decision)
                    selected_tokens += candidate.token_count
                    selected_ids.add(candidate.chunk_id)

        # Step 2: fill remaining slots with non-reserved candidates
        for candidate in candidates:
            if candidate.chunk_id in selected_ids:
                continue
            budget_evidence = None
            if any(
                _is_redundant(candidate, item.candidate, configuration.overlap_policy)
                for item in selected
            ):
                outcome = "REDUNDANT_OVERLAP"
            elif len(selected) >= configuration.max_evidence_chunks:
                outcome = "CHUNK_COUNT_LIMIT"
                budget_evidence = {
                    "max_evidence_chunks": configuration.max_evidence_chunks,
                    "max_evidence_tokens": configuration.max_evidence_tokens,
                    "selected_chunk_count": len(selected),
                    "selected_token_count": selected_tokens,
                    "candidate_token_count": candidate.token_count,
                    "token_total": selected_tokens + candidate.token_count,
                }
            elif selected_tokens + candidate.token_count > configuration.max_evidence_tokens:
                outcome = "TOKEN_BUDGET_EXCEEDED"
                budget_evidence = {
                    "max_evidence_chunks": configuration.max_evidence_chunks,
                    "max_evidence_tokens": configuration.max_evidence_tokens,
                    "selected_chunk_count": len(selected),
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
            decisions.append(decision)
            if outcome == "SELECTED":
                selected.append(decision)
                selected_tokens += candidate.token_count

        selection = EvidenceSelection(selected=tuple(selected), decisions=tuple(decisions))

    # Calculate final support assessment if subquestions were provided
    if subquestions:
        from knora.answering.evidence_support import assess_evidence_support

        final_support = assess_evidence_support(
            subquestions,
            [d.candidate for d in selection.selected],
            purpose="final_support",
        )
        return EvidenceSelection(
            selected=selection.selected,
            decisions=selection.decisions,
            support_assessment=final_support,
        )

    return selection
