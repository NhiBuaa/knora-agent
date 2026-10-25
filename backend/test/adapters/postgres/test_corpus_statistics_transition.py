"""Tests for consistent atomic generation transition and dynamic corpus snapshot loading."""

from __future__ import annotations

import hashlib
import json
from contextlib import nullcontext
from dataclasses import asdict

import pytest

from knora.adapters.postgres.search_index_store import PostgresSearchIndexStore
from knora.adapters.postgres.tables import (
    ChunkSetTable,
    ChunkTable,
    DocumentTable,
    DocumentVersionTable,
    LexicalGenerationTable,
    LexicalHeadTable,
    WorkspaceTable,
)
from knora.domain.errors import KnoraError
from knora.ingestion.lexical_population import CorpusStatisticsSnapshot
from knora.ingestion.search_indexing import (
    LexicalChunk,
    LexicalGeneration,
    LexicalProfile,
    StageReceipt,
    StaleGenerationError,
)

DOC_1 = "d1" * 32
DOC_2 = "d2" * 32
CHUNK_1_TEXT = "Chunk one text"
CHUNK_2_TEXT = "Chunk two text"
CHUNK_1_HASH = hashlib.sha256(b"Chunk one text").hexdigest()
CHUNK_2_HASH = hashlib.sha256(b"Chunk two text").hexdigest()


class MockScalarResult:
    def __init__(self, items: list[object]) -> None:
        self._items = items

    def all(self) -> list[object]:
        return self._items

    def __iter__(self):
        return iter(self._items)


class MockSession:
    def __init__(self, rows: list[object]) -> None:
        self.rows: dict[tuple[type, str], object] = {
            (type(r), getattr(r, "id", None)): r for r in rows if getattr(r, "id", None) is not None
        }
        self.heads: dict[str, LexicalHeadTable] = {
            r.document_id: r for r in rows if isinstance(r, LexicalHeadTable)
        }

    def get(self, model: type, identity: str):
        if model is LexicalHeadTable:
            return self.heads.get(identity)
        return self.rows.get((model, identity))

    def scalar(self, statement):
        model = statement.column_descriptions[0]["entity"]
        params = statement.compile().params
        if model is WorkspaceTable:
            return self.get(WorkspaceTable, params.get("id_1"))
        if model is DocumentTable:
            doc = self.get(DocumentTable, params.get("id_1"))
            if doc and doc.workspace_id == params.get("workspace_id_1"):
                return doc
            return None
        return None

    def scalars(self, statement):
        model = statement.column_descriptions[0]["entity"]
        params = statement.compile().params
        if model is DocumentTable:
            ws_id = params.get("workspace_id_1")
            doc_ids = sorted(
                [
                    r.id
                    for (m, _), r in self.rows.items()
                    if m is DocumentTable
                    and r.workspace_id == ws_id
                    and not r.archived
                    and self.heads.get(r.id)
                    and self.heads[r.id].active_generation_id
                ]
            )
            return MockScalarResult(doc_ids)
        if model is ChunkTable:
            cs_id = params.get("chunk_set_id_1")
            chunks = sorted(
                [
                    r
                    for (m, _), r in self.rows.items()
                    if m is ChunkTable and r.chunk_set_id == cs_id
                ],
                key=lambda c: c.ordinal,
            )
            return MockScalarResult(chunks)
        if model is LexicalGenerationTable:
            doc_id = params.get("document_id_1")
            gens = [
                r
                for (m, _), r in self.rows.items()
                if m is LexicalGenerationTable and r.document_id == doc_id
            ]
            return MockScalarResult(gens)
        return MockScalarResult([])

    def add(self, obj: object) -> None:
        if isinstance(obj, LexicalHeadTable):
            self.heads[obj.document_id] = obj
        elif hasattr(obj, "id"):
            self.rows[(type(obj), obj.id)] = obj

    def flush(self) -> None:
        pass


class MockSessionFactory:
    def __init__(self, session: MockSession) -> None:
        self.session = session

    def begin(self):
        return nullcontext(self.session)


