"""Private answering collaborator: one projection query and PostgreSQL hydration."""

import hashlib

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from knora.adapters.postgres.search_index_store import PostgresSearchIndexStore
from knora.adapters.postgres.tables import ChunkTable, DocumentTable, DocumentVersionTable
from knora.adapters.qdrant.native_search_index import NativeQdrantSearchIndex
from knora.adapters.qdrant.search_index import (
    AuthorizedLexicalSnapshot,
    ProjectionResponseError,
)
from knora.answering.stores import (
    BranchObservation,
    RetrievalCandidate,
    RetrievalConfiguration,
    RetrievalResult,
)
from knora.answering.stores import LexicalGeneration as RetrievedLexicalGeneration
from knora.domain.errors import KnoraError
from knora.ingestion.lexical_population import LexicalPopulationError, VerifiedLexicalPopulation
from knora.ingestion.search_indexing import (
    LexicalGeneration,
    LexicalGenerationError,
    LexicalProjectionUnavailable,
)
from knora.providers.embedding import EmbeddingConfiguration


def validate_population_in_transaction(
    session: Session,
    workspace_id: str,
    generations: tuple[LexicalGeneration, ...],
    population: VerifiedLexicalPopulation | None,
) -> None:
    """Validate the whole serving population in the caller's authority transaction."""

    try:
        if population is None or not generations:
            raise LexicalPopulationError("verified population is required")

        document_ids = session.scalars(
            select(DocumentTable.id).where(
                DocumentTable.workspace_id == workspace_id,
                DocumentTable.archived.is_(False),
                DocumentTable.current_document_version_id.is_not(None),
            )
        ).all()

        if len(generations) != len(document_ids) or set(document_ids) != {
            g.document_id for g in generations
        }:
            raise LexicalPopulationError("serving population has changed")

        documents = []

        for generation in generations:
            if (
                generation.workspace_id != workspace_id
                or generation.lexical_profile.digest() != population.profile.digest()
            ):
                raise LexicalPopulationError("serving profile is not pinned")

            version = session.get(DocumentVersionTable, generation.document_version_id)

            if version is None or version.document_id != generation.document_id:
                raise LexicalPopulationError("serving version is foreign")

            texts = []

            for expected in sorted(generation.chunks, key=lambda c: c.ordinal):
                chunk = session.get(ChunkTable, expected.chunk_id)

                if (
                    chunk is None
                    or chunk.chunk_set_id != generation.chunk_set_id
                    or chunk.ordinal != expected.ordinal
                    or chunk.content_checksum != expected.content_checksum
                ):
                    raise LexicalPopulationError("serving chunk identity has changed")

                texts.append(chunk.content)

            documents.append((version.raw_sha256, tuple(texts)))

        population.validate_corpus(documents, population.profile)

    except LexicalPopulationError as exc:
        raise KnoraError("LEXICAL_RETRIEVAL_UNAVAILABLE") from exc


def validate_dynamic_population_in_transaction(
    session: Session,
    workspace_id: str,
    generations: tuple[LexicalGeneration, ...],
) -> None:
    """Validate dynamic serving population in the caller's authority transaction."""

    try:
        if not generations:
            raise LexicalPopulationError("serving population is empty")

        document_ids = session.scalars(
            select(DocumentTable.id).where(
                DocumentTable.workspace_id == workspace_id,
                DocumentTable.archived.is_(False),
                DocumentTable.current_document_version_id.is_not(None),
            )
        ).all()

        if len(generations) != len(document_ids) or set(document_ids) != {
            g.document_id for g in generations
        }:
            raise LexicalPopulationError("serving population has changed")

        for generation in generations:
            if generation.workspace_id != workspace_id:
                raise LexicalPopulationError("serving generation has foreign workspace")

            version = session.get(DocumentVersionTable, generation.document_version_id)

            if version is None or version.document_id != generation.document_id:
                raise LexicalPopulationError("serving version is foreign")

            for expected in generation.chunks:
                chunk = session.get(ChunkTable, expected.chunk_id)

                if (
                    chunk is None
                    or chunk.chunk_set_id != generation.chunk_set_id
                    or chunk.ordinal != expected.ordinal
                    or chunk.content_checksum != expected.content_checksum
                    or hashlib.sha256(chunk.content.encode("utf-8")).hexdigest()
                    != expected.content_checksum
                ):
                    raise LexicalPopulationError("serving chunk identity has changed")

    except LexicalPopulationError as exc:
        raise KnoraError("LEXICAL_RETRIEVAL_UNAVAILABLE") from exc


