from dataclasses import dataclass

from knora.answering.stores import RetrievalCandidate, RetrievalConfiguration


@dataclass(frozen=True, slots=True)
class CandidateDecision:
    candidate: RetrievalCandidate
    outcome: str


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
        if any(_is_redundant(candidate, item.candidate) for item in selected):
            outcome = "REDUNDANT_OVERLAP"
        elif len(selected) >= configuration.max_evidence_chunks:
            outcome = "CHUNK_COUNT_LIMIT"
        elif selected_tokens + candidate.token_count > configuration.max_evidence_tokens:
            outcome = "TOKEN_BUDGET_EXCEEDED"
        else:
            outcome = "SELECTED"
        decision = CandidateDecision(candidate=candidate, outcome=outcome)
        decisions.append(decision)
        if outcome == "SELECTED":
            selected.append(decision)
            selected_tokens += candidate.token_count
    return EvidenceSelection(selected=tuple(selected), decisions=tuple(decisions))
