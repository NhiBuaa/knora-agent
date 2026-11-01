"""BM25 + Phrase Boost evaluation comparator (diagnostic policy bm25-phrase-boost-v1).

Re-ranks BM25 candidates by blending normalized BM25 with adjacent phrase matching ratio.
Does not perform search queries, embedding calls, or mutate candidates.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from knora.answering.sequential_dependence import tokenize_lexical_text
from knora.answering.stores import RetrievalCandidate


@dataclass(frozen=True, slots=True)
class PhraseBoostConfig:
    """Parameters for the BM25 + Phrase Boost comparator."""

    policy_id: str = "bm25-phrase-boost-v1"
    lambda_param: float = 0.5

    def __post_init__(self) -> None:
        if not isinstance(self.lambda_param, (int, float)) or isinstance(self.lambda_param, bool):
            raise TypeError("lambda_param must be numeric")
        if not math.isfinite(self.lambda_param) or not (0.0 <= self.lambda_param <= 1.0):
            raise ValueError("lambda_param must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class PhraseBoostResult:
    """Diagnostic ranking result for one candidate under phrase boost comparator."""

    candidate: RetrievalCandidate
    raw_bm25: float
    normalized_bm25: float
    matched_pairs: int
    total_query_pairs: int
    phrase_ratio: float
    combined_score: float
    rank: int


class PhraseBoostComparator:
    """Pure offline comparator for BM25 + Phrase Boost."""

    def __init__(self, config: PhraseBoostConfig | None = None) -> None:
        self.config = config or PhraseBoostConfig()

    def rerank(
        self, query: str, candidates: Sequence[RetrievalCandidate]
    ) -> list[PhraseBoostResult]:
        """Rerank candidates using BM25 score and adjacent phrase match ratio."""
        if not candidates:
            return []

        query_tokens = tokenize_lexical_text(query)
        n = len(query_tokens)
        total_query_pairs = n - 1 if n >= 2 else 0

        # Query pairs
        query_pairs = (
            [(query_tokens[i], query_tokens[i + 1]) for i in range(n - 1)] if n >= 2 else []
        )

        # Extract raw BM25 scores
        raw_scores = []
        for c in candidates:
            score = c.bm25_score if c.bm25_score is not None else (c.fusion_score or 0.0)
            raw_scores.append(score)

        min_bm25 = min(raw_scores)
        max_bm25 = max(raw_scores)
        span = max_bm25 - min_bm25

        evaluated = []
        lambda_param = self.config.lambda_param

        for c, raw_bm25 in zip(candidates, raw_scores, strict=True):
            # 1. Normalized BM25: u = (bm25 - min) / (max - min) if max > min else 0.0
            u = (raw_bm25 - min_bm25) / span if span > 0.0 else 0.0

            # 2. Phrase matching ratio p
            if total_query_pairs > 0:
                doc_tokens = tokenize_lexical_text(c.content)
                matched_count = 0
                for t1, t2 in query_pairs:
                    # Check if (t1, t2) appears consecutively in doc_tokens
                    matched = False
                    for idx in range(len(doc_tokens) - 1):
                        if doc_tokens[idx] == t1 and doc_tokens[idx + 1] == t2:
                            matched = True
                            break
                    if matched:
                        matched_count += 1
                p = matched_count / total_query_pairs
            else:
                matched_count = 0
                p = 0.0

            # 3. Combined score = (1 - lambda) * u + lambda * p
            combined = (1.0 - lambda_param) * u + lambda_param * p
            evaluated.append((combined, raw_bm25, u, matched_count, p, c))

        # Sort descending by combined_score, then raw_bm25, then chunk_id ascending
        evaluated.sort(key=lambda item: (-item[0], -item[1], item[5].chunk_id))

        results = []
        for rank, (combined, raw_bm25, u, matched_count, p, c) in enumerate(evaluated, start=1):
            results.append(
                PhraseBoostResult(
                    candidate=c,
                    raw_bm25=raw_bm25,
                    normalized_bm25=u,
                    matched_pairs=matched_count,
                    total_query_pairs=total_query_pairs,
                    phrase_ratio=p,
                    combined_score=combined,
                    rank=rank,
                )
            )

        return results