def retrieve_lexical_candidates(
    session_factory: sessionmaker,
    workspace_id: str,
    query_text: str,
    configuration: RetrievalConfiguration,
    projection: NativeQdrantSearchIndex,
    *,
    population: VerifiedLexicalPopulation | None = None,
) -> RetrievalResult:

    if configuration.strategy != "bm25-only" or not 1 <= configuration.candidate_k <= 200:
        raise KnoraError("LEXICAL_RETRIEVAL_UNAVAILABLE")

    if population is None:
        raise KnoraError("LEXICAL_RETRIEVAL_UNAVAILABLE")

    authority = PostgresSearchIndexStore(session_factory)

    generations = authority.read_active_generations(workspace_id, configuration.lexical_policy_id)

    profile = generations[0].lexical_profile

    snapshots = tuple(
        RetrievedLexicalGeneration(
            workspace_id,
            g.document_id,
            g.document_version_id,
            g.chunk_set_id,
            g.generation_id,
            profile.id,
            statistics_digest=getattr(profile, "statistics_digest", None),
        )
        for g in generations
    )

    authorized = AuthorizedLexicalSnapshot(
        workspace_id, tuple(g.generation_id for g in generations), profile.id, profile.digest()
    )

    with session_factory.begin() as session:
        authority.revalidate_lexical_snapshot_in_transaction(
            session, workspace_id, profile.id, snapshots
        )

        validate_population_in_transaction(session, workspace_id, generations, population)

    try:
        # The authority transaction has ended before projection I/O.

        hits = projection.query(authorized, query_text, limit=200)

    except (
        LexicalGenerationError,
        LexicalProjectionUnavailable,
        ProjectionResponseError,
    ) as exc:
        raise KnoraError("LEXICAL_RETRIEVAL_UNAVAILABLE") from exc

    by_id = {g.generation_id: g for g in generations}

    candidates, observations = [], []

    with session_factory.begin() as session:
        authority.revalidate_lexical_snapshot_in_transaction(
            session, workspace_id, profile.id, snapshots
        )

        validate_population_in_transaction(session, workspace_id, generations, population)

        for hit in hits:
            generation = by_id.get(hit["generation_id"])

            chunk = session.get(ChunkTable, hit["chunk_id"])

            expected = (
                next((c for c in generation.chunks if c.chunk_id == hit["chunk_id"]), None)
                if generation
                else None
            )

            if (
                expected is None
                or chunk is None
                or chunk.chunk_set_id != generation.chunk_set_id
                or chunk.ordinal != expected.ordinal
                or chunk.content_checksum != expected.content_checksum
                or hashlib.sha256(chunk.content.encode("utf-8")).hexdigest()
                != expected.content_checksum
                or hit["score_policy_digest"] != profile.digest()
            ):
                raise KnoraError("LEXICAL_RETRIEVAL_UNAVAILABLE")

            eligible = hit["rank"] <= configuration.candidate_k

            observations.append(
                BranchObservation(
                    branch="bm25",
                    status="ELIGIBLE" if eligible else "RANK_LIMIT",
                    chunk_id=chunk.id,
                    branch_rank=hit["rank"],
                    raw_score=hit["score"],
                    score_kind="bm25",
                    lexical_policy_id=profile.id,
                    index_generation_id=generation.generation_id,
                    decision_reason=None if eligible else "RANK_LIMIT",
                )
            )

            if not eligible:
                continue

            document = session.get(DocumentTable, generation.document_id)

            candidates.append(
                RetrievalCandidate(
                    document_id=document.id,
                    document_version_id=generation.document_version_id,
                    source_key=document.source_key,
                    source_name=document.source_name,
                    chunk_set_id=chunk.chunk_set_id,
                    embedding_set_id=None,
                    embedding_configuration_id=None,
                    chunk_id=chunk.id,
                    chunk_ordinal=chunk.ordinal,
                    heading_path=tuple(chunk.heading_path),
                    start_line=chunk.start_line,
                    end_line=chunk.end_line,
                    content=chunk.content,
                    content_checksum=chunk.content_checksum,
                    token_count=chunk.token_count,
                    cosine_distance=None,
                    similarity=None,
                    page_start=chunk.page_start,
                    page_end=chunk.page_end,
                    start_offset=chunk.start_offset,
                    end_offset=chunk.end_offset,
                    bm25_score=hit["score"],
                    bm25_rank=hit["rank"],
                    index_generation_id=generation.generation_id,
                )
            )

    if not hits:
        observations.append(
            BranchObservation(
                branch="bm25",
                status="NO_CONTRIBUTION",
                score_kind="bm25",
                lexical_policy_id=profile.id,
            )
        )

    return RetrievalResult(
        candidates=tuple(candidates),
        branch_observations=tuple(observations),
        chunk_set_ids=tuple(g.chunk_set_id for g in generations),
        lexical_generations=snapshots,
    )


