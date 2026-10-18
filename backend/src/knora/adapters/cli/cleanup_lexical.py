"""Remove one stale lexical projection after PostgreSQL authority revalidation."""

from __future__ import annotations

import argparse
import json
import sys

import httpx

from knora.adapters.postgres.database import SessionFactory
from knora.adapters.postgres.search_index_store import PostgresSearchIndexStore
from knora.adapters.qdrant.native_search_index import (
    NativeQdrantSearchIndex,
    ProjectionResponseError,
)
from knora.adapters.qdrant.search_index import QdrantSearchIndex
from knora.answering.retrieval_configuration import resolve_retrieval_configuration
from knora.infrastructure.lexical_configuration import load_lexical_population
from knora.infrastructure.settings import settings
from knora.ingestion.search_indexing import LexicalProjectionUnavailable


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Remove one PostgreSQL-authorized stale lexical projection"
    )
    parser.add_argument("generation_id")
    return parser


def run_cleanup(generation_id: str) -> dict[str, str]:
    if not generation_id:
        raise ValueError("generation_id is required")
    configuration = resolve_retrieval_configuration(
        settings.retrieval_configuration_id,
        vector_min_similarity=settings.vector_min_similarity,
    )
    population = load_lexical_population(configuration, settings.lexical_population_manifest)
    if (
        population is None
        or not settings.lexical_qdrant_url
        or not settings.lexical_qdrant_collection
    ):
        raise ValueError("lexical cleanup requires a reviewed Qdrant configuration")
    with httpx.Client(base_url=settings.lexical_qdrant_url, timeout=10, trust_env=False) as client:
        index = NativeQdrantSearchIndex(
            index=QdrantSearchIndex(settings.lexical_qdrant_collection, population.profile),
            client=client,
        )
        store = PostgresSearchIndexStore(SessionFactory)
        with SessionFactory.begin() as session:
            outcome = store.cleanup_generation_in_transaction(
                session, generation_id, index.remove_generation
            )
    return {"generation_id": generation_id, "outcome": outcome}


def main() -> int:
    args = build_parser().parse_args()
    try:
        print(json.dumps(run_cleanup(args.generation_id), ensure_ascii=False))
    except (LexicalProjectionUnavailable, ProjectionResponseError, OSError, ValueError) as error:
        print(
            json.dumps(
                {
                    "error": error.__class__.__name__,
                    "retryable": isinstance(error, LexicalProjectionUnavailable),
                }
            ),
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
