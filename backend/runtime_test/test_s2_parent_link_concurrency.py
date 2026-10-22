"""Real trigger races using new structural fixtures in the owned S2 database."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import UTC, datetime
from queue import Queue
from time import monotonic, sleep
from uuid import uuid4

import pytest
import test_s2_search_index_store as lifecycle
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from knora.adapters.postgres.database import SessionFactory
from knora.adapters.postgres.search_index_store import PostgresSearchIndexStore
from knora.adapters.postgres.tables import (
    ChunkSetTable,
    DocumentVersionTable,
    IngestionJobTable,
    OriginalSourceObjectTable,
)

lexical_generation = lifecycle.lexical_generation


@pytest.fixture
def parent_and_pending_child(lexical_generation):
    # Terminal structural rows test the trigger; the separate coordinator tests prove real jobs.
    generation = lexical_generation
    source_id = str(uuid4())
    with SessionFactory.begin() as session:
        version = session.get(DocumentVersionTable, generation.document_version_id)
        version.raw_sha256 = "a" * 64
        version.media_type = "application/pdf"
        session.add(
            OriginalSourceObjectTable(
                id=source_id,
                workspace_id=generation.workspace_id,
                document_version_id=generation.document_version_id,
                object_key="q10-structural-" + uuid4().hex,
                raw_sha256="a" * 64,
                byte_size=1,
                media_type="application/pdf",
            )
        )
        chunk_set = session.get(ChunkSetTable, generation.chunk_set_id)
        chunk_set.parser_configuration_id = "fixture"
        chunk_set.normalizer_configuration_id = "fixture"
        common = {
            "workspace_id": generation.workspace_id,
            "operation": "submit_pdf",
            "document_id": generation.document_id,
            "target_document_version_id": generation.document_version_id,
            "source_object_id": source_id,
            "parser_configuration_id": "fixture",
            "normalizer_configuration_id": "fixture",
            "chunking_configuration_id": chunk_set.chunking_configuration_id,
            "source_revision": 0,
            "workspace_revision": 0,
        }
    profile = {**asdict(generation.lexical_profile), "digest": generation.lexical_profile.digest()}
    PostgresSearchIndexStore(SessionFactory).request_generation(generation, expected_revision=0)
    parent_id = str(uuid4())
    with SessionFactory.begin() as session:
        session.add(
            IngestionJobTable(
                id=parent_id,
                **common,
                content_fingerprint="q10-structural-parent-" + uuid4().hex,
                derivation_kind="pdf_extraction",
                lexical_profile=profile,
                status="succeeded",
                attempt_count=1,
                terminal_outcome_code="succeeded",
                started_at=datetime.now(UTC),
                terminal_at=datetime.now(UTC),
            )
        )
    return parent_id, {
        "id": str(uuid4()),
        **common,
        "content_fingerprint": "q10-structural-child-" + uuid4().hex,
        "derivation_kind": "lexical_index",
        "lexical_generation_id": generation.generation_id,
        "parent_ingestion_job_id": parent_id,
        # Structural terminal rows never enter the worker queue.
        "status": "succeeded",
        "attempt_count": 1,
        "started_at": datetime.now(UTC),
        "terminal_at": datetime.now(UTC),
        "terminal_outcome_code": "succeeded",
    }


def _session_pid(session):
    session.execute(text("SET LOCAL statement_timeout = '10s'"))
    return session.scalar(text("SELECT pg_backend_pid()"))


def _assert_blocked_by(waiter, blocker):
    deadline = monotonic() + 5
    while monotonic() < deadline:
        # Each observation gets fresh PostgreSQL activity statistics.
        with SessionFactory() as observer:
            state = observer.execute(
                text(
                    "SELECT wait_event_type, pg_blocking_pids(pid) "
                    "FROM pg_stat_activity WHERE pid = :pid"
                ),
                {"pid": waiter},
            ).one()
            if state[0] == "Lock" and blocker in state[1]:
                return
        sleep(0.02)
    pytest.fail("the competing statement never waited for the expected transaction")


def test_child_first_prevents_parent_identity_mutation_after_wait(parent_and_pending_child):
    parent_id, child = parent_and_pending_child
    pids = Queue()

    def update_parent():
        try:
            with SessionFactory.begin() as session:
                pids.put(_session_pid(session))
                session.execute(
                    text(
                        "UPDATE ingestion_jobs SET parser_configuration_id = 'changed' "
                        "WHERE id = :id"
                    ),
                    {"id": parent_id},
                )
        except IntegrityError as error:
            return error.orig.sqlstate, str(error.orig)
        pytest.fail("parent identity changed after its child committed")

    with ThreadPoolExecutor(max_workers=1) as pool:
        with SessionFactory.begin() as session:
            blocker = _session_pid(session)
            session.add(IngestionJobTable(**child))
            session.flush()
            pending = pool.submit(update_parent)
            _assert_blocked_by(pids.get(timeout=5), blocker)
        code, message = pending.result(timeout=15)
    assert code == "23514" and "linked extraction identity is immutable" in message
    with SessionFactory() as session:
        assert (
            session.get(IngestionJobTable, parent_id).parser_configuration_id
            == child["parser_configuration_id"]
        )
        assert session.get(IngestionJobTable, child["id"]).parent_ingestion_job_id == parent_id


def test_parent_first_rejects_child_against_changed_identity_after_wait(parent_and_pending_child):
    parent_id, child = parent_and_pending_child
    pids = Queue()

    def insert_child():
        try:
            with SessionFactory.begin() as session:
                pids.put(_session_pid(session))
                session.add(IngestionJobTable(**child))
                session.flush()
        except IntegrityError as error:
            return error.orig.sqlstate, str(error.orig)
        pytest.fail("child accepted the previous parent identity after the parent committed")

    with ThreadPoolExecutor(max_workers=1) as pool:
        with SessionFactory.begin() as session:
            blocker = _session_pid(session)
            session.execute(
                text(
                    "UPDATE ingestion_jobs SET parser_configuration_id = 'changed' WHERE id = :id"
                ),
                {"id": parent_id},
            )
            pending = pool.submit(insert_child)
            _assert_blocked_by(pids.get(timeout=5), blocker)
        code, message = pending.result(timeout=15)
    assert code == "23514" and "invalid lexical index parent" in message
    with SessionFactory() as session:
        assert session.get(IngestionJobTable, parent_id).parser_configuration_id == "changed"
        assert session.get(IngestionJobTable, child["id"]) is None