def retrieve_dense_candidates(
    session_factory: sessionmaker,
    workspace_id: str,
    query_vector: tuple[float, ...] | list[float],
    configuration: RetrievalConfiguration,
    projection: NativeQdrantSearchIndex,
    *,
    embedding_configuration: EmbeddingConfiguration | None = None,
    population: VerifiedLexicalPopulation | None = None,
) -> RetrievalResult:

    if configuration.strategy != "dense-only" or not 1 <= configuration.candidate_k <= 200:
        raise KnoraError("LEXICAL_RETRIEVAL_UNAVAILABLE")

    if configuration.min_similarity is None:
        raise KnoraError("LEXICAL_RETRIEVAL_UNAVAILABLE")

    if not query_vector:
        raise KnoraError("LEXICAL_RETRIEVAL_UNAVAILABLE")

    if embedding_configuration and len(query_vector) != embedding_configuration.dimensions:
        raise KnoraError("EMBEDDING_DIMENSION_MISMATCH")

    authority = PostgresSearchIndexStore(session_factory)

    policy_id = configuration.lexical_policy_id or projection.index.profile.id

    generations = authority.read_active_generations(workspace_id, policy_id)

    profile = generations[0].lexical_profile

    snapshots = tuple(
        RetrievedLexicalGeneration(
            workspace_id,
            g.document_id,
            g.document_version_id,
            g.chunk_set_id,
            g.generation_id,
            profile.id,
            statistics_digest=getattr(profile, "statistics_digest", None),
        )
        for g in generations
    )

    authorized = AuthorizedLexicalSnapshot(
        workspace_id,
        tuple(g.generation_id for g in generations),
        profile.id,
        profile.digest(),
        embedding_configuration_id=embedding_configuration.id if embedding_configuration else None,
    )

    with session_factory.begin() as session:
        authority.revalidate_lexical_snapshot_in_transaction(
            session, workspace_id, profile.id, snapshots
        )

        if population is not None:
            validate_population_in_transaction(session, workspace_id, generations, population)

        else:
            validate_dynamic_population_in_transaction(session, workspace_id, generations)

    try:
        hits = projection.query_dense(
            authorized,
            query_vector,
            limit=200,
            hnsw_ef=256,
            rescore=True,
            oversampling=2.0,
        )

    except (
        LexicalGenerationError,
        LexicalProjectionUnavailable,
        ProjectionResponseError,
    ) as exc:
        raise KnoraError("LEXICAL_RETRIEVAL_UNAVAILABLE") from exc

    by_id = {g.generation_id: g for g in generations}

    candidates, observations = [], []

    with session_factory.begin() as session:
        authority.revalidate_lexical_snapshot_in_transaction(
            session, workspace_id, profile.id, snapshots
        )

        if population is not None:
            validate_population_in_transaction(session, workspace_id, generations, population)

        else:
            validate_dynamic_population_in_transaction(session, workspace_id, generations)

        for hit in hits:
            generation = by_id.get(hit["generation_id"])

            chunk = session.get(ChunkTable, hit["chunk_id"])

            expected = (
                next((c for c in generation.chunks if c.chunk_id == hit["chunk_id"]), None)
                if generation
                else None
            )

            if (
                expected is None
                or chunk is None
                or chunk.chunk_set_id != generation.chunk_set_id
                or chunk.ordinal != expected.ordinal
                or chunk.content_checksum != expected.content_checksum
                or hashlib.sha256(chunk.content.encode("utf-8")).hexdigest()
                != expected.content_checksum
                or hit["score_policy_digest"] != profile.digest()
            ):
                raise KnoraError("LEXICAL_RETRIEVAL_UNAVAILABLE")

            score = hit["score"]

            above_threshold = score >= configuration.min_similarity

            within_rank = hit["rank"] <= configuration.candidate_k

            eligible = above_threshold and within_rank

            status = (
                "ELIGIBLE"
                if eligible
                else ("SIMILARITY_THRESHOLD" if not above_threshold else "RANK_LIMIT")
            )

            observations.append(
                BranchObservation(
                    branch="dense",
                    status=status,
                    chunk_id=chunk.id,
                    branch_rank=hit["rank"],
                    cosine_distance=1.0 - score,
                    similarity=score,
                    raw_score=score,
                    score_kind="cosine_similarity",
                    index_generation_id=generation.generation_id,
                    decision_reason=None if eligible else status,
                )
            )

            if not eligible:
                continue

            document = session.get(DocumentTable, generation.document_id)

            active_emb_cfg = document.active_embedding_configuration_id if document else None

            active_emb_set = document.active_embedding_set_id if document else None

            if (
                embedding_configuration
                and active_emb_cfg
                and active_emb_cfg != embedding_configuration.id
            ):
                raise KnoraError("EMBEDDING_CONFIGURATION_MISMATCH")

            candidates.append(
                RetrievalCandidate(
                    document_id=document.id,
                    document_version_id=generation.document_version_id,
                    source_key=document.source_key,
                    source_name=document.source_name,
                    chunk_set_id=chunk.chunk_set_id,
                    embedding_set_id=active_emb_set,
                    embedding_configuration_id=(
                        active_emb_cfg
                        or (embedding_configuration.id if embedding_configuration else None)
                    ),
                    chunk_id=chunk.id,
                    chunk_ordinal=chunk.ordinal,
                    heading_path=tuple(chunk.heading_path),
                    start_line=chunk.start_line,
                    end_line=chunk.end_line,
                    content=chunk.content,
                    content_checksum=chunk.content_checksum,
                    token_count=chunk.token_count,
                    cosine_distance=1.0 - score,
                    similarity=score,
                    page_start=chunk.page_start,
                    page_end=chunk.page_end,
                    start_offset=chunk.start_offset,
                    end_offset=chunk.end_offset,
                    index_generation_id=generation.generation_id,
                )
            )

    if not hits:
        observations.append(
            BranchObservation(
                branch="dense",
                status="NO_CONTRIBUTION",
                score_kind="cosine_similarity",
            )
        )

    return RetrievalResult(
        candidates=tuple(candidates),
        branch_observations=tuple(observations),
        chunk_set_ids=tuple(g.chunk_set_id for g in generations),
        lexical_generations=snapshots,
    )