def build_harness() -> tuple[PostgresSearchIndexStore, MockSession, dict[str, object]]:
    # Create initial dynamic snapshot for 2 documents
    snapshot_a = CorpusStatisticsSnapshot.build(
        population_id="corpus-dynamic-v1",
        documents=[
            (DOC_1, [(CHUNK_1_HASH, 3)]),
            (DOC_2, [(CHUNK_2_HASH, 5)]),
        ],
    )
    profile_a = snapshot_a.profile

    gen1_a = LexicalGeneration(
        generation_id="gen-1-a",
        workspace_id="workspace-1",
        document_id="doc-1",
        document_version_id="ver-1",
        chunk_set_id="cs-1",
        lexical_profile=profile_a,
        revision=1,
        chunks=(LexicalChunk("c-1", 0, CHUNK_1_HASH),),
    )
    gen2_a = LexicalGeneration(
        generation_id="gen-2-a",
        workspace_id="workspace-1",
        document_id="doc-2",
        document_version_id="ver-2",
        chunk_set_id="cs-2",
        lexical_profile=profile_a,
        revision=1,
        chunks=(LexicalChunk("c-2", 0, CHUNK_2_HASH),),
    )

    ws = WorkspaceTable(id="workspace-1", archived=False, revision=1)
    doc1 = DocumentTable(
        id="doc-1",
        workspace_id="workspace-1",
        archived=False,
        revision=1,
        current_document_version_id="ver-1",
    )
    doc2 = DocumentTable(
        id="doc-2",
        workspace_id="workspace-1",
        archived=False,
        revision=1,
        current_document_version_id="ver-2",
    )
    ver1 = DocumentVersionTable(
        id="ver-1", document_id="doc-1", raw_sha256=DOC_1, media_type="application/pdf"
    )
    ver2 = DocumentVersionTable(
        id="ver-2", document_id="doc-2", raw_sha256=DOC_2, media_type="application/pdf"
    )
    cs1 = ChunkSetTable(
        id="cs-1",
        document_version_id="ver-1",
        status="completed",
        parser_configuration_id="p",
        normalizer_configuration_id="n",
        chunking_configuration_id="c",
    )
    cs2 = ChunkSetTable(
        id="cs-2",
        document_version_id="ver-2",
        status="completed",
        parser_configuration_id="p",
        normalizer_configuration_id="n",
        chunking_configuration_id="c",
    )
    c1 = ChunkTable(
        id="c-1",
        chunk_set_id="cs-1",
        ordinal=0,
        content=CHUNK_1_TEXT,
        content_checksum=CHUNK_1_HASH,
        token_count=3,
    )
    c2 = ChunkTable(
        id="c-2",
        chunk_set_id="cs-2",
        ordinal=0,
        content=CHUNK_2_TEXT,
        content_checksum=CHUNK_2_HASH,
        token_count=5,
    )

    row1_a = LexicalGenerationTable(
        id="gen-1-a",
        workspace_id="workspace-1",
        document_id="doc-1",
        document_version_id="ver-1",
        chunk_set_id="cs-1",
        revision=1,
        source_revision=1,
        workspace_revision=1,
        profile_digest=profile_a.digest(),
        content_digest=gen1_a.content_digest(),
        expected_count=1,
        acknowledged_count=1,
        manifest=json.loads(json.dumps(asdict(gen1_a))),
        status="active",
    )
    row2_a = LexicalGenerationTable(
        id="gen-2-a",
        workspace_id="workspace-1",
        document_id="doc-2",
        document_version_id="ver-2",
        chunk_set_id="cs-2",
        revision=1,
        source_revision=1,
        workspace_revision=1,
        profile_digest=profile_a.digest(),
        content_digest=gen2_a.content_digest(),
        expected_count=1,
        acknowledged_count=1,
        manifest=json.loads(json.dumps(asdict(gen2_a))),
        status="active",
    )
    head1 = LexicalHeadTable(
        document_id="doc-1",
        revision=1,
        active_generation_id="gen-1-a",
        desired_generation_id="gen-1-a",
    )
    head2 = LexicalHeadTable(
        document_id="doc-2",
        revision=1,
        active_generation_id="gen-2-a",
        desired_generation_id="gen-2-a",
    )

    rows = [ws, doc1, doc2, ver1, ver2, cs1, cs2, c1, c2, row1_a, row2_a, head1, head2]
    session = MockSession(rows)
    store = PostgresSearchIndexStore(MockSessionFactory(session))
    return (
        store,
        session,
        {
            "profile_a": profile_a,
            "gen1_a": gen1_a,
            "gen2_a": gen2_a,
            "row1_a": row1_a,
            "row2_a": row2_a,
            "head1": head1,
            "head2": head2,
            "doc1": doc1,
            "doc2": doc2,
            "ws": ws,
        },
    )


