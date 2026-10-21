"""Mode-specific validation for lexical results at the application store boundary."""

from dataclasses import asdict
from math import isfinite

from knora.answering.stores import RetrievalConfiguration, RetrievalResult
from knora.domain.errors import KnoraError


def validate_bm25_result(
    result: RetrievalResult, *, workspace_id: str, configuration: RetrievalConfiguration
) -> None:
    def invalid():
        raise KnoraError("RETRIEVAL_PROVENANCE_INVALID")

    if not isinstance(result, RetrievalResult) or result.embedding_set_ids:
        invalid()
    generations = {g.index_generation_id: g for g in result.lexical_generations}
    if len(generations) != len(result.lexical_generations) or any(
        g.workspace_id != workspace_id
        or g.lexical_policy_id != configuration.lexical_policy_id
        or any(not isinstance(value, str) or not value for value in asdict(g).values())
        for g in generations.values()
    ):
        invalid()
    if set(result.chunk_set_ids) != {g.chunk_set_id for g in generations.values()}:
        invalid()
    eligible = {}
    observed = set()
    ranked = []
    for o in result.branch_observations:
        if (
            o.branch != "bm25"
            or o.lexical_policy_id != configuration.lexical_policy_id
            or o.score_kind != "bm25"
        ):
            invalid()
        if o.cosine_distance is not None or o.similarity is not None or o.native_rank is not None:
            invalid()
        if o.status == "NO_CONTRIBUTION":
            if len(result.branch_observations) != 1:
                invalid()
            if any(
                value is not None
                for value in (
                    o.chunk_id,
                    o.branch_rank,
                    o.raw_score,
                    o.index_generation_id,
                    o.decision_reason,
                )
            ):
                invalid()
            continue
        if (
            not o.chunk_id
            or type(o.branch_rank) is not int
            or o.branch_rank < 1
            or isinstance(o.raw_score, bool)
            or not isinstance(o.raw_score, (float, int))
            or not isfinite(o.raw_score)
            or not o.index_generation_id
        ):
            invalid()
        identity = (o.chunk_id, o.index_generation_id)
        if identity in observed:
            invalid()
        observed.add(identity)
        ranked.append(o)
        if o.status == "ELIGIBLE":
            if (
                o.chunk_id in eligible
                or o.decision_reason is not None
                or o.branch_rank > configuration.candidate_k
            ):
                invalid()
            eligible[o.chunk_id] = o
        elif (
            (
                o.status not in {"RANK_LIMIT", "STALE_GENERATION", "REVOKED"}
                or o.decision_reason != o.status
            )
            or o.status == "RANK_LIMIT"
            and o.branch_rank <= configuration.candidate_k
        ):
            invalid()
    ranked.sort(key=lambda o: o.branch_rank)
    if len(ranked) > 200 or [o.branch_rank for o in ranked] != list(range(1, len(ranked) + 1)):
        invalid()
    native_full_window = len(ranked) == 200
    order = [(-o.raw_score, o.branch_rank if native_full_window else o.chunk_id) for o in ranked]
    if len({o.branch_rank for o in ranked}) != len(ranked) or order != sorted(order):
        invalid()
    if not result.branch_observations or set(eligible) != {c.chunk_id for c in result.candidates}:
        invalid()
    if len(result.candidates) > configuration.candidate_k or len(eligible) != len(
        result.candidates
    ):
        invalid()
    previous = None
    for c in result.candidates:
        g = generations.get(c.index_generation_id)
        o = eligible[c.chunk_id]
        if (
            g is None
            or (c.document_id, c.document_version_id, c.chunk_set_id)
            != (g.document_id, g.document_version_id, g.chunk_set_id)
            or any(
                value is not None
                for value in (
                    c.embedding_set_id,
                    c.embedding_configuration_id,
                    c.cosine_distance,
                    c.similarity,
                    c.vector_contribution,
                    c.fts_contribution,
                )
            )
            or (c.bm25_rank, c.bm25_score, c.index_generation_id)
            != (o.branch_rank, o.raw_score, o.index_generation_id)
        ):
            invalid()
        order = (-o.raw_score, o.branch_rank if native_full_window else c.chunk_id)
        if previous is not None and order < previous:
            invalid()
        previous = order