def retrieve_hybrid_candidates(
    session_factory: sessionmaker,
    workspace_id: str,
    query_text: str,
    query_vector: tuple[float, ...] | list[float],
    configuration: RetrievalConfiguration,
    projection: NativeQdrantSearchIndex,
    *,
    embedding_configuration: EmbeddingConfiguration | None = None,
    population: VerifiedLexicalPopulation | None = None,
) -> RetrievalResult:

    if (
        configuration.strategy != "hybrid"
        or configuration.fusion_policy_id != "dbsf-v1"
        or not 1 <= configuration.candidate_k <= 100
    ):
        raise KnoraError("LEXICAL_RETRIEVAL_UNAVAILABLE")

    if not query_text or not query_vector:
        raise KnoraError("LEXICAL_RETRIEVAL_UNAVAILABLE")

    if embedding_configuration and len(query_vector) != embedding_configuration.dimensions:
        raise KnoraError("EMBEDDING_DIMENSION_MISMATCH")

    authority = PostgresSearchIndexStore(session_factory)

    policy_id = configuration.lexical_policy_id or projection.index.profile.id

    generations = authority.read_active_generations(workspace_id, policy_id)

    profile = generations[0].lexical_profile

    snapshots = tuple(
        RetrievedLexicalGeneration(
            workspace_id,
            g.document_id,
            g.document_version_id,
            g.chunk_set_id,
            g.generation_id,
            profile.id,
            statistics_digest=getattr(profile, "statistics_digest", None),
        )
        for g in generations
    )

    authorized = AuthorizedLexicalSnapshot(
        workspace_id,
        tuple(g.generation_id for g in generations),
        profile.id,
        profile.digest(),
        embedding_configuration_id=embedding_configuration.id if embedding_configuration else None,
    )

    with session_factory.begin() as session:
        authority.revalidate_lexical_snapshot_in_transaction(
            session, workspace_id, profile.id, snapshots
        )

        if population is not None:
            validate_population_in_transaction(session, workspace_id, generations, population)

        else:
            validate_dynamic_population_in_transaction(session, workspace_id, generations)

    try:
        hits = projection.query_hybrid(
            authorized,
            query_text,
            query_vector,
            dense_limit=configuration.vector_candidate_k or 200,
            sparse_limit=configuration.fts_candidate_k or 200,
            final_limit=100,
            hnsw_ef=256,
            rescore=True,
            oversampling=2.0,
        )

    except (
        LexicalGenerationError,
        LexicalProjectionUnavailable,
        ProjectionResponseError,
    ) as exc:
        raise KnoraError("LEXICAL_RETRIEVAL_UNAVAILABLE") from exc

    by_id = {g.generation_id: g for g in generations}

    candidates, observations = [], []

    with session_factory.begin() as session:
        authority.revalidate_lexical_snapshot_in_transaction(
            session, workspace_id, profile.id, snapshots
        )

        if population is not None:
            validate_population_in_transaction(session, workspace_id, generations, population)

        else:
            validate_dynamic_population_in_transaction(session, workspace_id, generations)

        for hit in hits:
            generation = by_id.get(hit["generation_id"])

            chunk = session.get(ChunkTable, hit["chunk_id"])

            expected = (
                next((c for c in generation.chunks if c.chunk_id == hit["chunk_id"]), None)
                if generation
                else None
            )

            if (
                expected is None
                or chunk is None
                or chunk.chunk_set_id != generation.chunk_set_id
                or chunk.ordinal != expected.ordinal
                or chunk.content_checksum != expected.content_checksum
                or hashlib.sha256(chunk.content.encode("utf-8")).hexdigest()
                != expected.content_checksum
                or hit["score_policy_digest"] != profile.digest()
            ):
                raise KnoraError("LEXICAL_RETRIEVAL_UNAVAILABLE")

            score = hit["score"]

            eligible = hit["rank"] <= configuration.candidate_k

            observations.append(
                BranchObservation(
                    branch="fused",
                    status="ELIGIBLE" if eligible else "RANK_LIMIT",
                    chunk_id=chunk.id,
                    branch_rank=hit["rank"],
                    raw_score=score,
                    score_kind="dbsf",
                    index_generation_id=generation.generation_id,
                    decision_reason=None if eligible else "RANK_LIMIT",
                )
            )

            if not eligible:
                continue

            document = session.get(DocumentTable, generation.document_id)

            active_emb_cfg = document.active_embedding_configuration_id if document else None

            active_emb_set = document.active_embedding_set_id if document else None

            if (
                embedding_configuration
                and active_emb_cfg
                and active_emb_cfg != embedding_configuration.id
            ):
                raise KnoraError("EMBEDDING_CONFIGURATION_MISMATCH")

            candidates.append(
                RetrievalCandidate(
                    document_id=document.id,
                    document_version_id=generation.document_version_id,
                    source_key=document.source_key,
                    source_name=document.source_name,
                    chunk_set_id=chunk.chunk_set_id,
                    embedding_set_id=active_emb_set,
                    embedding_configuration_id=(
                        active_emb_cfg
                        or (embedding_configuration.id if embedding_configuration else None)
                    ),
                    chunk_id=chunk.id,
                    chunk_ordinal=chunk.ordinal,
                    heading_path=tuple(chunk.heading_path),
                    start_line=chunk.start_line,
                    end_line=chunk.end_line,
                    content=chunk.content,
                    content_checksum=chunk.content_checksum,
                    token_count=chunk.token_count,
                    cosine_distance=None,
                    similarity=None,
                    fusion_score=score,
                    page_start=chunk.page_start,
                    page_end=chunk.page_end,
                    start_offset=chunk.start_offset,
                    end_offset=chunk.end_offset,
                    index_generation_id=generation.generation_id,
                )
            )

    if not hits:
        observations.append(
            BranchObservation(
                branch="fused",
                status="NO_CONTRIBUTION",
                score_kind="dbsf",
            )
        )

    return RetrievalResult(
        candidates=tuple(candidates),
        branch_observations=tuple(observations),
        chunk_set_ids=tuple(g.chunk_set_id for g in generations),
        lexical_generations=snapshots,
    )
