"""Offline reader wiring; real PostgreSQL snapshots require separate runtime evidence."""

from contextlib import contextmanager
from dataclasses import asdict, replace
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import pytest_asyncio
from backend.test.adapters.postgres.test_s2_population_read_fence import (
    population_snapshot as population_snapshot,
)
from backend.test.answering.test_bm25_contract import LexicalStore, candidate, execute, observation

from knora.adapters.postgres import evaluation_reader as reader_module
from knora.adapters.postgres.tables import ChunkTable, DocumentVersionTable
from knora.answering.stores import LexicalGeneration


@pytest_asyncio.fixture
async def lexical_reader(population_snapshot, monkeypatch):
    session, generations, manifest, objects, _ = population_snapshot
    first = generations[0]
    chunk = objects[ChunkTable, first.chunks[0].chunk_id]
    item = replace(
        candidate(),
        document_id=first.document_id,
        document_version_id=first.document_version_id,
        chunk_set_id=first.chunk_set_id,
        chunk_id=chunk.id,
        chunk_ordinal=chunk.ordinal,
        content=chunk.content,
        content_checksum=chunk.content_checksum,
        index_generation_id=first.generation_id,
    )
    snapshots = tuple(
        LexicalGeneration(
            g.workspace_id,
            g.document_id,
            g.document_version_id,
            g.chunk_set_id,
            g.generation_id,
            g.lexical_profile.id,
        )
        for g in generations
    )
    store = LexicalStore((item,))
    store.result = replace(
        store.result,
        candidates=(item,),
        lexical_generations=snapshots,
        chunk_set_ids=tuple(g.chunk_set_id for g in generations),
        branch_observations=(replace(observation(item), index_generation_id=first.generation_id),),
    )
    await execute(store)
    record = store.traces[0]
    trace = SimpleNamespace(id="trace-1", **asdict(record))
    version = objects[DocumentVersionTable, first.document_version_id]
    version.id = first.document_version_id
    document = SimpleNamespace(id=first.document_id, workspace_id="workspace", source_key="pdf")
    chunk_set = SimpleNamespace(
        id=first.chunk_set_id,
        parser_configuration_id="pypdf-layout-v2",
        normalizer_configuration_id="normalizer",
        chunking_configuration_id="chunker",
    )
    for key, value in dict(
        start_line=1,
        end_line=1,
        page_start=1,
        page_end=1,
        start_offset=0,
        end_offset=len(chunk.content),
        token_count=2,
    ).items():
        setattr(chunk, key, value)
    rows = [(chunk, document, version, chunk_set)]
    events = []
    session.scalar = lambda _: trace
    session.execute = lambda _: SimpleNamespace(all=lambda: rows)
    session.get_bind = lambda: object()
    session.connection = lambda **kw: events.append(kw)

    @contextmanager
    def sessions():
        yield session

    authority = Mock()
    authority.read_active_generations_in_snapshot.return_value = generations
    monkeypatch.setattr(
        reader_module, "PostgresSearchIndexStore", lambda _: authority, raising=False
    )
    return SimpleNamespace(
        sessions=sessions,
        manifest=manifest,
        trace=trace,
        rows=rows,
        authority=authority,
        session=session,
        events=events,
        objects=objects,
        first=first,
        generations=generations,
    )


@pytest.mark.asyncio
async def test_bm25_reader_resolves_authority_and_content_in_one_snapshot(lexical_reader):
    f = lexical_reader
    reader = reader_module.PostgresEvaluationReader(f.sessions, lexical_population=f.manifest)
    trace = reader.read_trace(trace_id="trace-1", workspace_id="workspace")
    assert trace.embedding_configuration_id is None
    assert trace.candidates[0].content == f.rows[0][0].content
    assert trace.candidates[0].bm25_contribution["raw_score"] == 12.5
    assert f.events == [{"execution_options": {"isolation_level": "REPEATABLE READ"}}]
    f.authority.read_active_generations_in_snapshot.assert_called_once_with(
        f.session, "workspace", f.manifest.profile.id
    )
    f.authority.revalidate_lexical_snapshot_in_transaction.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mutation",
    [
        "manifest",
        "authority",
        "missing_candidate",
        "foreign_branch",
        "branch_generation",
        "source",
        "alias",
        "foreign_version",
        "workspace",
    ],
)
async def test_bm25_reader_rejects_invalid_authority_and_trace(lexical_reader, mutation):
    f = lexical_reader
    manifest = f.manifest
    if mutation == "manifest":
        manifest = None
    elif mutation == "authority":
        f.authority.read_active_generations_in_snapshot.return_value = (
            replace(f.first, generation_id="replacement"),
            *f.authority.read_active_generations_in_snapshot.return_value[1:],
        )
    elif mutation == "missing_candidate":
        f.rows.clear()
    elif mutation == "foreign_branch":
        f.trace.branch_observations[0]["chunk_id"] = "foreign"
    elif mutation == "branch_generation":
        f.trace.branch_observations[0]["index_generation_id"] = "foreign"
    elif mutation == "source":
        f.objects[DocumentVersionTable, f.first.document_version_id].raw_sha256 = "0" * 64
    elif mutation == "alias":
        f.trace.alias_mapping = {"E1": "foreign"}
    elif mutation == "foreign_version":
        f.rows[0][2].id = "foreign"
    else:
        f.trace.workspace_id = "foreign"
    reader = reader_module.PostgresEvaluationReader(f.sessions, lexical_population=manifest)
    with pytest.raises(LookupError, match="lexical"):
        reader.read_trace(trace_id="trace-1", workspace_id="workspace")


@pytest.mark.asyncio
@pytest.mark.parametrize("missing_chunk", [False, True])
async def test_pdf_binding_reads_only_the_complete_lexical_population(
    lexical_reader, missing_chunk
):
    f = lexical_reader
    f.rows.clear()
    for g in f.generations:
        document = SimpleNamespace(
            id=g.document_id, workspace_id="workspace", source_key=g.document_id
        )
        version = f.objects[DocumentVersionTable, g.document_version_id]
        version.id = g.document_version_id
        chunk_set = SimpleNamespace(
            id=g.chunk_set_id,
            parser_configuration_id="pypdf-layout-v2",
            normalizer_configuration_id="normalizer",
            chunking_configuration_id="chunker",
        )
        for expected in g.chunks:
            chunk = f.objects[ChunkTable, expected.chunk_id]
            for key, value in dict(
                start_line=1,
                end_line=1,
                page_start=1,
                page_end=1,
                start_offset=0,
                end_offset=len(chunk.content),
                token_count=2,
            ).items():
                setattr(chunk, key, value)
            f.rows.append((chunk, document, version, chunk_set))
    if missing_chunk:
        f.rows.pop()
    reader = reader_module.PostgresEvaluationReader(f.sessions, lexical_population=f.manifest)
    if missing_chunk:
        with pytest.raises(LookupError, match="lexical"):
            reader.read_pdf_chunks(workspace_id="workspace")
    else:
        chunks = reader.read_pdf_chunks(workspace_id="workspace")
        assert len(chunks) == 47
        assert {c.chunk_id for c in chunks} == {r[0].id for r in f.rows}
        assert f.events == [{"execution_options": {"isolation_level": "REPEATABLE READ"}}]
