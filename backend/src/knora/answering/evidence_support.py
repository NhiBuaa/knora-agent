"""Evidence support assessment and constraint verification against source text.

Evaluates whether retrieved source text provides factual support for required subquestions
and constraints (identifiers, numbers, dates, negations, section anchors).
Refs #153 (Retrieval V3 Stage 7).
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections.abc import Sequence
from dataclasses import asdict, dataclass

from knora.answering.query_planning import (
    Subquestion,
    extract_protected_spans,
)
from knora.answering.stores import RetrievalCandidate


@dataclass(frozen=True, slots=True)
class GroupAssessment:
    """Assessment outcome for a single subquestion/coverage group."""

    group_id: str
    status: str  # supported, unsupported, unknown
    supporting_chunk_ids: tuple[str, ...]
    reason: str
    method: str = "deterministic_constraint_v1"


@dataclass(frozen=True, slots=True)
class EvidenceSupportAssessment:
    """Consolidated support assessment across all required groups."""

    purpose: str  # candidate_support or final_support
    group_assessments: tuple[GroupAssessment, ...]
    assessment_digest: str
    all_required_supported: bool
    missing_group_ids: tuple[str, ...]

    def to_observation(self) -> dict[str, object]:
        return {
            "purpose": self.purpose,
            "assessment_digest": self.assessment_digest,
            "all_required_supported": self.all_required_supported,
            "missing_group_ids": list(self.missing_group_ids),
            "group_assessments": [asdict(ga) for ga in self.group_assessments],
        }


def _matches_constraint(target: str, context: str) -> bool:
    cleaned = target.strip()
    if not cleaned:
        return False
    pattern = rf"(?<![a-zA-Z0-9_]){re.escape(cleaned)}(?![a-zA-Z0-9_])"
    return re.search(pattern, context, re.IGNORECASE) is not None


def assess_evidence_support(
    subquestions: Sequence[Subquestion],
    candidates: Sequence[RetrievalCandidate],
    *,
    purpose: str = "final_support",
) -> EvidenceSupportAssessment:
    """Deterministically assesses factual support for each subquestion against candidate text.

    Guarantees:
    - Checks both section/heading context and factual keyword presence.
    - Preserves protected span constraints (numbers, negations, identifiers).
    - Prevents false-support claims: distractor chunks cannot support an unrelated subquestion.
    - Output supporting_chunk_ids are strictly subsets of candidate chunk_ids.
    """
    assessments: list[GroupAssessment] = []
    missing_groups: list[str] = []

    candidate_map = {c.chunk_id: c for c in candidates}

    for sq in subquestions:
        norm_sq_text = unicodedata.normalize("NFKC", sq.text).casefold()
        sq_protected = sq.protected_spans or extract_protected_spans(sq.text)

        # Extract required keywords (excluding stop words)
        sq_keywords = [
            w
            for w in re.findall(r"\w+", norm_sq_text)
            if len(w) >= 3 and w not in {"thông", "tin", "về", "trong", "của", "cho", "với"}
        ]

        # Extract required section constraint (e.g. "chương 2", "mục 3.1")
        section_constraints = [s.text.casefold() for s in sq_protected if s.category == "section"]
        number_constraints = [s.text for s in sq_protected if s.category == "number"]
        identifier_constraints = [
            s.text.casefold() for s in sq_protected if s.category == "identifier"
        ]
        negation_constraints = [s.text.casefold() for s in sq_protected if s.category == "negation"]
        date_constraints = [s.text.casefold() for s in sq_protected if s.category == "date"]

        matching_chunk_ids: list[str] = []

        for cid, cand in candidate_map.items():
            cand_text = unicodedata.normalize("NFKC", cand.content).casefold()
            cand_heading = " ".join(cand.heading_path).casefold()
            full_cand_context = f"{cand_heading} {cand_text}"

            # 1. Section constraint check with exact boundary (C2 != C20)
            if section_constraints and not any(
                _matches_constraint(sec, full_cand_context) for sec in section_constraints
            ):
                continue

            # 2. Identifier constraint check with exact boundary (AUTH_403 != AUTH_404)
            if identifier_constraints and not all(
                _matches_constraint(ident, full_cand_context) for ident in identifier_constraints
            ):
                continue

            # 3. Number constraint check with exact boundary (14 != 140)
            if number_constraints and not all(
                _matches_constraint(num, full_cand_context) for num in number_constraints
            ):
                continue

            # 4. Negation constraint check with exact boundary
            if negation_constraints and not all(
                _matches_constraint(neg, full_cand_context) for neg in negation_constraints
            ):
                continue

            # 5. Date constraint check with exact boundary
            if date_constraints and not all(
                _matches_constraint(d, full_cand_context) for d in date_constraints
            ):
                continue

            # 6. Keyword presence check with exact boundary
            if sq_keywords:
                matched_kw = sum(
                    1 for kw in sq_keywords if _matches_constraint(kw, full_cand_context)
                )
                if matched_kw == 0 or matched_kw / len(sq_keywords) < 0.4:
                    continue

            matching_chunk_ids.append(cid)

        if matching_chunk_ids:
            assessments.append(
                GroupAssessment(
                    group_id=sq.id,
                    status="supported",
                    supporting_chunk_ids=tuple(matching_chunk_ids),
                    reason=f"Matched {len(matching_chunk_ids)} chunk(s) satisfying constraints",
                )
            )
        else:
            assessments.append(
                GroupAssessment(
                    group_id=sq.id,
                    status="unsupported",
                    supporting_chunk_ids=(),
                    reason="No candidate in pool satisfies required section and entity constraints",
                )
            )
            if sq.required:
                missing_groups.append(sq.id)

    # Compute deterministic input/output digest
    digest_payload = {
        "purpose": purpose,
        "subquestions": [sq.id for sq in subquestions],
        "candidates": [c.chunk_id for c in candidates],
        "outcomes": [(ga.group_id, ga.status, ga.supporting_chunk_ids) for ga in assessments],
    }
    raw_digest = json.dumps(digest_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    assessment_digest = hashlib.sha256(raw_digest).hexdigest()

    return EvidenceSupportAssessment(
        purpose=purpose,
        group_assessments=tuple(assessments),
        assessment_digest=assessment_digest,
        all_required_supported=len(missing_groups) == 0,
        missing_group_ids=tuple(missing_groups),
    )
