"""Competing real transactions must not publish conflicting lexical authority."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from dataclasses import replace
from threading import Barrier
from uuid import uuid4

import test_s2_search_index_store as lifecycle
from sqlalchemy import select

from knora.adapters.postgres.database import SessionFactory
from knora.adapters.postgres.search_index_store import PostgresSearchIndexStore
from knora.adapters.postgres.tables import LexicalGenerationTable, LexicalHeadTable
from knora.ingestion.search_indexing import StageReceipt, StaleGenerationError

lexical_generation = lifecycle.lexical_generation


def test_competing_desired_requests_have_one_cas_winner(lexical_generation):
    generations = (lexical_generation, replace(lexical_generation, generation_id=str(uuid4())))
    start = Barrier(2)

    def request(generation):
        start.wait(timeout=5)
        try:
            PostgresSearchIndexStore(SessionFactory).request_generation(
                generation, expected_revision=0
            )
            return generation.generation_id
        except StaleGenerationError:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        winners = [result for result in pool.map(request, generations) if result is not None]
    assert len(winners) == 1
    with SessionFactory() as session:
        head = session.get(LexicalHeadTable, lexical_generation.document_id)
        assert head.desired_generation_id == winners[0] and head.revision == 1
        rows = session.scalars(
            select(LexicalGenerationTable).where(
                LexicalGenerationTable.document_id == lexical_generation.document_id
            )
        ).all()
        assert [row.id for row in rows] == winners


def test_concurrent_revoke_and_activation_end_revoked(lexical_generation):
    generation = lexical_generation
    store = PostgresSearchIndexStore(SessionFactory)
    store.request_generation(generation, expected_revision=0)
    receipt = StageReceipt(generation.generation_id, 1, generation.content_digest())
    start = Barrier(2)

    def activate():
        start.wait(timeout=5)
        with suppress(StaleGenerationError):
            store.activate_ready(generation, receipt)

    def revoke():
        start.wait(timeout=5)
        store.revoke(workspace_id=generation.workspace_id, document_id=generation.document_id)

    with ThreadPoolExecutor(max_workers=2) as pool:
        operations = [pool.submit(activate), pool.submit(revoke)]
        for operation in operations:
            operation.result(timeout=10)
    with SessionFactory() as session:
        head = session.get(LexicalHeadTable, generation.document_id)
        assert head.active_generation_id is None and head.desired_generation_id is None
        assert session.get(LexicalGenerationTable, generation.generation_id).status == "revoked"
