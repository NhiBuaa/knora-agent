"""Exercise population checks at application-store serving checkpoints offline."""

from contextlib import contextmanager
from dataclasses import asdict
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from test_s2_population_read_fence import population_snapshot as population_snapshot

from knora.adapters.postgres import answering_store
from knora.answering.stores import LexicalGeneration
from knora.domain.errors import KnoraError


@pytest.mark.parametrize("checkpoint", ["readiness", "before_generation", "trace_commit"])
@pytest.mark.parametrize("changed", [False, True, "missing_manifest"])
def test_all_serving_checkpoints_require_the_exact_population(
    population_snapshot, monkeypatch, checkpoint, changed
):
    session, generations, manifest, _, ids = population_snapshot
    if changed is True:
        ids.append("new-unknown-document")

    @contextmanager
    def begin():
        yield session

    sessions = SimpleNamespace(begin=begin)
    authority = Mock()
    authority.read_active_generations.return_value = generations
    authority.read_active_generations_in_snapshot.return_value = generations
    monkeypatch.setattr(answering_store, "PostgresSearchIndexStore", lambda _: authority)
    store = answering_store.PostgresAnsweringStore(
        sessions,
        lexical_index=object(),
        lexical_population=None if changed == "missing_manifest" else manifest,
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

    def run():
        if checkpoint == "readiness":
            store.require_lexical_corpus("workspace", manifest.profile.id)
        elif checkpoint == "before_generation":
            store.revalidate_lexical_snapshot("workspace", manifest.profile.id, snapshots)
        else:
            trace = SimpleNamespace(
                trace_schema_version=3,
                workspace_id="workspace",
                provider_metadata={
                    "retrieval": {
                        "mode": "bm25-only",
                        "lexical_generations": [asdict(g) for g in snapshots],
                    }
                },
            )
            store._revalidate_lexical_trace(session, trace)

    if changed:
        with pytest.raises(KnoraError, match="LEXICAL_RETRIEVAL_UNAVAILABLE"):
            run()
    else:
        run()


@pytest.mark.parametrize("mutation", [None, "before_query", "during_query"])
def test_retrieval_checks_population_around_one_query_without_a_database_transaction(
    population_snapshot, monkeypatch, mutation
):
    from dataclasses import replace

    from knora.adapters.postgres import lexical_retrieval
    from knora.answering.stores import RetrievalConfiguration

    session, generations, manifest, _, ids = population_snapshot
    if mutation == "before_query":
        ids.append("unknown-source")
    active = False

    @contextmanager
    def begin():
        nonlocal active
        assert not active
        active = True
        try:
            yield session
        finally:
            active = False

    authority = Mock()
    authority.read_active_generations.return_value = generations
    monkeypatch.setattr(lexical_retrieval, "PostgresSearchIndexStore", lambda _: authority)

    class Projection:
        calls = 0

        def query(self, snapshot, query, *, limit):
            assert not active
            assert limit == 200
            self.calls += 1
            if mutation == "during_query":
                ids.append("unknown-source")
            return ()

    projection = Projection()

    def run():
        return lexical_retrieval.retrieve_lexical_candidates(
            SimpleNamespace(begin=begin),
            "workspace",
            "question?",
            replace(
                RetrievalConfiguration.bm25_diagnostic_v1(), lexical_policy_id=manifest.profile.id
            ),
            projection,
            population=manifest,
        )

    if mutation:
        with pytest.raises(KnoraError, match="LEXICAL_RETRIEVAL_UNAVAILABLE"):
            run()
        assert projection.calls == (0 if mutation == "before_query" else 1)
    else:
        result = run()
        assert projection.calls == 1
        assert result.candidates == ()
        assert result.branch_observations[0].status == "NO_CONTRIBUTION"


@pytest.mark.parametrize("state", ["valid", "unknown_source", "missing_manifest"])
def test_public_answer_availability_requires_the_complete_pinned_population(
    population_snapshot, monkeypatch, state
):
    from dataclasses import replace

    from knora.adapters.postgres import document_reader
    from knora.answering.stores import RetrievalConfiguration
    from knora.ingestion.documents import DocumentProjection

    session, generations, manifest, _, ids = population_snapshot
    if state == "unknown_source":
        ids.append("unknown-source")
    session.scalar = lambda statement: None
    authority = Mock()
    authority.read_active_generation_in_snapshot.return_value = generations[0]
    authority.read_active_generations_in_snapshot.return_value = generations
    monkeypatch.setattr(document_reader, "PostgresSearchIndexStore", lambda _: authority)
    reader = document_reader.PostgresDocumentReader(
        object(),
        deployed_retrieval_configuration=replace(
            RetrievalConfiguration.bm25_diagnostic_v1(), lexical_policy_id=manifest.profile.id
        ),
        lexical_population=None if state == "missing_manifest" else manifest,
    )
    row = SimpleNamespace(id=generations[0].document_id, workspace_id="workspace")
    projection = DocumentProjection(row.id, "workspace", "source", "source.pdf", False, 1)
    result = reader._lexical_projection(session, row, projection)
    assert result.answer_availability == ("available" if state == "valid" else "unavailable")
    assert result.embedding_readiness == "not_indexed"
