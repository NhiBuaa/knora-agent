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


def _tokens(content: str) -> set[str]:
    return {token.casefold().strip(".,!?;:()[]{}") for token in content.split() if token}


def _is_redundant(candidate: RetrievalCandidate, selected: RetrievalCandidate) -> bool:
    if candidate.chunk_set_id != selected.chunk_set_id:
        return False
    if abs(candidate.chunk_ordinal - selected.chunk_ordinal) != 1:
        return False
    candidate_tokens = _tokens(candidate.content)
    selected_tokens = _tokens(selected.content)
    smaller = min(len(candidate_tokens), len(selected_tokens))
    return bool(smaller) and len(candidate_tokens & selected_tokens) / smaller >= 0.5


def select_evidence(
    candidates: tuple[RetrievalCandidate, ...],
    configuration: RetrievalConfiguration,
) -> EvidenceSelection:
    selected: list[CandidateDecision] = []
    decisions: list[CandidateDecision] = []
    selected_tokens = 0
    for candidate in candidates:
        budget_evidence: dict[str, Any] | None = None
        if any(_is_redundant(candidate, item.candidate) for item in selected):
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
    return EvidenceSelection(selected=tuple(selected), decisions=tuple(decisions))