def test_consistent_atomic_generation_transition() -> None:
    store, session, ctx = build_harness()
    profile_a = ctx["profile_a"]

    # 1. Before transition, reader returns 2 active generations with profile A
    active = store.read_active_generations("workspace-1", profile_a.id)
    assert len(active) == 2
    assert active[0].generation_id == "gen-1-a"
    assert active[1].generation_id == "gen-2-a"
    assert {g.lexical_profile.digest() for g in active} == {profile_a.digest()}

    # 2. Build updated snapshot with altered token counts (reweight/rebuild)
    snapshot_b = CorpusStatisticsSnapshot.build(
        population_id="corpus-dynamic-v1",
        documents=[
            (DOC_1, [(CHUNK_1_HASH, 4)]),
            (DOC_2, [(CHUNK_2_HASH, 6)]),
        ],
    )
    profile_b = snapshot_b.profile
    assert profile_b.digest() != profile_a.digest()

    gen1_b = LexicalGeneration(
        generation_id="gen-1-b",
        workspace_id="workspace-1",
        document_id="doc-1",
        document_version_id="ver-1",
        chunk_set_id="cs-1",
        lexical_profile=profile_b,
        revision=2,
        chunks=(LexicalChunk("c-1", 0, CHUNK_1_HASH),),
    )
    gen2_b = LexicalGeneration(
        generation_id="gen-2-b",
        workspace_id="workspace-1",
        document_id="doc-2",
        document_version_id="ver-2",
        chunk_set_id="cs-2",
        lexical_profile=profile_b,
        revision=2,
        chunks=(LexicalChunk("c-2", 0, CHUNK_2_HASH),),
    )

    # Stage both generations for transition without disrupting active serving
    store.stage_corpus_transition([gen1_b, gen2_b])

    # While staging, reader still returns the old profile A generations
    active_during_staging = store.read_active_generations("workspace-1", profile_a.id)
    assert len(active_during_staging) == 2
    assert {g.lexical_profile.digest() for g in active_during_staging} == {profile_a.digest()}

    # 3. Receipts arrive for both generations
    receipt1 = StageReceipt("gen-1-b", 1, gen1_b.content_digest())
    receipt2 = StageReceipt("gen-2-b", 1, gen2_b.content_digest())

    # 4. Atomic CAS commit of both generations
    store.commit_corpus_transition([(gen1_b, receipt1), (gen2_b, receipt2)])

    # 5. Reader now returns profile B generations for both documents atomically
    active_after = store.read_active_generations("workspace-1", profile_b.id)
    assert len(active_after) == 2
    assert active_after[0].generation_id == "gen-1-b"
    assert active_after[1].generation_id == "gen-2-b"
    assert {g.lexical_profile.digest() for g in active_after} == {profile_b.digest()}


def test_transition_fails_on_mixed_profiles_in_batch() -> None:
    store, session, ctx = build_harness()
    profile_a = ctx["profile_a"]

    profile_other = LexicalProfile(
        "corpus-dynamic-v1", "word", "qdrant-1.19.2", 1.2, 0.75, 99.0, "other-stats"
    )

    gen1 = LexicalGeneration(
        generation_id="gen-1-b",
        workspace_id="workspace-1",
        document_id="doc-1",
        document_version_id="ver-1",
        chunk_set_id="cs-1",
        lexical_profile=profile_a,
        revision=2,
        chunks=(LexicalChunk("c-1", 0, CHUNK_1_HASH),),
    )
    gen2 = LexicalGeneration(
        generation_id="gen-2-b",
        workspace_id="workspace-1",
        document_id="doc-2",
        document_version_id="ver-2",
        chunk_set_id="cs-2",
        lexical_profile=profile_other,
        revision=2,
        chunks=(LexicalChunk("c-2", 0, CHUNK_2_HASH),),
    )
    receipt1 = StageReceipt("gen-1-b", 1, gen1.content_digest())
    receipt2 = StageReceipt("gen-2-b", 1, gen2.content_digest())

    with pytest.raises(StaleGenerationError, match="mixed profile digests"):
        store.commit_corpus_transition([(gen1, receipt1), (gen2, receipt2)])


def test_transition_fails_when_document_revoked() -> None:
    store, session, ctx = build_harness()
    profile_a = ctx["profile_a"]

    gen1 = LexicalGeneration(
        generation_id="gen-1-b",
        workspace_id="workspace-1",
        document_id="doc-1",
        document_version_id="ver-1",
        chunk_set_id="cs-1",
        lexical_profile=profile_a,
        revision=2,
        chunks=(LexicalChunk("c-1", 0, CHUNK_1_HASH),),
    )
    store.request_generation(gen1, expected_revision=1)
    receipt1 = StageReceipt("gen-1-b", 1, gen1.content_digest())

    # Document 1 is revoked prior to commit
    store.revoke(workspace_id="workspace-1", document_id="doc-1")

    with pytest.raises(StaleGenerationError, match="transition compare-and-set failed"):
        store.commit_corpus_transition([(gen1, receipt1)])


