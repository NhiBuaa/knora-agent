"""Sequential Dependence Model (SDM) scoring for candidate reranking.

Implements the Markov Random Field model for information retrieval (Metzler & Croft, SIGIR 2005)
combining unigram (T), ordered adjacent pair (O), and unordered window (U) features under
Dirichlet language model smoothing.
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace

from knora.answering.stores import RetrievalCandidate

_TOKEN_PATTERN = re.compile(r"\w+(?:\.\w+)*", re.UNICODE)


def tokenize_lexical_text(text: str) -> tuple[str, ...]:
    """Tokenize text preserving Unicode letters, digits, and internal dots/underscores."""
    normalized = unicodedata.normalize("NFKC", text).lower()
    return tuple(_TOKEN_PATTERN.findall(normalized))


@dataclass(frozen=True, slots=True)
class CorpusStatistics:
    """Immutable collection statistics required for Dirichlet background probabilities."""

    total_tokens: int
    total_chunks: int
    unigram_frequencies: Mapping[str, int] = field(default_factory=dict)
    average_chunk_length: float | None = None
    statistics_digest: str | None = None

    def __post_init__(self) -> None:
        if self.total_tokens <= 0:
            raise ValueError("total_tokens must be positive")
        if self.total_chunks <= 0:
            raise ValueError("total_chunks must be positive")


@dataclass(frozen=True, slots=True)
class SequentialDependenceConfig:
    """Parameters for the Sequential Dependence Model and DBSF combination."""

    policy_id: str = "sdm-metzler-croft-2005-v1"
    lambda_t: float = 0.85
    lambda_o: float = 0.10
    lambda_u: float = 0.05
    mu: float = 1000.0
    window_size: int = 8
    blend_alpha: float = 0.30

    def __post_init__(self) -> None:
        if self.lambda_t < 0.0 or self.lambda_o < 0.0 or self.lambda_u < 0.0:
            raise ValueError("weights must be non-negative")
        if self.lambda_t + self.lambda_o + self.lambda_u <= 0.0:
            raise ValueError("sum of weights must be positive")
        if self.window_size < 2:
            raise ValueError("window_size must be at least 2")
        if self.mu <= 0.0:
            raise ValueError("mu must be positive")
        if not (0.0 <= self.blend_alpha <= 1.0):
            raise ValueError("blend_alpha must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class SDMScoringResult:
    """Scoring result and diagnostic breakdown for one retrieval candidate."""

    candidate: RetrievalCandidate
    unigram_score: float
    ordered_score: float
    unordered_score: float
    raw_sdm_score: float
    normalized_sdm_score: float
    combined_score: float
    unigram_matches: int
    ordered_matches: int
    unordered_matches: int


class SequentialDependenceScorer:
    """Pure scoring engine for Sequential Dependence reranking."""

    def __init__(
        self,
        config: SequentialDependenceConfig | None = None,
        corpus_stats: CorpusStatistics | None = None,
    ) -> None:
        self.config = config or SequentialDependenceConfig()
        self.corpus_stats = corpus_stats

    def _background_unigram_prob(self, token: str) -> float:
        if not self.corpus_stats:
            return 1e-6
        cf = self.corpus_stats.unigram_frequencies.get(token, 0)
        if cf > 0:
            return cf / self.corpus_stats.total_tokens
        return 1.0 / (self.corpus_stats.total_tokens + 1.0)

    def _background_ordered_prob(self, t1: str, t2: str) -> float:
        p1 = self._background_unigram_prob(t1)
        p2 = self._background_unigram_prob(t2)
        prod = p1 * p2
        if prod > 0.0:
            return prod
        floor = 1.0 / ((self.corpus_stats.total_tokens if self.corpus_stats else 1000) + 1.0)
        return floor

    def _background_unordered_prob(self, t1: str, t2: str) -> float:
        p_ind = self._background_ordered_prob(t1, t2)
        w = float(self.config.window_size)
        if p_ind > 0.0:
            return min(1.0, w * p_ind)
        floor = 1.0 / ((self.corpus_stats.total_tokens if self.corpus_stats else 1000) + 1.0)
        return floor

    def _count_ordered_pair(self, doc_tokens: Sequence[str], t1: str, t2: str) -> int:
        count = 0
        for i in range(len(doc_tokens) - 1):
            if doc_tokens[i] == t1 and doc_tokens[i + 1] == t2:
                count += 1
        return count

    def _count_unordered_pair(
        self,
        doc_tokens: Sequence[str],
        t1: str,
        t2: str,
        window_size: int,
        pos1: Sequence[int] | None = None,
        pos2: Sequence[int] | None = None,
    ) -> int:
        if pos1 is None:
            pos1 = [idx for idx, tok in enumerate(doc_tokens) if tok == t1]
        if pos2 is None:
            pos2 = [idx for idx, tok in enumerate(doc_tokens) if tok == t2]

        if not pos1 or not pos2:
            return 0

        # Build candidate matching intervals where span <= window_size
        intervals = []
        if t1 == t2:
            for i in range(len(pos1)):
                for j in range(i + 1, len(pos1)):
                    start, end = pos1[i], pos1[j]
                    if (end - start + 1) <= window_size:
                        intervals.append((start, end))
        else:
            for p1 in pos1:
                for p2 in pos2:
                    if p1 < p2:
                        if (p2 - p1 + 1) <= window_size:
                            intervals.append((p1, p2))
                    else:
                        if (p1 - p2 + 1) <= window_size:
                            intervals.append((p2, p1))

        if not intervals:
            return 0

        # Sort intervals by end position, then start position (greedy non-overlapping)
        intervals.sort(key=lambda span: (span[1], span[0]))
        count = 0
        last_end = -1
        for start, end in intervals:
            if start > last_end:
                count += 1
                last_end = end
        return count

    def score_candidates(
        self,
        query: str,
        candidates: Sequence[RetrievalCandidate],
        positions_by_chunk: Mapping[str, object] | None = None,
    ) -> list[SDMScoringResult]:
        """Score and rerank candidates according to Sequential Dependence Model."""
        if not candidates:
            return []

        query_tokens = tokenize_lexical_text(query)
        n = len(query_tokens)
        query_set = set(query_tokens)
        query_pairs = (
            [(query_tokens[i], query_tokens[i + 1]) for i in range(n - 1)] if n >= 2 else ()
        )

        # Pre-tokenize or resolve positional tokens for all candidate contents
        parsed = []
        for cand in candidates:
            if positions_by_chunk and cand.chunk_id in positions_by_chunk:
                deriv = positions_by_chunk[cand.chunk_id]
                tokens_attr = getattr(deriv, "tokens", None)
                if tokens_attr:
                    doc_tokens = [t.token for t in tokens_attr]
                else:
                    doc_tokens = tokenize_lexical_text(cand.content)
            else:
                doc_tokens = tokenize_lexical_text(cand.content)
            doc_len = cand.token_count if cand.token_count > 0 else len(doc_tokens)
            parsed.append((cand, doc_tokens, doc_len))

        mu = self.config.mu
        lambda_t = self.config.lambda_t
        lambda_o = self.config.lambda_o
        lambda_u = self.config.lambda_u

        # Evaluate SDM raw components for each candidate
        scored_items = []
        for cand, doc_tokens, doc_len in parsed:
            denom = doc_len + mu

            # If query is empty, return 0.0 scores
            if n == 0:
                scored_items.append((cand, 0.0, 0.0, 0.0, 0.0, 0, 0, 0))
                continue

            # 1-pass term position indexing for query terms
            pos: dict[str, list[int]] = {q: [] for q in query_set}
            for idx, tok in enumerate(doc_tokens):
                if tok in query_set:
                    pos[tok].append(idx)

            # 1. Unigram score f_T
            s_t = 0.0
            unigram_match_count = 0
            for q_term in query_tokens:
                c_t = len(pos[q_term])
                if c_t > 0:
                    unigram_match_count += c_t
                p_c = self._background_unigram_prob(q_term)
                s_t += math.log((c_t + mu * p_c) / denom)

            # 2. Ordered and Unordered scores f_O, f_U
            s_o = 0.0
            s_u = 0.0
            ordered_match_count = 0
            unordered_match_count = 0

            if n >= 2:
                for t1, t2 in query_pairs:
                    p1 = pos[t1]
                    p2 = pos[t2]

                    # Ordered
                    if p1 and p2:
                        c_o = sum(
                            1 for p in p1 if p + 1 < len(doc_tokens) and doc_tokens[p + 1] == t2
                        )
                    else:
                        c_o = 0
                    ordered_match_count += c_o
                    p_o = self._background_ordered_prob(t1, t2)
                    s_o += math.log((c_o + mu * p_o) / denom)

                    # Unordered
                    if p1 and p2:
                        c_u = self._count_unordered_pair(
                            doc_tokens, t1, t2, self.config.window_size, pos1=p1, pos2=p2
                        )
                    else:
                        c_u = 0
                    unordered_match_count += c_u
                    p_u = self._background_unordered_prob(t1, t2)
                    s_u += math.log((c_u + mu * p_u) / denom)

                raw_sdm = lambda_t * s_t + lambda_o * s_o + lambda_u * s_u
            else:
                raw_sdm = s_t

            scored_items.append(
                (
                    cand,
                    s_t,
                    s_o,
                    s_u,
                    raw_sdm,
                    unigram_match_count,
                    ordered_match_count,
                    unordered_match_count,
                )
            )

        # Normalize raw SDM scores across the candidate pool to [0, 1]
        raw_scores = [item[4] for item in scored_items]
        min_raw = min(raw_scores)
        max_raw = max(raw_scores)

        results = []
        blend_alpha = self.config.blend_alpha

        for (
            cand,
            s_t,
            s_o,
            s_u,
            raw_sdm,
            u_matches,
            o_matches,
            un_matches,
        ) in scored_items:
            if max_raw > min_raw:
                norm_sdm = (raw_sdm - min_raw) / (max_raw - min_raw)
            else:
                norm_sdm = 1.0 if max_raw > -1e9 else 0.0

            dbsf_score = cand.fusion_score if cand.fusion_score is not None else 0.0
            combined = (1.0 - blend_alpha) * dbsf_score + blend_alpha * norm_sdm

            results.append(
                (
                    combined,
                    dbsf_score,
                    norm_sdm,
                    cand,
                    s_t,
                    s_o,
                    s_u,
                    raw_sdm,
                    u_matches,
                    o_matches,
                    un_matches,
                )
            )

        # Sort deterministically:
        # 1. combined descending
        # 2. dbsf_score descending
        # 3. norm_sdm descending
        # 4. chunk_id ascending
        results.sort(key=lambda r: (-r[0], -r[1], -r[2], r[3].chunk_id))

        final_list = []
        for rank, (
            combined,
            _dbsf,
            norm_sdm,
            cand,
            s_t,
            s_o,
            s_u,
            raw_sdm,
            u_matches,
            o_matches,
            un_matches,
        ) in enumerate(results, start=1):
            contribution = {
                "policy_id": self.config.policy_id,
                "unigram_score": s_t,
                "ordered_score": s_o,
                "unordered_score": s_u,
                "raw_sdm_score": raw_sdm,
                "normalized_sdm_score": norm_sdm,
                "combined_score": combined,
                "blend_alpha": blend_alpha,
                "unigram_matches": u_matches,
                "ordered_matches": o_matches,
                "unordered_matches": un_matches,
            }
            updated_cand = replace(
                cand,
                sdm_score=combined,
                sdm_rank=rank,
                sdm_contribution=contribution,
            )
            final_list.append(
                SDMScoringResult(
                    candidate=updated_cand,
                    unigram_score=s_t,
                    ordered_score=s_o,
                    unordered_score=s_u,
                    raw_sdm_score=raw_sdm,
                    normalized_sdm_score=norm_sdm,
                    combined_score=combined,
                    unigram_matches=u_matches,
                    ordered_matches=o_matches,
                    unordered_matches=un_matches,
                )
            )

        return final_list