def test_transition_rejects_empty_batch() -> None:
    store, _, _ = build_harness()
    with pytest.raises(StaleGenerationError, match="cannot be empty"):
        store.commit_corpus_transition([])


def test_reader_fails_closed_when_profiles_mismatched() -> None:
    store, session, ctx = build_harness()
    profile_a = ctx["profile_a"]
    row2_a = ctx["row2_a"]

    # Artificially alter doc2's profile_digest in DB row to simulate profile corruption
    row2_a.profile_digest = "corrupted-profile-digest"

    with pytest.raises(KnoraError) as exc:
        store.read_active_generations("workspace-1", profile_a.id)
    assert exc.value.code == "LEXICAL_RETRIEVAL_UNAVAILABLE"


class CorpusTransitionHarness:
    def __init__(self, store, session, ctx):
        self.store = store
        self.session = session
        self.ctx = ctx
        self.base_snapshot = ctx["profile_a"].digest()

    def prepare_two_document_transition(self):
        snapshot_b = CorpusStatisticsSnapshot.build(
            population_id="corpus-dynamic-v1",
            documents=[
                (DOC_1, [(CHUNK_1_HASH, 4)]),
                (DOC_2, [(CHUNK_2_HASH, 6)]),
            ],
        )
        self.profile_b = snapshot_b.profile
        self.snapshot_id = self.profile_b.digest()
        self.all_member_ids = ("doc-1", "doc-2")

        self.gen1_b = LexicalGeneration(
            generation_id="gen-1-b",
            workspace_id="workspace-1",
            document_id="doc-1",
            document_version_id="ver-1",
            chunk_set_id="cs-1",
            lexical_profile=self.profile_b,
            revision=2,
            chunks=(LexicalChunk("c-1", 0, CHUNK_1_HASH),),
        )
        self.gen2_b = LexicalGeneration(
            generation_id="gen-2-b",
            workspace_id="workspace-1",
            document_id="doc-2",
            document_version_id="ver-2",
            chunk_set_id="cs-2",
            lexical_profile=self.profile_b,
            revision=2,
            chunks=(LexicalChunk("c-2", 0, CHUNK_2_HASH),),
        )
        self.receipt1 = StageReceipt("gen-1-b", 1, self.gen1_b.content_digest())
        self.receipt2 = StageReceipt("gen-2-b", 1, self.gen2_b.content_digest())

        self.store.stage_corpus_transition([self.gen1_b, self.gen2_b])
        return self

    def finish_first_child(self, prepared) -> None:
        with pytest.raises(StaleGenerationError):
            self.store.commit_corpus_transition([(self.gen1_b, self.receipt1)])

    def active_snapshot(self) -> str:
        try:
            active_b = self.store.read_active_generations("workspace-1", self.profile_b.id)
            if {g.lexical_profile.digest() for g in active_b} == {self.snapshot_id}:
                return self.snapshot_id
        except Exception:
            pass
        active_a = self.store.read_active_generations("workspace-1", self.ctx["profile_a"].id)
        return active_a[0].lexical_profile.digest()

    def finish_last_child(self, prepared) -> None:
        self.store.commit_corpus_transition(
            [(self.gen1_b, self.receipt1), (self.gen2_b, self.receipt2)]
        )

    def active_member_ids(self) -> tuple[str, ...]:
        active = self.store.read_active_generations("workspace-1", self.profile_b.id)
        return tuple(sorted(g.document_id for g in active))


@pytest.fixture
def corpus_case():
    store, session, ctx = build_harness()
    return CorpusTransitionHarness(store, session, ctx)


def test_corpus_switch_requires_every_member_receipt(corpus_case: CorpusTransitionHarness) -> None:
    prepared = corpus_case.prepare_two_document_transition()
    corpus_case.finish_first_child(prepared)
    assert corpus_case.active_snapshot() == prepared.base_snapshot
    corpus_case.finish_last_child(prepared)
    assert corpus_case.active_snapshot() == prepared.snapshot_id
    assert corpus_case.active_member_ids() == prepared.all_member_ids
